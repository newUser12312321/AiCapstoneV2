"""
데이터셋 수집 스크립트

웹캠 화면을 실시간으로 보면서 스페이스바로 이미지를 저장합니다.
라즈베리파이에 SSH로 접속한 뒤 실행하면 됩니다.

실행 방법:
    cd ~/inspection/edge
    source .venv/bin/activate
    python capture/collect_dataset.py

    # 결함 이미지 저장 폴더를 바꾸려면:
    python capture/collect_dataset.py --label defect --output dataset/defect_images

조작법:
    스페이스바   → 현재 화면 저장
    q           → 종료
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

from config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# 저장 시 화면에 잠깐 표시할 플래시 지속 시간 (초)
FLASH_DURATION = 0.3


def run_collector(
    label: str = "good",
    output_dir: str = None,
    device_index: int = None,
    width: int = None,
    height: int = None,
    preview_scale: float = 0.5,
):
    """
    웹캠 화면을 보면서 스페이스바로 이미지를 저장하는 메인 루프.

    Args:
        label:         저장 폴더 구분자 ('good' 또는 'defect')
        output_dir:    이미지 저장 경로 (None이면 dataset/{label}/)
        device_index:  카메라 장치 번호 (None이면 settings 값 사용)
        width:         캡처 해상도 가로 (None이면 settings 값 사용)
        height:        캡처 해상도 세로 (None이면 settings 값 사용)
        preview_scale: 프리뷰 창 크기 비율 (1.0 = 원본, 0.5 = 절반)
    """
    # 설정값 결정
    dev_idx = device_index if device_index is not None else settings.CAMERA_DEVICE_INDEX
    cap_w   = width  if width  is not None else settings.CAMERA_WIDTH
    cap_h   = height if height is not None else settings.CAMERA_HEIGHT

    # 저장 폴더 결정 및 생성
    save_dir = Path(output_dir) if output_dir else Path(f"dataset/{label}")
    save_dir.mkdir(parents=True, exist_ok=True)

    # 카메라 열기
    logger.info("[수집기] 카메라 %d 열기 중...", dev_idx)
    cap = cv2.VideoCapture(dev_idx, cv2.CAP_V4L2)
    if not cap.isOpened():
        # CAP_V4L2 실패 시 기본 백엔드로 재시도 (macOS/Windows 개발 환경)
        cap = cv2.VideoCapture(dev_idx)
    if not cap.isOpened():
        logger.error("❌ 카메라를 열 수 없습니다. (device_index=%d)", dev_idx)
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  cap_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cap_h)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info("[수집기] 해상도: %dx%d", actual_w, actual_h)
    logger.info("[수집기] 저장 폴더: %s", save_dir.resolve())
    logger.info("─" * 50)
    logger.info("  스페이스바 → 사진 저장")
    logger.info("  q          → 종료")
    logger.info("─" * 50)

    # 카메라 노출 안정화 대기
    time.sleep(1.0)

    saved_count = 0
    flash_until = 0.0   # 저장 플래시 효과 종료 시각

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            logger.warning("프레임 읽기 실패 — 재시도 중...")
            continue

        now = time.time()

        # ── 프리뷰 화면 구성 ─────────────────────────────────────────────────
        preview_w = int(actual_w * preview_scale)
        preview_h = int(actual_h * preview_scale)
        display = cv2.resize(frame, (preview_w, preview_h))

        # 저장 플래시 효과 (저장 직후 잠깐 밝게 반전)
        if now < flash_until:
            display = cv2.bitwise_not(display)

        # 안내 텍스트 오버레이
        _draw_ui(display, saved_count, label, preview_w, preview_h)

        cv2.imshow("Dataset Collector — Press SPACE to save, Q to quit", display)

        # ── 키 입력 처리 ─────────────────────────────────────────────────────
        key = cv2.waitKey(30) & 0xFF

        if key == ord("q") or key == 27:   # q 또는 ESC → 종료
            break

        elif key == ord(" "):              # 스페이스바 → 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename  = f"{label}_{timestamp}.jpg"
            save_path = save_dir / filename

            cv2.imwrite(str(save_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            saved_count += 1
            flash_until = now + FLASH_DURATION

            logger.info("✅ [%3d장] 저장: %s", saved_count, filename)

    # ── 종료 처리 ────────────────────────────────────────────────────────────
    cap.release()
    cv2.destroyAllWindows()
    logger.info("─" * 50)
    logger.info("수집 완료: 총 %d장 저장 → %s", saved_count, save_dir.resolve())


def _draw_ui(img, count: int, label: str, w: int, h: int):
    """프리뷰 화면에 안내 텍스트와 저장 카운터를 표시합니다."""
    # 반투명 상단 바 배경
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, 55), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.45, img, 0.55, 0, img)

    # 레이블 색상 (정상=초록, 결함=빨강)
    label_color = (50, 220, 50) if label == "good" else (50, 50, 220)
    label_text  = f"MODE: {label.upper()}"
    count_text  = f"SAVED: {count}"

    cv2.putText(img, label_text, (12, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, label_color, 2, cv2.LINE_AA)
    cv2.putText(img, count_text, (w - 180, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)

    # 하단 안내 텍스트
    cv2.putText(img, "SPACE: Save  |  Q: Quit",
                (12, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1, cv2.LINE_AA)

    # 화면 중앙 십자선 (구도 잡기용)
    cx, cy = w // 2, h // 2
    cv2.line(img, (cx - 20, cy), (cx + 20, cy), (0, 200, 200), 1)
    cv2.line(img, (cx, cy - 20), (cx, cy + 20), (0, 200, 200), 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="웹캠 화면을 보면서 데이터셋 이미지를 수집합니다."
    )
    parser.add_argument(
        "--label", default="good", choices=["good", "defect"],
        help="저장 레이블 (good: 정상 기판 / defect: 결함 기판)"
    )
    parser.add_argument(
        "--output", default=None,
        help="저장 폴더 경로 (기본값: dataset/good 또는 dataset/defect)"
    )
    parser.add_argument(
        "--device", type=int, default=None,
        help="카메라 장치 번호 (기본값: settings의 CAMERA_DEVICE_INDEX)"
    )
    parser.add_argument(
        "--scale", type=float, default=0.5,
        help="프리뷰 창 크기 비율 (기본값: 0.5 = 절반 크기)"
    )
    args = parser.parse_args()

    run_collector(
        label        = args.label,
        output_dir   = args.output,
        device_index = args.device,
        preview_scale= args.scale,
    )
