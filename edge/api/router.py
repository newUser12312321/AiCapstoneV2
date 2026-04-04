"""
FastAPI 로컬 API 라우터

라즈베리파이 자체에서 서빙하는 로컬 REST API 엔드포인트.
같은 네트워크의 다른 기기(운영자 PC, 모니터링 툴 등)가
엣지 디바이스의 상태를 조회하거나 수동 검사를 트리거할 때 사용한다.

Base URL: http://<라즈베리파이_IP>:8000
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from api.sender import create_dummy_packet, ServerSender
from config.settings import settings

logger = logging.getLogger(__name__)

# APIRouter: main.py의 FastAPI 앱에 include_router()로 등록한다.
router = APIRouter(prefix="/edge", tags=["Edge Device"])

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


class CompareModelsBody(BaseModel):
    """대시보드에서 여러 .pt를 같은 촬영으로 비교할 때 사용."""

    weights: list[str] = Field(..., min_length=1, description="edge/weights 기준 상대 경로 (예: alice.pt, team/best.pt)")
    defect_weights: Optional[list[str]] = Field(
        default=None,
        description="분리 학습 시 결함 가중치 (weights 와 동일 개수)",
    )
    image: Optional[str] = Field(
        default=None,
        description="캡처 대신 사용할 이미지 (edge/captures 기준, 예: snap.jpg)",
    )
    conf: Optional[float] = Field(default=None, description="신뢰도 임계값 (기본: settings)")
    camera_index: Optional[int] = Field(default=None, description="비디오 장치 인덱스")


@router.post("/compare-models", summary="동일 촬영으로 여러 가중치 비교")
async def compare_models_endpoint(body: CompareModelsBody) -> dict[str, Any]:
    """
    라즈베리파이에서 한 번 캡처한 프레임(또는 captures 이미지)으로
    weights 목록에 대해 순차 추론하여 표 형태 비교 결과를 반환한다.
    """
    from inference.model_compare import compare_models as run_compare

    loop = asyncio.get_running_loop()
    try:
        rows, src = await loop.run_in_executor(
            None,
            lambda: run_compare(
                body.weights,
                body.defect_weights,
                body.image,
                body.camera_index,
                body.conf,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        # 예: 카메라 장치 인덱스 오류 — Internal Server Error 대신 원인 전달
        msg = str(e)
        raise HTTPException(
            status_code=503,
            detail=msg + " — edge/.env 의 CAMERA_DEVICE_INDEX 를 0 등으로 바꾸거나, "
            "대시보드에서 카메라 인덱스를 지정하세요.",
        ) from e

    return {
        "input_source": src if src else "camera",
        "max_deskew_angle_deg": settings.MAX_DESKEW_ANGLE_DEG,
        "max_angle_error_deg": settings.MAX_ANGLE_ERROR_DEG,
        "conf": body.conf if body.conf is not None else settings.YOLO_CONFIDENCE_THRESHOLD,
        "rows": rows,
        "note": "동일 장면에서의 상대 비교이며, mAP 등 검증 정확도는 아님. 라벨 세트는 yolo val 권장.",
    }


@router.get("/status", summary="카메라/모델 상태 조회")
async def get_status() -> dict[str, Any]:
    """
    카메라 설정, YOLO 모델 경로, GPIO 핀 설정 등
    현재 엣지 디바이스의 구성 정보를 반환한다.
    """
    from pathlib import Path
    weights_exists = Path(settings.YOLO_WEIGHTS_PATH).exists()

    return {
        "camera": {
            "device_index": settings.CAMERA_DEVICE_INDEX,
            "resolution": f"{settings.CAMERA_WIDTH}x{settings.CAMERA_HEIGHT}",
        },
        "yolo": {
            "weights_path": settings.YOLO_WEIGHTS_PATH,
            "weights_loaded": weights_exists,
            "confidence_threshold": settings.YOLO_CONFIDENCE_THRESHOLD,
        },
        "gpio": {
            "buzzer_pin": settings.BUZZER_PIN,
            "led_red_pin": settings.LED_RED_PIN,
            "led_green_pin": settings.LED_GREEN_PIN,
        },
        "server": {
            "base_url": settings.SERVER_BASE_URL,
        },
    }


# ── 수동 검사 트리거 ──────────────────────────────────────────────────────────

@router.post("/inspect/trigger", summary="수동 검사 트리거")
async def trigger_inspection(background_tasks: BackgroundTasks) -> dict[str, str]:
    """
    운영자가 HTTP 요청으로 즉시 검사를 한 번 실행하도록 트리거한다.

    실제 검사 파이프라인은 main.py의 run_inspection_pipeline()을 호출하며,
    BackgroundTasks로 비동기 실행하여 API 응답을 즉시 반환한다.

    Returns:
        요청 수락 메시지 (실제 검사 결과는 서버 DB에서 확인)
    """
    logger.info("[라우터] 수동 검사 트리거 요청 수신")

    # main 모듈의 파이프라인을 지연 import (순환 참조 방지)
    try:
        from main import run_inspection_pipeline
        background_tasks.add_task(run_inspection_pipeline)
        return {"message": "검사가 백그라운드에서 시작되었습니다."}
    except ImportError:
        raise HTTPException(status_code=503, detail="검사 파이프라인을 로드할 수 없습니다.")


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
