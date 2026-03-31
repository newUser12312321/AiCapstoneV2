package com.inspection.service;

import com.inspection.domain.entity.DefectDetail;
import com.inspection.domain.entity.InspectionLog;
import com.inspection.domain.enums.InspectionResult;
import com.inspection.dto.DefectDetailDto;
import com.inspection.dto.InspectionRequestDto;
import com.inspection.dto.InspectionResponseDto;
import com.inspection.repository.InspectionLogRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 검사 이력 비즈니스 로직 서비스
 *
 * <p>컨트롤러에서 요청을 받아 엔티티를 구성하고 DB에 저장하며,
 * 대시보드에 필요한 데이터를 조회·집계하여 반환한다.
 *
 * @Slf4j: Lombok이 log 변수를 자동 생성 (log.info, log.warn 등 사용 가능)
 * @RequiredArgsConstructor: final 필드를 파라미터로 받는 생성자를 자동 생성
 *                           → @Autowired 없이 의존성 주입
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class InspectionService {

    private final InspectionLogRepository inspectionLogRepository;

    // ── 검사 결과 저장 ────────────────────────────────────────────────────────

    /**
     * 라즈베리파이로부터 수신한 검사 결과를 DB에 저장한다.
     *
     * <p>처리 순서:
     * 1. RequestDto → InspectionLog 엔티티 변환
     * 2. 결함 목록(DefectDetailDto) → DefectDetail 엔티티 변환 및 연관 설정
     * 3. InspectionLog 저장 (Cascade로 DefectDetail도 함께 저장)
     * 4. 저장된 엔티티 → ResponseDto 변환 후 반환
     *
     * @param dto 엣지 디바이스가 전송한 검사 결과 DTO
     * @return 저장된 검사 이력 응답 DTO (id 포함)
     */
    @Transactional
    public InspectionResponseDto saveInspectionResult(InspectionRequestDto dto) {
        log.info("[검사 수신] 디바이스: {}, 결과: {}, 시각: {}",
                dto.getDeviceId(), dto.getResult(), dto.getInspectedAt());

        // 1. 요청 DTO → InspectionLog 엔티티 구성
        InspectionLog log = InspectionLog.builder()
                .deviceId(dto.getDeviceId())
                .result(InspectionResult.valueOf(dto.getResult()))
                .fiducial1X(dto.getFiducial1X())
                .fiducial1Y(dto.getFiducial1Y())
                .fiducial2X(dto.getFiducial2X())
                .fiducial2Y(dto.getFiducial2Y())
                .angleErrorDeg(dto.getAngleErrorDeg())
                .inferenceTimeMs(dto.getInferenceTimeMs())
                .totalTimeMs(dto.getTotalTimeMs())
                .imagePath(dto.getImagePath())
                .inspectedAt(dto.getInspectedAt())
                .build();

        // 2. 결함 목록 변환 및 양방향 연관 설정
        if (dto.getDefects() != null) {
            dto.getDefects().forEach(defectDto -> {
                DefectDetail defect = DefectDetail.builder()
                        .inspectionLog(log)      // 외래키 설정
                        .defectType(defectDto.getDefectType())
                        .confidence(defectDto.getConfidence())
                        .bboxX(defectDto.getBboxX())
                        .bboxY(defectDto.getBboxY())
                        .bboxWidth(defectDto.getBboxWidth())
                        .bboxHeight(defectDto.getBboxHeight())
                        .build();
                log.addDefect(defect);           // 부모 엔티티 리스트에 추가
            });
        }

        // 3. 저장 (CascadeType.ALL로 DefectDetail도 함께 INSERT)
        InspectionLog saved = inspectionLogRepository.save(log);
        InspectionService.log.info("[검사 저장 완료] ID: {}", saved.getId());

        // 4. 저장된 엔티티 → 응답 DTO 변환 후 반환
        return InspectionResponseDto.from(saved);
    }

    // ── 조회 ─────────────────────────────────────────────────────────────────

    /**
     * 전체 검사 이력을 최신순으로 조회한다.
     * 대시보드 이력 테이블에 표시하는 기본 목록.
     *
     * @return 전체 검사 이력 응답 DTO 목록
     */
    @Transactional(readOnly = true)
    public List<InspectionResponseDto> getAllInspections() {
        return inspectionLogRepository.findAll().stream()
                .map(InspectionResponseDto::from)
                .collect(Collectors.toList());
    }

    /**
     * 단건 검사 이력을 ID로 조회한다.
     * 프론트엔드 결함 상세 뷰어에 사용.
     *
     * @param id 검사 로그 ID
     * @return 검사 이력 응답 DTO
     * @throws IllegalArgumentException ID에 해당하는 레코드가 없을 때
     */
    @Transactional(readOnly = true)
    public InspectionResponseDto getInspectionById(Long id) {
        InspectionLog log = inspectionLogRepository.findById(id)
                .orElseThrow(() ->
                        new IllegalArgumentException("검사 이력을 찾을 수 없습니다. ID: " + id));
        return InspectionResponseDto.from(log);
    }

    /**
     * 최근 N건의 검사 이력을 조회한다.
     * 대시보드 실시간 피드 영역에 사용.
     *
     * @param limit 조회 건수
     */
    @Transactional(readOnly = true)
    public List<InspectionResponseDto> getRecentInspections(int limit) {
        return inspectionLogRepository.findTopNByOrderByInspectedAtDesc(limit).stream()
                .map(InspectionResponseDto::from)
                .collect(Collectors.toList());
    }

    // ── 통계 집계 ─────────────────────────────────────────────────────────────

    /**
     * 전체 검사 통계 요약을 집계하여 반환한다.
     * 대시보드 상단 StatCard 컴포넌트에 표시.
     *
     * <p>반환 Map 키:
     * - totalCount: 전체 검사 건수
     * - passCount:  합격 건수
     * - failCount:  불합격 건수
     * - failRate:   불량률 (0.0 ~ 1.0)
     *
     * @return 통계 집계 Map
     */
    @Transactional(readOnly = true)
    public Map<String, Object> getStatsSummary() {
        long total = inspectionLogRepository.count();
        long pass  = inspectionLogRepository.countByResult(InspectionResult.PASS);
        long fail  = inspectionLogRepository.countByResult(InspectionResult.FAIL);
        double failRate = (total > 0) ? (double) fail / total : 0.0;

        return Map.of(
                "totalCount", total,
                "passCount",  pass,
                "failCount",  fail,
                "failRate",   Math.round(failRate * 10000.0) / 100.0  // 소수점 2자리 %
        );
    }

    /**
     * 특정 기간의 검사 이력을 조회한다.
     * 대시보드 날짜 필터 기능에 사용.
     *
     * @param from 시작 시각
     * @param to   종료 시각
     */
    @Transactional(readOnly = true)
    public List<InspectionResponseDto> getInspectionsByPeriod(
            LocalDateTime from, LocalDateTime to) {
        return inspectionLogRepository
                .findByInspectedAtBetweenOrderByInspectedAtDesc(from, to)
                .stream()
                .map(InspectionResponseDto::from)
                .collect(Collectors.toList());
    }
}
