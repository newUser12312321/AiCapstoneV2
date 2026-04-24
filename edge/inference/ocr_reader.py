"""
PCB 모델명 OCR 유틸리티.

Tesseract(pytesseract) 기반으로 이미지에서 텍스트를 읽고,
설정된 기대 모델명과의 매칭 여부를 계산한다.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class OcrResult:
    text: str
    normalized_text: str
    expected_text: Optional[str]
    is_match: Optional[bool]
    elapsed_ms: int
    roi_x: int
    roi_y: int
    roi_w: int
    roi_h: int
    source: str = "aligned"


def _normalize_text(value: str) -> str:
    # OCR 노이즈를 줄이기 위해 공백/줄바꿈을 정리하고 대문자로 통일한다.
    compact = re.sub(r"\s+", "", value or "")
    return compact.upper().strip()


def _normalize_text_alnum(value: str) -> str:
    # 비교 전용: 숫자/영문만 남겨 구두점 노이즈를 더 줄인다.
    upper = _normalize_text(value)
    return re.sub(r"[^A-Z0-9]", "", upper)


def _resolve_roi(image: np.ndarray) -> tuple[np.ndarray, int, int, int, int]:
    h, w = image.shape[:2]
    x = int(settings.OCR_ROI_X or 0)
    y = int(settings.OCR_ROI_Y or 0)
    rw = int(settings.OCR_ROI_WIDTH or w)
    rh = int(settings.OCR_ROI_HEIGHT or h)

    x = max(0, min(x, w - 1 if w > 0 else 0))
    y = max(0, min(y, h - 1 if h > 0 else 0))
    rw = max(1, min(rw, w - x))
    rh = max(1, min(rh, h - y))

    return image[y:y + rh, x:x + rw], x, y, rw, rh


def _preprocess_for_ocr(roi: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    # 작은 폰트의 가장자리를 살리고 잡음을 줄인다.
    gray = cv2.bilateralFilter(gray, 5, 50, 50)
    gray = cv2.equalizeHist(gray)
    bw = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        8,
    )
    return bw


def _build_tesseract_config(psm: int) -> str:
    return (
        f"--oem 3 --psm {int(psm)} "
        f"-c tessedit_char_whitelist={settings.OCR_CHAR_WHITELIST}"
    )


def _read_best_orientation_text(prep: np.ndarray, lang: str, config: str) -> str:
    """
    세로 텍스트 대응: 원본 + 90도 회전 후보 중 더 그럴듯한 문자열을 선택한다.
    """
    import pytesseract

    candidates: list[str] = []
    candidates.append(pytesseract.image_to_string(prep, lang=lang, config=config))

    if settings.OCR_AUTO_ROTATE_VERTICAL and prep.shape[0] > prep.shape[1]:
        rot_cw = cv2.rotate(prep, cv2.ROTATE_90_CLOCKWISE)
        rot_ccw = cv2.rotate(prep, cv2.ROTATE_90_COUNTERCLOCKWISE)
        candidates.append(pytesseract.image_to_string(rot_cw, lang=lang, config=config))
        candidates.append(pytesseract.image_to_string(rot_ccw, lang=lang, config=config))

    expected = _normalize_text(settings.OCR_EXPECTED_MODEL_NAME or "")
    expected_alnum = _normalize_text_alnum(settings.OCR_EXPECTED_MODEL_NAME or "")
    best_text = candidates[0] if candidates else ""
    best_score = -1

    for text in candidates:
        normalized = _normalize_text(text)
        normalized_alnum = _normalize_text_alnum(text)
        score = len(normalized_alnum)
        if expected:
            if expected in normalized:
                score += 1000
            if expected_alnum and expected_alnum in normalized_alnum:
                score += 1000
        if score > best_score:
            best_score = score
            best_text = text

    return best_text


def _score_candidate_text(text: str, expected: str, expected_alnum: str) -> int:
    normalized = _normalize_text(text)
    normalized_alnum = _normalize_text_alnum(text)
    score = len(normalized_alnum)
    if expected:
        if expected in normalized:
            score += 1000
        if expected_alnum and expected_alnum in normalized_alnum:
            score += 1000
    return score


def _parse_psm_candidates() -> list[int]:
    values: list[int] = [int(settings.OCR_PSM)]
    raw = (settings.OCR_PSM_CANDIDATES or "").strip()
    if raw:
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                psm = int(token)
            except ValueError:
                continue
            if 3 <= psm <= 13 and psm not in values:
                values.append(psm)
    return values


def _upscale_for_ocr(prep: np.ndarray) -> np.ndarray:
    factor = float(settings.OCR_UPSCALE_FACTOR or 1.0)
    if factor <= 1.0:
        return prep
    return cv2.resize(prep, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)


def select_best_ocr_result(results: list[Optional[OcrResult]]) -> Optional[OcrResult]:
    valid = [r for r in results if r is not None]
    if not valid:
        return None

    def _rank_key(r: OcrResult) -> tuple[int, int, int]:
        # 1) 기대 문자열 매칭 성공 우선, 2) 정규화 길이, 3) 원문 길이
        return (
            1 if r.is_match is True else 0,
            len(r.normalized_text),
            len(r.text),
        )

    return max(valid, key=_rank_key)


def read_model_name(image: np.ndarray, source: str = "aligned") -> Optional[OcrResult]:
    """
    이미지에서 모델명 텍스트를 OCR로 읽는다.

    Returns:
        OcrResult 또는 OCR 미사용/실패 시 None
    """
    if not settings.OCR_ENABLED:
        return None

    try:
        import pytesseract
    except ImportError:
        logger.warning("[OCR] pytesseract 미설치 — OCR 단계를 건너뜁니다.")
        return None

    start = time.perf_counter()
    roi, x, y, w, h = _resolve_roi(image)
    prep = _preprocess_for_ocr(roi)
    prep = _upscale_for_ocr(prep)
    expected = _normalize_text(settings.OCR_EXPECTED_MODEL_NAME or "")
    expected_alnum = _normalize_text_alnum(settings.OCR_EXPECTED_MODEL_NAME or "")

    best_text = ""
    best_score = -1
    for psm in _parse_psm_candidates():
        config = _build_tesseract_config(psm)
        cand = _read_best_orientation_text(prep, lang=settings.OCR_LANG, config=config)
        score = _score_candidate_text(cand, expected, expected_alnum)
        if score > best_score:
            best_score = score
            best_text = cand
    raw_text = best_text

    normalized = _normalize_text(raw_text)
    normalized_alnum = _normalize_text_alnum(raw_text)
    is_match = None
    if expected:
        is_match = (expected in normalized) or (
            bool(expected_alnum) and expected_alnum in normalized_alnum
        )

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return OcrResult(
        text=(raw_text or "").strip(),
        normalized_text=normalized,
        expected_text=expected or None,
        is_match=is_match,
        elapsed_ms=elapsed_ms,
        roi_x=x,
        roi_y=y,
        roi_w=w,
        roi_h=h,
        source=source,
    )
