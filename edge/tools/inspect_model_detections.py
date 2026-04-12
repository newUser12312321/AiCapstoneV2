"""
가중치(.pt)별로 같은 이미지에 대해 Ultralytics raw 탐지를 출력한다.
피듀셜이 0으로만 나올 때: 모델이 진짜로 아무것도 안 내는지 / 클래스 이름이 뭔지 확인.

  cd edge && source .venv/bin/activate
  python tools/inspect_model_detections.py captures/xxx.jpg weights/best.pt weights/best_jinho.pt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_EDGE = Path(__file__).resolve().parent.parent
if str(_EDGE) not in sys.path:
    sys.path.insert(0, str(_EDGE))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("image", help="edge/captures 기준 또는 절대 경로 JPG/PNG")
    p.add_argument("weights", nargs="+", help="weights/*.pt 여러 개")
    p.add_argument("--conf", type=float, default=0.1, help="낮출수록 더 많이 잡힘 (기본 0.1)")
    args = p.parse_args()

    img = Path(args.image)
    if not img.is_file():
        img = _EDGE / "captures" / args.image
    if not img.is_file():
        raise SystemExit(f"이미지 없음: {args.image}")

    from ultralytics import YOLO

    for w in args.weights:
        wp = Path(w)
        if not wp.is_file():
            wp = _EDGE / "weights" / w
        if not wp.is_file():
            print(f"--- skip (없음): {w}")
            continue

        m = YOLO(str(wp))
        print("=" * 60)
        print(f"FILE: {wp.name}")
        print(f"names: {dict(m.names) if m.names else m.names}")
        r = m.predict(str(img), conf=args.conf, verbose=False)[0]
        boxes = r.boxes
        n = len(boxes) if boxes is not None else 0
        print(f"탐지 수 (conf>={args.conf}): {n}")
        if boxes is None or n == 0:
            continue
        for i in range(n):
            cls = int(boxes.cls[i])
            cf = float(boxes.conf[i])
            name = m.names.get(cls, f"cls_{cls}")
            print(f"  [{i}] class={cls} name={name!r} conf={cf:.4f}")


if __name__ == "__main__":
    main()
