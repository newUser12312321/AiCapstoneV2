from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

import yaml


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    (path / "images" / "train").mkdir(parents=True, exist_ok=True)
    (path / "images" / "val").mkdir(parents=True, exist_ok=True)
    (path / "labels" / "train").mkdir(parents=True, exist_ok=True)
    (path / "labels" / "val").mkdir(parents=True, exist_ok=True)


def collect_pairs(images_dir: Path, labels_dir: Path) -> list[tuple[Path, Path]]:
    pairs = []
    for img in sorted(images_dir.glob("*")):
        if not img.is_file() or img.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        lbl = labels_dir / f"{img.stem}.txt"
        if lbl.exists():
            pairs.append((img, lbl))
    return pairs


def remap_synthetic_label(src: Path, dst: Path) -> bool:
    # defect_simulator class ids:
    # 0 trace_open, 1 metal_damage, 2 pinhole, 3 short
    # merged class ids:
    # 0 FIDUCIAL, 1 TRACE_OPEN, 2 METAL_DAMAGE
    kept = []
    for line in src.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        try:
            cid = int(parts[0])
            coords = parts[1:]
        except ValueError:
            continue
        if cid == 0:
            new_cid = 1
        elif cid == 1:
            new_cid = 2
        else:
            continue
        kept.append(" ".join([str(new_cid), *coords]))

    if not kept:
        return False
    dst.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return True


def split_copy_pairs(pairs: list[tuple[Path, Path]], out_dir: Path, val_ratio: float, seed: int) -> None:
    random.seed(seed)
    random.shuffle(pairs)
    val_count = int(len(pairs) * val_ratio)
    val_pairs = pairs[:val_count]
    train_pairs = pairs[val_count:]

    for subset, subset_pairs in [("train", train_pairs), ("val", val_pairs)]:
        for img, lbl in subset_pairs:
            shutil.copy2(img, out_dir / "images" / subset / img.name)
            shutil.copy2(lbl, out_dir / "labels" / subset / lbl.name)


def write_yaml(out_dir: Path) -> None:
    data = {
        "path": ".",
        "train": "images/train",
        "val": "images/val",
        "nc": 3,
        "names": {
            0: "FIDUCIAL",
            1: "TRACE_OPEN",
            2: "METAL_DAMAGE",
        },
    }
    (out_dir / "data.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build merged YOLO dataset from prepared + synthetic.")
    parser.add_argument("--prepared-dir", default="prepared_dataset")
    parser.add_argument("--synthetic-dir", default="synthetic_dataset")
    parser.add_argument("--out-dir", default="merged_dataset")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    root = Path.cwd()
    prepared = (root / args.prepared_dir).resolve()
    synthetic = (root / args.synthetic_dir).resolve()
    out_dir = (root / args.out_dir).resolve()

    prepared_img_train = prepared / "images" / "train"
    prepared_lbl_train = prepared / "labels" / "train"
    prepared_img_val = prepared / "images" / "val"
    prepared_lbl_val = prepared / "labels" / "val"
    synthetic_img = synthetic / "images"
    synthetic_lbl = synthetic / "labels"

    for p in [prepared_img_train, prepared_lbl_train, prepared_img_val, prepared_lbl_val, synthetic_img, synthetic_lbl]:
        if not p.exists():
            raise FileNotFoundError(f"Required folder not found: {p}")

    reset_dir(out_dir)

    # 1) Copy prepared dataset as-is (FIDUCIAL class 0)
    prepared_pairs = collect_pairs(prepared_img_train, prepared_lbl_train) + collect_pairs(prepared_img_val, prepared_lbl_val)
    for img, lbl in prepared_pairs:
        # split later together with synthetic for global 8:2 split
        pass

    temp_dir = out_dir / "_temp_all"
    temp_img = temp_dir / "images"
    temp_lbl = temp_dir / "labels"
    temp_img.mkdir(parents=True, exist_ok=True)
    temp_lbl.mkdir(parents=True, exist_ok=True)

    for img, lbl in prepared_pairs:
        shutil.copy2(img, temp_img / img.name)
        shutil.copy2(lbl, temp_lbl / lbl.name)

    # 2) Add synthetic with class remap and filtering
    synthetic_kept = 0
    synthetic_dropped = 0
    for img in sorted(synthetic_img.glob("*")):
        if not img.is_file() or img.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        src_lbl = synthetic_lbl / f"{img.stem}.txt"
        if not src_lbl.exists():
            continue
        dst_lbl = temp_lbl / f"{img.stem}.txt"
        ok = remap_synthetic_label(src_lbl, dst_lbl)
        if not ok:
            synthetic_dropped += 1
            continue
        shutil.copy2(img, temp_img / img.name)
        synthetic_kept += 1

    # 3) Global split
    all_pairs = collect_pairs(temp_img, temp_lbl)
    split_copy_pairs(all_pairs, out_dir, args.val_ratio, args.seed)
    write_yaml(out_dir)

    # cleanup temp
    shutil.rmtree(temp_dir, ignore_errors=True)

    train_count = len(list((out_dir / "images" / "train").glob("*")))
    val_count = len(list((out_dir / "images" / "val").glob("*")))
    report = [
        f"prepared_pairs: {len(prepared_pairs)}",
        f"synthetic_kept_trace_metal: {synthetic_kept}",
        f"synthetic_dropped_other_classes: {synthetic_dropped}",
        f"total_pairs: {len(all_pairs)}",
        f"train_count: {train_count}",
        f"val_count: {val_count}",
    ]
    (out_dir / "merge_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print(f"Output: {out_dir}")


if __name__ == "__main__":
    main()
