"""
피듀셜 마크(Fiducial Mark) 정렬 검사 모듈

PCB 기판의 두 피듀셜 마크를 기준으로 수평 정렬 오차 각도를 계산하고
허용 범위 이내인지 판별한다.

정렬 원리:
  - 마크1(좌하단)과 마크2(우하단) 두 점을 연결한 벡터를 구한다.
  - 이 벡터와 수평축(x축) 사이의 각도를 arctan2로 계산한다.
  - 각도가 MAX_ANGLE_ERROR_DEG(기본 3°) 이하면 PASS, 초과면 FAIL.

    마크1 ●────────────● 마크2
           ←── 이 선의 기울기 계산 ──→
"""

import math
import logging
from typing import Optional

import numpy as np

from config.settings import settings
from models.schemas import AlignmentResult, DetectionItem

logger = logging.getLogger(__name__)


def compute_alignment(
    fiducials: list[DetectionItem],
    max_angle_error_deg: float = settings.MAX_ANGLE_ERROR_DEG,
) -> AlignmentResult:
    """
    탐지된 피듀셜 마크 목록으로 정렬 오차를 계산한다.

    Args:
        fiducials:          YOLO가 탐지한 피듀셜 마크 DetectionItem 목록
        max_angle_error_deg: 허용 오차 각도 상한 (기본: settings에서 로드)

    Returns:
        AlignmentResult: 정렬 여부, 두 마크 위치, 오차 각도를 담은 결과 객체

    처리 케이스:
        - 마크가 0개: 탐지 실패 → FAIL
        - 마크가 1개: 단일 마크로 각도 계산 불가 → FAIL
        - 마크가 2개 이상: 가장 신뢰도 높은 2개 사용 → 오차 계산
    """

    # ── Case 1: 마크 탐지 실패 ────────────────────────────────────────────────
    if len(fiducials) < 2:
        logger.warning("[정렬] 피듀셜 마크 탐지 부족: %d개 (최소 2개 필요)", len(fiducials))
        return AlignmentResult(
            is_aligned=False,
            fiducial1=fiducials[0] if len(fiducials) == 1 else None,
            fiducial2=None,
            angle_error_deg=999.0,  # 탐지 실패를 나타내는 sentinel 값
        )

    # ── Case 2: 마크 2개 이상 → 신뢰도 상위 2개 선택 ─────────────────────────
    # confidence 내림차순 정렬 후 상위 2개 추출
    top2 = sorted(fiducials, key=lambda d: d.confidence, reverse=True)[:2]

    # X 좌표 기준으로 마크1(왼쪽), 마크2(오른쪽) 구분
    mark_a, mark_b = sorted(top2, key=lambda d: d.center_x)

    # ── 오차 각도 계산 ────────────────────────────────────────────────────────
    # 두 마크 중심점을 연결하는 벡터 (dx, dy)
    dx = mark_b.center_x - mark_a.center_x
    dy = mark_b.center_y - mark_a.center_y

    # arctan2로 수평 기준 각도 계산 (라디안 → 도)
    # 이미지 좌표계는 Y축이 아래 방향이므로 -dy를 사용
    angle_rad = math.atan2(-dy, dx)
    angle_deg = abs(math.degrees(angle_rad))

    logger.info(
        "[정렬] 마크1=(%d,%d), 마크2=(%d,%d), 오차=%.2f°, 허용=%.1f°",
        mark_a.center_x, mark_a.center_y,
        mark_b.center_x, mark_b.center_y,
        angle_deg, max_angle_error_deg,
    )

    # 허용 오차 범위 내인지 판정
    is_aligned = angle_deg <= max_angle_error_deg

    if not is_aligned:
        logger.warning("[정렬] 오차 초과 → FAIL (%.2f° > %.1f°)", angle_deg, max_angle_error_deg)

    return AlignmentResult(
        is_aligned=is_aligned,
        fiducial1=mark_a,
        fiducial2=mark_b,
        angle_error_deg=round(angle_deg, 3),
    )


def crop_inspection_roi(
    image: np.ndarray,
    alignment: AlignmentResult,
    padding_ratio: float = 0.05,
) -> np.ndarray:
    """
    정렬 결과를 기반으로 두 피듀셜 마크 사이 ROI(관심 영역)를 크롭한다.

    ROI 설정 로직:
      - 두 마크의 바운딩 박스를 감싸는 최소 사각형을 구한다.
      - padding_ratio만큼 여백을 추가한다. (기본 5%)
      - 이미지 경계를 넘지 않도록 클리핑한다.

    Args:
        image:         원본 캡처 이미지 (H, W, 3)
        alignment:     compute_alignment()의 반환값
        padding_ratio: ROI 바깥쪽 여백 비율

    Returns:
        크롭된 ROI numpy 배열.
        마크 정보가 없으면 원본 이미지 전체를 반환한다.
    """
    if alignment.fiducial1 is None or alignment.fiducial2 is None:
        logger.warning("[ROI] 마크 정보 없음 → 이미지 전체를 ROI로 사용")
        return image

    h, w = image.shape[:2]
    b1 = alignment.fiducial1.bbox
    b2 = alignment.fiducial2.bbox

    # 두 바운딩 박스를 포함하는 최소 사각형 좌표 계산
    x_min = min(b1.x, b2.x)
    y_min = min(b1.y, b2.y)
    x_max = max(b1.x + b1.width, b2.x + b2.width)
    y_max = max(b1.y + b1.height, b2.y + b2.height)

    # 여백 추가
    pad_x = int((x_max - x_min) * padding_ratio)
    pad_y = int((y_max - y_min) * padding_ratio)

    # 이미지 경계 클리핑 (음수/초과 방지)
    x_min = max(0, x_min - pad_x)
    y_min = max(0, y_min - pad_y)
    x_max = min(w, x_max + pad_x)
    y_max = min(h, y_max + pad_y)

    roi = image[y_min:y_max, x_min:x_max]
    logger.debug("[ROI] 크롭 영역: (%d,%d) ~ (%d,%d), 크기=%dx%d",
                 x_min, y_min, x_max, y_max, roi.shape[1], roi.shape[0])

    return roi
