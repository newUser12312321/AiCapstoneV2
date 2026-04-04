"""
Evaluate multiple fiducial YOLO models and rank them.

Usage example:
  python edge/tools/eval_fiducial_models.py \
    --models-dir ./model_candidates \
    --data-yaml ./prepared_dataset/data.yaml \
    --image-dir ./prepared_dataset/images/val \
    --conf 0.25
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import yaml
from ultralytics import YOLO


def load_dataset_paths(data_yaml: Path) -> tuple[Path, Path]:
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML format: {data_yaml}")

    base = Path(str(data.get("path", ".")))
    if not base.is_absolute():
        base = (data_yaml.parent / base).resolve()

    val_rel = data.get("val")
    if not val_rel:
        raise ValueError("data.yaml must include 'val' path")

    val_path = (base / str(val_rel)).resolve()
    return base, val_path


def collect_images(image_dir: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = [p for p in sorted(image_dir.glob("*")) if p.suffix.lower() in exts]
    if not images:
        raise ValueError(f"No images found in: {image_dir}")
    return images


def safe_metric(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def fiducial_detect_success_rate(model: YOLO, images: list[Path], conf: float) -> float:
    """
    Success rule:
    - Count image as success when model detects >= 2 boxes of class 0 (FIDUCIAL)
    """
    success = 0
    total = len(images)

    for img in images:
        results = model.predict(source=str(img), conf=conf, verbose=False)
        if not results:
            continue

        r = results[0]
        if r.boxes is None or r.boxes.cls is None:
            continue

        cls_list = [int(c) for c in r.boxes.cls.tolist()]
        fid_count = sum(1 for c in cls_list if c == 0)
        if fid_count >= 2:
            success += 1

    return success / total if total else 0.0


def evaluate_model(model_path: Path, data_yaml: Path, images: list[Path], conf: float) -> dict[str, Any]:
    model = YOLO(str(model_path))

    # Standard validation metrics (mAP/precision/recall)
    metrics = model.val(data=str(data_yaml), conf=conf, verbose=False)
    map50 = safe_metric(metrics.box.map50)
    map5095 = safe_metric(metrics.box.map)
    precision = safe_metric(metrics.box.mp)
    recall = safe_metric(metrics.box.mr)

    # Operational metric for this project (>=2 fiducials detected)
    detect_rate = fiducial_detect_success_rate(model, images, conf)

    return {
        "model": model_path.name,
        "map50": round(map50, 4),
        "map50_95": round(map5095, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "fiducial_detect_success_rate": round(detect_rate, 4),
    }


def print_table(rows: list[dict[str, Any]]) -> None:
    headers = [
        "rank",
        "model",
        "fiducial_detect_success_rate",
        "map50",
        "recall",
        "precision",
        "map50_95",
    ]
    print(" | ".join(headers))
    print("-" * 100)
    for i, r in enumerate(rows, start=1):
        print(
            f"{i} | {r['model']} | {r['fiducial_detect_success_rate']:.4f} | "
            f"{r['map50']:.4f} | {r['recall']:.4f} | {r['precision']:.4f} | {r['map50_95']:.4f}"
        )


def write_csv(rows: list[dict[str, Any]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "rank",
        "model",
        "fiducial_detect_success_rate",
        "map50",
        "recall",
        "precision",
        "map50_95",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, r in enumerate(rows, start=1):
            row = dict(r)
            row["rank"] = i
            w.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate and rank fiducial models")
    parser.add_argument("--models-dir", required=True, help="Directory containing candidate .pt files")
    parser.add_argument("--data-yaml", required=True, help="Dataset YAML path")
    parser.add_argument(
        "--image-dir",
        default="",
        help="Image directory for operational success-rate metric (default: val path from data.yaml)",
    )
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument(
        "--out-csv",
        default="edge/tools/fiducial_eval_report.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()

    models_dir = Path(args.models_dir).resolve()
    data_yaml = Path(args.data_yaml).resolve()
    out_csv = Path(args.out_csv).resolve()

    if not models_dir.exists():
        raise FileNotFoundError(f"models directory not found: {models_dir}")
    if not data_yaml.exists():
        raise FileNotFoundError(f"data.yaml not found: {data_yaml}")

    _, val_path = load_dataset_paths(data_yaml)
    image_dir = Path(args.image_dir).resolve() if args.image_dir else val_path
    images = collect_images(image_dir)

    model_files = sorted(models_dir.glob("*.pt"))
    if not model_files:
        raise ValueError(f"No .pt files found in: {models_dir}")

    results = []
    for m in model_files:
        print(f"[eval] {m.name}")
        results.append(evaluate_model(m, data_yaml, images, conf=args.conf))

    # Rank priority: operational detect success > map50 > recall
    results.sort(
        key=lambda r: (r["fiducial_detect_success_rate"], r["map50"], r["recall"]),
        reverse=True,
    )

    print("\n=== Fiducial Model Ranking ===")
    print_table(results)
    write_csv(results, out_csv)
    print(f"\nCSV report saved: {out_csv}")


if __name__ == "__main__":
    main()

