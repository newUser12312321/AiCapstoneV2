package com.inspection.repository;

import com.inspection.domain.entity.DefectDetail;
import org.springframework.data.jpa.repository.JpaRepository;

/**
 * 결함 상세 JPA 리포지토리.
 * <p>전체 검사 이력 삭제 시 자식 행을 먼저 배치 삭제하는 데 사용한다.
 */
public interface DefectDetailRepository extends JpaRepository<DefectDetail, Long> {
}
