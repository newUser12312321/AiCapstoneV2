/**
 * 검사 데이터 조회 React Query 커스텀 훅 모음
 *
 * React Query(TanStack Query v5)의 useQuery를 래핑하여
 * 각 컴포넌트에서 데이터 패칭·캐싱·자동 갱신을 단순하게 사용하도록 한다.
 *
 * 자동 폴링(refetchInterval):
 *   엣지 디바이스가 실시간으로 검사 결과를 전송하므로
 *   대시보드는 5초마다 자동 갱신하여 최신 데이터를 표시한다.
 */

import { useQuery } from '@tanstack/react-query'
import {
  fetchAllInspections,
  fetchFiducialOperationalStats,
  fetchInspectionById,
  fetchInspectionsByPeriod,
  fetchRecentInspections,
  fetchStats,
} from '@/api/inspectionApi'
import type { TrendDataPoint } from '@/types/inspection'

/** React Query 캐시 키 상수 — 오타 방지를 위해 중앙 관리 */
export const QUERY_KEYS = {
  stats:        ['inspections', 'stats']         as const,
  fiducialStats: ['inspections', 'stats', 'fiducial'] as const,
  all:          ['inspections', 'all']           as const,
  recent:       (limit: number) => ['inspections', 'recent', limit] as const,
  byId:         (id: number)    => ['inspections', id]              as const,
  byPeriod:     (from: string, to: string) =>
                  ['inspections', 'period', from, to]               as const,
}

// ── 통계 훅 ──────────────────────────────────────────────────────────────────

/**
 * 전체 통계 요약을 조회한다. (totalCount, passCount, failCount, failRate)
 * 5초마다 자동 갱신하여 대시보드 StatCard를 최신 상태로 유지한다.
 */
export function useStats() {
  return useQuery({
    queryKey:        QUERY_KEYS.stats,
    queryFn:         fetchStats,
    refetchInterval: 5_000,   // 5초마다 자동 갱신
    staleTime:       3_000,   // 3초 이내 데이터는 fresh로 간주 (불필요한 재요청 방지)
  })
}

/**
 * 피듀셜 운영 지표 (오늘 기준, 서버가 기간을 결정). 기간 커스텀은 필요 시 fetch에 인자 추가.
 */
export function useFiducialOperationalStats() {
  return useQuery({
    queryKey:        QUERY_KEYS.fiducialStats,
    queryFn:         () => fetchFiducialOperationalStats(),
    refetchInterval: 5_000,
    staleTime:       3_000,
  })
}

// ── 이력 목록 훅 ──────────────────────────────────────────────────────────────

/**
 * 전체 검사 이력 목록을 조회한다.
 * InspectionTable, TrendChart에서 사용.
 */
export function useAllInspections() {
  return useQuery({
    queryKey:        QUERY_KEYS.all,
    queryFn:         fetchAllInspections,
    refetchInterval: 5_000,
    staleTime:       3_000,
  })
}

/**
 * 최근 N건의 검사 이력을 조회한다.
 * 대시보드 실시간 피드에 사용.
 *
 * @param limit 조회 건수 (기본값 10)
 */
export function useRecentInspections(limit = 10) {
  return useQuery({
    queryKey:        QUERY_KEYS.recent(limit),
    queryFn:         () => fetchRecentInspections(limit),
    refetchInterval: 5_000,
    staleTime:       3_000,
  })
}

/**
 * 단건 검사 이력을 ID로 조회한다.
 * DefectViewer(바운딩박스 상세 뷰)에서 사용.
 *
 * @param id 조회할 검사 로그 ID (undefined이면 쿼리 비활성화)
 */
export function useInspectionById(id: number | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.byId(id!),
    queryFn:  () => fetchInspectionById(id!),
    enabled:  id !== undefined,  // id가 없으면 쿼리 실행 안 함
  })
}

/**
 * 기간 필터 검사 이력을 조회한다.
 * HistoryPage의 날짜 필터 기능에 사용.
 *
 * @param from 시작 시각 (ISO 8601 문자열)
 * @param to   종료 시각 (ISO 8601 문자열)
 */
export function useInspectionsByPeriod(from: string, to: string) {
  return useQuery({
    queryKey: QUERY_KEYS.byPeriod(from, to),
    queryFn:  () => fetchInspectionsByPeriod(from, to),
    enabled:  Boolean(from && to),  // 날짜가 모두 입력된 경우만 실행
    staleTime: 10_000,
  })
}

// ── 파생 데이터 훅 ────────────────────────────────────────────────────────────

/**
 * 전체 이력 데이터를 시간대별로 집계하여 TrendChart용 데이터를 반환한다.
 *
 * 집계 방식: inspectedAt의 시(hour) 단위로 그룹핑하여
 * 각 시간대의 PASS/FAIL 건수를 카운트한다.
 *
 * 예시 반환값:
 *   [{ label: "09:00", pass: 12, fail: 2 }, ...]
 */
export function useTrendData(): { data: TrendDataPoint[]; isLoading: boolean } {
  const { data: logs = [], isLoading } = useAllInspections()

  if (isLoading || logs.length === 0) {
    return { data: [], isLoading }
  }

  // 최근 24시간 데이터만 필터링
  const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000)
  const recent = logs.filter((l) => new Date(l.inspectedAt) >= cutoff)

  // 시간(HH:00) 단위로 그룹핑
  const grouped: Record<string, { pass: number; fail: number }> = {}

  recent.forEach((log) => {
    const d = new Date(log.inspectedAt)
    // "HH:00" 형식 레이블 생성
    const label = `${String(d.getHours()).padStart(2, '0')}:00`

    if (!grouped[label]) grouped[label] = { pass: 0, fail: 0 }

    if (log.result === 'PASS') grouped[label].pass++
    else                       grouped[label].fail++
  })

  // 시간 오름차순 정렬
  const trendData: TrendDataPoint[] = Object.entries(grouped)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([label, counts]) => ({ label, ...counts }))

  return { data: trendData, isLoading }
}
