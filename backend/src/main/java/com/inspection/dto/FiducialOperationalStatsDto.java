package com.inspection.dto;

import java.time.LocalDateTime;

/**
 * 피듀셜 관련 운영 지표 (정답 라벨 없이 DB 이력만으로 집계).
 *
 * <p>※ mAP 같은 "모델 정확도"가 아니라, 저장된 좌표·각도로부터 계산한 비율이다.
 */
public record FiducialOperationalStatsDto(
        LocalDateTime periodFrom,
        LocalDateTime periodTo,
        long totalInspections,
        /** fiducial1·2 좌표가 모두 존재하는 검사 비율 (%) */
        double fiducialPairRatePct,
        /** angleErrorDeg가 서버 설정 허용 각도 이하인 검사 비율 (%) */
        double alignmentPassRatePct,
        /** 집계에 사용한 최대 허용 각도 (°), 엣지 MAX_ANGLE_ERROR_DEG와 맞출 것 */
        double maxAngleErrorDeg
) {}
