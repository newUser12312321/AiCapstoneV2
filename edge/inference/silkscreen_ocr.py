"""
실크스크린 문자 OCR (선택)

deskew 직후 프레임의 고정 ROI에서 Tesseract로 문자를 읽고,
설정된 정규식과 매칭 여부를 판단한다.

사용 전: OS에 tesseract 설치 + pip pytesseract
  macOS: brew install tesseract
  Debian/Ubuntu: apt install tesseract-ocr
  Docker edge 이미지에 동일 패키지 추가 필요

비활성화 시(SILKSCREEN_OCR_ENABLED=false) 오버헤드 없음.
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


@dataclass(frozen=True)
class SilkscreenOcrResult:
    """실크 OCR 한 번 실행 결과."""

    raw_text: Optional[str]
    """인식된 원문(공백 정리). 없으면 None."""

    matched: Optional[bool]
    """SILKSCREEN_TEXT_REGEX 가 있을 때 정규식 만족 여부. 정규식 없으면 None."""

    skipped_reason: Optional[str]
    """실행하지 않았거나 오류 시 사유. 정상 실행이면 None."""

    elapsed_ms: int


def _normalize_for_match(text: str) -> str:
    s = re.sub(r"\s+", " ", text).strip()
    return s


def run_silkscreen_ocr(frame_bgr: np.ndarray) -> SilkscreenOcrResult:
    """
    deskew된 BGR 이미지에서 설정 ROI를 잘라 OCR 수행.

    Returns:
        SilkscreenOcrResult
    """
    if not getattr(settings, "SILKSCREEN_OCR_ENABLED", False):
        return SilkscreenOcrResult(None, None, None, 0)

    if frame_bgr is None or frame_bgr.size == 0:
        return SilkscreenOcrResult(None, None, "empty_frame", 0)

    try:
        import pytesseract
    except ImportError:
        logger.warning("[실크 OCR] pytesseract 미설치 — pip install pytesseract")
        return SilkscreenOcrResult(None, None, "pytesseract_not_installed", 0)

    tcmd = getattr(settings, "TESSERACT_CMD", None)
    if tcmd:
        pytesseract.pytesseract.tesseract_cmd = tcmd

    h, w = frame_bgr.shape[:2]
    nx = float(settings.SILKSCREEN_ROI_X_NORM)
    ny = float(settings.SILKSCREEN_ROI_Y_NORM)
    nw = float(settings.SILKSCREEN_ROI_W_NORM)
    nh = float(settings.SILKSCREEN_ROI_H_NORM)

    x1 = int(max(0, min(w - 1, nx * w)))
    y1 = int(max(0, min(h - 1, ny * h)))
    x2 = int(max(x1 + 1, min(w, (nx + nw) * w)))
    y2 = int(max(y1 + 1, min(h, (ny + nh) * h)))

    roi = frame_bgr[y1:y2, x1:x2]
    if roi.size == 0:
        return SilkscreenOcrResult(None, None, "roi_empty", 0)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 5, 35, 35)
    # 약한 대비 향상 (실크 흰색 / 녹색 기판)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    _, thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    t0 = time.perf_counter()
    try:
        config = f'--oem 3 --psm {int(settings.SILKSCREEN_TESSERACT_PSM)}'
        raw = pytesseract.image_to_string(thr, config=config, lang="eng")
    except Exception as e:
        logger.warning("[실크 OCR] Tesseract 실행 실패: %s", e)
        return SilkscreenOcrResult(None, None, f"tesseract_error:{e!s}", 0)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    cleaned = _normalize_for_match(raw) if raw else ""
    raw_out: Optional[str] = cleaned if cleaned else None

    pattern = getattr(settings, "SILKSCREEN_TEXT_REGEX", None)
    matched: Optional[bool] = None
    if pattern and pattern.strip():
        try:
            matched = bool(re.search(pattern.strip(), cleaned, re.IGNORECASE | re.DOTALL))
        except re.error as e:
            logger.warning("[실크 OCR] SILKSCREEN_TEXT_REGEX 오류: %s", e)
            matched = False
    elif raw_out is None:
        matched = None
    else:
        matched = None

    logger.info(
        "[실크 OCR] %dms, raw_len=%d, matched=%s",
        elapsed_ms,
        len(cleaned),
        matched,
    )
    return SilkscreenOcrResult(raw_text=raw_out, matched=matched, skipped_reason=None, elapsed_ms=elapsed_ms)
