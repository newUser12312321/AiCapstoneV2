"""
PCB 결함 시뮬레이터
정상 기판 이미지에 가상 결함(단선·까짐·핀홀·단락)을 합성하여 학습 데이터를 생성합니다.
"""

import cv2
import numpy as np
import json
import os
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BBox:
    x_center: float  # YOLO 형식 (0~1 정규화)
    y_center: float
    width: float
    height: float
    class_id: int


# YOLO 클래스 ID 정의
CLASS_TRACE_OPEN = 0      # 단선 (Trace Open)
CLASS_METAL_DAMAGE = 1    # 까짐 (Metal Damage / Scratch)
CLASS_PINHOLE = 2         # 핀홀 (Pinhole)
CLASS_SHORT = 3           # 단락 (Short Circuit)

CLASS_NAMES = {
    CLASS_TRACE_OPEN: "trace_open",
    CLASS_METAL_DAMAGE: "metal_damage",
    CLASS_PINHOLE: "pinhole",
    CLASS_SHORT: "short",
}


def add_trace_open(img: np.ndarray, region: Optional[tuple] = None) -> tuple[np.ndarray, BBox]:
    """
    단선(Trace Open) 결함 추가
    구리 배선 위에 검은 갭을 그려서 단선처럼 보이게 합니다.
    region: (x1, y1, x2, y2) 결함을 넣을 영역. None이면 랜덤 선택.
    """
    h, w = img.shape[:2]
    result = img.copy()

    if region is None:
        cx = random.randint(w // 4, w * 3 // 4)
        cy = random.randint(h // 4, h * 3 // 4)
    else:
        x1, y1, x2, y2 = region
        cx = random.randint(x1, x2)
        cy = random.randint(y1, y2)

    gap_w = random.randint(6, 18)
    gap_h = random.randint(3, 8)
    angle = random.uniform(-30, 30)

    # 갭 영역을 어두운 색(배경색)으로 채워 단선처럼 표현
    rot = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    bg_color = _sample_background_color(img, cx, cy)
    cv2.ellipse(result, (cx, cy), (gap_w, gap_h), angle, 0, 360, bg_color, -1)
    _add_noise_patch(result, cx, cy, gap_w + 4, gap_h + 2)

    x_center = cx / w
    y_center = cy / h
    bbox_w = (gap_w * 2 + 10) / w
    bbox_h = (gap_h * 2 + 8) / h
    bbox = BBox(x_center, y_center, bbox_w, bbox_h, CLASS_TRACE_OPEN)

    return result, bbox


def add_metal_damage(img: np.ndarray, region: Optional[tuple] = None) -> tuple[np.ndarray, BBox]:
    """
    까짐(Metal Damage) 결함 추가
    구리 표면이 긁히거나 벗겨진 것처럼 불규칙한 패치를 적용합니다.
    """
    h, w = img.shape[:2]
    result = img.copy()

    if region is None:
        cx = random.randint(w // 5, w * 4 // 5)
        cy = random.randint(h // 5, h * 4 // 5)
    else:
        x1, y1, x2, y2 = region
        cx = random.randint(x1, x2)
        cy = random.randint(y1, y2)

    size = random.randint(10, 25)

    # 불규칙한 다각형으로 까짐 영역 표현
    num_points = random.randint(5, 9)
    pts = []
    for i in range(num_points):
        angle = 2 * np.pi * i / num_points
        r = size * random.uniform(0.5, 1.0)
        pts.append([int(cx + r * np.cos(angle)), int(cy + r * np.sin(angle))])

    pts = np.array(pts, dtype=np.int32)

    # 노출된 기재 색 (베이지/갈색 계열)
    damage_color = (
        random.randint(80, 130),
        random.randint(100, 160),
        random.randint(110, 170),
    )
    cv2.fillPoly(result, [pts], damage_color)

    # 경계 블러 처리로 자연스럽게
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)
    blurred = cv2.GaussianBlur(result, (5, 5), 0)
    result = np.where(mask[:, :, np.newaxis] > 0, blurred, result)

    _add_noise_patch(result, cx, cy, size + 2, size + 2)

    x_center = cx / w
    y_center = cy / h
    bbox_w = (size * 2 + 12) / w
    bbox_h = (size * 2 + 12) / h
    bbox = BBox(x_center, y_center, bbox_w, bbox_h, CLASS_METAL_DAMAGE)

    return result, bbox


def add_pinhole(img: np.ndarray, region: Optional[tuple] = None) -> tuple[np.ndarray, BBox]:
    """
    핀홀(Pinhole) 결함 추가
    솔더 마스크에 미세한 구멍이 생긴 것처럼 표현합니다.
    """
    h, w = img.shape[:2]
    result = img.copy()

    if region is None:
        cx = random.randint(w // 6, w * 5 // 6)
        cy = random.randint(h // 6, h * 5 // 6)
    else:
        x1, y1, x2, y2 = region
        cx = random.randint(x1, x2)
        cy = random.randint(y1, y2)

    radius = random.randint(2, 6)
    # 구멍 — 밝은 구리색 노출
    hole_color = (random.randint(140, 190), random.randint(120, 170), random.randint(50, 100))
    cv2.circle(result, (cx, cy), radius, hole_color, -1)
    # 테두리 — 어두운 산화 링
    cv2.circle(result, (cx, cy), radius + 1, (40, 40, 40), 1)

    x_center = cx / w
    y_center = cy / h
    size = (radius * 2 + 6)
    bbox = BBox(x_center, y_center, size / w, size / h, CLASS_PINHOLE)

    return result, bbox


def add_short(img: np.ndarray, region: Optional[tuple] = None) -> tuple[np.ndarray, BBox]:
    """
    단락(Short) 결함 추가
    두 배선이 연결된 것처럼 구리색 브릿지를 그립니다.
    """
    h, w = img.shape[:2]
    result = img.copy()

    if region is None:
        cx = random.randint(w // 4, w * 3 // 4)
        cy = random.randint(h // 4, h * 3 // 4)
    else:
        x1, y1, x2, y2 = region
        cx = random.randint(x1, x2)
        cy = random.randint(y1, y2)

    length = random.randint(15, 35)
    thickness = random.randint(3, 7)
    angle = random.uniform(0, 180)

    dx = int(length * np.cos(np.radians(angle)))
    dy = int(length * np.sin(np.radians(angle)))

    # 구리색 브릿지
    copper_color = (random.randint(30, 80), random.randint(120, 180), random.randint(160, 210))
    cv2.line(result, (cx - dx // 2, cy - dy // 2), (cx + dx // 2, cy + dy // 2), copper_color, thickness)
    _add_noise_patch(result, cx, cy, length // 2 + 4, thickness + 4)

    x_center = cx / w
    y_center = cy / h
    bbox = BBox(x_center, y_center, (abs(dx) + 16) / w, (abs(dy) + 16) / h, CLASS_SHORT)

    return result, bbox


def _sample_background_color(img: np.ndarray, cx: int, cy: int) -> tuple:
    """이미지 코너에서 배경색 샘플링 (기재색 추정)"""
    h, w = img.shape[:2]
    corners = [
        img[10:30, 10:30],
        img[10:30, w - 30:w - 10],
        img[h - 30:h - 10, 10:30],
        img[h - 30:h - 10, w - 30:w - 10],
    ]
    sample = np.concatenate([c.reshape(-1, 3) for c in corners], axis=0)
    mean_color = sample.mean(axis=0)
    return tuple(int(c) for c in mean_color)


def _add_noise_patch(img: np.ndarray, cx: int, cy: int, w: int, h: int):
    """결함 주변에 약간의 노이즈를 추가해 자연스럽게 만들기"""
    x1 = max(0, cx - w)
    y1 = max(0, cy - h)
    x2 = min(img.shape[1], cx + w)
    y2 = min(img.shape[0], cy + h)
    patch = img[y1:y2, x1:x2].astype(np.float32)
    noise = np.random.normal(0, 4, patch.shape)
    img[y1:y2, x1:x2] = np.clip(patch + noise, 0, 255).astype(np.uint8)


DEFECT_FUNCTIONS = {
    "trace_open": add_trace_open,
    "metal_damage": add_metal_damage,
    "pinhole": add_pinhole,
    "short": add_short,
}


def generate_defect_dataset(
    input_dir: str,
    output_dir: str,
    defects_per_image: int = 3,
    augment_count: int = 5,
    defect_types: list = None,
):
    """
    정상 PCB 이미지들로부터 결함 데이터셋을 생성합니다.

    Args:
        input_dir: 정상 PCB 이미지 폴더 경로
        output_dir: 생성된 데이터셋 저장 경로
        defects_per_image: 한 이미지에 넣을 결함 수 (1~4 권장)
        augment_count: 이미지 1장당 생성할 변형 수
        defect_types: 사용할 결함 유형 목록 (None이면 전체 사용)
    """
    if defect_types is None:
        defect_types = list(DEFECT_FUNCTIONS.keys())

    # 출력 디렉토리 생성 (YOLO 형식)
    img_out = Path(output_dir) / "images"
    lbl_out = Path(output_dir) / "labels"
    img_out.mkdir(parents=True, exist_ok=True)
    lbl_out.mkdir(parents=True, exist_ok=True)

    # classes.txt 생성
    with open(Path(output_dir) / "classes.txt", "w") as f:
        for cid in sorted(CLASS_NAMES.keys()):
            f.write(CLASS_NAMES[cid] + "\n")

    input_images = list(Path(input_dir).glob("*.jpg")) + list(Path(input_dir).glob("*.png"))
    if not input_images:
        print(f"❌ {input_dir} 에서 이미지를 찾을 수 없습니다.")
        return

    total_generated = 0

    for img_path in input_images:
        orig = cv2.imread(str(img_path))
        if orig is None:
            continue

        for aug_idx in range(augment_count):
            img = orig.copy()
            bboxes = []

            # 기본 augmentation (밝기, 대비, 회전 등)
            img = _apply_basic_augmentation(img)

            # 결함 랜덤 추가
            num_defects = random.randint(1, defects_per_image)
            chosen = random.choices(defect_types, k=num_defects)

            for dtype in chosen:
                try:
                    img, bbox = DEFECT_FUNCTIONS[dtype](img)
                    bboxes.append(bbox)
                except Exception as e:
                    print(f"⚠️ 결함 생성 실패 ({dtype}): {e}")

            # 저장
            stem = img_path.stem
            out_name = f"{stem}_defect_{aug_idx:03d}"
            cv2.imwrite(str(img_out / f"{out_name}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])

            # YOLO 라벨 저장
            with open(lbl_out / f"{out_name}.txt", "w") as f:
                for bbox in bboxes:
                    f.write(f"{bbox.class_id} {bbox.x_center:.6f} {bbox.y_center:.6f} "
                            f"{bbox.width:.6f} {bbox.height:.6f}\n")

            total_generated += 1

    print(f"✅ 데이터셋 생성 완료: {total_generated}장 → {output_dir}")
    _write_data_yaml(output_dir, defect_types)


def _apply_basic_augmentation(img: np.ndarray) -> np.ndarray:
    """기본 이미지 augmentation (밝기/대비/회전/플립)"""
    # 밝기/대비 랜덤 조정
    alpha = random.uniform(0.85, 1.15)  # 대비
    beta = random.randint(-20, 20)       # 밝기
    img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

    # 랜덤 수평 플립
    if random.random() < 0.5:
        img = cv2.flip(img, 1)

    # 랜덤 수직 플립
    if random.random() < 0.3:
        img = cv2.flip(img, 0)

    # 약간의 회전 (±5도 이내)
    if random.random() < 0.4:
        h, w = img.shape[:2]
        angle = random.uniform(-5, 5)
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

    # 가우시안 노이즈
    if random.random() < 0.3:
        noise = np.random.normal(0, 3, img.shape).astype(np.float32)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    return img


def _write_data_yaml(output_dir: str, defect_types: list):
    """YOLO 학습용 data.yaml 생성"""
    yaml_content = f"""# YOLOv8 Dataset Config
path: {os.path.abspath(output_dir)}
train: images
val: images   # 실제 사용 시 train/val 분리 권장

nc: {len(CLASS_NAMES)}
names: {[CLASS_NAMES[i] for i in sorted(CLASS_NAMES.keys())]}
"""
    with open(Path(output_dir) / "data.yaml", "w") as f:
        f.write(yaml_content)


def preview_defects(image_path: str, save_path: Optional[str] = None):
    """
    결함 시뮬레이션 미리보기 (4가지 결함을 2x2 그리드로 표시)
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ 이미지를 열 수 없습니다: {image_path}")
        return

    # 4가지 결함 각각 적용
    results = []
    for name, func in DEFECT_FUNCTIONS.items():
        defected, bbox = func(img.copy())
        # 바운딩 박스 시각화
        h, w = defected.shape[:2]
        x1 = int((bbox.x_center - bbox.width / 2) * w)
        y1 = int((bbox.y_center - bbox.height / 2) * h)
        x2 = int((bbox.x_center + bbox.width / 2) * w)
        y2 = int((bbox.y_center + bbox.height / 2) * h)
        cv2.rectangle(defected, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(defected, name, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        results.append(defected)

    # 2x2 그리드로 합치기
    top = np.hstack([results[0], results[1]])
    bottom = np.hstack([results[2], results[3]])
    grid = np.vstack([top, bottom])

    # 화면에 맞게 축소
    scale = min(1200 / grid.shape[1], 800 / grid.shape[0])
    preview = cv2.resize(grid, (int(grid.shape[1] * scale), int(grid.shape[0] * scale)))

    if save_path:
        cv2.imwrite(save_path, preview)
        print(f"✅ 미리보기 저장: {save_path}")
    else:
        cv2.imshow("Defect Simulation Preview (Press any key to close)", preview)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PCB 결함 시뮬레이터")
    parser.add_argument("--mode", choices=["preview", "generate"], default="preview",
                        help="preview: 미리보기 / generate: 데이터셋 생성")
    parser.add_argument("--input", required=True, help="정상 PCB 이미지 경로 또는 폴더")
    parser.add_argument("--output", default="./synthetic_dataset", help="출력 폴더 (generate 모드)")
    parser.add_argument("--count", type=int, default=5, help="이미지당 생성 수 (generate 모드)")
    parser.add_argument("--defects", type=int, default=3, help="이미지당 결함 수")
    parser.add_argument("--save", help="미리보기 저장 경로 (preview 모드)")
    args = parser.parse_args()

    if args.mode == "preview":
        preview_defects(args.input, args.save)
    else:
        generate_defect_dataset(
            input_dir=args.input,
            output_dir=args.output,
            defects_per_image=args.defects,
            augment_count=args.count,
        )
