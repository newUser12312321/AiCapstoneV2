"""
웹캠 캡처 모듈

C922 웹캠에서 1080p 이미지를 캡처하고,
v4l2-ctl 명령어로 오토포커스를 비활성화하여 고정 초점을 유지한다.

v4l2-ctl 은 Video4Linux2 유틸리티로 리눅스(라즈베리파이) 전용이며,
개발 환경(macOS/Windows)에서는 해당 명령이 없으므로 자동으로 건너뛴다.
"""

import subprocess
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import cv2
import numpy as np

from config.settings import settings

logger = logging.getLogger(__name__)


class CameraCapture:
    """
    웹캠 연결·설정·캡처를 담당하는 클래스.

    사용 예:
        cam = CameraCapture()
        cam.open()
        frame = cam.capture()
        cam.release()

    또는 컨텍스트 매니저로:
        with CameraCapture() as cam:
            frame = cam.capture()
    """

    def __init__(
        self,
        device_index: int = settings.CAMERA_DEVICE_INDEX,
        width: int = settings.CAMERA_WIDTH,
        height: int = settings.CAMERA_HEIGHT,
    ) -> None:
        self.device_index = device_index
        self.width = width
        self.height = height
        self._cap: Optional[cv2.VideoCapture] = None

    # ── 카메라 초기화 ──────────────────────────────────────────────────────────

    def open(self) -> None:
        """
        카메라를 열고 해상도를 설정한 뒤 오토포커스를 비활성화한다.

        v4l2-ctl 명령 순서:
        1. 오토포커스 끄기 (focus_auto=0)
        2. 수동 초점값 설정 (focus_absolute=30: 가까운 피사체에 적합한 값)
        3. 오토화이트밸런스 끄기 (white_balance_temperature_auto=0)
        4. 자동 노출 끄기 (exposure_auto=1 → 수동)
        """
        logger.info("[카메라] 장치 %d 열기 시도 (%dx%d)", self.device_index, self.width, self.height)

        # V4L2 오토포커스 비활성화 (라즈베리파이 리눅스 전용)
        self._disable_autofocus()

        # OpenCV VideoCapture 초기화
        # CAP_V4L2: 라즈베리파이에서 성능 최적화된 V4L2 백엔드 사용
        self._cap = cv2.VideoCapture(self.device_index, cv2.CAP_V4L2)

        if not self._cap.isOpened():
            raise RuntimeError(f"카메라 장치 {self.device_index}를 열 수 없습니다.")

        # 해상도 설정 (1920×1080 → 1080p)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        # 버퍼 크기를 1로 최소화하여 항상 최신 프레임을 받는다.
        # (버퍼가 크면 오래된 프레임을 캡처할 위험)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # 설정 확인
        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info("[카메라] 실제 해상도: %dx%d", actual_w, actual_h)

        # 카메라 안정화 대기 (노출 자동 조정 시간 확보)
        time.sleep(1.0)

    def _disable_autofocus(self) -> None:
        """
        v4l2-ctl 명령으로 오토포커스를 끄고 수동 초점값을 설정한다.
        리눅스 환경이 아닌 경우(개발 PC)는 경고만 출력하고 진행한다.
        """
        v4l2_commands = [
            # 오토포커스 비활성화 (0 = 수동)
            ["v4l2-ctl", f"--device=/dev/video{self.device_index}",
             "--set-ctrl=focus_auto=0"],
            # 수동 초점 거리 설정 (0~255 범위, 30 ≈ 15cm 근접 촬영)
            ["v4l2-ctl", f"--device=/dev/video{self.device_index}",
             "--set-ctrl=focus_absolute=30"],
        ]

        for cmd in v4l2_commands:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if result.returncode != 0:
                    logger.warning("[v4l2-ctl] 명령 실패 (무시): %s", result.stderr.strip())
                else:
                    logger.debug("[v4l2-ctl] 성공: %s", " ".join(cmd[2:]))
            except FileNotFoundError:
                # v4l2-ctl이 설치되지 않은 환경(macOS, Windows)에서는 건너뜀
                logger.warning("[v4l2-ctl] 명령을 찾을 수 없습니다. 개발 환경으로 간주하고 건너뜁니다.")
                break
            except subprocess.TimeoutExpired:
                logger.warning("[v4l2-ctl] 명령 타임아웃")

    # ── 이미지 캡처 ───────────────────────────────────────────────────────────

    def capture(self) -> np.ndarray:
        """
        웹캠에서 프레임을 캡처하여 numpy 배열(BGR)로 반환한다.

        버퍼 플러시: 연속 read()를 3회 실행한 뒤 마지막 프레임을 사용하여
        버퍼에 쌓인 오래된 프레임을 버린다.

        Returns:
            np.ndarray: BGR 형식의 이미지 배열 (H, W, 3)

        Raises:
            RuntimeError: 카메라가 열리지 않았거나 프레임 읽기 실패 시
        """
        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError("카메라가 초기화되지 않았습니다. open()을 먼저 호출하세요.")

        # 버퍼에 쌓인 이전 프레임 제거 (3프레임 버퍼 플러시)
        for _ in range(3):
            self._cap.grab()

        ret, frame = self._cap.read()
        if not ret or frame is None:
            raise RuntimeError("프레임을 읽을 수 없습니다. 카메라 연결을 확인하세요.")

        logger.debug("[카메라] 캡처 완료: shape=%s", frame.shape)
        return frame

    def capture_and_save(self, save_dir: str = "captures") -> tuple[np.ndarray, str]:
        """
        프레임을 캡처하고 타임스탬프 파일명으로 디스크에 저장한다.

        Returns:
            (frame, 저장된 파일 경로) 튜플
        """
        frame = self.capture()

        # 저장 디렉토리가 없으면 생성
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        # 파일명: captures/20260331_143000_123456.jpg
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_path = str(Path(save_dir) / f"{timestamp}.jpg")

        # JPEG 품질 95로 저장 (품질 ↔ 파일 크기 균형)
        cv2.imwrite(file_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        logger.info("[카메라] 이미지 저장: %s", file_path)

        return frame, file_path

    def preview(self, window_name: str = "PCB Inspection Preview") -> None:
        """
        OpenCV GUI 창으로 실시간 프리뷰를 띄운다.
        'q' 키를 누르면 종료된다.

        개발 환경에서 카메라 초점·위치를 조정할 때 사용.
        """
        if self._cap is None:
            self.open()

        logger.info("[프리뷰] 시작. 'q' 키로 종료.")
        while True:
            ret, frame = self._cap.read()
            if not ret:
                break

            # 화면에 안내 텍스트 오버레이
            cv2.putText(
                frame, "Press 'q' to quit",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2
            )
            cv2.imshow(window_name, frame)

            # 1ms 대기, 'q' 입력 시 루프 종료
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cv2.destroyAllWindows()
        logger.info("[프리뷰] 종료.")

    # ── 자원 해제 ─────────────────────────────────────────────────────────────

    def release(self) -> None:
        """VideoCapture 자원을 해제한다."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("[카메라] 해제 완료.")

    # ── 컨텍스트 매니저 지원 ─────────────────────────────────────────────────

    def __enter__(self) -> "CameraCapture":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
