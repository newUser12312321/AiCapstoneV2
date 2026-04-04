"""
엣지 디바이스 내부에서 사용하는 Pydantic 데이터 모델 정의

검사 파이프라인 각 단계에서 결과를 구조화된 객체로 전달하여
타입 안전성을 보장하고, 최종적으로 Spring Boot 서버 전송용
JSON 페이로드로 직렬화된다.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── 열거형 ────────────────────────────────────────────────────────────────────

class InspectionResult(str, Enum):
    """최종 검사 판정 결과. str 상속으로 JSON 직렬화 시 문자열로 자동 변환."""
    PASS = "PASS"
    FAIL = "FAIL"


class DefectType(str, Enum):
    """YOLO 모델이 탐지하는 결함 종류."""
    TRACE_OPEN     = "TRACE_OPEN"      # 단선 (배선이 끊긴 경우)
    METAL_DAMAGE   = "METAL_DAMAGE"    # 까짐 (금속 표면 손상)
    FIDUCIAL_MISSING = "FIDUCIAL_MISSING"  # 피듀셜 마크 인식 실패


# ── 바운딩 박스 ───────────────────────────────────────────────────────────────

class BoundingBox(BaseModel):
    """
    YOLO 탐지 결과 바운딩 박스 좌표.
    좌상단 (x, y) 기준, 너비·높이 형식 (XYWH).
    """
    x: int = Field(ge=0, description="좌상단 X 좌표 (픽셀)")
    y: int = Field(ge=0, description="좌상단 Y 좌표 (픽셀)")
    width: int = Field(gt=0, description="너비 (픽셀)")
    height: int = Field(gt=0, description="높이 (픽셀)")


# ── 탐지 결과 단위 ────────────────────────────────────────────────────────────

class DetectionItem(BaseModel):
    """
    YOLO가 한 프레임에서 탐지한 단일 객체 정보.
    피듀셜 마크 탐지와 결함 탐지 모두 이 모델을 사용한다.
    """
    defect_type: str = Field(description="결함 또는 마크 종류")
    confidence: float = Field(ge=0.0, le=1.0, description="YOLO 신뢰도 (0~1)")
    bbox: BoundingBox = Field(description="바운딩 박스 좌표")

    @property
    def center_x(self) -> int:
        """바운딩 박스 중심 X 좌표 (정렬 계산에 사용)"""
        return self.bbox.x + self.bbox.width // 2

    @property
    def center_y(self) -> int:
        """바운딩 박스 중심 Y 좌표 (정렬 계산에 사용)"""
        return self.bbox.y + self.bbox.height // 2


# ── 정렬 검사 결과 ────────────────────────────────────────────────────────────

class AlignmentResult(BaseModel):
    """
    1차 피듀셜 마크 정렬 검사 결과.
    두 마크의 좌표와 계산된 오차 각도를 담는다.
    """
    is_aligned: bool = Field(
        description="피듀셜 2개·기울기 한도 내 여부(엣지: MAX_DESKEW_ANGLE_DEG 이하이면 보정 가능)"
    )
    fiducial1: Optional[DetectionItem] = Field(default=None, description="1번 마크 탐지 결과")
    fiducial2: Optional[DetectionItem] = Field(default=None, description="2번 마크 탐지 결과")
    angle_error_deg: float = Field(default=0.0, description="수평 기준 오차 각도 (°)")


# ── 최종 검사 패킷 (서버 전송용) ──────────────────────────────────────────────

class InspectionPacket(BaseModel):
    """
    검사 완료 후 Spring Boot 서버로 POST 전송하는 최종 JSON 페이로드.
    Spring Boot InspectionRequestDto와 필드명이 1:1로 매핑된다.

    camelCase 직렬화:
        Pydantic v2의 alias_generator를 사용하지 않고
        model_config의 populate_by_name으로 snake_case ↔ camelCase 양쪽 허용.
    """
    # 디바이스 식별자
    device_id: str = Field(serialization_alias="deviceId")

    # 최종 판정 결과
    result: InspectionResult

    # 피듀셜 마크 좌표 (탐지 실패 시 None)
    fiducial1_x: Optional[int] = Field(default=None, serialization_alias="fiducial1X")
    fiducial1_y: Optional[int] = Field(default=None, serialization_alias="fiducial1Y")
    fiducial2_x: Optional[int] = Field(default=None, serialization_alias="fiducial2X")
    fiducial2_y: Optional[int] = Field(default=None, serialization_alias="fiducial2Y")

    # Stage1 YOLO 탐지 신뢰도 (0~1, 없으면 None)
    fiducial1_confidence: Optional[float] = Field(default=None, serialization_alias="fiducial1Confidence")
    fiducial2_confidence: Optional[float] = Field(default=None, serialization_alias="fiducial2Confidence")

    # 정렬 오차 각도
    angle_error_deg: Optional[float] = Field(default=None, serialization_alias="angleErrorDeg")

    # 성능 지표
    inference_time_ms: Optional[int] = Field(default=None, serialization_alias="inferenceTimeMs")
    total_time_ms: Optional[int] = Field(default=None, serialization_alias="totalTimeMs")

    # 이미지 저장 경로
    image_path: Optional[str] = Field(default=None, serialization_alias="imagePath")

    # 검사 수행 시각 (ISO 8601 문자열로 직렬화)
    inspected_at: datetime = Field(serialization_alias="inspectedAt")

    # 탐지된 결함 목록
    defects: list[DefectPayload] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    def to_server_json(self) -> dict:
        """
        Spring Boot 서버가 기대하는 camelCase JSON 딕셔너리로 변환.
        serialization_alias 값을 키로 사용한다.
        """
        return self.model_dump(by_alias=True, mode="json")


class DefectPayload(BaseModel):
    """InspectionPacket.defects 배열의 각 요소 — 결함 단위 페이로드."""
    defect_type: str = Field(serialization_alias="defectType")
    confidence: float = Field(serialization_alias="confidence")
    bbox_x: int = Field(serialization_alias="bboxX")
    bbox_y: int = Field(serialization_alias="bboxY")
    bbox_width: int = Field(serialization_alias="bboxWidth")
    bbox_height: int = Field(serialization_alias="bboxHeight")

    model_config = {"populate_by_name": True}


# 전방 참조 해결: InspectionPacket이 DefectPayload를 참조하므로
# 클래스 정의 완료 후 모델을 재빌드한다.
InspectionPacket.model_rebuild()
