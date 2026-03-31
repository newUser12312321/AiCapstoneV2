/**
 * 통계 요약 카드 컴포넌트
 *
 * 대시보드 상단에 4개 배치되어 전체 검사 건수, 합격, 불합격, 불량률을 표시한다.
 * 로딩 중에는 Skeleton 애니메이션을 보여준다.
 */

import type { LucideIcon } from 'lucide-react'
import { CheckCircle, XCircle, Activity, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import { useStats } from '@/hooks/useInspectionData'

// ── 개별 카드 컴포넌트 ────────────────────────────────────────────────────────

interface StatCardProps {
  title:   string
  value:   string | number
  icon:    LucideIcon
  /** 아이콘 배경 + 텍스트 색상 테마 */
  theme:   'indigo' | 'green' | 'red' | 'yellow'
  /** 카드 하단에 표시할 보조 설명 (선택) */
  caption?: string
}

const THEME_MAP: Record<StatCardProps['theme'], { bg: string; text: string; border: string }> = {
  indigo: { bg: 'bg-indigo-500/10', text: 'text-indigo-400', border: 'border-indigo-500/20' },
  green:  { bg: 'bg-green-500/10',  text: 'text-green-400',  border: 'border-green-500/20'  },
  red:    { bg: 'bg-red-500/10',    text: 'text-red-400',    border: 'border-red-500/20'    },
  yellow: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/20' },
}

function StatCard({ title, value, icon: Icon, theme, caption }: StatCardProps) {
  const colors = THEME_MAP[theme]

  return (
    <div className={clsx(
      'bg-gray-900 rounded-xl p-5 border',
      colors.border
    )}>
      {/* 상단: 아이콘 + 제목 */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-gray-400 font-medium">{title}</span>
        <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center', colors.bg)}>
          <Icon size={18} className={colors.text} />
        </div>
      </div>

      {/* 주요 수치 */}
      <p className="text-3xl font-bold text-white tracking-tight">{value}</p>

      {/* 보조 설명 */}
      {caption && (
        <p className="text-xs text-gray-500 mt-1.5">{caption}</p>
      )}
    </div>
  )
}

// ── 스켈레톤 (로딩 상태) ─────────────────────────────────────────────────────

function StatCardSkeleton() {
  return (
    <div className="bg-gray-900 rounded-xl p-5 border border-gray-800 animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <div className="h-4 w-20 bg-gray-800 rounded" />
        <div className="w-9 h-9 bg-gray-800 rounded-lg" />
      </div>
      <div className="h-8 w-24 bg-gray-800 rounded mt-1" />
      <div className="h-3 w-32 bg-gray-800 rounded mt-3" />
    </div>
  )
}

// ── 통계 카드 그룹 (4개 묶음) ─────────────────────────────────────────────────

/**
 * 통계 API 데이터를 가져와 4개 StatCard를 렌더링한다.
 * 데이터 패칭은 useStats()에 위임하여 컴포넌트 코드를 단순하게 유지한다.
 */
export default function StatCardGroup() {
  const { data: stats, isLoading, isError } = useStats()

  /* 로딩 중: 스켈레톤 4개 표시 */
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)}
      </div>
    )
  }

  /* 오류 시: 안내 메시지 */
  if (isError || !stats) {
    return (
      <div className="col-span-4 text-center py-8 text-gray-500 text-sm">
        통계 데이터를 불러올 수 없습니다. 서버 연결을 확인하세요.
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard
        title="전체 검사"
        value={stats.totalCount.toLocaleString()}
        icon={Activity}
        theme="indigo"
        caption="누적 검사 건수"
      />
      <StatCard
        title="합격 (PASS)"
        value={stats.passCount.toLocaleString()}
        icon={CheckCircle}
        theme="green"
        caption={`전체의 ${(100 - stats.failRate).toFixed(1)}%`}
      />
      <StatCard
        title="불합격 (FAIL)"
        value={stats.failCount.toLocaleString()}
        icon={XCircle}
        theme="red"
        caption={`전체의 ${stats.failRate.toFixed(1)}%`}
      />
      <StatCard
        title="불량률"
        value={`${stats.failRate.toFixed(2)}%`}
        icon={AlertTriangle}
        /* 불량률 3% 이상이면 빨간색, 미만이면 노란색 */
        theme={stats.failRate >= 3 ? 'red' : 'yellow'}
        caption="FAIL / 전체 검사"
      />
    </div>
  )
}
