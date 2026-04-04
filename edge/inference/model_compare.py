"""
동일 프레임으로 여러 YOLO 가중치를 비교하는 로직 (CLI·FastAPI 공용).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import cv2

from config.settings import settings
from capture.camera import CameraCapture
from inference.alignment import compute_alignment, crop_inspection_roi, deskew_image_by_fiducial_angle
from inference.yolo_detector import YoloDetector

logger = logging.getLogger(__name__)

_EDGE_ROOT = Path(__file__).resolve().parent.parent
_CAPTURES_DIR = _EDGE_ROOT / "captures"


def _safe_stem(name: str) -> str:
    base = Path(name).name
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", base)[:100]
    return s or "model"


def _annotate_fiducials(frame: Any, fiducials: list) -> Any:
    """BGR 프레임에 피듀셜 박스·conf 텍스트 오버레이."""
    out = frame.copy()
    color = (255, 255, 0)  # BGR: 청록에 가까운 색
    for d in fiducials:
        b = d.bbox
        x1, y1 = b.x, b.y
        x2, y2 = b.x + b.width, b.y + b.height
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        txt = f"{d.confidence:.2f}"
        cv2.putText(
            out,
            txt,
            (x1, max(18, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )
    if not fiducials:
        cv2.putText(
            out,
            "FIDUCIAL 0",
            (24, 48),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (100, 100, 255),
            2,
            cv2.LINE_AA,
        )
    return out


def _save_fiducial_preview(frame_drawn: Any, run_id: str, label: str) -> str:
    """
    captures/compare_{run_id}_{label}.jpg 저장.
    Returns:
        파일명만 (프론트 /captures/파일명)
    """
    stem = _safe_stem(label)
    fname = f"compare_{run_id}_{stem}.jpg"
    path = _CAPTURES_DIR / fname
    _CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), frame_drawn, [cv2.IMWRITE_JPEG_QUALITY, 92])
    logger.info("[model_compare] 피듀셜 미리보기 저장: %s", fname)
    return fname


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


def _frame_from_running_edge_camera() -> Optional[Any]:
    """
    main.py lifespan 이 이미 연 전역 카메라가 있으면 1프레임만 읽는다.
    같은 /dev/video 를 두 번 열면(점유) 실패하는 경우가 많아 비교 API에서는 필수에 가깝다.
    """
    try:
        import main as main_mod

        cam = getattr(main_mod, "camera", None)
        if cam is None:
            return None
        cap = getattr(cam, "_cap", None)
        if cap is None or not cap.isOpened():
            return None
        logger.info("[model_compare] 전역 카메라(검사 파이프라인과 공유)로 1프레임 캡처")
        return cam.capture()
    except Exception as e:
        logger.debug("[model_compare] 전역 카메라 미사용: %s", e)
        return None


def load_frame(image_path: str | None, camera_index: int) -> tuple[Any, str | None]:
    """BGR 프레임과 (이미지 경로 또는 None) 반환."""
    if image_path:
        p = resolve_safe_capture_path(image_path)
        frame = cv2.imread(str(p))
        if frame is None:
            raise RuntimeError(f"이미지 로드 실패: {p}")
        return frame, str(p.resolve())

    existing = _frame_from_running_edge_camera()
    if existing is not None:
        return existing, None

    cam = CameraCapture(device_index=camera_index)
    cam.open()
    try:
        frame = cam.capture()
    finally:
        cam.release()
    return frame, None


def run_unified(frame: Any, weights: Path, conf: float, run_id: str) -> dict[str, Any]:
    det = YoloDetector(str(weights), confidence_threshold=conf)
    det.load()
    fiducials, t1 = det.detect_fiducials(frame)
    preview_frame = frame.copy()
    alignment = compute_alignment(fiducials)
    measured_deg = float(alignment.angle_error_deg)
    t2 = 0
    defects: list = []
    if alignment.is_aligned:
        frame, alignment = deskew_image_by_fiducial_angle(frame, alignment)
        roi = crop_inspection_roi(frame, alignment)
        defects, t2 = det.detect_defects(roi)
    confs = [d.confidence for d in defects]
    drawn = _annotate_fiducials(preview_frame, fiducials)
    preview_name = _save_fiducial_preview(drawn, run_id, weights.name)
    return {
        "weights": str(weights),
        "weightsLabel": weights.name,
        "mode": "unified",
        "fiducial_count": len(fiducials),
        "aligned": alignment.is_aligned,
        "angle_error_deg": round(measured_deg, 3),
        "defect_count": len(defects),
        "defect_conf_mean": round(sum(confs) / len(confs), 4) if confs else None,
        "defect_conf_max": round(max(confs), 4) if confs else None,
        "infer_ms_stage1": t1,
        "infer_ms_stage2": t2,
        "infer_ms_total": t1 + t2,
        "fiducial_preview_path": preview_name,
    }


def run_separate(frame: Any, w_fid: Path, w_def: Path, conf: float, run_id: str) -> dict[str, Any]:
    d1 = YoloDetector(str(w_fid), confidence_threshold=conf)
    d1.load()
    fiducials, t1 = d1.detect_fiducials(frame)
    preview_frame = frame.copy()
    alignment = compute_alignment(fiducials)
    measured_deg = float(alignment.angle_error_deg)
    t2 = 0
    defects: list = []
    if alignment.is_aligned:
        frame, alignment = deskew_image_by_fiducial_angle(frame, alignment)
        roi = crop_inspection_roi(frame, alignment)
        d2 = YoloDetector(str(w_def), confidence_threshold=conf)
        d2.load()
        defects, t2 = d2.detect_defects(roi)
    confs = [d.confidence for d in defects]
    label = f"{w_fid.name} + {w_def.name}"
    drawn = _annotate_fiducials(preview_frame, fiducials)
    preview_name = _save_fiducial_preview(drawn, run_id, label.replace(" ", "_"))
    return {
        "weights": label,
        "weightsLabel": label,
        "mode": "separate",
        "fiducial_count": len(fiducials),
        "aligned": alignment.is_aligned,
        "angle_error_deg": round(measured_deg, 3),
        "defect_count": len(defects),
        "defect_conf_mean": round(sum(confs) / len(confs), 4) if confs else None,
        "defect_conf_max": round(max(confs), 4) if confs else None,
        "infer_ms_stage1": t1,
        "infer_ms_stage2": t2,
        "infer_ms_total": t1 + t2,
        "fiducial_preview_path": preview_name,
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
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    rows: list[dict[str, Any]] = []
    if defect_resolved:
        for wf, wd in zip(resolved, defect_resolved, strict=True):
            rows.append(run_separate(frame, wf, wd, conf, run_id))
    else:
        for w in resolved:
            rows.append(run_unified(frame, w, conf, run_id))

    return rows, src
