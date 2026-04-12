"""
GT 라벨과 YOLO 예측 박스를 한 이미지에 겹쳐 그린다.
smd_array_block(클래스 3) 오검 여부를 육안으로 보기 좋게 예측만 두껍게 강조한다.

  cd edge
  python tools/visualize_pred_vs_gt.py --weights weights/best.pt ^
    --dataset ../PCB_V3/for_colab --split val --out ../PCB_V3/vis_compare --max-images 20

  단일 파일:
  python tools/visualize_pred_vs_gt.py --weights weights/best.pt ^
    --image ../PCB_V3/for_colab/images/val/xxx.jpg --label ../PCB_V3/for_colab/labels/val/xxx.txt ^
    --out ../PCB_V3/vis_out
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

_EDGE = Path(__file__).resolve().parent.parent
if str(_EDGE) not in sys.path:
    sys.path.insert(0, str(_EDGE))

# BGR — 예측 클래스별 (smd_array_block=3 은 주황으로 눈에 띄게)
_PRED_COLORS_BGR: dict[int, tuple[int, int, int]] = {
    0: (180, 105, 255),   # mount_hole — 분홍
    1: (255, 200, 100),   # gold_finger_row
    2: (255, 255, 0),     # fiducial — 시안에 가깝
    3: (0, 140, 255),     # smd_array_block — 주황 (강조)
    4: (200, 200, 200),   # ic_chip
    5: (147, 20, 255),    # edge_connector_zone
}
_GT_COLOR = (60, 220, 60)
_HIGHLIGHT_CLASS = 3  # smd_array_block


def resolve_weights(w: str) -> Path:
    p = Path(w)
    if not p.is_file():
        p = _EDGE / "weights" / w
    return p


def norm_box_to_pixels(
    xc: float, yc: float, w: float, h: float, iw: int, ih: int
) -> tuple[int, int, int, int]:
    x1 = int((xc - w / 2.0) * iw)
    y1 = int((yc - h / 2.0) * ih)
    x2 = int((xc + w / 2.0) * iw)
    y2 = int((yc + h / 2.0) * ih)
    x1 = max(0, min(x1, iw - 1))
    x2 = max(0, min(x2, iw - 1))
    y1 = max(0, min(y1, ih - 1))
    y2 = max(0, min(y2, ih - 1))
    return x1, y1, x2, y2


def parse_yolo_labels(path: Path) -> list[tuple[int, float, float, float, float]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    rows: list[tuple[int, float, float, float, float]] = []
    for line in text.splitlines():
        p = line.split()
        if len(p) != 5:
            continue
        cid = int(float(p[0]))
        xc, yc, w, h = map(float, p[1:5])
        rows.append((cid, xc, yc, w, h))
    return rows


def draw_gt(img: np.ndarray, labels: list[tuple[int, float, float, float, float]], names: dict) -> None:
    ih, iw = img.shape[:2]
    for cid, xc, yc, w, h in labels:
        x1, y1, x2, y2 = norm_box_to_pixels(xc, yc, w, h, iw, ih)
        cv2.rectangle(img, (x1, y1), (x2, y2), _GT_COLOR, 2)
        tag = f"GT {names.get(cid, cid)}"
        cv2.putText(
            img,
            tag,
            (x1, max(12, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            _GT_COLOR,
            1,
            cv2.LINE_AA,
        )


def draw_predictions(
    img: np.ndarray,
    boxes,
    names: dict,
    highlight_class: int,
) -> None:
    if boxes is None or len(boxes) == 0:
        return
    ih, iw = img.shape[:2]
    for i in range(len(boxes)):
        cid = int(boxes.cls[i])
        conf = float(boxes.conf[i])
        xyxy = boxes.xyxy[i].cpu().numpy()
        x1, y1, x2, y2 = map(int, xyxy.tolist())
        color = _PRED_COLORS_BGR.get(cid, (200, 200, 200))
        thick = 4 if cid == highlight_class else 2
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thick)
        tag = f"P {names.get(cid, cid)} {conf:.2f}"
        cv2.putText(
            img,
            tag,
            (x1, max(14, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )


def process_one(
    image_path: Path,
    label_path: Path | None,
    model: object,
    names: dict,
    out_dir: Path,
    conf: float,
    imgsz: int,
    highlight_class: int,
) -> None:
    img_bgr = cv2.imread(str(image_path))
    if img_bgr is None:
        print(f"[skip] 이미지 로드 실패: {image_path}")
        return

    gt_rows: list[tuple[int, float, float, float, float]] = []
    if label_path and label_path.is_file():
        gt_rows = parse_yolo_labels(label_path)

    # GT 먼저 그린 뒤 예측을 위에 겹침
    canvas = img_bgr.copy()
    draw_gt(canvas, gt_rows, names)

    r = model.predict(str(image_path), conf=conf, imgsz=imgsz, verbose=False)[0]
    draw_predictions(canvas, r.boxes, names, highlight_class)

    # 범례
    legend_y = 24
    cv2.putText(
        canvas,
        "Green = GT  |  Orange thick = Pred smd_array_block  |  Other = Pred",
        (8, legend_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (240, 240, 240),
        2,
        cv2.LINE_AA,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"compare_{image_path.stem}.jpg"
    cv2.imwrite(str(out_path), canvas)
    print(f"saved: {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Draw GT + YOLO predictions (highlight smd_array_block).")
    ap.add_argument("--weights", default="weights/best.pt", help="weights/*.pt 또는 절대 경로")
    ap.add_argument("--out", type=Path, required=True, help="출력 폴더")
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument("--imgsz", type=int, default=1024)
    ap.add_argument("--highlight-class", type=int, default=_HIGHLIGHT_CLASS, help="두껍게 그릴 예측 클래스 id")
    ap.add_argument("--image", type=Path, default=None, help="단일 이미지")
    ap.add_argument("--label", type=Path, default=None, help="단일 라벨 (.txt). 없으면 dataset 기준 자동")
    ap.add_argument("--dataset", type=Path, default=None, help="for_colab 루트 (images/train|val, labels/...)")
    ap.add_argument("--split", choices=("train", "val", "both"), default="val")
    ap.add_argument("--max-images", type=int, default=30, help="배치 시 최대 장 수")

    args = ap.parse_args()
    wpath = resolve_weights(args.weights)
    if not wpath.is_file():
        raise SystemExit(f"가중치 없음: {wpath}")

    from ultralytics import YOLO

    m = YOLO(str(wpath))
    names = dict(m.names) if m.names else {}

    if args.image:
        lbl = args.label
        if lbl is None and args.dataset:
            for sp in ("train", "val"):
                cand = args.dataset / "images" / sp / args.image.name
                if cand.is_file():
                    lbl = args.dataset / "labels" / sp / f"{args.image.stem}.txt"
                    break
        process_one(
            args.image,
            lbl,
            m,
            names,
            args.out,
            args.conf,
            args.imgsz,
            args.highlight_class,
        )
        return

    if args.dataset is None:
        raise SystemExit("--image 또는 --dataset 가 필요합니다.")

    splits: list[str]
    if args.split == "both":
        splits = ["train", "val"]
    else:
        splits = [args.split]

    images: list[Path] = []
    for sp in splits:
        d = args.dataset / "images" / sp
        if d.is_dir():
            images.extend(sorted(d.glob("*.jpg")) + sorted(d.glob("*.png")))

    images = images[: args.max_images]
    if not images:
        raise SystemExit(f"이미지 없음: {args.dataset}")

    for img_path in images:
        sp = img_path.parent.name
        lbl = args.dataset / "labels" / sp / f"{img_path.stem}.txt"
        process_one(
            img_path,
            lbl,
            m,
            names,
            args.out,
            args.conf,
            args.imgsz,
            args.highlight_class,
        )


if __name__ == "__main__":
    main()
