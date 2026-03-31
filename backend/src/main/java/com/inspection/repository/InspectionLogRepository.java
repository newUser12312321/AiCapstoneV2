package com.inspection.repository;

import com.inspection.domain.entity.InspectionLog;
import com.inspection.domain.enums.InspectionResult;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;

/**
 * InspectionLog JPA 리포지토리
 *
 * <p>JpaRepository<InspectionLog, Long>을 상속받아
 * save(), findById(), findAll(), deleteById() 등 기본 CRUD를 자동으로 제공한다.
 *
 * <p>아래에는 대시보드에 필요한 쿼리 메서드를 추가로 선언한다.
 * Spring Data JPA가 메서드명을 파싱하여 자동으로 SQL을 생성한다.
 */
public interface InspectionLogRepository extends JpaRepository<InspectionLog, Long> {

    /**
     * 특정 기간 내 모든 검사 이력을 시각 내림차순으로 조회
     * → 대시보드 이력 테이블에 표시
     *
     * @param from 시작 시각 (포함)
     * @param to   종료 시각 (포함)
     */
    List<InspectionLog> findByInspectedAtBetweenOrderByInspectedAtDesc(
            LocalDateTime from, LocalDateTime to);

    /**
     * 특정 판정 결과(PASS/FAIL)로 필터링한 이력 조회
     * → 불량 목록만 뽑는 필터 기능
     *
     * @param result InspectionResult.PASS 또는 FAIL
     */
    List<InspectionLog> findByResultOrderByInspectedAtDesc(InspectionResult result);

    /**
     * 전체 검사 건수 대비 FAIL 비율 계산용 카운트 쿼리
     * (Spring Data 메서드 네이밍으로 COUNT 자동 생성)
     *
     * @param result 집계할 판정 결과
     */
    long countByResult(InspectionResult result);

    /**
     * 최근 N건의 검사 이력 조회 (실시간 모니터링 피드)
     * JPQL 직접 작성: Limit는 JPQL 표준이 아니므로 쿼리 + Pageable 대신 직접 처리
     *
     * @param limit 조회할 최대 건수
     */
    @Query("SELECT l FROM InspectionLog l ORDER BY l.inspectedAt DESC LIMIT :limit")
    List<InspectionLog> findTopNByOrderByInspectedAtDesc(@Param("limit") int limit);

    /**
     * 특정 디바이스의 검사 이력만 조회
     * → 다중 라인 운영 시 라인별 필터링
     *
     * @param deviceId 디바이스 식별자
     */
    List<InspectionLog> findByDeviceIdOrderByInspectedAtDesc(String deviceId);
}
