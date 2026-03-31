from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

import yaml


def load_class_names(cvat_yaml_path: Path) -> dict:
    if not cvat_yaml_path.exists():
        return {0: "FIDUCIAL"}
    data = yaml.safe_load(cvat_yaml_path.read_text(encoding="utf-8")) or {}
    names = data.get("names", {})
    if isinstance(names, list):
        return {idx: name for idx, name in enumerate(names)}
    if isinstance(names, dict):
        normalized = {}
        for k, v in names.items():
            try:
                normalized[int(k)] = str(v)
            except (ValueError, TypeError):
                continue
        return normalized or {0: "FIDUCIAL"}
    return {0: "FIDUCIAL"}


def build_image_index(images_dir: Path) -> dict:
    index = {}
    for p in images_dir.iterdir():
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            index[p.stem] = p
    return index


def prepare_dirs(out_dir: Path) -> None:
    for rel in [
        "images/train",
        "images/val",
        "labels/train",
        "labels/val",
    ]:
        (out_dir / rel).mkdir(parents=True, exist_ok=True)


def write_data_yaml(out_dir: Path, names: dict) -> None:
    data = {
        "path": ".",
        "train": "images/train",
        "val": "images/val",
        "nc": len(names),
        "names": names,
    }
    (out_dir / "data.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match CVAT labels with local images and build YOLO train/val dataset."
    )
    parser.add_argument("--images-dir", default="PCB_photo")
    parser.add_argument("--cvat-dir", default="pcb-good-batch-01")
    parser.add_argument("--out-dir", default="prepared_dataset")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    root = Path.cwd()
    images_dir = (root / args.images_dir).resolve()
    cvat_dir = (root / args.cvat_dir).resolve()
    out_dir = (root / args.out_dir).resolve()

    labels_dir = cvat_dir / "labels" / "train"
    cvat_yaml = cvat_dir / "data.yaml"

    if not images_dir.exists():
        raise FileNotFoundError(f"Images folder not found: {images_dir}")
    if not labels_dir.exists():
        raise FileNotFoundError(f"Label folder not found: {labels_dir}")

    prepare_dirs(out_dir)
    names = load_class_names(cvat_yaml)
    image_index = build_image_index(images_dir)
    label_files = sorted(labels_dir.glob("*.txt"))

    matched_stems = []
    missing_images = []

    for label in label_files:
        stem = label.stem
        img = image_index.get(stem)
        if img is None:
            missing_images.append(stem)
            continue
        matched_stems.append(stem)
        shutil.copy2(img, out_dir / "images" / "train" / img.name)
        shutil.copy2(label, out_dir / "labels" / "train" / label.name)

    random.seed(args.seed)
    random.shuffle(matched_stems)
    val_count = int(len(matched_stems) * args.val_ratio)
    val_stems = set(matched_stems[:val_count])

    for stem in val_stems:
        # Move into val split after initial train copy
        for ext in [".jpg", ".jpeg", ".png"]:
            src_img = out_dir / "images" / "train" / f"{stem}{ext}"
            if src_img.exists():
                shutil.move(str(src_img), str(out_dir / "images" / "val" / src_img.name))
                break
        src_lbl = out_dir / "labels" / "train" / f"{stem}.txt"
        if src_lbl.exists():
            shutil.move(str(src_lbl), str(out_dir / "labels" / "val" / src_lbl.name))

    write_data_yaml(out_dir, names)

    source_image_stems = set(image_index.keys())
    label_stems = {p.stem for p in label_files}
    unlabeled_images = sorted(source_image_stems - label_stems)

    report_lines = [
        f"source_images: {len(source_image_stems)}",
        f"source_labels: {len(label_files)}",
        f"matched_pairs: {len(matched_stems)}",
        f"missing_images_for_labels: {len(missing_images)}",
        f"unlabeled_images: {len(unlabeled_images)}",
        f"train_count: {len(list((out_dir / 'images' / 'train').glob('*')))}",
        f"val_count: {len(list((out_dir / 'images' / 'val').glob('*')))}",
        "",
        "[missing_images_for_labels]",
        *missing_images,
        "",
        "[unlabeled_images]",
        *unlabeled_images,
    ]
    (out_dir / "organize_report.txt").write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Done. Output: {out_dir}")
    print(f"Matched pairs: {len(matched_stems)}")
    print(f"Train/Val: {len(list((out_dir / 'images' / 'train').glob('*')))} / {len(list((out_dir / 'images' / 'val').glob('*')))}")
    print(f"Report: {out_dir / 'organize_report.txt'}")


if __name__ == "__main__":
    main()
