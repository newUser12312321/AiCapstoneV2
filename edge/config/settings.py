"""
엣지 디바이스 전역 설정 모듈

pydantic-settings를 사용하여 .env 파일 또는 OS 환경변수에서
설정값을 자동으로 로드하고 타입을 검증한다.

사용법:
    from config.settings import settings
    print(settings.SERVER_BASE_URL)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    애플리케이션 전체에서 사용하는 설정값 클래스.
    .env 파일이 있으면 우선 적용하고, 없으면 아래 default 값을 사용한다.
    """

    # ── 중앙 서버 연결 정보 ──────────────────────────────────────────────────
    # Spring Boot 서버 주소 (같은 LAN 내 IP 또는 hostname)
    SERVER_BASE_URL: str = Field(default="http://192.168.0.10:8080")

    # ── 카메라 설정 ──────────────────────────────────────────────────────────
    # /dev/video0 → 0, C922가 video1·video2만 있으면 1 또는 2
    CAMERA_DEVICE_INDEX: int = Field(default=0)
    CAMERA_WIDTH: int = Field(default=1920)
    CAMERA_HEIGHT: int = Field(default=1080)
    # False: 예전 기본과 동일 — 오토포커스 끄고 focus_absolute만 사용(거리 고정 스테이션에 맞으면 유지)
    # True: 거리가 자주 바뀔 때 v4l2 오토포커스
    CAMERA_FOCUS_AUTO: bool = Field(default=False)
    # 수동 초점일 때만 사용 (0~255). 과거 하드코드 30과 동일 기본값
    CAMERA_FOCUS_ABSOLUTE: int = Field(default=30, ge=0, le=255)

    # ── YOLO 추론 설정 ───────────────────────────────────────────────────────
    # Stage 1: 피듀셜 마크 탐지 모델 (클래스: FIDUCIAL)
    YOLO_FIDUCIAL_WEIGHTS: str = Field(default="weights/fiducial_best.pt")
    # Stage 2: 결함 탐지 모델 (클래스: TRACE_OPEN, METAL_DAMAGE)
    YOLO_DEFECT_WEIGHTS: str = Field(default="weights/defect_best.pt")

    # 하위 호환: 단일 모델 사용 시 (두 Stage 합쳐서 학습한 경우)
    YOLO_WEIGHTS_PATH: str = Field(default="weights/best.pt")

    # 이 값 이상의 confidence를 가진 탐지 결과만 사용
    YOLO_CONFIDENCE_THRESHOLD: float = Field(default=0.5)

    # 2-Stage 분리 모델 사용 여부
    # True: fiducial_best.pt + defect_best.pt 각각 사용
    # False: best.pt 단일 모델 사용
    USE_SEPARATE_MODELS: bool = Field(default=False)

    # ── FastAPI 서버 포트 ────────────────────────────────────────────────────
    EDGE_API_PORT: int = Field(default=8000)

    # ── GPIO 핀 번호 (BCM 모드) ──────────────────────────────────────────────
    BUZZER_PIN: int = Field(default=17)
    LED_RED_PIN: int = Field(default=27)    # 불합격(FAIL) 표시
    LED_GREEN_PIN: int = Field(default=22)  # 합격(PASS) 표시

    # ── 실행 환경 ────────────────────────────────────────────────────────────
    # "production": 실제 라즈베리파이에서 GPIO/YOLO 실제 동작
    # "development": 개발 PC에서 더미 데이터로 동작
    ENVIRONMENT: str = Field(default="development")

    # ── 정렬 / 각도 보정 ───────────────────────────────────────────────────────
    # 피듀셜 2개로 측정한 기울기가 이 각도(°)를 넘으면 FAIL (오탐·이상 배치로 간주, 보정 안 함)
    MAX_DESKEW_ANGLE_DEG: float = Field(default=45.0)
    # 이보다 작으면 회전 보정 생략 (미세 보간 노이즈 감소)
    MIN_DESKEW_ANGLE_DEG: float = Field(default=0.05)
    # 하위 호환·문서용: 과거 "허용 오차 초과 시 FAIL" 모드에서 사용. 파이프라인은 MAX_DESKEW_* 기준.
    MAX_ANGLE_ERROR_DEG: float = Field(default=3.0)

    # pydantic-settings 설정:
    # .env 파일을 자동으로 찾아 읽고, 대소문자를 구분하지 않는다.
    # extra='ignore': .env에 아직 모델에 없는 키가 있어도 기동 실패하지 않음(구버전 코드·부분 배포)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# 싱글턴 인스턴스: 모든 모듈에서 이 객체를 import해서 사용
settings = Settings()
