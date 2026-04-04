"""
엣지 디바이스 메인 진입점

FastAPI 서버를 기동하고, 2-Stage 비전 검사 파이프라인을 실행한다.

실행 방법:
    # 개발 환경 (더미 모드)
    ENVIRONMENT=development uvicorn main:app --host 0.0.0.0 --port 8000 --reload

    # 라즈베리파이 운영 환경
    uvicorn main:app --host 0.0.0.0 --port 8000

검사 파이프라인 흐름:
    ┌──────────────────────────────────────────────────────────────┐
    │  1. 카메라 캡처 (1080p)                                        │
    │  2-A. Stage 1: YOLO → 피듀셜 탐지 → 기울기 측정 → 이미지 회전 보정  │
    │  2-B. Stage 2: 보정된 ROI Crop → YOLO → 결함 탐지              │
    │  3. 판정 (PASS / FAIL)                                         │
    │  4. GPIO 즉시 알람 (부저 + LED)                                 │
    │  5. Spring Boot 서버로 JSON 전송                               │
    └──────────────────────────────────────────────────────────────┘
"""

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# 캡처 저장·정적 서빙 경로 (settings와 무관, 항상 main.py 기준 edge/captures)
_EDGE_DIR = Path(__file__).resolve().parent
CAPTURES_DIR = _EDGE_DIR / "captures"
DEMO_SAMPLES_DIR = _EDGE_DIR / "demo_samples"
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.router import router as edge_router
from api.sender import ServerSender, create_dummy_packet
from capture.camera import CameraCapture
from config.settings import settings
from hardware.gpio_controller import GpioController
from inference.alignment import (
    compute_alignment,
    crop_inspection_roi_with_offset,
    deskew_image_by_fiducial_angle,
)
from inference.yolo_detector import YoloDetector
from models.schemas import (
    DefectPayload,
    InspectionPacket,
    InspectionResult,
)

# ── 로깅 설정 ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.ENVIRONMENT == "development" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("main")


# ── 전역 싱글턴 객체 (앱 수명 주기 동안 유지) ─────────────────────────────────
camera:           Optional[CameraCapture] = None
detector:         Optional[YoloDetector]  = None  # 단일 모델 모드
fiducial_detector: Optional[YoloDetector] = None  # 분리 모델 — Stage 1 전용
defect_detector:   Optional[YoloDetector] = None  # 분리 모델 — Stage 2 전용
gpio:             Optional[GpioController] = None
sender:           Optional[ServerSender]   = None


# ── FastAPI 수명 주기 이벤트 ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 앱 시작/종료 시 실행되는 수명 주기 관리자.

    [시작 시]
    - 카메라 초기화 및 오토포커스 비활성화
    - YOLO 모델 로드 (최초 1회만 수행, 이후 캐시 재사용)
    - GPIO 초기화
    - 서버 HTTP 세션 준비

    [종료 시]
    - 카메라 자원 해제
    - GPIO 핀 안전 초기화
    - HTTP 세션 종료
    """
    global camera, detector, fiducial_detector, defect_detector, gpio, sender
    logger.info("=" * 60)
    logger.info("   PCB 비전 검사 스테이션 시작 [%s]", settings.ENVIRONMENT.upper())
    logger.info("=" * 60)

    # 카메라 초기화
    camera = CameraCapture()
    try:
        camera.open()
        logger.info("[시작] 카메라 초기화 완료")
    except RuntimeError as e:
        logger.warning("[시작] 카메라 초기화 실패 (더미 모드로 계속): %s", e)
        camera = None

    # YOLO 모델 로드 — settings.USE_SEPARATE_MODELS 값에 따라 분기
    if settings.USE_SEPARATE_MODELS:
        # 2-Stage 분리 모델: fiducial_best.pt + defect_best.pt 각각 로드
        logger.info("[시작] 2-Stage 분리 모델 로드 모드")
        fiducial_detector = YoloDetector(weights_path=settings.YOLO_FIDUCIAL_WEIGHTS)
        fiducial_detector.load()
        defect_detector = YoloDetector(weights_path=settings.YOLO_DEFECT_WEIGHTS)
        defect_detector.load()
    else:
        # 단일 통합 모델: best.pt 하나로 모든 클래스 탐지
        logger.info("[시작] 단일 통합 모델 로드 모드")
        detector = YoloDetector()
        detector.load()

    # GPIO 초기화
    gpio = GpioController()
    logger.info("[시작] GPIO 초기화 완료")

    # HTTP 송신 세션 준비
    sender = ServerSender()
    logger.info("[시작] 서버 연결 준비 완료: %s", settings.SERVER_BASE_URL)
    logger.info("[시작] 초기화 완료 — 검사 대기 중")

    yield  # ← FastAPI 앱이 여기서 실행된다.

    # ── 종료 시 자원 정리 ─────────────────────────────────────────────────────
    logger.info("[종료] 자원 해제 시작...")
    if camera:
        camera.release()
    if gpio:
        gpio.cleanup()
    if sender:
        sender.close()
    logger.info("[종료] 정상 종료 완료.")


# ── FastAPI 앱 인스턴스 ───────────────────────────────────────────────────────

app = FastAPI(
    title="PCB Edge Vision Inspection API",
    description="라즈베리파이 5 엣지 디바이스 로컬 제어 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 설정: 같은 LAN의 운영자 PC 브라우저에서 직접 접근 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 운영 환경에서는 특정 IP로 제한할 것
    allow_methods=["*"],
    allow_headers=["*"],
)

# 엣지 라우터 등록 (/edge/health, /edge/inspect/dummy 등)
app.include_router(edge_router)

# 캡처 이미지 정적 서빙 — edge/captures 고정 (uvicorn 실행 위치와 무관). 라우터보다 뒤에 마운트.
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
DEMO_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/captures", StaticFiles(directory=str(CAPTURES_DIR)), name="captures")
app.mount("/demo_samples", StaticFiles(directory=str(DEMO_SAMPLES_DIR)), name="demo_samples")


# ── 2-Stage 비전 검사 파이프라인 ──────────────────────────────────────────────

async def run_inspection_pipeline() -> Optional[InspectionPacket]:
    """
    PCB 검사 전체 파이프라인을 실행한다.

    개발(ENVIRONMENT=development) 환경:
        카메라/YOLO 없이 더미 데이터로 파이프라인 흐름을 테스트한다.

    운영(ENVIRONMENT=production) 환경:
        실제 카메라 캡처 → YOLO 추론 → GPIO 알람 → 서버 전송을 수행한다.

    Returns:
        생성된 InspectionPacket (서버 전송 완료 여부와 무관하게 반환)
        파이프라인 오류 시 None
    """
    pipeline_start = time.perf_counter()

    # ── 개발 환경: 더미 모드 ─────────────────────────────────────────────────
    if settings.ENVIRONMENT == "development" or camera is None:
        logger.info("[파이프라인] 더미 모드 실행")
        packet = create_dummy_packet()

        # 더미 결과로 GPIO 신호 테스트
        if gpio:
            if packet.result == InspectionResult.PASS:
                gpio.signal_pass()
            else:
                gpio.signal_fail()

        # 서버 전송
        if sender:
            sender.send(packet)

        total_ms = int((time.perf_counter() - pipeline_start) * 1000)
        logger.info("[파이프라인] 더미 완료: %s (%dms)", packet.result.value, total_ms)
        return packet

    # ── 운영 환경: 실제 파이프라인 ───────────────────────────────────────────
    try:
        # STEP 1: 카메라 캡처
        logger.info("[파이프라인] STEP 1 — 이미지 캡처")
        if gpio:
            gpio.signal_processing()  # 처리 중 LED 점멸

        frame, image_path = camera.capture_and_save()

        debug_imshow = settings.ENVIRONMENT == "development"
        return _run_production_vision_pipeline(
            frame, image_path, pipeline_start, debug_imshow=debug_imshow
        )

    except Exception as e:
        logger.error("[파이프라인] 예외 발생: %s", e, exc_info=True)
        if gpio:
            gpio.signal_error()
        return None


def _run_production_vision_pipeline(
    frame: np.ndarray,
    image_path: str,
    pipeline_start: float,
    *,
    debug_imshow: bool = False,
) -> Optional[InspectionPacket]:
    """카메라/파일 공통 — Stage 1·2 및 전송."""
    try:
        if debug_imshow:
            cv2.imshow("Captured Frame", cv2.resize(frame, (640, 360)))
            cv2.waitKey(1)

        # STEP 2-A: Stage 1 — 피듀셜 마크 탐지 및 정렬 검사
        logger.info("[파이프라인] STEP 2-A — 피듀셜 마크 탐지")
        stage1 = fiducial_detector if settings.USE_SEPARATE_MODELS else detector
        fiducials, fiducial_ms = stage1.detect_fiducials(frame)
        alignment = compute_alignment(fiducials)

        measured_skew_deg = alignment.angle_error_deg

        logger.info(
            "[파이프라인] 기울기 측정: %s, |각도|: %.2f°",
            "보정 가능" if alignment.is_aligned else "한도 초과",
            measured_skew_deg,
        )

        f1x = f1y = f2x = f2y = None
        if alignment.fiducial1:
            f1x, f1y = alignment.fiducial1.center_x, alignment.fiducial1.center_y
        if alignment.fiducial2:
            f2x, f2y = alignment.fiducial2.center_x, alignment.fiducial2.center_y

        if not alignment.is_aligned:
            logger.warning("[파이프라인] 피듀셜/기울기 조건 불충족 → FAIL, Stage 2 건너뜀")
            packet = _build_packet(
                result=InspectionResult.FAIL,
                f1x=f1x, f1y=f1y, f2x=f2x, f2y=f2y,
                angle_error=measured_skew_deg,
                inference_ms=fiducial_ms,
                defects=[],
                image_path=image_path,
                pipeline_start=pipeline_start,
            )
            _finalize(packet)
            return packet

        logger.info("[파이프라인] STEP 2-A′ — 기울기 보정 (deskew)")
        frame, alignment = deskew_image_by_fiducial_angle(frame, alignment)

        orig_p = Path(image_path)
        deskew_path = str(orig_p.parent / f"{orig_p.stem}_deskew{orig_p.suffix}")
        cv2.imwrite(deskew_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        logger.info("[파이프라인] 보정 후 이미지 저장: %s", deskew_path)

        if alignment.fiducial1:
            f1x, f1y = alignment.fiducial1.center_x, alignment.fiducial1.center_y
        if alignment.fiducial2:
            f2x, f2y = alignment.fiducial2.center_x, alignment.fiducial2.center_y

        logger.info("[파이프라인] STEP 2-B — 결함 탐지 (ROI)")
        roi, roi_x, roi_y = crop_inspection_roi_with_offset(frame, alignment)
        stage2 = defect_detector if settings.USE_SEPARATE_MODELS else detector
        defect_items, defect_ms = stage2.detect_defects(roi)

        logger.info("[파이프라인] 결함 탐지: %d건", len(defect_items))

        final_result = InspectionResult.FAIL if defect_items else InspectionResult.PASS

        defect_payloads = [
            DefectPayload(
                defect_type=d.defect_type,
                confidence=d.confidence,
                bbox_x=d.bbox.x + roi_x,
                bbox_y=d.bbox.y + roi_y,
                bbox_width=d.bbox.width,
                bbox_height=d.bbox.height,
            )
            for d in defect_items
        ]

        packet = _build_packet(
            result=final_result,
            f1x=f1x, f1y=f1y, f2x=f2x, f2y=f2y,
            angle_error=measured_skew_deg,
            inference_ms=fiducial_ms + defect_ms,
            defects=defect_payloads,
            image_path=deskew_path,
            pipeline_start=pipeline_start,
        )

        _finalize(packet)
        return packet

    except Exception as e:
        logger.error("[파이프라인] 예외 발생: %s", e, exc_info=True)
        if gpio:
            gpio.signal_error()
        return None


async def run_inspection_pipeline_from_source_file(relative_path: str) -> Optional[InspectionPacket]:
    """
    edge/captures 또는 edge/demo_samples 아래 저장된 이미지로 동일 파이프라인 실행.
    카메라 없이 시연·합성 데이터 검증에 사용한다.
    """
    from inference.model_compare import resolve_safe_inspection_source_image

    pipeline_start = time.perf_counter()
    has_models = (
        (fiducial_detector is not None and defect_detector is not None)
        if settings.USE_SEPARATE_MODELS
        else detector is not None
    )
    if not has_models:
        logger.error("[파이프라인] YOLO 모델이 로드되지 않아 파일 검사를 건너뜁니다.")
        return None

    src = resolve_safe_inspection_source_image(relative_path)

    frame = cv2.imread(str(src))
    if frame is None:
        raise RuntimeError(f"이미지 디코딩 실패: {src}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = CAPTURES_DIR / f"{ts}_fromfile{src.suffix.lower() if src.suffix else '.jpg'}"
    cv2.imwrite(str(dest), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    image_path = str(dest.resolve())

    logger.info("[파이프라인] STEP 1 — 파일 로드 검사: %s → %s", src.name, dest.name)
    if gpio:
        gpio.signal_processing()

    return _run_production_vision_pipeline(
        frame, image_path, pipeline_start, debug_imshow=False
    )


def _build_packet(
    result: InspectionResult,
    f1x, f1y, f2x, f2y,
    angle_error: float,
    inference_ms: int,
    defects: list[DefectPayload],
    image_path: str,
    pipeline_start: float,
) -> InspectionPacket:
    """InspectionPacket 조립 헬퍼."""
    total_ms = int((time.perf_counter() - pipeline_start) * 1000)
    return InspectionPacket(
        device_id="RPI5-LINE-A",
        result=result,
        fiducial1_x=f1x, fiducial1_y=f1y,
        fiducial2_x=f2x, fiducial2_y=f2y,
        angle_error_deg=angle_error,
        inference_time_ms=inference_ms,
        total_time_ms=total_ms,
        image_path=image_path,
        inspected_at=datetime.now(),
        defects=defects,
    )


def _finalize(packet: InspectionPacket) -> None:
    """GPIO 알람 출력 및 서버 전송을 수행하는 마무리 단계."""
    # GPIO 판정 신호 출력
    if gpio:
        if packet.result == InspectionResult.PASS:
            gpio.signal_pass()
        else:
            gpio.signal_fail()

    # Spring Boot 서버로 결과 전송
    if sender:
        sender.send(packet)

    logger.info(
        "[파이프라인] 완료 — 결과: %s, 결함: %d건, 총시간: %dms",
        packet.result.value,
        len(packet.defects),
        packet.total_time_ms or 0,
    )


# ── 루트 엔드포인트 ───────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    """API 루트 — 기본 안내 메시지."""
    return {
        "service": "PCB Edge Vision Inspection",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/edge/health",
        "dummy_test": "POST /edge/inspect/dummy",
    }


# ── 직접 실행 (python main.py) ────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.EDGE_API_PORT,
        reload=(settings.ENVIRONMENT == "development"),
        log_level="debug" if settings.ENVIRONMENT == "development" else "info",
    )
