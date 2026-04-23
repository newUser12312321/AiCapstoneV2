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


def _normalize_text(value: str) -> str:
    # OCR 노이즈를 줄이기 위해 공백/줄바꿈을 정리하고 대문자로 통일한다.
    compact = re.sub(r"\s+", "", value or "")
    return compact.upper().strip()


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


def read_model_name(image: np.ndarray) -> Optional[OcrResult]:
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

    config = (
        f"--oem 3 --psm {int(settings.OCR_PSM)} "
        f"-c tessedit_char_whitelist={settings.OCR_CHAR_WHITELIST}"
    )
    raw_text = pytesseract.image_to_string(prep, lang=settings.OCR_LANG, config=config)

    normalized = _normalize_text(raw_text)
    expected = _normalize_text(settings.OCR_EXPECTED_MODEL_NAME or "")
    is_match = None
    if expected:
        is_match = expected in normalized

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
    )
