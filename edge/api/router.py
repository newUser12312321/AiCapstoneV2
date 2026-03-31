"""
FastAPI 로컬 API 라우터

라즈베리파이 자체에서 서빙하는 로컬 REST API 엔드포인트.
같은 네트워크의 다른 기기(운영자 PC, 모니터링 툴 등)가
엣지 디바이스의 상태를 조회하거나 수동 검사를 트리거할 때 사용한다.

Base URL: http://<라즈베리파이_IP>:8000
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.sender import create_dummy_packet, ServerSender
from config.settings import settings

logger = logging.getLogger(__name__)

# APIRouter: main.py의 FastAPI 앱에 include_router()로 등록한다.
router = APIRouter(prefix="/edge", tags=["Edge Device"])


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
