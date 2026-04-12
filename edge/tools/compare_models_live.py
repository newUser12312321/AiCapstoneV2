"""
여러 YOLO 가중치(.pt)를 동일한 실제 촬영(또는 동일 이미지)으로 비교한다.

구현은 inference.model_compare 를 사용한다.

실행 예 (edge 디렉터리):

  python tools/compare_models_live.py \\
    --weights weights/alice.pt --weights weights/bob.pt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_EDGE_ROOT = Path(__file__).resolve().parent.parent
if str(_EDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_EDGE_ROOT))

from config.settings import settings  # noqa: E402
from inference.model_compare import compare_models  # noqa: E402


def _print_table(rows: list) -> None:
    headers = [
        "가중치",
        "피듀셜수",
        "정렬OK",
        "각도°",
        "결함수",
        "결함평균conf",
        "추론ms",
    ]
    print(" | ".join(headers))
    print("-" * 96)
    for r in rows:
        mean_c = r["defect_conf_mean"]
        mean_s = f"{mean_c:.3f}" if mean_c is not None else "-"
        label = r.get("weightsLabel") or Path(r["weights"]).name
        if len(label) > 36:
            label = label[:33] + "..."
        print(
            f"{label} | "
            f"{r['fiducial_count']} | "
            f"{'Y' if r['aligned'] else 'N'} | "
            f"{r['angle_error_deg']:.2f} | "
            f"{r['defect_count']} | "
            f"{mean_s} | "
            f"{r['infer_ms_total']}"
        )


def main() -> None:
    p = argparse.ArgumentParser(
        description="동일 촬영으로 여러 .pt 비교",
        epilog="정확도(mAP) 순위는 라벨 있는 data.yaml 로: yolo val model=X.pt data=...",
    )
    p.add_argument("--weights", action="append", dest="weights_list", required=True)
    p.add_argument("--defect-weights", nargs="*", default=None)
    p.add_argument("--image", default=None)
    p.add_argument("--camera-index", type=int, default=None)
    p.add_argument("--conf", type=float, default=None)
    p.add_argument("--json", dest="json_out")
    args = p.parse_args()

    rows, src = compare_models(
        args.weights_list,
        args.defect_weights,
        args.image,
        args.camera_index,
        args.conf,
    )

    print()
    print("=== 동일 입력 비교 (실제 정확도=mAP 아님, 장면 일관 비교용) ===")
    if src:
        print(f"입력: {src}")
    else:
        idx = args.camera_index if args.camera_index is not None else settings.CAMERA_DEVICE_INDEX
        print(f"입력: 카메라 장치 {idx} 단발 캡처")
    c = args.conf if args.conf is not None else settings.YOLO_CONFIDENCE_THRESHOLD
    print(f"conf={c}, MAX_ANGLE_ERROR_DEG={settings.MAX_ANGLE_ERROR_DEG}")
    print()
    _print_table(rows)
    print()
    print(
        "※ 순위를 ‘정확도’라고 부르려면: 검증용 라벨이 있는 data.yaml 에 대해 "
        "각 .pt 마다 `yolo val model=... data=...` 로 mAP50 등을 비교하세요."
    )

    if args.json_out:
        out = Path(args.json_out)
        out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nJSON 저장: {out.resolve()}")


if __name__ == "__main__":
    main()
