"""
Spring Boot 서버 전송 모듈

검사 완료 후 InspectionPacket을 JSON으로 직렬화하여
Spring Boot REST API(POST /api/inspections)로 전송한다.

재시도 로직:
  네트워크 불안정에 대비해 최대 3회 재시도하며,
  재시도 간격은 지수 백오프(1s → 2s → 4s)로 증가한다.
"""

import logging
import time
from typing import Optional

import requests
from requests.exceptions import ConnectionError, Timeout, RequestException

from config.settings import settings
from models.schemas import InspectionPacket

logger = logging.getLogger(__name__)

# ── 전송 설정 상수 ────────────────────────────────────────────────────────────
MAX_RETRY = 3           # 최대 재시도 횟수
RETRY_BASE_DELAY = 1.0  # 첫 번째 재시도 대기 시간(초), 이후 2배씩 증가
REQUEST_TIMEOUT = 10    # HTTP 요청 타임아웃 (초)


class ServerSender:
    """
    Spring Boot 서버로 검사 결과를 전송하는 클래스.

    싱글턴 패턴은 아니지만 requests.Session을 재사용하여
    Keep-Alive 연결로 반복 전송 시 오버헤드를 줄인다.
    """

    def __init__(self, base_url: str = settings.SERVER_BASE_URL) -> None:
        # POST 엔드포인트 URL 조립
        self.endpoint = f"{base_url.rstrip('/')}/api/inspections"
        # Session 재사용: TCP 연결 유지 (Connection Keep-Alive)
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept":       "application/json",
            # 엣지 디바이스 식별용 커스텀 헤더
            "X-Device-Type": "RaspberryPi5-EdgeNode",
        })
        logger.info("[전송] 서버 엔드포인트: %s", self.endpoint)

    # ── 전송 메서드 ───────────────────────────────────────────────────────────

    def send(self, packet: InspectionPacket) -> Optional[dict]:
        """
        InspectionPacket을 서버로 POST 전송한다.

        재시도 로직:
          - ConnectionError / Timeout 발생 시 지수 백오프 후 재시도
          - 서버 응답 4xx: 요청 오류이므로 재시도하지 않음
          - 서버 응답 5xx: 서버 오류이므로 재시도

        Args:
            packet: 전송할 검사 결과 패킷

        Returns:
            전송 성공 시 서버 응답 JSON 딕셔너리,
            실패 시 None
        """
        # InspectionPacket → camelCase JSON 딕셔너리 변환
        payload = packet.to_server_json()
        logger.info("[전송] 전송 시작 — 디바이스: %s, 결과: %s",
                    packet.device_id, packet.result.value)
        logger.debug("[전송] 페이로드: %s", payload)

        last_exception: Optional[Exception] = None

        for attempt in range(1, MAX_RETRY + 1):
            try:
                response = self._session.post(
                    self.endpoint,
                    json=payload,
                    timeout=REQUEST_TIMEOUT,
                )

                # 4xx 클라이언트 오류 → 재시도 없이 즉시 실패 처리
                if 400 <= response.status_code < 500:
                    logger.error(
                        "[전송] 클라이언트 오류 %d — 재시도 안함: %s",
                        response.status_code, response.text[:200]
                    )
                    return None

                # 5xx 서버 오류 → 재시도
                if response.status_code >= 500:
                    logger.warning(
                        "[전송] 서버 오류 %d (시도 %d/%d)",
                        response.status_code, attempt, MAX_RETRY
                    )
                    raise RequestException(f"서버 오류: {response.status_code}")

                # 201 Created 성공
                logger.info(
                    "[전송] 성공 (시도 %d/%d) — 응답 코드: %d, 저장 ID: %s",
                    attempt, MAX_RETRY, response.status_code,
                    response.json().get("id", "N/A")
                )
                return response.json()

            except (ConnectionError, Timeout) as e:
                last_exception = e
                logger.warning(
                    "[전송] 연결 실패 (시도 %d/%d): %s",
                    attempt, MAX_RETRY, type(e).__name__
                )

            except RequestException as e:
                last_exception = e
                logger.warning("[전송] 요청 오류 (시도 %d/%d): %s", attempt, MAX_RETRY, e)

            # 마지막 시도가 아니면 지수 백오프 대기
            if attempt < MAX_RETRY:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))  # 1s, 2s, 4s
                logger.info("[전송] %.1f초 후 재시도...", delay)
                time.sleep(delay)

        logger.error(
            "[전송] 최종 실패 — %d회 시도 후 서버에 전달하지 못했습니다. 마지막 오류: %s",
            MAX_RETRY, last_exception
        )
        return None

    def close(self) -> None:
        """HTTP 세션을 닫는다. 애플리케이션 종료 시 호출."""
        self._session.close()
        logger.info("[전송] HTTP 세션 종료.")

    def __del__(self):
        self.close()


# ── 더미 패킷 생성 유틸리티 (개발/테스트용) ──────────────────────────────────

def create_dummy_packet(
    device_id: str = "RPI5-LINE-A",
    force_fail: bool = False,
    force_pass: bool = False,
) -> InspectionPacket:
    """
    Step 3 테스트용 더미 InspectionPacket을 생성한다.

    실제 카메라/YOLO 없이 서버 연동을 확인할 때 사용.
    main.py의 더미 모드에서 호출된다.

    Args:
        force_fail: True면 무조건 FAIL 결과 생성 (시연용)
        force_pass: True면 무조건 PASS 결과 생성 (시연용)

    Returns:
        더미 검사 결과 패킷
    """
    from datetime import datetime
    from models.schemas import DefectPayload, InspectionResult
    import random

    if force_fail:
        is_pass = False
    elif force_pass:
        is_pass = True
    else:
        # 70% 확률 PASS, 30% 확률 FAIL
        is_pass = random.random() > 0.3
    result = InspectionResult.PASS if is_pass else InspectionResult.FAIL

    defects = []
    if not is_pass:
        # FAIL인 경우 더미 결함 1~2개 생성
        num_defects = random.randint(1, 2)
        defect_types = ["TRACE_OPEN", "METAL_DAMAGE"]
        for i in range(num_defects):
            defects.append(DefectPayload(
                defect_type=random.choice(defect_types),
                confidence=round(random.uniform(0.6, 0.95), 2),
                bbox_x=random.randint(200, 800),
                bbox_y=random.randint(100, 500),
                bbox_width=random.randint(30, 80),
                bbox_height=random.randint(20, 50),
            ))

    return InspectionPacket(
        device_id=device_id,
        result=result,
        fiducial1_x=320, fiducial1_y=240,
        fiducial2_x=960, fiducial2_y=242,
        angle_error_deg=round(random.uniform(0.1, 1.5), 2),
        inference_time_ms=random.randint(80, 200),
        total_time_ms=random.randint(200, 500),
        image_path=f"/captures/dummy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
        inspected_at=datetime.now(),
        defects=defects,
    )
