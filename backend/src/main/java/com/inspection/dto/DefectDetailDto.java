package com.inspection.dto;

import jakarta.validation.constraints.*;
import lombok.*;

/**
 * 결함 상세 정보 DTO (요청/응답 공용)
 *
 * <p>라즈베리파이가 전송하는 JSON 배열의 각 요소와 매핑된다.
 * 예시 JSON:
 * {
 *   "defectType": "TRACE_OPEN",
 *   "confidence": 0.87,
 *   "bboxX": 430, "bboxY": 210,
 *   "bboxWidth": 55, "bboxHeight": 30
 * }
 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DefectDetailDto {

    /** 결함 종류 (TRACE_OPEN / METAL_DAMAGE / FIDUCIAL_MISSING) */
    @NotBlank(message = "결함 종류는 필수입니다.")
    private String defectType;

    /** YOLO 신뢰도 (0.0 ~ 1.0) */
    @NotNull
    @DecimalMin("0.0") @DecimalMax("1.0")
    private Float confidence;

    /** 바운딩 박스 좌상단 X (픽셀) */
    @NotNull @Min(0)
    private Integer bboxX;

    /** 바운딩 박스 좌상단 Y (픽셀) */
    @NotNull @Min(0)
    private Integer bboxY;

    /** 바운딩 박스 너비 (픽셀) */
    @NotNull @Min(1)
    private Integer bboxWidth;

    /** 바운딩 박스 높이 (픽셀) */
    @NotNull @Min(1)
    private Integer bboxHeight;
}
