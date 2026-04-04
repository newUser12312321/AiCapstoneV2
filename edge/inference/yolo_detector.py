"""
YOLOv8 / YOLO11 추론 모듈

Ultralytics 라이브러리를 사용하여 모델을 로드하고,
주어진 이미지에서 피듀셜 마크 또는 결함을 탐지한다.

2-Stage 파이프라인:
  Stage 1: 전체 이미지에서 피듀셜 마크(FIDUCIAL) 탐지 → 정렬 판단
  Stage 2: 정렬된 ROI(관심 영역)에서 결함(TRACE_OPEN, METAL_DAMAGE) 탐지
"""

import time
import logging
from pathlib import Path
from typing import Optional

import numpy as np

from config.settings import settings
from models.schemas import BoundingBox, DetectionItem

logger = logging.getLogger(__name__)


def _is_fiducial_class_name(class_name: str, num_model_classes: int) -> bool:
    """
    Stage1 피듀셜 필터: CVAT/팀마다 fiducial, FIDUCIAL, fiducial_mark 등 이름이 달라서
    'fiducial' 부분 문자열로도 매칭. 단일 클래스 모델은 그 한 클래스를 피듀셜로 간주.
    """
    n = class_name.lower().strip()
    if n == "fiducial" or "fiducial" in n:
        return True
    if num_model_classes == 1:
        return True
    return False


def _matches_target_class(class_name: str, target_class: str, num_model_classes: int) -> bool:
    if target_class != "FIDUCIAL":
        return class_name == target_class
    return _is_fiducial_class_name(class_name, num_model_classes)


# 가중치 파일이 없을 때 개발 환경에서 사용할 더미 클래스 레이블
DUMMY_CLASS_NAMES = {
    0: "FIDUCIAL",
    1: "TRACE_OPEN",
    2: "METAL_DAMAGE",
}


class YoloDetector:
    """
    YOLOv8n / YOLO11n 모델 래퍼 클래스.

    모델 로드는 최초 1회만 수행하고 이후에는 캐시된 모델을 재사용한다.
    (애플리케이션 시작 시 한 번만 인스턴스화할 것)

    사용 예 — 단일 모델:
        detector = YoloDetector()
        items = detector.detect(frame, target_class="FIDUCIAL")

    사용 예 — 2-Stage 분리 모델:
        fiducial_detector = YoloDetector(weights_path=settings.YOLO_FIDUCIAL_WEIGHTS)
        defect_detector   = YoloDetector(weights_path=settings.YOLO_DEFECT_WEIGHTS)
    """

    def __init__(
        self,
        weights_path: str = settings.YOLO_WEIGHTS_PATH,
        confidence_threshold: float = settings.YOLO_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.weights_path = Path(weights_path)
        self.confidence_threshold = confidence_threshold
        self._model = None   # 지연 로드(Lazy Load)

    # ── 모델 로드 ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        YOLO 모델을 메모리에 로드한다.

        가중치 파일(.pt)이 없는 경우(개발 환경):
          - Ultralytics에서 YOLOv8n 기본 모델을 자동 다운로드한다.
          - 실제 클래스 레이블 대신 더미 레이블을 사용한다.
        """
        try:
            from ultralytics import YOLO

            if not self.weights_path.exists():
                logger.warning(
                    "[YOLO] 가중치 파일 없음: %s → YOLOv8n 기본 모델로 대체합니다.",
                    self.weights_path
                )
                # 기본 공개 모델로 대체 (개발/테스트 용도)
                self._model = YOLO("yolov8n.pt")
            else:
                self._model = YOLO(str(self.weights_path))
                logger.info("[YOLO] 커스텀 모델 로드 완료: %s", self.weights_path)

            logger.info("[YOLO] 모델 준비 완료 (confidence 임계값: %.2f)", self.confidence_threshold)

        except ImportError:
            # ultralytics 패키지가 설치되지 않은 경우 더미 모드로 동작
            logger.error("[YOLO] ultralytics 패키지가 없습니다. 더미 탐지 모드로 동작합니다.")
            self._model = None

    # ── 추론 ─────────────────────────────────────────────────────────────────

    def detect(
        self,
        image: np.ndarray,
        target_class: Optional[str] = None,
    ) -> tuple[list[DetectionItem], int]:
        """
        이미지에서 객체를 탐지하고 DetectionItem 목록을 반환한다.

        Args:
            image:        OpenCV BGR 이미지 (H, W, 3)
            target_class: 이 이름의 클래스만 필터링. None이면 전체 반환.
                          예: "FIDUCIAL" → 피듀셜 마크만 반환

        Returns:
            (탐지 결과 목록, 추론 소요 시간 ms) 튜플
        """
        if self._model is None:
            # 더미 모드: 빈 결과 반환 (모델 없이 파이프라인 흐름 테스트 가능)
            logger.warning("[YOLO] 더미 모드 — 빈 탐지 결과 반환")
            return [], 0

        start_time = time.perf_counter()

        # YOLO 추론 실행
        # verbose=False: 콘솔 출력 억제
        # conf: 신뢰도 임계값 이하는 자동으로 필터링
        results = self._model.predict(
            source=image,
            conf=self.confidence_threshold,
            verbose=False,
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.debug("[YOLO] 추론 완료: %dms", elapsed_ms)

        detections: list[DetectionItem] = []

        num_cls = len(self._model.names) if getattr(self._model, "names", None) else 0

        # results[0]: 단일 이미지 추론 결과
        # .boxes: 탐지된 박스 목록 (없으면 빈 텐서)
        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                # 클래스 인덱스 및 이름 추출
                class_idx = int(box.cls[0])
                class_name: str = self._model.names.get(class_idx, f"CLASS_{class_idx}")
                conf: float = float(box.conf[0])

                # target_class 필터 적용 (None이면 전체)
                if target_class and not _matches_target_class(class_name, target_class, num_cls):
                    continue

                # YOLO xywh → 좌상단 기준 정수 좌표로 변환
                # box.xywh: [center_x, center_y, width, height] (float)
                xywh = box.xywh[0].tolist()
                cx, cy, bw, bh = xywh
                x = int(cx - bw / 2)
                y = int(cy - bh / 2)

                detection = DetectionItem(
                    defect_type=class_name,
                    confidence=round(conf, 4),
                    bbox=BoundingBox(
                        x=max(0, x),
                        y=max(0, y),
                        width=max(1, int(bw)),
                        height=max(1, int(bh)),
                    ),
                )
                detections.append(detection)

        logger.info("[YOLO] 탐지 수: %d건 (필터: %s)", len(detections), target_class or "전체")
        return detections, elapsed_ms

    def detect_fiducials(self, image: np.ndarray) -> tuple[list[DetectionItem], int]:
        """
        Stage 1 전용: 이미지 전체에서 피듀셜 마크만 탐지한다.

        Returns:
            (피듀셜 마크 목록, 추론 ms)
        """
        return self.detect(image, target_class="FIDUCIAL")

    def detect_defects(self, roi: np.ndarray) -> tuple[list[DetectionItem], int]:
        """
        Stage 2 전용: ROI 크롭 이미지에서 결함(단선, 까짐)을 탐지한다.

        Args:
            roi: Stage 1 정렬 후 크롭한 관심 영역 이미지

        Returns:
            (결함 목록, 추론 ms)
        """
        # 결함 클래스 중 하나라도 탐지되면 반환 (target_class=None → 전체)
        defects, ms = self.detect(roi, target_class=None)
        # 피듀셜 마크 결과는 결함 목록에서 제외
        defects = [d for d in defects if "fiducial" not in d.defect_type.lower()]
        return defects, ms
