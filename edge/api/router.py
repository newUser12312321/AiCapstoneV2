"""
FastAPI 로컬 API 라우터

라즈베리파이 자체에서 서빙하는 로컬 REST API 엔드포인트.
같은 네트워크의 다른 기기(운영자 PC, 모니터링 툴 등)가
엣지 디바이스의 상태를 조회하거나 수동 검사를 트리거할 때 사용한다.

Base URL: http://<라즈베리파이_IP>:8000
"""

import asyncio
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import cv2

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.sender import create_dummy_packet, ServerSender
from config.settings import settings

logger = logging.getLogger(__name__)

# APIRouter: main.py의 FastAPI 앱에 include_router()로 등록한다.
router = APIRouter(prefix="/edge", tags=["Edge Device"])

_preview_lock = threading.Lock()
_last_preview_jpeg: Optional[bytes] = None


def _normalize_stage2_mode(stage2_source: Optional[str]) -> str:
    mode = (stage2_source or settings.STAGE2_SOURCE_MODE).strip().lower()
    if mode == "deskew":
        mode = "aligned"
    if mode not in {"raw", "aligned"}:
        raise HTTPException(status_code=400, detail="stage2Source must be 'raw' or 'aligned'")
    return mode

# ── 자동 연속 검사 상태 관리 ──────────────────────────────────────────────────
_auto_running: bool = False       # 자동 검사 루프 실행 중 여부
_auto_interval: float = 5.0      # 검사 간격 (초)


# ── 상태 조회 ─────────────────────────────────────────────────────────────────

@router.get("/health", summary="헬스체크")
async def health_check() -> dict[str, Any]:
    """
    엣지 디바이스 서버 가동 여부를 확인하는 헬스체크 엔드포인트.

    모니터링 시스템이나 운영자가 라즈베리파이 FastAPI 서버가
    정상 동작 중인지 확인할 때 사용한다.

    Returns:
        status: "ok"
        timestamp: 현재 서버 시각 (ISO 8601)
        environment: 현재 실행 환경 (production / development)
    """
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "device_id": "RPI5-LINE-A",
        "environment": settings.ENVIRONMENT,
        "server_url": settings.SERVER_BASE_URL,
    }


@router.get("/status", summary="카메라/모델 상태 조회")
async def get_status() -> dict[str, Any]:
    """
    카메라 설정, YOLO 모델 경로, GPIO 핀 설정 등
    현재 엣지 디바이스의 구성 정보를 반환한다.
    """
    from inference.yolo_detector import resolve_edge_weights_path

    sep = settings.USE_SEPARATE_MODELS
    if sep:
        wf = resolve_edge_weights_path(settings.YOLO_FIDUCIAL_WEIGHTS)
        wd = resolve_edge_weights_path(settings.YOLO_DEFECT_WEIGHTS)
        weights_loaded = wf.exists() and wd.exists()
        yolo_block = {
            "use_separate_models": True,
            "fiducial_weights": str(wf),
            "defect_weights": str(wd),
            "fiducial_exists": wf.exists(),
            "defect_exists": wd.exists(),
            "weights_loaded": weights_loaded,
            "weights_path": settings.YOLO_WEIGHTS_PATH,
            "confidence_threshold": settings.YOLO_CONFIDENCE_THRESHOLD,
            "fiducial_confidence": settings.effective_fiducial_confidence(),
            "defect_confidence": settings.effective_defect_confidence(),
        }
    else:
        wu = resolve_edge_weights_path(settings.YOLO_WEIGHTS_PATH)
        weights_loaded = wu.exists()
        yolo_block = {
            "use_separate_models": False,
            "weights_path": str(wu),
            "weights_loaded": weights_loaded,
            "confidence_threshold": settings.YOLO_CONFIDENCE_THRESHOLD,
            "fiducial_confidence": settings.effective_fiducial_confidence(),
            "defect_confidence": settings.effective_defect_confidence(),
        }

    return {
        "camera": {
            "device_index": settings.CAMERA_DEVICE_INDEX,
            "resolution": f"{settings.CAMERA_WIDTH}x{settings.CAMERA_HEIGHT}",
        },
        "yolo": yolo_block,
        "gpio": {
            "buzzer_pin": settings.BUZZER_PIN,
            "led_red_pin": settings.LED_RED_PIN,
            "led_green_pin": settings.LED_GREEN_PIN,
        },
        "server": {
            "base_url": settings.SERVER_BASE_URL,
        },
        "pipeline": {
            "stage2_source_mode": settings.STAGE2_SOURCE_MODE,
            "ocr_enabled": settings.OCR_ENABLED,
            "ocr_expected_model_name": settings.OCR_EXPECTED_MODEL_NAME,
            "ocr_fail_on_mismatch": settings.OCR_FAIL_ON_MISMATCH,
        },
    }


@router.get("/camera/preview.jpg", summary="카메라 프리뷰 단일 프레임(JPEG)")
async def camera_preview_frame() -> Response:
    """
    라즈베리파이 카메라 현재 프레임을 JPEG로 반환한다.
    프론트 대시보드에서 주기적으로 호출해 실시간 미리보기를 구성할 때 사용한다.
    """
    try:
        import main as main_mod

        cam = getattr(main_mod, "camera", None)
        if cam is None:
            raise HTTPException(status_code=503, detail="카메라가 초기화되지 않았습니다.")

        # 프리뷰와 검사 파이프라인이 동시에 카메라를 읽을 수 있어 직렬화한다.
        with _preview_lock:
            frame = cam.capture()
            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
            if not ok:
                raise HTTPException(status_code=500, detail="카메라 프레임 인코딩 실패")

            global _last_preview_jpeg
            _last_preview_jpeg = encoded.tobytes()

        return Response(
            content=_last_preview_jpeg,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )
    except HTTPException:
        raise
    except Exception as e:
        # 프레임 일시 실패 시 마지막 정상 프레임을 반환해 화면 정지를 줄인다.
        if _last_preview_jpeg is not None:
            logger.warning("[프리뷰] 캡처 실패 — 마지막 정상 프레임으로 대체: %s", e)
            return Response(
                content=_last_preview_jpeg,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "X-Preview-Stale": "1",
                },
            )
        raise HTTPException(status_code=500, detail=f"카메라 프리뷰 실패: {e}") from e


@router.get("/camera/stream.mjpg", summary="카메라 MJPEG 스트리밍")
async def camera_preview_stream() -> StreamingResponse:
    """
    대시보드용 실시간 카메라 스트리밍.
    브라우저 <img> 태그에서 multipart/x-mixed-replace(MJPEG)로 재생한다.
    """
    try:
        import main as main_mod
        cam = getattr(main_mod, "camera", None)
        if cam is None:
            raise HTTPException(status_code=503, detail="카메라가 초기화되지 않았습니다.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"카메라 스트림 초기화 실패: {e}") from e

    boundary = b"frame"

    def _gen():
        global _last_preview_jpeg
        while True:
            try:
                with _preview_lock:
                    frame = cam.capture()
                    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
                    if ok:
                        _last_preview_jpeg = encoded.tobytes()
            except Exception as e:
                logger.debug("[프리뷰 스트림] 캡처 실패: %s", e)

            if _last_preview_jpeg is None:
                time.sleep(0.05)
                continue

            chunk = (
                b"--" + boundary + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Cache-Control: no-store\r\n\r\n" +
                _last_preview_jpeg +
                b"\r\n"
            )
            yield chunk
            time.sleep(0.10)  # 약 10fps

    return StreamingResponse(
        _gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


# ── 수동 검사 트리거 ──────────────────────────────────────────────────────────

@router.post("/inspect/trigger", summary="수동 검사 트리거")
async def trigger_inspection(
    background_tasks: BackgroundTasks,
    stage2Source: Optional[str] = None,
) -> dict[str, str]:
    """
    운영자가 HTTP 요청으로 즉시 검사를 한 번 실행하도록 트리거한다.

    실제 검사 파이프라인은 main.py의 run_inspection_pipeline()을 호출하며,
    BackgroundTasks로 비동기 실행하여 API 응답을 즉시 반환한다.

    Returns:
        요청 수락 메시지 (실제 검사 결과는 서버 DB에서 확인)
    """
    mode = _normalize_stage2_mode(stage2Source)
    logger.info("[라우터] 수동 검사 트리거 요청 수신 (stage2=%s)", mode)

    # main 모듈의 파이프라인을 지연 import (순환 참조 방지)
    try:
        from main import run_inspection_pipeline
        background_tasks.add_task(run_inspection_pipeline, mode)
        return {"message": f"검사가 백그라운드에서 시작되었습니다. (stage2={mode})"}
    except ImportError:
        raise HTTPException(status_code=503, detail="검사 파이프라인을 로드할 수 없습니다.")


_EDGE_ROOT = Path(__file__).resolve().parent.parent
_DEMO_SAMPLES_DIR = _EDGE_ROOT / "demo_samples"
_CAPTURES_DIR = _EDGE_ROOT / "captures"
_IMAGE_SUFFIX = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class InspectFromFileBody(BaseModel):
    """저장된 이미지로 검사 — edge/captures 또는 edge/demo_samples 기준 상대 경로."""

    path: str = Field(
        ...,
        min_length=1,
        description='예: demo_samples/synthetic/foo.jpg 또는 20260404_120000_xxx.jpg',
    )


class CameraFocusBody(BaseModel):
    auto: bool = Field(default=False, description="true면 오토포커스")
    value: int = Field(default=30, ge=0, le=255, description="수동 초점 값 (0~255)")


@router.get("/camera/focus", summary="카메라 초점 상태 조회")
async def get_camera_focus() -> dict[str, Any]:
    try:
        import main as main_mod

        cam = getattr(main_mod, "camera", None)
        if cam is None:
            raise HTTPException(status_code=503, detail="카메라가 초기화되지 않았습니다.")
        with _preview_lock:
            state = cam.get_focus_state()
        return {"camera_focus": state}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"초점 상태 조회 실패: {e}") from e


@router.post("/camera/focus", summary="카메라 초점 실시간 설정")
async def set_camera_focus(body: CameraFocusBody) -> dict[str, Any]:
    try:
        import main as main_mod

        cam = getattr(main_mod, "camera", None)
        if cam is None:
            raise HTTPException(status_code=503, detail="카메라가 초기화되지 않았습니다.")
        with _preview_lock:
            state = cam.set_focus_runtime(auto=body.auto, value=body.value)
        return {"message": "카메라 초점을 적용했습니다.", "camera_focus": state}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"초점 설정 실패: {e}") from e


@router.post("/inspect/upload", summary="이미지 업로드 후 검사 (캡처 생략)")
async def inspect_from_uploaded_file(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(..., description="검사할 이미지 파일 (.jpg/.jpeg/.png/.bmp/.webp)"),
    stage2Source: Optional[str] = None,
) -> dict[str, str]:
    """
    브라우저에서 업로드한 이미지를 edge/captures 에 저장한 뒤 동일 검사 파이프라인을 실행한다.
    라즈베리파이·웹캠이 없는 팀원의 로컬 테스트 경로로 사용한다.
    """
    filename = image.filename or "upload.jpg"
    suffix = Path(filename).suffix.lower()
    if suffix not in _IMAGE_SUFFIX:
        raise HTTPException(status_code=400, detail="지원하지 않는 이미지 형식입니다.")

    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="업로드된 파일이 비어 있습니다.")

    # 원본 파일명의 특수문자를 제거해 안전한 저장 파일명을 만든다.
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).stem)[:40] or "upload"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    save_name = f"{ts}_{stem}{suffix}"
    _CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    save_path = _CAPTURES_DIR / save_name
    save_path.write_bytes(raw)

    if cv2.imread(str(save_path)) is None:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="이미지를 디코딩할 수 없습니다.")

    try:
        import main as main_mod

        det = getattr(main_mod, "detector", None)
        f1 = getattr(main_mod, "fiducial_detector", None)
        f2 = getattr(main_mod, "defect_detector", None)
        if settings.USE_SEPARATE_MODELS:
            if f1 is None or f2 is None:
                raise HTTPException(status_code=503, detail="YOLO 분리 모델이 로드되지 않았습니다.")
        elif det is None:
            raise HTTPException(status_code=503, detail="YOLO 모델이 로드되지 않았습니다.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"모델 상태 확인 실패: {e}") from e

    from main import run_inspection_pipeline_from_source_file

    mode = _normalize_stage2_mode(stage2Source)
    background_tasks.add_task(run_inspection_pipeline_from_source_file, save_name, mode)
    return {
        "message": f"업로드 이미지 검사를 시작했습니다: {save_name} (stage2={mode})",
    }


@router.get("/inspect/demo-samples", summary="데모용 샘플 이미지 목록 (demo_samples/)")
async def list_demo_sample_images() -> dict[str, Any]:
    """
    edge/demo_samples 아래의 이미지 파일 목록을 반환한다.
    합성 데이터를 Pi에 복사한 뒤 대시보드에서 선택해 검사할 때 사용.
    """
    if not _DEMO_SAMPLES_DIR.is_dir():
        return {"paths": [], "root": "demo_samples"}
    paths: list[str] = []
    for p in sorted(_DEMO_SAMPLES_DIR.rglob("*")):
        if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIX:
            rel = p.relative_to(_EDGE_ROOT)
            paths.append(str(rel).replace("\\", "/"))
    return {"paths": paths[:500], "root": "demo_samples"}


@router.post("/inspect/from-file", summary="저장 이미지 파일로 검사 (캡처 생략)")
async def inspect_from_file(
    body: InspectFromFileBody,
    background_tasks: BackgroundTasks,
    stage2Source: Optional[str] = None,
) -> dict[str, str]:
    """
    카메라 대신 edge/captures 또는 edge/demo_samples 아래 파일로 동일 검사 파이프라인을 실행한다.
    결과는 Spring Boot DB로 전송된다.
    """
    from inference.model_compare import resolve_safe_inspection_source_image

    try:
        src = resolve_safe_inspection_source_image(body.path.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    if cv2.imread(str(src)) is None:
        raise HTTPException(status_code=400, detail="이미지를 디코딩할 수 없습니다.")

    try:
        import main as main_mod

        det = getattr(main_mod, "detector", None)
        f1 = getattr(main_mod, "fiducial_detector", None)
        f2 = getattr(main_mod, "defect_detector", None)
        if settings.USE_SEPARATE_MODELS:
            if f1 is None or f2 is None:
                raise HTTPException(status_code=503, detail="YOLO 분리 모델이 로드되지 않았습니다.")
        elif det is None:
            raise HTTPException(status_code=503, detail="YOLO 모델이 로드되지 않았습니다.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"모델 상태 확인 실패: {e}") from e

    from main import run_inspection_pipeline_from_source_file

    mode = _normalize_stage2_mode(stage2Source)
    background_tasks.add_task(run_inspection_pipeline_from_source_file, body.path.strip(), mode)
    return {
        "message": f"파일 검사를 시작했습니다: {body.path.strip()} (stage2={mode})",
    }


@router.post("/inspect/dummy", summary="더미 데이터 전송 테스트")
async def send_dummy_inspection() -> dict[str, Any]:
    """
    더미(Dummy) 검사 결과 패킷을 생성하여 Spring Boot 서버로 전송한다.

    카메라나 YOLO 모델 없이 서버 연동을 빠르게 검증할 때 사용.
    Step 3의 핵심 테스트 엔드포인트.

    Returns:
        서버 응답 데이터 또는 오류 메시지
    """
    logger.info("[라우터] 더미 전송 테스트 시작")

    # 더미 패킷 생성
    packet = create_dummy_packet(device_id="RPI5-LINE-A")
    logger.info("[라우터] 더미 패킷 — 결과: %s, 결함 수: %d",
                packet.result.value, len(packet.defects))

    # 서버로 전송
    sender = ServerSender()
    response = sender.send(packet)
    sender.close()

    if response is None:
        raise HTTPException(
            status_code=502,
            detail=f"Spring Boot 서버({settings.SERVER_BASE_URL})에 전송 실패. "
                   "서버가 실행 중인지 확인하세요."
        )

    return {
        "message": "더미 전송 성공",
        "sent_packet": packet.to_server_json(),
        "server_response": response,
    }


# ── 시연용 엔드포인트 ─────────────────────────────────────────────────────────

@router.post("/inspect/demo/fail", summary="[시연용] FAIL 결과 강제 전송")
async def demo_force_fail() -> dict[str, Any]:
    """
    시연용: FAIL 결과를 무조건 생성하여 서버로 전송합니다.
    모델 학습 전에도 FAIL 알람·대시보드 표시를 시연할 때 사용합니다.

    GPIO 알람(빨간 LED + 부저)도 함께 동작합니다.
    """
    logger.info("[시연] FAIL 강제 전송 요청")

    packet = create_dummy_packet(device_id="RPI5-LINE-A", force_fail=True)

    # GPIO 알람 동작
    try:
        from main import _gpio
        if _gpio:
            _gpio.signal_fail()
    except Exception:
        pass

    sender = ServerSender()
    response = sender.send(packet)
    sender.close()

    if response is None:
        raise HTTPException(status_code=502, detail="서버 전송 실패")

    return {
        "message": "🔴 FAIL 시연 전송 완료 — 빨간 LED + 부저 동작",
        "result": "FAIL",
        "defects": [d.defect_type for d in packet.defects],
        "server_response": response,
    }


@router.post("/inspect/demo/pass", summary="[시연용] PASS 결과 강제 전송")
async def demo_force_pass() -> dict[str, Any]:
    """
    시연용: PASS 결과를 무조건 생성하여 서버로 전송합니다.
    정상 → 결함 → 정상 복구 흐름을 시연할 때 사용합니다.

    GPIO 알람(초록 LED)도 함께 동작합니다.
    """
    logger.info("[시연] PASS 강제 전송 요청")

    packet = create_dummy_packet(device_id="RPI5-LINE-A", force_pass=True)

    try:
        from main import _gpio
        if _gpio:
            _gpio.signal_pass()
    except Exception:
        pass

    sender = ServerSender()
    response = sender.send(packet)
    sender.close()

    if response is None:
        raise HTTPException(status_code=502, detail="서버 전송 실패")

    return {
        "message": "🟢 PASS 시연 전송 완료 — 초록 LED 동작",
        "result": "PASS",
        "server_response": response,
    }


@router.post("/inspect/auto/start", summary="[시연용] 자동 연속 검사 시작")
async def auto_inspect_start(
    interval: float = 5.0,
    background_tasks: BackgroundTasks = None,
) -> dict[str, str]:
    """
    시연용: 일정 간격으로 자동 반복 검사를 시작합니다.
    기판을 올려놓으면 자동으로 검사 → 결과 전송이 반복됩니다.

    Args:
        interval: 검사 간격 (초, 기본값 5초)
    """
    global _auto_running, _auto_interval
    if _auto_running:
        return {"message": f"자동 검사가 이미 실행 중입니다. (간격: {_auto_interval}초)"}

    _auto_running = True
    _auto_interval = interval
    logger.info("[시연] 자동 연속 검사 시작 — 간격: %.1f초", interval)

    background_tasks.add_task(_auto_inspect_loop)
    return {"message": f"✅ 자동 검사 시작 (간격: {interval}초) — /edge/inspect/auto/stop 으로 중지"}


@router.post("/inspect/auto/stop", summary="[시연용] 자동 연속 검사 중지")
async def auto_inspect_stop() -> dict[str, str]:
    """자동 반복 검사를 중지합니다."""
    global _auto_running
    _auto_running = False
    logger.info("[시연] 자동 연속 검사 중지 요청")
    return {"message": "⏹ 자동 검사 중지됨"}


@router.get("/inspect/auto/status", summary="자동 검사 실행 상태 조회")
async def auto_inspect_status() -> dict[str, Any]:
    """자동 검사 실행 여부와 설정된 간격을 반환합니다."""
    return {
        "running": _auto_running,
        "interval_seconds": _auto_interval,
    }


async def _auto_inspect_loop() -> None:
    """
    자동 연속 검사 백그라운드 루프.
    _auto_running 이 False가 될 때까지 interval마다 검사를 실행합니다.
    """
    global _auto_running
    while _auto_running:
        try:
            from main import run_inspection_pipeline
            logger.info("[자동검사] 검사 실행 중...")
            await asyncio.get_event_loop().run_in_executor(None, run_inspection_pipeline)
        except Exception as e:
            logger.error("[자동검사] 파이프라인 오류: %s", e)

        if _auto_running:
            await asyncio.sleep(_auto_interval)
