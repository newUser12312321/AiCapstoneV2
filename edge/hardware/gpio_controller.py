"""
GPIO 하드웨어 제어 모듈 (부저 + LED)

gpiozero 라이브러리를 사용하여 라즈베리파이 GPIO 핀을 제어한다.
gpiozero가 없는 개발 환경(macOS/Windows)에서는 MockGPIO로 자동 대체되어
실제 하드웨어 없이도 파이프라인 흐름 테스트가 가능하다.

핀 배치 (BCM 모드):
  ┌─────────────────────────────────────────┐
  │  GPIO 17  ─→  부저 (Buzzer)              │
  │  GPIO 27  ─→  빨간 LED (FAIL 표시)        │
  │  GPIO 22  ─→  초록 LED (PASS 표시)        │
  └─────────────────────────────────────────┘
"""

import logging
import time
from config.settings import settings

logger = logging.getLogger(__name__)


# ── gpiozero 가용성 확인 및 MockGPIO 폴백 ────────────────────────────────────

try:
    from gpiozero import Buzzer, LED
    GPIO_AVAILABLE = True
    logger.info("[GPIO] gpiozero 사용 가능 — 실제 핀 제어 모드")
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("[GPIO] gpiozero 없음 — MockGPIO 모드로 동작 (개발 환경)")


class MockOutputDevice:
    """
    개발 환경에서 실제 GPIO 없이 동작하는 더미 출력 장치.
    on()/off()/beep()/blink() 호출을 로그로 출력한다.
    """

    def __init__(self, name: str, pin: int) -> None:
        self.name = name
        self.pin = pin

    def on(self):
        logger.debug("[MockGPIO] %s (pin=%d) ON", self.name, self.pin)

    def off(self):
        logger.debug("[MockGPIO] %s (pin=%d) OFF", self.name, self.pin)

    def beep(self, on_time=0.1, off_time=0.1, n=None, background=True):
        logger.debug("[MockGPIO] %s BEEP (on=%.1fs, off=%.1fs, n=%s)",
                     self.name, on_time, off_time, n)

    def blink(self, on_time=1, off_time=1, n=None, background=True):
        logger.debug("[MockGPIO] %s BLINK (on=%.1fs, off=%.1fs, n=%s)",
                     self.name, on_time, off_time, n)

    def close(self):
        logger.debug("[MockGPIO] %s closed", self.name)


class GpioController:
    """
    부저와 LED를 통합 제어하는 클래스.

    PASS 판정 시: 초록 LED 점등 + 짧은 비프음 1회
    FAIL 판정 시: 빨간 LED 점등 + 경고 비프음 3회

    사용 예:
        gpio = GpioController()
        gpio.signal_pass()
        # ... 검사 완료 후
        gpio.cleanup()
    """

    def __init__(self) -> None:
        if GPIO_AVAILABLE:
            # 실제 라즈베리파이 GPIO 핀 초기화
            self._buzzer   = Buzzer(settings.BUZZER_PIN)
            self._led_red  = LED(settings.LED_RED_PIN)
            self._led_green = LED(settings.LED_GREEN_PIN)
        else:
            # 개발 환경: 더미 장치로 대체
            self._buzzer    = MockOutputDevice("Buzzer",    settings.BUZZER_PIN)
            self._led_red   = MockOutputDevice("LED_RED",   settings.LED_RED_PIN)
            self._led_green = MockOutputDevice("LED_GREEN", settings.LED_GREEN_PIN)

        # 초기 상태: 모두 OFF
        self._all_off()

    # ── 판정 신호 출력 ────────────────────────────────────────────────────────

    def signal_pass(self) -> None:
        """
        합격(PASS) 신호를 출력한다.
        - 초록 LED 2초 점등
        - 비프음 1회 (0.1초)
        """
        logger.info("[GPIO] ✅ PASS 신호 출력")
        self._all_off()  # 이전 상태 초기화

        self._led_green.on()
        # n=1: 1회만 비프, background=False: 비프 완료까지 대기
        self._buzzer.beep(on_time=0.1, off_time=0.1, n=1, background=False)
        time.sleep(2.0)

        self._all_off()

    def signal_fail(self) -> None:
        """
        불합격(FAIL) 신호를 출력한다.
        - 빨간 LED 점멸 (0.3초 주기 × 3회)
        - 경고 비프음 3회 (각 0.3초)

        즉각적인 알람이 필요하므로 background=False로 동기 실행한다.
        """
        logger.warning("[GPIO] ❌ FAIL 신호 출력 — 즉시 알람")
        self._all_off()

        # 빨간 LED 점멸과 비프음 동시 실행
        self._led_red.on()
        # n=3: 3회 비프, background=False: 완료까지 블록
        self._buzzer.beep(on_time=0.3, off_time=0.2, n=3, background=False)
        time.sleep(1.0)

        self._all_off()

    def signal_processing(self) -> None:
        """
        검사 진행 중 상태를 표시한다.
        - 초록 LED 천천히 점멸 (비동기)
        """
        self._all_off()
        self._led_green.blink(on_time=0.5, off_time=0.5, background=True)

    def signal_error(self) -> None:
        """
        시스템 오류(카메라 연결 실패 등) 상태를 표시한다.
        - 빨간·초록 LED 빠르게 교대 점멸
        - 연속 비프음
        """
        logger.error("[GPIO] ⚠️ 시스템 오류 신호")
        self._all_off()
        self._led_red.blink(on_time=0.2, off_time=0.2, background=True)
        self._buzzer.beep(on_time=0.1, off_time=0.1, n=5, background=False)
        self._all_off()

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────────

    def _all_off(self) -> None:
        """모든 출력 장치를 OFF 상태로 초기화한다."""
        self._buzzer.off()
        self._led_red.off()
        self._led_green.off()

    # ── 자원 해제 ─────────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """
        GPIO 자원을 해제한다.
        애플리케이션 종료 시 반드시 호출해야 핀이 안전하게 초기화된다.
        """
        self._all_off()
        self._buzzer.close()
        self._led_red.close()
        self._led_green.close()
        logger.info("[GPIO] 자원 해제 완료.")
