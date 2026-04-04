/**
 * 피듀셜 운영 지표 — GET /api/inspections/stats/fiducial (기본: 오늘 0시~현재)
 *
 * 정답 라벨이 없으므로 "모델 정확도"가 아니라 DB에 남은 좌표·각도로부터 한 비율이다.
 */

import { Crosshair, Waypoints } from 'lucide-react'
import clsx from 'clsx'
import { useFiducialOperationalStats } from '@/hooks/useInspectionData'

function MiniStat({
  title,
  value,
  caption,
  icon: Icon,
  theme,
}: {
  title: string
  value: string
  caption: string
  icon: typeof Crosshair
  theme: 'cyan' | 'amber'
}) {
  const colors =
    theme === 'cyan'
      ? { bg: 'bg-cyan-500/10', text: 'text-cyan-400', border: 'border-cyan-500/20' }
      : { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20' }

  return (
    <div className={clsx('bg-gray-900 rounded-xl p-5 border', colors.border)}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-gray-400 font-medium">{title}</span>
        <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center', colors.bg)}>
          <Icon size={18} className={colors.text} />
        </div>
      </div>
      <p className="text-3xl font-bold text-white tracking-tight">{value}</p>
      <p className="text-xs text-gray-500 mt-1.5">{caption}</p>
    </div>
  )
}

function SkeletonPair() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {[0, 1].map((i) => (
        <div
          key={i}
          className="bg-gray-900 rounded-xl p-5 border border-gray-800 animate-pulse"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="h-4 w-28 bg-gray-800 rounded" />
            <div className="w-9 h-9 bg-gray-800 rounded-lg" />
          </div>
          <div className="h-8 w-20 bg-gray-800 rounded mt-1" />
          <div className="h-3 w-full bg-gray-800 rounded mt-3" />
        </div>
      ))}
    </div>
  )
}

export default function FiducialOpsCardGroup() {
  const { data, isLoading, isError } = useFiducialOperationalStats()

  if (isLoading) {
    return (
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-gray-300">피듀셜 운영 지표</h3>
        <SkeletonPair />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <p className="text-xs text-gray-500">
        피듀셜 운영 지표를 불러오지 못했습니다.
      </p>
    )
  }

  const n = data.totalInspections
  const periodNote =
    n === 0
      ? '해당 기간 검사 0건'
      : `기간 내 ${n.toLocaleString()}건 중 (오늘 0시~현재 · 서버 Asia/Seoul)`

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-300">피듀셜 운영 지표</h3>
        <span className="text-[11px] text-gray-500">{periodNote}</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <MiniStat
          title="피듀셜 쌍 검출률"
          value={`${data.fiducialPairRatePct.toFixed(1)}%`}
          caption="fiducial1·2 좌표가 모두 저장된 검사 비율 (정답 라벨 없음)"
          icon={Crosshair}
          theme="cyan"
        />
        <MiniStat
          title="정렬 각도 통과율"
          value={`${data.alignmentPassRatePct.toFixed(1)}%`}
          caption={`angleErrorDeg ≤ ${data.maxAngleErrorDeg}° 인 검사 비율 (엣지 설정과 맞추려면 application.yml 참고)`}
          icon={Waypoints}
          theme="amber"
        />
      </div>
      <p className="text-[11px] text-gray-600 leading-relaxed">
        이 수치는 mAP 같은 모델 검증 정확도가 아니라, 운영 중 저장된 데이터만으로 집계한 추정치입니다.
      </p>
    </div>
  )
}
