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
    # /dev/video0 → 0, /dev/video2 → 2
    CAMERA_DEVICE_INDEX: int = Field(default=0)
    CAMERA_WIDTH: int = Field(default=1920)
    CAMERA_HEIGHT: int = Field(default=1080)

    # ── YOLO 추론 설정 ───────────────────────────────────────────────────────
    # .pt 가중치 파일 경로 (프로젝트 루트 기준 상대 경로)
    YOLO_WEIGHTS_PATH: str = Field(default="weights/best.pt")
    # 이 값 이상의 confidence를 가진 탐지 결과만 사용
    YOLO_CONFIDENCE_THRESHOLD: float = Field(default=0.5)

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

    # ── 정렬 허용 오차 ───────────────────────────────────────────────────────
    # 이 각도(°) 초과 시 FAIL 판정
    MAX_ANGLE_ERROR_DEG: float = Field(default=3.0)

    # pydantic-settings 설정:
    # .env 파일을 자동으로 찾아 읽고, 대소문자를 구분하지 않는다.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# 싱글턴 인스턴스: 모든 모듈에서 이 객체를 import해서 사용
settings = Settings()
