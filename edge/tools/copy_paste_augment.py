"""
Copy-Paste 결함 합성기
인터넷에서 수집한 실제 PCB 결함 패치를 내 기판 이미지에 자연스럽게 붙입니다.
Poisson Blending(seamlessClone)을 사용해 경계가 부자연스럽지 않게 합성합니다.
"""

import cv2
import numpy as np
import os
import random
from pathlib import Path


def paste_defect_patch(
    background: np.ndarray,
    patch: np.ndarray,
    position: tuple = None,
    blend: bool = True,
) -> tuple[np.ndarray, tuple]:
    """
    결함 패치를 배경 이미지에 붙입니다.

    Args:
        background: 정상 PCB 이미지 (붙일 대상)
        patch: 결함 패치 이미지 (잘라낸 결함 영역)
        position: (cx, cy) 붙일 위치. None이면 랜덤
        blend: True면 Poisson Blending 사용 (자연스러운 합성)

    Returns:
        (합성된 이미지, (x1, y1, x2, y2) 결함 위치)
    """
    bh, bw = background.shape[:2]
    ph, pw = patch.shape[:2]

    # 패치 크기가 배경보다 크면 리사이즈
    max_size = min(bw, bh) // 4
    if pw > max_size or ph > max_size:
        scale = max_size / max(pw, ph)
        patch = cv2.resize(patch, (int(pw * scale), int(ph * scale)))
        ph, pw = patch.shape[:2]

    # 붙일 위치 결정
    if position is None:
        margin = max(pw, ph) // 2 + 5
        cx = random.randint(margin, bw - margin)
        cy = random.randint(margin, bh - margin)
    else:
        cx, cy = position

    result = background.copy()

    if blend:
        # Poisson Blending — 경계를 자연스럽게 블렌딩
        try:
            mask = 255 * np.ones(patch.shape, patch.dtype)
            result = cv2.seamlessClone(patch, result, mask, (cx, cy), cv2.NORMAL_CLONE)
        except cv2.error:
            # Poisson 실패 시 알파 블렌딩으로 폴백
            result = _alpha_blend(result, patch, cx, cy)
    else:
        result = _alpha_blend(result, patch, cx, cy)

    x1 = max(0, cx - pw // 2)
    y1 = max(0, cy - ph // 2)
    x2 = min(bw, cx + pw // 2)
    y2 = min(bh, cy + ph // 2)

    return result, (x1, y1, x2, y2)


def _alpha_blend(bg: np.ndarray, patch: np.ndarray, cx: int, cy: int) -> np.ndarray:
    """알파 블렌딩 (Poisson 실패 시 폴백)"""
    ph, pw = patch.shape[:2]
    bh, bw = bg.shape[:2]

    x1 = max(0, cx - pw // 2)
    y1 = max(0, cy - ph // 2)
    x2 = min(bw, x1 + pw)
    y2 = min(bh, y1 + ph)

    patch_crop = patch[:y2 - y1, :x2 - x1]

    # 가우시안 마스크로 경계 페이드아웃
    mask = np.ones((y2 - y1, x2 - x1), dtype=np.float32)
    ksize = max(3, min((y2 - y1) // 3 * 2 + 1, (x2 - x1) // 3 * 2 + 1))
    if ksize % 2 == 0:
        ksize += 1
    mask = cv2.GaussianBlur(mask, (ksize, ksize), 0)
    mask = mask[:, :, np.newaxis]

    bg[y1:y2, x1:x2] = (
        bg[y1:y2, x1:x2].astype(np.float32) * (1 - mask)
        + patch_crop.astype(np.float32) * mask
    ).astype(np.uint8)

    return bg


def batch_copy_paste(
    good_dir: str,
    patch_dir: str,
    output_dir: str,
    patches_per_image: int = 2,
    augment_count: int = 5,
):
    """
    정상 이미지 폴더 + 결함 패치 폴더를 받아 합성 데이터셋을 생성합니다.

    디렉토리 구조 예시:
      patch_dir/
        trace_open/   ← 단선 패치 이미지들
        metal_damage/ ← 까짐 패치 이미지들
        pinhole/      ← 핀홀 패치 이미지들
    
    Args:
        good_dir: 정상 PCB 이미지 폴더
        patch_dir: 결함 패치 폴더 (하위 폴더명 = 클래스명)
        output_dir: 출력 폴더
        patches_per_image: 이미지당 붙일 패치 수
        augment_count: 이미지 1장당 생성 수
    """
    # 클래스 맵 로드
    class_dirs = {
        d.name: list(d.glob("*.jpg")) + list(d.glob("*.png"))
        for d in Path(patch_dir).iterdir() if d.is_dir()
    }
    if not class_dirs:
        print(f"❌ {patch_dir} 에서 클래스 폴더를 찾을 수 없습니다.")
        print("   폴더 구조: patch_dir/trace_open/*.jpg, patch_dir/metal_damage/*.jpg ...")
        return

    class_names = sorted(class_dirs.keys())
    class_id_map = {name: i for i, name in enumerate(class_names)}
    print(f"✅ 클래스 발견: {class_names}")

    # 출력 폴더 생성
    img_out = Path(output_dir) / "images"
    lbl_out = Path(output_dir) / "labels"
    img_out.mkdir(parents=True, exist_ok=True)
    lbl_out.mkdir(parents=True, exist_ok=True)

    with open(Path(output_dir) / "classes.txt", "w") as f:
        for name in class_names:
            f.write(name + "\n")

    good_images = list(Path(good_dir).glob("*.jpg")) + list(Path(good_dir).glob("*.png"))
    if not good_images:
        print(f"❌ {good_dir} 에서 정상 이미지를 찾을 수 없습니다.")
        return

    total = 0
    for img_path in good_images:
        bg = cv2.imread(str(img_path))
        if bg is None:
            continue
        bh, bw = bg.shape[:2]

        for aug_idx in range(augment_count):
            result = bg.copy()
            bboxes = []

            available = [cls for cls, files in class_dirs.items() if files]
            chosen_classes = random.choices(available, k=min(patches_per_image, len(available)))

            for cls_name in chosen_classes:
                patch_path = random.choice(class_dirs[cls_name])
                patch = cv2.imread(str(patch_path))
                if patch is None:
                    continue

                result, (x1, y1, x2, y2) = paste_defect_patch(result, patch, blend=True)

                # YOLO 형식 바운딩 박스
                cx = ((x1 + x2) / 2) / bw
                cy = ((y1 + y2) / 2) / bh
                w_norm = (x2 - x1) / bw
                h_norm = (y2 - y1) / bh
                cid = class_id_map[cls_name]
                bboxes.append(f"{cid} {cx:.6f} {cy:.6f} {w_norm:.6f} {h_norm:.6f}")

            out_name = f"{img_path.stem}_paste_{aug_idx:03d}"
            cv2.imwrite(str(img_out / f"{out_name}.jpg"), result, [cv2.IMWRITE_JPEG_QUALITY, 95])
            with open(lbl_out / f"{out_name}.txt", "w") as f:
                f.write("\n".join(bboxes))

            total += 1

    print(f"✅ Copy-Paste 데이터셋 생성 완료: {total}장 → {output_dir}")


def create_patch_from_region(
    image_path: str,
    x1: int, y1: int, x2: int, y2: int,
    save_path: str,
):
    """
    이미지에서 결함 영역을 잘라내어 패치로 저장합니다.
    CVAT에서 라벨링한 좌표를 이용해 패치를 추출할 때 사용합니다.

    Args:
        image_path: 원본 이미지 경로
        x1, y1, x2, y2: 결함 영역 픽셀 좌표
        save_path: 저장할 패치 경로
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ 이미지를 열 수 없습니다: {image_path}")
        return
    patch = img[y1:y2, x1:x2]
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    cv2.imwrite(save_path, patch)
    print(f"✅ 패치 저장: {save_path} ({x2-x1}×{y2-y1}px)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Copy-Paste 결함 합성기")
    subparsers = parser.add_subparsers(dest="cmd")

    # batch 명령
    p_batch = subparsers.add_parser("batch", help="배치 합성 실행")
    p_batch.add_argument("--good", required=True, help="정상 이미지 폴더")
    p_batch.add_argument("--patches", required=True, help="결함 패치 폴더")
    p_batch.add_argument("--output", default="./paste_dataset", help="출력 폴더")
    p_batch.add_argument("--per-image", type=int, default=2, help="이미지당 패치 수")
    p_batch.add_argument("--count", type=int, default=5, help="이미지당 생성 수")

    # crop 명령 (패치 추출)
    p_crop = subparsers.add_parser("crop", help="이미지에서 결함 패치 추출")
    p_crop.add_argument("--image", required=True, help="원본 이미지 경로")
    p_crop.add_argument("--x1", type=int, required=True)
    p_crop.add_argument("--y1", type=int, required=True)
    p_crop.add_argument("--x2", type=int, required=True)
    p_crop.add_argument("--y2", type=int, required=True)
    p_crop.add_argument("--save", required=True, help="저장 경로")

    args = parser.parse_args()

    if args.cmd == "batch":
        batch_copy_paste(args.good, args.patches, args.output, args.per_image, args.count)
    elif args.cmd == "crop":
        create_patch_from_region(args.image, args.x1, args.y1, args.x2, args.y2, args.save)
    else:
        parser.print_help()
