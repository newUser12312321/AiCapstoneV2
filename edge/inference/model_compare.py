"""
동일 프레임으로 여러 YOLO 가중치를 비교하는 로직 (CLI·FastAPI 공용).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2

from config.settings import settings
from capture.camera import CameraCapture
from inference.alignment import compute_alignment, crop_inspection_roi
from inference.yolo_detector import YoloDetector

logger = logging.getLogger(__name__)

_EDGE_ROOT = Path(__file__).resolve().parent.parent


def resolve_safe_weights_path(user_path: str) -> Path:
    """
    edge/weights 아래만 허용 (디렉터리 탈출 방지).
    예: alice.pt, team_a/best.pt
    """
    raw = Path(user_path.strip())
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError("허용되지 않는 경로입니다.")
    weights_root = (_EDGE_ROOT / "weights").resolve()
    candidate = (weights_root / raw).resolve()
    try:
        candidate.relative_to(weights_root)
    except ValueError as e:
        raise ValueError(f"가중치는 edge/weights 아래만 허용됩니다: {user_path}") from e
    if not candidate.is_file():
        raise FileNotFoundError(f"파일 없음: {candidate}")
    return candidate


def resolve_safe_capture_path(user_path: str) -> Path:
    """edge/captures 아래 JPG/PNG 등만 허용."""
    raw = Path(user_path.strip())
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError("허용되지 않는 이미지 경로입니다.")
    cap_root = (_EDGE_ROOT / "captures").resolve()
    candidate = (cap_root / raw).resolve()
    try:
        candidate.relative_to(cap_root)
    except ValueError as e:
        raise ValueError(f"이미지는 edge/captures 아래만 허용됩니다: {user_path}") from e
    if not candidate.is_file():
        raise FileNotFoundError(f"이미지 없음: {candidate}")
    return candidate


def load_frame(image_path: str | None, camera_index: int) -> tuple[Any, str | None]:
    """BGR 프레임과 (이미지 경로 또는 None) 반환."""
    if image_path:
        p = resolve_safe_capture_path(image_path)
        frame = cv2.imread(str(p))
        if frame is None:
            raise RuntimeError(f"이미지 로드 실패: {p}")
        return frame, str(p.resolve())

    cam = CameraCapture(device_index=camera_index)
    cam.open()
    try:
        frame = cam.capture()
    finally:
        cam.release()
    return frame, None


def run_unified(frame: Any, weights: Path, conf: float) -> dict[str, Any]:
    det = YoloDetector(str(weights), confidence_threshold=conf)
    det.load()
    fiducials, t1 = det.detect_fiducials(frame)
    alignment = compute_alignment(fiducials)
    t2 = 0
    defects: list = []
    if alignment.is_aligned:
        roi = crop_inspection_roi(frame, alignment)
        defects, t2 = det.detect_defects(roi)
    confs = [d.confidence for d in defects]
    return {
        "weights": str(weights),
        "weightsLabel": weights.name,
        "mode": "unified",
        "fiducial_count": len(fiducials),
        "aligned": alignment.is_aligned,
        "angle_error_deg": round(float(alignment.angle_error_deg), 3),
        "defect_count": len(defects),
        "defect_conf_mean": round(sum(confs) / len(confs), 4) if confs else None,
        "defect_conf_max": round(max(confs), 4) if confs else None,
        "infer_ms_stage1": t1,
        "infer_ms_stage2": t2,
        "infer_ms_total": t1 + t2,
    }


def run_separate(frame: Any, w_fid: Path, w_def: Path, conf: float) -> dict[str, Any]:
    d1 = YoloDetector(str(w_fid), confidence_threshold=conf)
    d1.load()
    fiducials, t1 = d1.detect_fiducials(frame)
    alignment = compute_alignment(fiducials)
    t2 = 0
    defects: list = []
    if alignment.is_aligned:
        roi = crop_inspection_roi(frame, alignment)
        d2 = YoloDetector(str(w_def), confidence_threshold=conf)
        d2.load()
        defects, t2 = d2.detect_defects(roi)
    confs = [d.confidence for d in defects]
    label = f"{w_fid.name} + {w_def.name}"
    return {
        "weights": label,
        "weightsLabel": label,
        "mode": "separate",
        "fiducial_count": len(fiducials),
        "aligned": alignment.is_aligned,
        "angle_error_deg": round(float(alignment.angle_error_deg), 3),
        "defect_count": len(defects),
        "defect_conf_mean": round(sum(confs) / len(confs), 4) if confs else None,
        "defect_conf_max": round(max(confs), 4) if confs else None,
        "infer_ms_stage1": t1,
        "infer_ms_stage2": t2,
        "infer_ms_total": t1 + t2,
    }


def compare_models(
    weights_list: list[str],
    defect_weights: list[str] | None,
    image_path: str | None,
    camera_index: int | None,
    conf: float | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Returns:
        (rows, capture_source) — capture_source는 카메라면 None, 파일이면 경로
    """
    conf = conf if conf is not None else settings.YOLO_CONFIDENCE_THRESHOLD
    cam_idx = camera_index if camera_index is not None else settings.CAMERA_DEVICE_INDEX

    resolved = [resolve_safe_weights_path(w) for w in weights_list]
    defect_resolved: list[Path] | None = None
    if defect_weights:
        if len(defect_weights) != len(weights_list):
            raise ValueError("defect_weights 개수는 weights와 같아야 합니다.")
        defect_resolved = [resolve_safe_weights_path(w) for w in defect_weights]

    safe_image: str | None = None
    if image_path and image_path.strip():
        safe_image = str(resolve_safe_capture_path(image_path))
    frame, src = load_frame(safe_image, cam_idx)
    rows: list[dict[str, Any]] = []
    if defect_resolved:
        for wf, wd in zip(resolved, defect_resolved, strict=True):
            rows.append(run_separate(frame, wf, wd, conf))
    else:
        for w in resolved:
            rows.append(run_unified(frame, w, conf))

    return rows, src
