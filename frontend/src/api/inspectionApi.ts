/**
 * Spring Boot REST API 클라이언트
 *
 * Axios 인스턴스를 생성하고 인터셉터로 공통 에러 처리를 설정한다.
 * vite.config.ts의 proxy 설정 덕분에 /api/* 요청은 자동으로
 * http://localhost:8080 으로 포워딩된다.
 */

import axios from 'axios'
import type { InspectionLog, InspectionStats } from '@/types/inspection'

// ── Axios 인스턴스 생성 ───────────────────────────────────────────────────────

const apiClient = axios.create({
  /* Vite 프록시(/api → :8080)를 사용하므로 baseURL은 /api만 지정 */
  baseURL: '/api',
  timeout: 10_000,  // 10초 응답 없으면 에러
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

// ── 응답 인터셉터: 전역 에러 처리 ─────────────────────────────────────────────

apiClient.interceptors.response.use(
  /* 성공 응답은 그대로 통과 */
  (response) => response,
  /* 에러 응답은 콘솔에 로깅 후 reject */
  (error) => {
    const status  = error.response?.status
    const message = error.response?.data?.message ?? error.message

    if (status === 404) {
      console.warn(`[API] 리소스 없음: ${message}`)
    } else if (status >= 500) {
      console.error(`[API] 서버 오류 ${status}: ${message}`)
    } else {
      console.error(`[API] 요청 오류: ${message}`)
    }

    return Promise.reject(error)
  }
)

// ── API 함수 모음 ─────────────────────────────────────────────────────────────

/**
 * 전체 검사 이력 목록을 조회한다.
 * 대시보드 이력 테이블 및 트렌드 차트에 사용.
 */
export const fetchAllInspections = async (): Promise<InspectionLog[]> => {
  const { data } = await apiClient.get<InspectionLog[]>('/inspections')
  return data
}

/**
 * 단건 검사 이력을 ID로 조회한다.
 * DefectViewer에서 바운딩박스 렌더링에 사용.
 *
 * @param id 검사 로그 ID
 */
export const fetchInspectionById = async (id: number): Promise<InspectionLog> => {
  const { data } = await apiClient.get<InspectionLog>(`/inspections/${id}`)
  return data
}

/**
 * 최근 N건의 검사 이력을 조회한다.
 * 대시보드 실시간 피드 영역에 사용.
 *
 * @param limit 조회 건수 (기본값 10)
 */
export const fetchRecentInspections = async (limit = 10): Promise<InspectionLog[]> => {
  const { data } = await apiClient.get<InspectionLog[]>('/inspections/recent', {
    params: { limit },
  })
  return data
}

/**
 * 전체 검사 통계 요약을 조회한다.
 * 대시보드 상단 StatCard에 사용.
 */
export const fetchStats = async (): Promise<InspectionStats> => {
  const { data } = await apiClient.get<InspectionStats>('/inspections/stats')
  return data
}

/**
 * 특정 기간의 검사 이력을 조회한다.
 * 이력 페이지 날짜 필터에 사용.
 *
 * @param from 시작 시각 (ISO 8601)
 * @param to   종료 시각 (ISO 8601)
 */
export const fetchInspectionsByPeriod = async (
  from: string,
  to: string
): Promise<InspectionLog[]> => {
  const { data } = await apiClient.get<InspectionLog[]>('/inspections/period', {
    params: { from, to },
  })
  return data
}
