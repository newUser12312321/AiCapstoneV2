"""
PCB 결함 시뮬레이터
정상 기판 이미지에 가상 결함(단선·까짐·핀홀·단락)을 합성하여 학습 데이터를 생성합니다.

합성 스타일(개략):
- 단선: 배선 방향의 좁은 끊김 스트립(로컬 색 샘플 + 가장자리 링), 타원 덩어리 채색 지양
- 까짐: 불규칙 폴리라인 스크래치 + 국소 블렌딩
- 핀홀: 미세 원 + 얇은 링
- 단락: 구리색 브리지 선분 + 하이라이트
"""

import cv2
import numpy as np
import os
import random
from pathlib import Path
from dataclasses import dataclass
from typing import Literal, Optional, Tuple

# 기본 증강: 엣지/피듀셜 파이프라인과 동일한 구도를 유지 (뒤집기·회전 제외)
# → 학습·검증 시 피듀셜이 안 잡히는 현상 완화. 강한 증강은 --augment-strength full
AugmentStrength = Literal["inference_safe", "full"]


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


def _clamp_i(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _sample_local_median_bgr(img: np.ndarray, cx: int, cy: int, half: int = 14) -> np.ndarray:
    """주변 패치에서 BGR 중앙값 — 배선·마스크 색에 맞춤."""
    h, w = img.shape[:2]
    x1, x2 = _clamp_i(cx - half, 0, w - 1), _clamp_i(cx + half, 0, w - 1)
    y1, y2 = _clamp_i(cy - half, 0, h - 1), _clamp_i(cy + half, 0, h - 1)
    patch = img[y1 : y2 + 1, x1 : x2 + 1]
    if patch.size == 0:
        return np.array([60.0, 95.0, 75.0])
    return np.median(patch.reshape(-1, 3), axis=0).astype(np.float32)


def _blend_with_mask(
    base: np.ndarray, mask_f: np.ndarray, color_bgr: np.ndarray, strength: float
) -> None:
    """mask_f: HxW float 0~1, base 이미지를 in-place로 블렌딩."""
    s = np.clip(mask_f * strength, 0.0, 1.0)[:, :, np.newaxis]
    c = color_bgr.reshape(1, 1, 3)
    out = base.astype(np.float32) * (1.0 - s) + c * s
    base[:, :, :] = np.clip(out, 0, 255).astype(np.uint8)


def _line_endpoints(
    cx: int, cy: int, length: float, angle_deg: float
) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    rad = np.radians(angle_deg)
    dx = (length / 2) * np.cos(rad)
    dy = (length / 2) * np.sin(rad)
    return (int(cx - dx), int(cy - dy)), (int(cx + dx), int(cy + dy))


def add_trace_open(img: np.ndarray, region: Optional[tuple] = None) -> tuple[np.ndarray, BBox]:
    """
    단선(Trace Open) — 배선 방향의 **좁은 끊김 갭**(얇은 스트립).
    주변 색을 샘플링해 어둡게 에칭된 듯 보이게 합니다(타원 덩어리 대신).
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

    angle = random.uniform(-40.0, 40.0)
    length = float(random.randint(36, 92))
    thickness = random.randint(3, 7)

    p1, p2 = _line_endpoints(cx, cy, length, angle)
    p1 = (_clamp_i(p1[0], 4, w - 5), _clamp_i(p1[1], 4, h - 5))
    p2 = (_clamp_i(p2[0], 4, w - 5), _clamp_i(p2[1], 4, h - 5))

    # 선분을 따라 몇 곳에서 샘플 → 갭 색(어두운 기판/에칭)
    samples = []
    for t in (0.2, 0.5, 0.8):
        sx = int(p1[0] + t * (p2[0] - p1[0]))
        sy = int(p1[1] + t * (p2[1] - p1[1]))
        samples.append(_sample_local_median_bgr(img, sx, sy, 10))
    base_col = np.mean(samples, axis=0)
    # FR4/에칭 느낌: 채도 낮추고 어둡게
    gap_bgr = base_col * np.array([0.42, 0.48, 0.44], dtype=np.float32) + np.array(
        [8.0, 12.0, 10.0], dtype=np.float32
    )

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.line(mask, p1, p2, 255, thickness=thickness, lineType=cv2.LINE_AA)
    mask_f = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), sigmaX=1.2, sigmaY=1.2) / 255.0
    _blend_with_mask(result, mask_f, gap_bgr, strength=0.82)

    # 스트립 가장자리(두꺼운 마스크 − 안쪽 코어)에 잔동/번짐
    inner = np.zeros((h, w), dtype=np.uint8)
    cv2.line(
        inner,
        p1,
        p2,
        255,
        thickness=max(1, thickness - 2),
        lineType=cv2.LINE_AA,
    )
    ring = cv2.subtract(mask, inner)
    ring_f = cv2.GaussianBlur(ring.astype(np.float32), (3, 3), 0) / 255.0
    rim = base_col * np.array([1.06, 0.96, 0.88], dtype=np.float32)
    _blend_with_mask(result, ring_f, rim, strength=0.38)

    xs = [p1[0], p2[0], cx]
    ys = [p1[1], p2[1], cy]
    pad = thickness + 10
    bx1, bx2 = _clamp_i(min(xs) - pad, 0, w - 1), _clamp_i(max(xs) + pad, 0, w - 1)
    by1, by2 = _clamp_i(min(ys) - pad, 0, h - 1), _clamp_i(max(ys) + pad, 0, h - 1)
    bw, bh = bx2 - bx1 + 1, by2 - by1 + 1
    x_center = (bx1 + bx2) / 2 / w
    y_center = (by1 + by2) / 2 / h
    bbox = BBox(x_center, y_center, bw / w, bh / h, CLASS_TRACE_OPEN)

    return result, bbox


def add_metal_damage(img: np.ndarray, region: Optional[tuple] = None) -> tuple[np.ndarray, BBox]:
    """
    까짐(Metal Damage) — **불규칙한 얇은 스크래치 폴리라인**(채워진 원/다각형 덩어리 대신).
    각 점 근처 색을 섞어 긁힌 자국처럼 보이게 합니다.
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

    n = random.randint(6, 14)
    pts: list[list[int]] = []
    x, y = float(cx), float(cy)
    step = random.uniform(4.0, 9.0)
    ang = random.uniform(0.0, 2 * np.pi)
    for _ in range(n):
        pts.append([int(x), int(y)])
        ang += random.uniform(-0.9, 0.9)
        x += step * np.cos(ang) + random.uniform(-2.5, 2.5)
        y += step * np.sin(ang) + random.uniform(-2.5, 2.5)
        x = float(_clamp_i(int(x), 8, w - 9))
        y = float(_clamp_i(int(y), 8, h - 9))

    arr = np.array(pts, dtype=np.int32)
    scratch_w = random.randint(1, 2)

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.polylines(mask, [arr], isClosed=False, color=255, thickness=scratch_w, lineType=cv2.LINE_AA)
    dil = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.dilate(mask, dil, iterations=random.randint(0, 1))
    mask_f = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), sigmaX=0.9) / 255.0

    for i, (px, py) in enumerate(pts):
        loc = _sample_local_median_bgr(result, px, py, 8)
        # 밝은 스크래치 하이라이트 + 약간 탈색
        sc = loc * np.array([1.12, 1.05, 0.92], dtype=np.float32) + np.array(
            [14.0, 10.0, 6.0], dtype=np.float32
        )
        sc = np.clip(sc, 0, 255)
        pt_mask = np.zeros((h, w), dtype=np.float32)
        cv2.circle(pt_mask, (px, py), random.randint(2, 4), 1.0, -1)
        pt_mask = cv2.GaussianBlur(pt_mask, (5, 5), 0)
        _blend_with_mask(result, pt_mask, sc, strength=0.55 + 0.1 * (i % 2))

    col_mid = _sample_local_median_bgr(result, pts[len(pts) // 2][0], pts[len(pts) // 2][1], 12)
    darker = col_mid * np.array([0.75, 0.78, 0.82], dtype=np.float32)
    _blend_with_mask(result, mask_f, darker, strength=0.62)

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    pad = 14
    bx1 = _clamp_i(min(xs) - pad, 0, w - 1)
    bx2 = _clamp_i(max(xs) + pad, 0, w - 1)
    by1 = _clamp_i(min(ys) - pad, 0, h - 1)
    by2 = _clamp_i(max(ys) + pad, 0, h - 1)
    bw, bh = bx2 - bx1 + 1, by2 - by1 + 1
    x_center = (bx1 + bx2) / 2 / w
    y_center = (by1 + by2) / 2 / h
    bbox = BBox(x_center, y_center, bw / w, bh / h, CLASS_METAL_DAMAGE)

    return result, bbox


def add_pinhole(img: np.ndarray, region: Optional[tuple] = None) -> tuple[np.ndarray, BBox]:
    """
    핀홀(Pinhole) — 마스크의 **아주 작은 원형 착색**(주변보다 약간 어둡거나 밝게, 얇은 링).
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

    r = random.randint(1, 4)
    loc = _sample_local_median_bgr(result, cx, cy, 10)
    # 구멍 내부: 미세하게 어두워진 마스크 + 중심만 동 색 기운
    inner = loc * np.array([0.72, 0.76, 0.74], dtype=np.float32) + np.array([5, 8, 12], dtype=np.float32)

    hole = np.zeros((h, w), dtype=np.float32)
    cv2.circle(hole, (cx, cy), r, 1.0, -1)
    hole = cv2.GaussianBlur(hole, (0, 0), sigmaX=0.55)
    _blend_with_mask(result, hole, inner, strength=0.78)

    ring = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(ring, (cx, cy), r + 1, 255, 1)
    ring_i = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(ring_i, (cx, cy), max(0, r - 1), 255, -1)
    ring_m = cv2.subtract(ring, ring_i).astype(np.float32) / 255.0
    ring_m = cv2.GaussianBlur(ring_m, (3, 3), 0)
    dark_ring = loc * np.array([0.45, 0.5, 0.48], dtype=np.float32)
    _blend_with_mask(result, ring_m, dark_ring, strength=0.55)

    d = (r + 3) * 2
    bbox = BBox(cx / w, cy / h, d / w, d / h, CLASS_PINHOLE)

    return result, bbox


def add_short(img: np.ndarray, region: Optional[tuple] = None) -> tuple[np.ndarray, BBox]:
    """
    단락(Short) — 두 트랙을 잇는 **얇은 구리 브리지**(선분 + 주변 색 블렌드).
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

    length = float(random.randint(18, 44))
    thickness = random.randint(2, 5)
    angle = random.uniform(0.0, 180.0)
    p1, p2 = _line_endpoints(cx, cy, length, angle)
    p1 = (_clamp_i(p1[0], 4, w - 5), _clamp_i(p1[1], 4, h - 5))
    p2 = (_clamp_i(p2[0], 4, w - 5), _clamp_i(p2[1], 4, h - 5))

    mx, my = (p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2
    loc = _sample_local_median_bgr(result, mx, my, 12)
    # BGR에서 구리 느낌: B 중간·G·R 높게
    copper = loc * 0.35 + np.array([42.0, 118.0, 198.0], dtype=np.float32)
    copper = np.clip(copper, 0, 255)

    bridge = np.zeros((h, w), dtype=np.uint8)
    cv2.line(bridge, p1, p2, 255, thickness=thickness, lineType=cv2.LINE_AA)
    bridge_f = cv2.GaussianBlur(bridge.astype(np.float32), (0, 0), sigmaX=0.85) / 255.0
    _blend_with_mask(result, bridge_f, copper, strength=0.72)

    hi = np.zeros((h, w), dtype=np.uint8)
    cv2.line(hi, p1, p2, 255, thickness=max(1, thickness - 1), lineType=cv2.LINE_AA)
    hi_f = cv2.GaussianBlur(hi.astype(np.float32), (3, 3), 0) / 255.0
    spec = np.clip(copper * 1.15 + 20.0, 0, 255)
    _blend_with_mask(result, hi_f, spec, strength=0.25)

    xs, ys = [p1[0], p2[0]], [p1[1], p2[1]]
    pad = thickness + 12
    bx1 = _clamp_i(min(xs) - pad, 0, w - 1)
    bx2 = _clamp_i(max(xs) + pad, 0, w - 1)
    by1 = _clamp_i(min(ys) - pad, 0, h - 1)
    by2 = _clamp_i(max(ys) + pad, 0, h - 1)
    bw, bh = bx2 - bx1 + 1, by2 - by1 + 1
    bbox = BBox((bx1 + bx2) / 2 / w, (by1 + by2) / 2 / h, bw / w, bh / h, CLASS_SHORT)

    return result, bbox


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
    augment_strength: AugmentStrength = "inference_safe",
):
    """
    정상 PCB 이미지들로부터 결함 데이터셋을 생성합니다.

    Args:
        input_dir: 정상 PCB 이미지 폴더 경로
        output_dir: 생성된 데이터셋 저장 경로
        defects_per_image: 한 이미지에 넣을 결함 수 (1~4 권장)
        augment_count: 이미지 1장당 생성할 변형 수
        defect_types: 사용할 결함 유형 목록 (None이면 전체 사용)
        augment_strength:
            inference_safe — 밝기·대비만 약하게 (뒤집기/회전/강노이즈 없음). 엣지 검사와 호환.
            full — 기존 랜덤 플립·회전·노이즈 (학습 데이터 다양도↑, 피듀셜 탐지 실패 가능↑)
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

            # 결함 합성 전 증강 — full 은 기하 변환으로 피듀셜 YOLO와 도메인 불일치 가능
            img = _apply_basic_augmentation(img, strength=augment_strength)

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

    print(f"데이터셋 생성 완료: {total_generated}장 -> {output_dir}")
    _write_data_yaml(output_dir, defect_types)


def _apply_basic_augmentation(
    img: np.ndarray, strength: AugmentStrength = "inference_safe"
) -> np.ndarray:
    """
    기본 이미지 augmentation.

    inference_safe: 밝기·대비만 좁은 범위로 조정. 피듀셜 2점 기반 정렬 파이프라인과
    같은 보드 방향·가장자리를 유지해 엣지 단일 YOLO(피듀셜+결함) 추론과 맞춘다.

    full: 플립·회전·노이즈 포함. 학습 세트 다양도는 올라가나 엣지에서 피듀셜 미검출(999°)이
    잦아질 수 있음(특히 BORDER_REPLICATE 끝 번짐).
    """
    if strength == "inference_safe":
        alpha = random.uniform(0.93, 1.07)
        beta = random.randint(-12, 12)
        return cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

    # ── full (기존 동작, 회전 시 가장자리 번짐 완화) ──
    alpha = random.uniform(0.85, 1.15)
    beta = random.randint(-20, 20)
    img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

    if random.random() < 0.5:
        img = cv2.flip(img, 1)
    if random.random() < 0.3:
        img = cv2.flip(img, 0)
    if random.random() < 0.4:
        h, w = img.shape[:2]
        angle = random.uniform(-5, 5)
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        img = cv2.warpAffine(
            img, M, (w, h), borderMode=cv2.BORDER_REFLECT_101
        )
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
    parser.add_argument(
        "--types",
        default="trace_open,metal_damage,pinhole,short",
        help="생성할 결함 타입 목록(콤마 구분). 예: trace_open,metal_damage",
    )
    parser.add_argument("--save", help="미리보기 저장 경로 (preview 모드)")
    parser.add_argument(
        "--augment-strength",
        choices=["inference_safe", "full"],
        default="inference_safe",
        help="inference_safe: 밝기·대비만(기본, 엣지 피듀셜 호환) | full: 플립·회전·노이즈 포함",
    )
    args = parser.parse_args()

    if args.mode == "preview":
        preview_defects(args.input, args.save)
    else:
        selected_types = [t.strip().lower() for t in args.types.split(",") if t.strip()]
        valid_types = [t for t in selected_types if t in DEFECT_FUNCTIONS]
        if not valid_types:
            raise ValueError(
                "유효한 결함 타입이 없습니다. 사용 가능: "
                + ", ".join(sorted(DEFECT_FUNCTIONS.keys()))
            )
        generate_defect_dataset(
            input_dir=args.input,
            output_dir=args.output,
            defects_per_image=args.defects,
            augment_count=args.count,
            defect_types=valid_types,
            augment_strength=args.augment_strength,
        )
