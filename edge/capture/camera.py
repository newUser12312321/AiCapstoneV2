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
import threading
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

import cv2
import numpy as np

from config.settings import settings

# settings.py와 무관 — 항상 edge/captures (구버전 Pi 설정 파일과 충돌 없음)
CAPTURES_DIR = Path(__file__).resolve().parent.parent / "captures"

logger = logging.getLogger(__name__)


def _try_open_video_index(index: int) -> Optional[cv2.VideoCapture]:
    """지정 인덱스(및 흔한 백엔드)로 VideoCapture 시도. 성공 시 열린 캡처만 반환."""
    dev_path = f"/dev/video{index}"
    factories: list[tuple[str, Callable[[], cv2.VideoCapture]]] = [
        ("CAP_V4L2+index", lambda i=index: cv2.VideoCapture(i, cv2.CAP_V4L2)),
        ("default+index", lambda i=index: cv2.VideoCapture(i)),
        ("CAP_V4L2+path", lambda p=dev_path: cv2.VideoCapture(p, cv2.CAP_V4L2)),
        ("default+path", lambda p=dev_path: cv2.VideoCapture(p)),
    ]
    for _label, factory in factories:
        cap = factory()
        if cap.isOpened():
            return cap
        cap.release()
    return None


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
        self._focus_lock = threading.Lock()

    # ── 카메라 초기화 ──────────────────────────────────────────────────────────

    def open(self) -> None:
        """
        카메라를 열고 해상도를 설정한다.

        초점은 .env의 CAMERA_FOCUS_AUTO / CAMERA_FOCUS_ABSOLUTE 로 제어한다.
        """
        requested = self.device_index
        logger.info("[카메라] 장치 %d 열기 시도 (%dx%d)", requested, self.width, self.height)

        # Pi 5 등에서는 /dev/video0 이 없고 USB 웹캠이 video1·2 인 경우가 많음.
        # pispbe·libcamera 노드는 video10+ 이라, USB 우선(1,2) 후 (10,11,12) 순으로 시도.
        try_order: list[int] = [requested]
        for x in (1, 2, 10, 11, 12, 0):
            if x not in try_order:
                try_order.append(x)

        self._cap = None
        for idx in try_order:
            cap = _try_open_video_index(idx)
            if cap is not None:
                self._cap = cap
                self.device_index = idx
                if idx != requested:
                    logger.warning(
                        "[카메라] .env 는 %d 였으나 장치 %d (/dev/video%d) 에서 열었습니다.",
                        requested,
                        idx,
                        idx,
                    )
                else:
                    logger.info("[카메라] 장치 %d 열기 성공", idx)
                break

        if self._cap is None or not self._cap.isOpened():
            dev_path = f"/dev/video{requested}"
            raise RuntimeError(
                f"카메라 장치 {requested} ({dev_path})를 열 수 없습니다. "
                "USB/카메라 모듈 연결, `sudo fuser -v /dev/video*`, "
                "`groups`(video 포함 여부), `v4l2-ctl --list-devices` 로 확인하세요. "
                "모델 비교만 할 때는 캡처 이미지(edge/captures)를 지정하면 카메라 없이 가능합니다."
            )

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

        # 초점: C922 등은 focus_auto 대신 focus_automatic_continuous 사용 · 권한은 video 그룹
        self._apply_focus_after_open()

    def _run_v4l2(self, dev: str, ctrl: str, value: str) -> bool:
        """v4l2-ctl 한 줄 실행. 성공 여부만 반환."""
        cmd = ["v4l2-ctl", f"--device={dev}", f"--set-ctrl={ctrl}={value}"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                logger.debug("[v4l2-ctl] OK %s=%s", ctrl, value)
                return True
            logger.debug("[v4l2-ctl] skip %s=%s: %s", ctrl, value, result.stderr.strip())
        except FileNotFoundError:
            return False
        except subprocess.TimeoutExpired:
            logger.warning("[v4l2-ctl] timeout %s", ctrl)
        return False

    def _apply_focus_after_open(self) -> None:
        """
        장치 오픈 후 초점 적용.

        Logitech C922 등: `focus_auto` 가 없고 `focus_automatic_continuous` 만 있는 경우가 많음.
        USB를 뺐다 꽂으면 렌즈·펌웨어가 리셋되어 첫 수동 초점 명령이 무시되는 경우가 있어,
        (옵션) 잠깐 연속 AF로 맞춘 뒤 고정하거나, 동일 값을 지연 재적용한다.

        Permission denied 시: `sudo usermod -aG video pi` 후 재로그인.
        """
        dev = f"/dev/video{self.device_index}"

        if settings.CAMERA_FOCUS_AUTO:
            logger.info("[카메라] 오토포커스 시도 (CAMERA_FOCUS_AUTO=true)")
            # 구 UVC / 일부 드라이버
            self._run_v4l2(dev, "focus_auto", "1")
            # C922·BRIO 계열에서 흔함 (0=수동 1=연속 AF)
            self._run_v4l2(dev, "focus_automatic_continuous", "1")
            self._opencv_set_autofocus(True)
        else:
            fa = settings.CAMERA_FOCUS_ABSOLUTE
            logger.info("[카메라] 수동 초점 시도 (focus_absolute=%d)", fa)
            self._run_v4l2(dev, "focus_auto", "0")
            self._run_v4l2(dev, "focus_automatic_continuous", "0")
            time.sleep(0.05)
            self._opencv_set_autofocus(False)

            warmup_ms = settings.CAMERA_FOCUS_POST_PLUG_AF_MS
            if warmup_ms > 0:
                logger.info(
                    "[카메라] POST_PLUG_AF %dms — 연속 AF 후 수동값 고정 (USB 재연결 후 흐림 완화)",
                    warmup_ms,
                )
                self._run_v4l2(dev, "focus_automatic_continuous", "1")
                self._opencv_set_autofocus(True)
                deadline = time.perf_counter() + (warmup_ms / 1000.0)
                while time.perf_counter() < deadline:
                    self._cap.grab()
                self._run_v4l2(dev, "focus_automatic_continuous", "0")
                self._run_v4l2(dev, "focus_auto", "0")
                self._opencv_set_autofocus(False)
                time.sleep(0.05)

            self._run_v4l2(dev, "focus_absolute", str(fa))
            self._opencv_set_focus_absolute(fa)

            if settings.CAMERA_FOCUS_MANUAL_DOUBLE_APPLY:
                time.sleep(settings.CAMERA_FOCUS_MANUAL_REAPPLY_DELAY_SEC)
                self._run_v4l2(dev, "focus_absolute", str(fa))
                self._opencv_set_focus_absolute(fa)
                logger.debug("[카메라] focus_absolute 재적용 완료")

        # AF/수동 적용 후 센서·렌즈 안정화 (프레임 버림)
        settle = 25 if settings.CAMERA_FOCUS_AUTO else 12
        for _ in range(settle):
            self._cap.grab()
        time.sleep(1.2 if settings.CAMERA_FOCUS_AUTO else 0.5)

    def _opencv_set_autofocus(self, enabled: bool) -> None:
        """OpenCV 속성으로 AF 보조 (카메라·드라이버가 지원할 때만 동작)."""
        if self._cap is None:
            return
        prop = getattr(cv2, "CAP_PROP_AUTOFOCUS", None)
        if prop is None:
            return
        try:
            self._cap.set(prop, 1.0 if enabled else 0.0)
        except Exception as e:
            logger.debug("[카메라] CAP_PROP_AUTOFOCUS 설정 생략: %s", e)

    def _opencv_set_focus_absolute(self, value: int) -> None:
        prop = getattr(cv2, "CAP_PROP_FOCUS", None)
        if prop is None or self._cap is None:
            return
        try:
            self._cap.set(prop, float(value))
            logger.debug("[카메라] CAP_PROP_FOCUS=%d", value)
        except Exception as e:
            logger.debug("[카메라] CAP_PROP_FOCUS 설정 생략: %s", e)

    def get_focus_state(self) -> dict[str, int | bool]:
        """
        현재 초점 상태를 반환한다.

        Returns:
            {
              "auto": 오토포커스 사용 여부,
              "value": 수동 초점 값(0~255)
            }
        """
        auto = settings.CAMERA_FOCUS_AUTO
        value = int(settings.CAMERA_FOCUS_ABSOLUTE)
        if self._cap is not None:
            auto_prop = getattr(cv2, "CAP_PROP_AUTOFOCUS", None)
            focus_prop = getattr(cv2, "CAP_PROP_FOCUS", None)
            try:
                if auto_prop is not None:
                    auto = bool(self._cap.get(auto_prop) >= 0.5)
            except Exception:
                pass
            try:
                if focus_prop is not None:
                    read_focus = int(round(self._cap.get(focus_prop)))
                    if 0 <= read_focus <= 255:
                        value = read_focus
            except Exception:
                pass
        return {"auto": auto, "value": value}

    def set_focus_runtime(self, *, auto: bool, value: int) -> dict[str, int | bool]:
        """
        실행 중 카메라 초점을 변경한다.
        """
        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError("카메라가 초기화되지 않았습니다.")

        clamped = max(0, min(255, int(value)))
        dev = f"/dev/video{self.device_index}"
        with self._focus_lock:
            if auto:
                self._run_v4l2(dev, "focus_auto", "1")
                self._run_v4l2(dev, "focus_automatic_continuous", "1")
                self._opencv_set_autofocus(True)
                logger.info("[카메라] 런타임 오토포커스 ON")
                return {"auto": True, "value": clamped}

            self._run_v4l2(dev, "focus_auto", "0")
            self._run_v4l2(dev, "focus_automatic_continuous", "0")
            self._opencv_set_autofocus(False)
            time.sleep(0.03)
            self._run_v4l2(dev, "focus_absolute", str(clamped))
            self._opencv_set_focus_absolute(clamped)
            logger.info("[카메라] 런타임 수동 초점 적용: %d", clamped)
            return {"auto": False, "value": clamped}

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

    def capture_and_save(self, save_dir: str | None = None) -> tuple[np.ndarray, str]:
        """
        프레임을 캡처하고 타임스탬프 파일명으로 디스크에 저장한다.

        Returns:
            (frame, 저장된 파일 경로) 튜플
        """
        frame = self.capture()

        base = Path(save_dir) if save_dir is not None else CAPTURES_DIR
        base.mkdir(parents=True, exist_ok=True)

        # 파일명: captures/20260331_143000_123456.jpg
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_path = str(base / f"{timestamp}.jpg")

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
