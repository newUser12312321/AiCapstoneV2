"""
PCB_IMG 원본들을 피듀셜 기준으로 deskew하여 새 폴더에 저장한다.

기본 경로:
  입력:  <repo>/PCB_IMG
  출력:  <repo>/PCB_IMG_deskew

사용 예:
  cd edge
  python tools/batch_deskew_from_fiducial.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import cv2

_EDGE = Path(__file__).resolve().parent.parent
_ROOT = _EDGE.parent
if str(_EDGE) not in sys.path:
    sys.path.insert(0, str(_EDGE))

from config.settings import settings
from inference.alignment import compute_alignment, deskew_image_by_fiducial_angle
from inference.yolo_detector import YoloDetector

LOG = logging.getLogger("batch_deskew")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="피듀셜 기준 배치 deskew 생성기")
    ap.add_argument(
        "--input-dir",
        type=Path,
        default=_ROOT / "PCB_IMG",
        help="원본 이미지 폴더 (기본: <repo>/PCB_IMG)",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=_ROOT / "PCB_IMG_deskew",
        help="deskew 이미지 출력 폴더 (기본: <repo>/PCB_IMG_deskew)",
    )
    ap.add_argument(
        "--weights",
        type=str,
        default=settings.YOLO_WEIGHTS_PATH,
        help="피듀셜 검출에 사용할 가중치 경로 (기본: settings.YOLO_WEIGHTS_PATH)",
    )
    ap.add_argument(
        "--conf",
        type=float,
        default=settings.effective_fiducial_confidence(),
        help="피듀셜 신뢰도 임계값 (기본: settings effective fiducial conf)",
    )
    ap.add_argument(
        "--max-angle",
        type=float,
        default=settings.MAX_DESKEW_ANGLE_DEG,
        help="허용 가능한 최대 기울기(°) (기본: settings.MAX_DESKEW_ANGLE_DEG)",
    )
    return ap.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()

    in_dir = args.input_dir.expanduser().resolve()
    out_dir = args.output_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_dir.exists():
        raise SystemExit(f"입력 폴더가 없습니다: {in_dir}")

    image_files = [
        p
        for p in sorted(in_dir.iterdir())
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    ]
    if not image_files:
        raise SystemExit(f"입력 폴더에 이미지가 없습니다: {in_dir}")

    det = YoloDetector(weights_path=args.weights, confidence_threshold=float(args.conf))
    det.load()

    ok_count = 0
    fail_count = 0
    fail_lines: list[str] = []

    LOG.info("입력: %s (%d장)", in_dir, len(image_files))
    LOG.info("출력: %s", out_dir)

    for img_path in image_files:
        img = cv2.imread(str(img_path))
        if img is None:
            fail_count += 1
            fail_lines.append(f"{img_path.name}\tdecode_failed")
            continue

        try:
            fiducials, _ = det.detect_fiducials(img)
            alignment = compute_alignment(fiducials, max_deskew_deg=float(args.max_angle))
            if not alignment.is_aligned or alignment.fiducial1 is None or alignment.fiducial2 is None:
                fail_count += 1
                fail_lines.append(f"{img_path.name}\tfiducial_not_aligned_or_missing")
                continue

            rotated, _ = deskew_image_by_fiducial_angle(img, alignment)
            out_path = out_dir / img_path.name
            cv2.imwrite(str(out_path), rotated, [cv2.IMWRITE_JPEG_QUALITY, 95])
            ok_count += 1
        except Exception as e:  # noqa: BLE001
            fail_count += 1
            fail_lines.append(f"{img_path.name}\terror:{e}")

    report = out_dir / "_deskew_report.txt"
    report.write_text(
        "\n".join(
            [
                f"input_dir: {in_dir}",
                f"output_dir: {out_dir}",
                f"weights: {args.weights}",
                f"conf: {args.conf}",
                f"max_angle: {args.max_angle}",
                f"total: {len(image_files)}",
                f"success: {ok_count}",
                f"failed: {fail_count}",
                "",
                "# failed items",
                *fail_lines,
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    LOG.info("완료: 성공 %d장 / 실패 %d장", ok_count, fail_count)
    LOG.info("리포트: %s", report)


if __name__ == "__main__":
    main()

