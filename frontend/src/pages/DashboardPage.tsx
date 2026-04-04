/**
 * 메인 대시보드 페이지
 *
 * 레이아웃 구성:
 * ┌──────────────────────────────────────────────────┐
 * │  [StatCard × 4]  전체/합격/불합격/불량률           │
 * ├─────────────────────┬────────────────────────────│
 * │  PassFailChart      │  TrendChart                │
 * │  (도넛 차트)          │  (스택 막대 차트)            │
 * ├─────────────────────┴────────────────────────────│
 * │  InspectionTable  (최근 15건 실시간 피드)           │
 * └──────────────────────────────────────────────────┘
 */

import StatCardGroup from '@/components/dashboard/StatCard'
import FiducialOpsCardGroup from '@/components/dashboard/FiducialOpsCardGroup'
import PassFailChart from '@/components/dashboard/PassFailChart'
import TrendChart from '@/components/dashboard/TrendChart'
import InspectionTable from '@/components/inspection/InspectionTable'
import { useRecentInspections } from '@/hooks/useInspectionData'

export default function DashboardPage() {
  /* 최근 15건 — 대시보드 하단 실시간 피드 테이블 */
  const { data: recentLogs = [], isLoading } = useRecentInspections(15)

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">

      {/* 페이지 제목 */}
      <div>
        <h2 className="text-lg font-bold text-white">실시간 대시보드</h2>
        <p className="text-xs text-gray-500 mt-0.5">5초마다 자동 갱신 · 라즈베리파이 엣지 노드 연결 중</p>
      </div>

      {/* 1행: 통계 카드 4개 */}
      <StatCardGroup />

      {/* 1b행: 피듀셜 운영 지표 (오늘 기준) */}
      <FiducialOpsCardGroup />

      {/* 2행: 도넛 차트 + 트렌드 차트 */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* PassFailChart: 2/5 너비 */}
        <div className="lg:col-span-2">
          <PassFailChart />
        </div>
        {/* TrendChart: 3/5 너비 */}
        <div className="lg:col-span-3">
          <TrendChart />
        </div>
      </div>

      {/* 3행: 실시간 이력 테이블 */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-300">최근 검사 이력</h2>
          <span className="text-xs text-gray-500">최근 15건</span>
        </div>
        <InspectionTable logs={recentLogs} isLoading={isLoading} />
      </div>
    </div>
  )
}
