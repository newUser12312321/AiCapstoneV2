"""
피듀셜 마크(Fiducial Mark) 정렬 검사 모듈

PCB 기판의 두 피듀셜 마크를 기준으로 수평 대비 기울기(°)를 계산하고,
허용 범위(MAX_DESKEW_ANGLE_DEG) 안이면 이후 단계에서 이미지 회전 보정(deskew)을 적용한다.

정렬 원리:
  - 마크1·마크2 중심을 연결한 벡터와 수평축 사이 각도를 arctan2로 계산한다.
  - 각도가 MAX_DESKEW_ANGLE_DEG(기본 45°) 초과면 FAIL(보정 불가로 간주).

    마크1 ●────────────● 마크2
           ←── 이 선의 기울기 계산 ──→
"""

import logging
import math

import cv2
import numpy as np

from config.settings import settings
from models.schemas import AlignmentResult, BoundingBox, DetectionItem

logger = logging.getLogger(__name__)


def compute_alignment(
    fiducials: list[DetectionItem],
    max_deskew_deg: float = settings.MAX_DESKEW_ANGLE_DEG,
) -> AlignmentResult:
    """
    탐지된 피듀셜 마크 목록으로 기울기 각도(°)를 계산한다.

    Args:
        fiducials:       YOLO가 탐지한 피듀셜 마크 DetectionItem 목록
        max_deskew_deg:  이 각도(°) 이하일 때만 회전 보정 후 결함 검사 진행 (초과 시 FAIL)

    Returns:
        AlignmentResult: is_aligned는 「2개 마크 + 각도 ≤ max_deskew_deg」 여부.
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
        "[정렬] 마크1=(%d,%d), 마크2=(%d,%d), |기울기|=%.2f°, 보정가능한도=%.1f°",
        mark_a.center_x, mark_a.center_y,
        mark_b.center_x, mark_b.center_y,
        angle_deg, max_deskew_deg,
    )

    is_aligned = angle_deg <= max_deskew_deg

    if not is_aligned:
        logger.warning("[정렬] 기울기 한도 초과 → FAIL (%.2f° > %.1f°)", angle_deg, max_deskew_deg)

    return AlignmentResult(
        is_aligned=is_aligned,
        fiducial1=mark_a,
        fiducial2=mark_b,
        angle_error_deg=round(angle_deg, 3),
    )


def _bbox_after_affine(bbox: BoundingBox, m23: np.ndarray) -> BoundingBox:
    """axis-aligned bbox의 네 꼭짓점을 affine 변환한 뒤 축정렬 최소 사각형."""
    corners = np.array(
        [
            [bbox.x, bbox.y, 1.0],
            [bbox.x + bbox.width, bbox.y, 1.0],
            [bbox.x + bbox.width, bbox.y + bbox.height, 1.0],
            [bbox.x, bbox.y + bbox.height, 1.0],
        ],
        dtype=np.float64,
    ).T
    pts = m23 @ corners
    xs, ys = pts[0], pts[1]
    x_min, x_max = float(xs.min()), float(xs.max())
    y_min, y_max = float(ys.min()), float(ys.max())
    return BoundingBox(
        x=max(0, int(x_min)),
        y=max(0, int(y_min)),
        width=max(1, int(round(x_max - x_min))),
        height=max(1, int(round(y_max - y_min))),
    )


def _clip_bbox_to_image(bbox: BoundingBox, w: int, h: int) -> BoundingBox:
    x = max(0, min(bbox.x, w - 1))
    y = max(0, min(bbox.y, h - 1))
    bw = max(1, min(bbox.width, w - x))
    bh = max(1, min(bbox.height, h - y))
    return BoundingBox(x=x, y=y, width=bw, height=bh)


def deskew_image_by_fiducial_angle(
    image: np.ndarray,
    alignment: AlignmentResult,
    min_deskew_deg: float = settings.MIN_DESKEW_ANGLE_DEG,
) -> tuple[np.ndarray, AlignmentResult]:
    """
    두 피듀셜을 잇는 선이 수평이 되도록 이미지를 회전한다 (캔버스 확장).

    alignment의 fiducial1/2는 원본 프레임 좌표계여야 한다.
    반환 alignment는 회전 후 이미지 좌표계로 갱신되며 angle_error_deg는 0에 가깝게 둔다.
    """
    if alignment.fiducial1 is None or alignment.fiducial2 is None:
        return image, alignment

    mark_a = alignment.fiducial1
    mark_b = alignment.fiducial2
    dx = mark_b.center_x - mark_a.center_x
    dy = mark_b.center_y - mark_a.center_y
    angle_rad = math.atan2(-dy, dx)
    angle_deg = math.degrees(angle_rad)

    if abs(angle_deg) < min_deskew_deg:
        logger.info("[정렬] |기울기| %.4f° < %.2f° — 회전 보정 생략", abs(angle_deg), min_deskew_deg)
        return image, alignment

    h, w = image.shape[:2]
    center = (w / 2.0, h / 2.0)
    rot_deg = -angle_deg

    m23 = cv2.getRotationMatrix2D(center, rot_deg, 1.0)
    cos = abs(m23[0, 0])
    sin = abs(m23[0, 1])
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))
    m23[0, 2] += (new_w / 2) - center[0]
    m23[1, 2] += (new_h / 2) - center[1]

    rotated = cv2.warpAffine(
        image,
        m23,
        (new_w, new_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )

    b1 = _clip_bbox_to_image(_bbox_after_affine(mark_a.bbox, m23), new_w, new_h)
    b2 = _clip_bbox_to_image(_bbox_after_affine(mark_b.bbox, m23), new_w, new_h)

    new_a = DetectionItem(defect_type=mark_a.defect_type, confidence=mark_a.confidence, bbox=b1)
    new_b = DetectionItem(defect_type=mark_b.defect_type, confidence=mark_b.confidence, bbox=b2)

    logger.info("[정렬] 회전 보정 적용: %.2f° → 캔버스 %dx%d", angle_deg, new_w, new_h)

    return rotated, AlignmentResult(
        is_aligned=True,
        fiducial1=new_a,
        fiducial2=new_b,
        angle_error_deg=0.0,
    )


def crop_inspection_roi_with_offset(
    image: np.ndarray,
    alignment: AlignmentResult,
    padding_ratio: float = 0.05,
) -> tuple[np.ndarray, int, int]:
    """
    ROI 크롭과 함께, 원본(또는 deskew 후) 이미지 좌표계에서의 ROI 좌상단 오프셋 (x_min, y_min) 반환.
    결함 박스가 ROI 기준이면 이 오프셋을 더해 전체 프레임 좌표로 변환할 때 사용한다.
    """
    if alignment.fiducial1 is None or alignment.fiducial2 is None:
        logger.warning("[ROI] 마크 정보 없음 → 이미지 전체를 ROI로 사용")
        return image, 0, 0

    h, w = image.shape[:2]
    b1 = alignment.fiducial1.bbox
    b2 = alignment.fiducial2.bbox

    x_min = min(b1.x, b2.x)
    y_min = min(b1.y, b2.y)
    x_max = max(b1.x + b1.width, b2.x + b2.width)
    y_max = max(b1.y + b1.height, b2.y + b2.height)

    pad_x = int((x_max - x_min) * padding_ratio)
    pad_y = int((y_max - y_min) * padding_ratio)

    x_min = max(0, x_min - pad_x)
    y_min = max(0, y_min - pad_y)
    x_max = min(w, x_max + pad_x)
    y_max = min(h, y_max + pad_y)

    roi = image[y_min:y_max, x_min:x_max]
    logger.debug("[ROI] 크롭 영역: (%d,%d) ~ (%d,%d), 크기=%dx%d",
                 x_min, y_min, x_max, y_max, roi.shape[1], roi.shape[0])

    return roi, x_min, y_min


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
    roi, _, _ = crop_inspection_roi_with_offset(image, alignment, padding_ratio)
    return roi
