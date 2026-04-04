package com.inspection.domain.entity;

import com.inspection.domain.enums.InspectionResult;
import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 검사 이력(Inspection Log) 메인 엔티티
 *
 * <p>라즈베리파이가 한 번의 PCB 검사를 수행할 때마다 이 레코드가 하나 생성된다.
 *
 * <p>테이블: inspection_log
 * <p>관계: InspectionLog(1) ↔ DefectDetail(N)
 *
 * <p>@EntityListeners(AuditingEntityListener.class):
 *     InspectionApplication의 @EnableJpaAuditing과 함께 작동하여
 *     createdAt 필드를 INSERT 시점에 자동으로 채운다.
 */
@Entity
@Table(name = "inspection_log")
@EntityListeners(AuditingEntityListener.class)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class InspectionLog {

    /** 검사 로그 고유 식별자 (자동 증가) */
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // ── 디바이스 정보 ────────────────────────────────────────────────────────

    /**
     * 검사를 수행한 엣지 디바이스 식별자
     * 예: "RPI5-LINE-A", "RPI5-LINE-B" (다중 라인 확장 대비)
     */
    @Column(name = "device_id", nullable = false, length = 50)
    private String deviceId;

    // ── 검사 결과 ────────────────────────────────────────────────────────────

    /**
     * 최종 판정 결과 (PASS / FAIL)
     * EnumType.STRING: DB에 "PASS" / "FAIL" 문자열로 저장 (숫자 인덱스 저장 금지)
     */
    @Enumerated(EnumType.STRING)
    @Column(name = "result", nullable = false, length = 10)
    private InspectionResult result;

    // ── 피듀셜 마크 정렬 정보 ────────────────────────────────────────────────

    /**
     * 피듀셜 마크 1번 탐지 좌표 X (픽셀)
     * null 허용: 마크를 찾지 못했을 경우
     */
    @Column(name = "fiducial1_x")
    private Integer fiducial1X;

    /** 피듀셜 마크 1번 탐지 좌표 Y (픽셀) */
    @Column(name = "fiducial1_y")
    private Integer fiducial1Y;

    /** 피듀셜 마크 2번 탐지 좌표 X (픽셀) */
    @Column(name = "fiducial2_x")
    private Integer fiducial2X;

    /** 피듀셜 마크 2번 탐지 좌표 Y (픽셀) */
    @Column(name = "fiducial2_y")
    private Integer fiducial2Y;

    /** 피듀셜 1번 YOLO 탐지 신뢰도 (0~1) */
    @Column(name = "fiducial1_confidence")
    private Float fiducial1Confidence;

    /** 피듀셜 2번 YOLO 탐지 신뢰도 (0~1) */
    @Column(name = "fiducial2_confidence")
    private Float fiducial2Confidence;

    /**
     * 기판 정렬 오차 각도 (도 단위, °)
     * 두 피듀셜 마크를 연결한 선의 수평 기준 편차
     * 허용 오차 초과 시 FAIL 판정
     */
    @Column(name = "angle_error_deg")
    private Float angleErrorDeg;

    // ── 추론 성능 지표 ────────────────────────────────────────────────────────

    /** YOLO 추론 소요 시간 (밀리초) */
    @Column(name = "inference_time_ms")
    private Integer inferenceTimeMs;

    /** 총 처리 시간 (캡처 ~ 전송 완료, 밀리초) */
    @Column(name = "total_time_ms")
    private Integer totalTimeMs;

    // ── 캡처 이미지 경로 ─────────────────────────────────────────────────────

    /**
     * 원본 캡처 이미지 저장 경로 (서버 로컬 또는 S3 URL)
     * 프론트엔드에서 바운딩 박스 오버레이 렌더링에 사용
     */
    @Column(name = "image_path", length = 512)
    private String imagePath;

    // ── 타임스탬프 ──────────────────────────────────────────────────────────

    /**
     * 검사 수행 시각 (라즈베리파이 로컬 시각)
     * 서버 수신 시각과 별도로 관리하여 네트워크 지연을 추적한다.
     */
    @Column(name = "inspected_at", nullable = false)
    private LocalDateTime inspectedAt;

    /**
     * 서버 레코드 생성 시각 (JPA Auditing 자동 주입)
     * updatable = false: 최초 INSERT 이후 변경 불가
     */
    @CreatedDate
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    // ── 연관 결함 목록 ────────────────────────────────────────────────────────

    /**
     * 이 검사에서 탐지된 결함 목록 (One-to-Many)
     *
     * cascade = ALL: InspectionLog 저장/삭제 시 DefectDetail도 함께 처리
     * orphanRemoval = true: 리스트에서 제거된 DefectDetail은 DB에서도 삭제
     * FetchType.LAZY: 성능 최적화 — 명시적 조회 시에만 쿼리 실행
     */
    @OneToMany(mappedBy = "inspectionLog",
               cascade = CascadeType.ALL,
               orphanRemoval = true,
               fetch = FetchType.LAZY)
    @Builder.Default
    private List<DefectDetail> defects = new ArrayList<>();

    // ── 연관 편의 메서드 ─────────────────────────────────────────────────────

    /**
     * 결함 상세를 추가하고 양방향 연관을 동기화한다.
     * (DefectDetail 측의 inspectionLog 참조도 함께 설정)
     *
     * @param defect 추가할 결함 상세 엔티티
     */
    public void addDefect(DefectDetail defect) {
        this.defects.add(defect);
    }
}
