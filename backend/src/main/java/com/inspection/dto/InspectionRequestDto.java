package com.inspection.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import lombok.*;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 라즈베리파이 → Spring Boot 서버로 전송하는 검사 결과 요청 DTO
 *
 * <p>엣지 디바이스가 검사 완료 후 POST /api/inspections 로 보내는
 * JSON 페이로드 전체와 1:1 매핑된다.
 *
 * <p>예시 JSON:
 * {
 *   "deviceId": "RPI5-LINE-A",
 *   "result": "FAIL",
 *   "fiducial1X": 320, "fiducial1Y": 240,
 *   "fiducial2X": 960, "fiducial2Y": 240,
 *   "angleErrorDeg": 2.3,
 *   "inferenceTimeMs": 145,
 *   "totalTimeMs": 312,
 *   "imagePath": "/captures/20260331_143000.jpg",
 *   "inspectedAt": "2026-03-31T14:30:00",
 *   "defects": [
 *     { "defectType": "TRACE_OPEN", "confidence": 0.91,
 *       "bboxX": 430, "bboxY": 210, "bboxWidth": 55, "bboxHeight": 30 }
 *   ]
 * }
 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class InspectionRequestDto {

    /** 검사 수행 디바이스 ID */
    @NotBlank(message = "디바이스 ID는 필수입니다.")
    private String deviceId;

    /** 최종 판정 결과 문자열 ("PASS" 또는 "FAIL") */
    @NotBlank(message = "판정 결과는 필수입니다.")
    @Pattern(regexp = "PASS|FAIL", message = "결과는 PASS 또는 FAIL이어야 합니다.")
    private String result;

    // ── 피듀셜 마크 좌표 (마크를 찾지 못한 경우 null 허용) ───────────────────
    private Integer fiducial1X;
    private Integer fiducial1Y;
    private Integer fiducial2X;
    private Integer fiducial2Y;

    /** 정렬 오차 각도 (°) */
    private Float angleErrorDeg;

    /** YOLO 추론 시간 (ms) */
    @Min(value = 0, message = "추론 시간은 0 이상이어야 합니다.")
    private Integer inferenceTimeMs;

    /** 총 처리 시간 (ms) */
    @Min(value = 0, message = "처리 시간은 0 이상이어야 합니다.")
    private Integer totalTimeMs;

    /** 캡처 이미지 저장 경로 */
    private String imagePath;

    /**
     * 검사 수행 시각 (라즈베리파이 로컬 시각)
     * ISO 8601 형식: "2026-03-31T14:30:00"
     */
    @NotNull(message = "검사 시각은 필수입니다.")
    private LocalDateTime inspectedAt;

    /**
     * 탐지된 결함 목록
     * @Valid: 리스트 내 각 DefectDetailDto에도 Bean Validation 적용
     */
    @Valid
    private List<DefectDetailDto> defects;
}
