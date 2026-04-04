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
    """BGR 프레임에 피듀셜 박스·F1/F2·신뢰도 오버레이 (대비 강화)."""
    out = frame.copy()
    # 녹색 기판 위에서 잘 보이도록 노랑 + 검은 외곽
    box_inner = (0, 255, 255)  # BGR 밝은 노랑
    box_outline = (0, 0, 0)
    line_thick = 3
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.75
    txt_thick = 2

    # 왼쪽→오른쪽 순으로 F1, F2 라벨
    indexed = list(enumerate(fiducials))
    indexed.sort(key=lambda t: t[1].bbox.x + t[1].bbox.width / 2)

    for rank, (_, d) in enumerate(indexed):
        b = d.bbox
        x1, y1 = int(b.x), int(b.y)
        x2, y2 = int(b.x + b.width), int(b.y + b.height)
        # 검은 두꺼운 외곽 + 안쪽 색 박스
        cv2.rectangle(out, (x1, y1), (x2, y2), box_outline, line_thick + 2)
        cv2.rectangle(out, (x1, y1), (x2, y2), box_inner, line_thick)
        label = f"F{rank + 1} {d.confidence * 100:.0f}%"
        (tw, th), _ = cv2.getTextSize(label, font, font_scale, txt_thick)
        pad = 6
        # 라벨 박스: putText 기준선(y) = text_baseline
        if y1 >= th + pad + 8:
            text_baseline = y1 - pad
        else:
            text_baseline = y2 + th + pad
        tx = x1
        y0 = int(text_baseline - th - 2)
        y1b = int(text_baseline + 4)
        cv2.rectangle(out, (tx, y0), (tx + tw + pad * 2, y1b), (0, 0, 0), -1)
        cv2.rectangle(out, (tx, y0), (tx + tw + pad * 2, y1b), box_inner, 1)
        cv2.putText(
            out,
            label,
            (tx + pad, text_baseline),
            font,
            font_scale,
            box_inner,
            txt_thick,
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


def resolve_safe_inspection_source_image(user_path: str) -> Path:
    """
    검사 파이프라인용 소스 이미지 — edge/captures 또는 edge/demo_samples 아래만 허용.
    예: \"20260404_xxx.jpg\", \"demo_samples/synthetic/defect_001.jpg\"
    """
    raw = Path(user_path.strip())
    if not str(raw) or raw.is_absolute() or ".." in raw.parts:
        raise ValueError("허용되지 않는 이미지 경로입니다.")
    parts = raw.parts
    if parts and parts[0] == "demo_samples":
        base = (_EDGE_ROOT / "demo_samples").resolve()
        rel = Path(*parts[1:]) if len(parts) > 1 else Path()
    else:
        base = (_EDGE_ROOT / "captures").resolve()
        rel = raw
    candidate = (base / rel).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as e:
        raise ValueError(
            f"이미지는 edge/captures 또는 edge/demo_samples 아래만 허용됩니다: {user_path}"
        ) from e
    if not candidate.is_file():
        raise FileNotFoundError(f"이미지 없음: {candidate}")
    if candidate.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
        raise ValueError(f"지원하지 않는 이미지 형식입니다: {candidate.suffix}")
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
