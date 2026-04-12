/**
 * 프론트엔드 전체에서 사용하는 TypeScript 인터페이스 정의
 *
 * Spring Boot InspectionResponseDto와 1:1로 매핑되므로
 * 백엔드 DTO가 변경되면 이 파일도 함께 수정해야 한다.
 */

// ── 결함 상세 ─────────────────────────────────────────────────────────────────

/** 개별 결함 정보 (바운딩 박스 포함) */
export interface DefectDetail {
  defectType: string      // "TRACE_OPEN" | "METAL_DAMAGE" | "FIDUCIAL_MISSING"
  confidence: number      // 0.0 ~ 1.0
  bboxX: number           // 좌상단 X (픽셀)
  bboxY: number           // 좌상단 Y (픽셀)
  bboxWidth: number       // 너비 (픽셀)
  bboxHeight: number      // 높이 (픽셀)
}

// ── 검사 이력 ─────────────────────────────────────────────────────────────────

/** 최종 판정 결과 타입 */
export type InspectionResultType = 'PASS' | 'FAIL'

/** 검사 이력 단건 레코드 (GET /api/inspections 응답 요소) */
export interface InspectionLog {
  id: number
  deviceId: string
  result: InspectionResultType

  /** 피듀셜 마크 좌표 (탐지 실패 시 null) */
  fiducial1X: number | null
  fiducial1Y: number | null
  fiducial2X: number | null
  fiducial2Y: number | null

  /** Stage1 YOLO 탐지 신뢰도 (0~1, 미전송·구 이력은 null/undefined) */
  fiducial1Confidence?: number | null
  fiducial2Confidence?: number | null

  /** 촬영 시 기울기 (°), 보정 적용 전 측정값 */
  angleErrorDeg: number | null

  /** 추론 소요 시간 (ms) */
  inferenceTimeMs: number | null

  /** 전체 처리 시간 (ms) */
  totalTimeMs: number | null

  /** 캡처 이미지 경로 */
  imagePath: string | null

  /** 검사 수행 시각 (ISO 8601) */
  inspectedAt: string

  /** 서버 레코드 생성 시각 */
  createdAt: string

  /** 탐지된 결함 목록 */
  defects: DefectDetail[]
}

// ── 통계 ─────────────────────────────────────────────────────────────────────

/** GET /api/inspections/stats 응답 */
export interface InspectionStats {
  totalCount: number   // 전체 검사 건수
  passCount:  number   // 합격 건수
  failCount:  number   // 불합격 건수
  failRate:   number   // 불량률 (0.0 ~ 100.0, %)
}

// ── 차트용 파생 타입 ──────────────────────────────────────────────────────────

/** TrendChart에서 사용하는 시간대별 집계 데이터 포인트 */
export interface TrendDataPoint {
  label: string    // X축 레이블 (예: "14:30", "03/31")
  pass:  number
  fail:  number
}

/** PassFailChart에서 사용하는 도넛 차트 데이터 */
export interface PieDataPoint {
  name:  string
  value: number
  fill:  string
}

// ── 결함 종류 한글 매핑 ───────────────────────────────────────────────────────

export const DEFECT_LABEL: Record<string, string> = {
  TRACE_OPEN:       '단선',
  METAL_DAMAGE:     '까짐',
  FIDUCIAL_MISSING: '마크 누락',
  // Ultralytics data.yaml / Colab 병합 클래스 (소문자 snake_case)
  trace_open:     '단선',
  metal_damage:   '까짐',
  pinhole:        '핀홀',
  short:          '단락',
  // PCB 통합 YOLO (data.yaml 클래스명과 동일)
  mount_hole:           '고정홀',
  gold_finger_row:      '금핑거 열',
  fiducial:             '피듀셜',
  smd_array_block:      'SMD 어레이',
  ic_chip:              'IC',
  edge_connector_zone:  '에지 커넥터',
}

/** 결함 종류별 표시 색상 (Tailwind 클래스 호환 hex) */
export const DEFECT_COLOR: Record<string, string> = {
  TRACE_OPEN:       '#f97316',  // orange-500
  METAL_DAMAGE:     '#ef4444',  // red-500
  FIDUCIAL_MISSING: '#a855f7',  // purple-500
  trace_open:       '#f97316',
  metal_damage:     '#ef4444',
  pinhole:          '#eab308',  // yellow-500
  short:            '#dc2626',  // red-600
  mount_hole:           '#22d3ee',  // cyan-400
  gold_finger_row:      '#fb7185',  // rose-400
  fiducial:             '#4ade80',  // green-400
  smd_array_block:      '#a78bfa',  // violet-400
  ic_chip:              '#fbbf24',  // amber-400
  edge_connector_zone:  '#f472b6',  // pink-400
}

/** 표시용 라벨 (한글 매핑 없으면 원문 그대로) */
export function defectDisplayName(defectType: string): string {
  return (
    DEFECT_LABEL[defectType] ??
    DEFECT_LABEL[defectType.toUpperCase()] ??
    defectType
  )
}
