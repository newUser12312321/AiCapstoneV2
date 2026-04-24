package com.inspection.domain.entity;

import jakarta.persistence.*;
import lombok.*;

/**
 * 개별 결함(Defect) 상세 정보 엔티티
 *
 * <p>하나의 InspectionLog에는 0개 이상의 DefectDetail이 존재할 수 있다.
 * (예: 단선 2개 + 까짐 1개 → DefectDetail 3개)
 *
 * <p>테이블: defect_detail
 * <p>관계: InspectionLog(1) ↔ DefectDetail(N) — 양방향 연관
 */
@Entity
@Table(name = "defect_detail")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)  // JPA 기본 생성자 (외부 직접 생성 방지)
@AllArgsConstructor
@Builder
public class DefectDetail {

    /** 결함 상세 레코드 고유 식별자 (자동 증가) */
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /**
     * 소속 검사 로그 (Many-to-One 관계)
     * FetchType.LAZY: 성능 최적화 — DefectDetail 조회 시 InspectionLog를 즉시 로드하지 않음
     */
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "inspection_log_id", nullable = false)
    private InspectionLog inspectionLog;

    /**
     * 결함 종류
     * 예: "TRACE_OPEN" (단선), "METAL_DAMAGE" (까짐), "FIDUCIAL_MISSING" (마크 누락)
     */
    @Column(name = "defect_type", nullable = false, length = 255)
    private String defectType;

    /** YOLO 모델의 신뢰도 점수 (0.0 ~ 1.0) */
    @Column(name = "confidence", nullable = false)
    private Float confidence;

    // ── 바운딩 박스 좌표 (원본 이미지 픽셀 기준) ──────────────────────────

    /** 바운딩 박스 좌상단 X 좌표 (픽셀) */
    @Column(name = "bbox_x", nullable = false)
    private Integer bboxX;

    /** 바운딩 박스 좌상단 Y 좌표 (픽셀) */
    @Column(name = "bbox_y", nullable = false)
    private Integer bboxY;

    /** 바운딩 박스 너비 (픽셀) */
    @Column(name = "bbox_width", nullable = false)
    private Integer bboxWidth;

    /** 바운딩 박스 높이 (픽셀) */
    @Column(name = "bbox_height", nullable = false)
    private Integer bboxHeight;
}
