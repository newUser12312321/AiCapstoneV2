"""
PCB_V4(CVAT 피듀셜) + defect_simulator 합성 데이터를 하나의 YOLO 학습용 폴더로 합칩니다.

클래스 ID (통합):
  0 fiducial       — CVAT 그대로
  1 trace_open     — 합성 (기존 0 → +1)
  2 metal_damage   — 합성 (기존 1 → +1)
  3 pinhole        — 합성 (기존 2 → +1)
  4 short          — 합성 (기존 3 → +1)

사용 예:
  cd edge
  python tools/merge_yolo_colab_dataset.py ^
    --pcb-v4 ../PCB_V4 ^
    --synthetic ../synthetic_defects ^
    --output ../dataset_yolo_colab

합성만 있는 경우:
  python tools/merge_yolo_colab_dataset.py --pcb-v4 ../PCB_V4 --synthetic ../syn --output ../out --skip-fiducial-if-missing

PCB_V4에 train.txt가 가리키는 이미지는 보통 CVAT_export/data/images/train/ 입니다.
이미지가 없으면 같은 stem의 jpg/png를 pcb_v4 루트 아래에서 재귀 검색합니다.
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path
from typing import Optional


# 통합 클래스 순서 (Ultralytics data.yaml names)
MERGED_NAMES = ["fiducial", "trace_open", "metal_damage", "pinhole", "short"]
SYNTHETIC_CLASS_OFFSET = 1  # 합성 defect_simulator id 0..3 → 1..4


def _find_image_for_stem(pcb_root: Path, stem: str) -> Optional[Path]:
    """CVAT 내보내기 흔한 경로 + 확장자 변종."""
    subdirs = [
        pcb_root / "data" / "images" / "train",
        pcb_root / "images" / "train",
        pcb_root / "images",
        pcb_root / "obj_train_data",
    ]
    exts = [".jpg", ".jpeg", ".png", ".JPG", ".PNG", ".bmp"]
    for sub in subdirs:
        if not sub.is_dir():
            continue
        for ext in exts:
            p = sub / f"{stem}{ext}"
            if p.is_file():
                return p
    # 재귀 검색 (이미지가 다른 하위 폴더에만 있는 경우)
    for ext in exts:
        hits = list(pcb_root.rglob(f"{stem}{ext}"))
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            # data/images/train 우선
            for h in hits:
                if "images" in h.parts:
                    return h
            return hits[0]
    return None


def _read_yolo_label_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _remap_synthetic_label_line(line: str) -> str:
    parts = line.split()
    if len(parts) < 5:
        return line
    cid = int(float(parts[0]))
    new_cid = cid + SYNTHETIC_CLASS_OFFSET
    parts[0] = str(new_cid)
    return " ".join(parts)


def _collect_fiducial_pairs(pcb_v4: Path) -> list[tuple[Path, Path]]:
    """(image_path, label_path) 목록. 라벨은 labels/train 기준."""
    lbl_dir = pcb_v4 / "labels" / "train"
    if not lbl_dir.is_dir():
        lbl_dir = pcb_v4 / "labels"
    if not lbl_dir.is_dir():
        return []

    pairs: list[tuple[Path, Path]] = []
    for lbl in sorted(lbl_dir.glob("*.txt")):
        stem = lbl.stem
        img = _find_image_for_stem(pcb_v4, stem)
        if img is None:
            print(f"[WARN] 이미지 없음(스킵): {lbl.name} stem={stem}")
            continue
        pairs.append((img, lbl))
    return pairs


def _collect_synthetic_pairs(synthetic_root: Path) -> list[tuple[Path, Path]]:
    img_dir = synthetic_root / "images"
    lbl_dir = synthetic_root / "labels"
    if not img_dir.is_dir() or not lbl_dir.is_dir():
        return []
    pairs: list[tuple[Path, Path]] = []
    for img in sorted(img_dir.glob("*.jpg")) + sorted(img_dir.glob("*.png")):
        lbl = lbl_dir / f"{img.stem}.txt"
        if lbl.is_file():
            pairs.append((img, lbl))
    return pairs


def _write_merged_data_yaml(out_root: Path) -> None:
    # Colab: path를 절대경로로 두면 드라이브에 풀었을 때 한 번만 수정하면 됨
    abs_path = out_root.resolve()
    content = f"""# Ultralytics YOLO — PCB 피듀셜 + 합성 결함 통합
# Colab: 압축 해제 후 path 를 /content/dataset_yolo_colab 등으로 바꾸세요.

path: {abs_path.as_posix()}
train: images/train
val: images/val

nc: {len(MERGED_NAMES)}
names: {MERGED_NAMES}
"""
    (out_root / "data.yaml").write_text(content, encoding="utf-8")

    cls_txt = out_root / "classes.txt"
    cls_txt.write_text("\n".join(MERGED_NAMES) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="CVAT 피듀셜(PCB_V4) + 합성 결함 YOLO 데이터셋 병합")
    ap.add_argument("--pcb-v4", type=Path, required=True, help="PCB_V4 (CVAT export 루트)")
    ap.add_argument("--synthetic", type=Path, required=True, help="defect_simulator 출력 폴더")
    ap.add_argument("--output", type=Path, required=True, help="합쳐서 저장할 폴더 (새로 생성)")
    ap.add_argument("--val-ratio", type=float, default=0.2, help="검증 비율 (0~1)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--skip-fiducial-if-missing",
        action="store_true",
        help="피듀셜 이미지가 하나도 없어도 합성만으로 진행",
    )
    args = ap.parse_args()

    pcb_v4: Path = args.pcb_v4.expanduser().resolve()
    syn_root: Path = args.synthetic.expanduser().resolve()
    out_root: Path = args.output.expanduser().resolve()

    if not syn_root.is_dir():
        raise SystemExit(f"합성 데이터 폴더가 없습니다: {syn_root}")

    fiducial_items: list[tuple[str, Path, list[str]]] = []
    for img, lbl in _collect_fiducial_pairs(pcb_v4):
        lines = _read_yolo_label_lines(lbl)
        fiducial_items.append(("fiducial", img, lines))

    if not fiducial_items and args.skip_fiducial_if_missing:
        print("[안내] 피듀셜 이미지 없음 — 합성 데이터만 병합합니다.")

    if not fiducial_items and not args.skip_fiducial_if_missing:
        raise SystemExit(
            "PCB_V4에서 (이미지+라벨) 쌍을 찾지 못했습니다.\n"
            "  • CVAT export 시 '이미지' 포함 여부 확인\n"
            "  • 또는 이미지를 PCB_V4/data/images/train/ 등에 두세요.\n"
            "합성만 병합하려면 --skip-fiducial-if-missing 를 주세요."
        )

    synthetic_items: list[tuple[str, Path, list[str]]] = []
    for img, lbl in _collect_synthetic_pairs(syn_root):
        raw_lines = _read_yolo_label_lines(lbl)
        remapped = [_remap_synthetic_label_line(L) for L in raw_lines]
        synthetic_items.append(("synthetic", img, remapped))

    if not synthetic_items:
        raise SystemExit(f"합성 라벨을 찾지 못했습니다: {syn_root / 'images'}")

    merged_list: list[tuple[str, Path, list[str]]] = []
    for tag, img, lines in fiducial_items:
        merged_list.append((tag, img, lines))
    for tag, img, lines in synthetic_items:
        merged_list.append((tag, img, lines))

    random.seed(args.seed)
    random.shuffle(merged_list)

    n = len(merged_list)
    n_val = max(1, int(n * args.val_ratio)) if n > 1 else 0
    if n == 1:
        n_val = 0

    # shuffle 후 뒤쪽 n_val 장을 val
    train_items = merged_list[:-n_val] if n_val else merged_list
    val_items = merged_list[-n_val:] if n_val else []

    for split_name, items in [("train", train_items), ("val", val_items)]:
        idir = out_root / "images" / split_name
        ldir = out_root / "labels" / split_name
        idir.mkdir(parents=True, exist_ok=True)
        ldir.mkdir(parents=True, exist_ok=True)

        for idx, (tag, src_img, lines) in enumerate(items):
            stem = f"{tag}_{src_img.stem}_{idx:04d}"
            ext = src_img.suffix.lower()
            if ext not in (".jpg", ".jpeg", ".png", ".bmp"):
                ext = ".jpg"
            dst_img = idir / f"{stem}{ext}"
            dst_lbl = ldir / f"{stem}.txt"
            shutil.copy2(src_img, dst_img)
            dst_lbl.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    _write_merged_data_yaml(out_root)

    print("[OK] 병합 완료:", out_root)
    print(f"   train: {len(train_items)}  val: {len(val_items)}  클래스: {MERGED_NAMES}")
    print("   다음 파일을 Colab에 업로드하거나 Drive에 올린 뒤 data.yaml 의 path 만 맞추면 됩니다.")


if __name__ == "__main__":
    main()
