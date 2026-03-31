/**
 * 상단 헤더 컴포넌트
 *
 * 서비스명, 라이브 상태 표시 인디케이터, 마지막 갱신 시각을 표시한다.
 * useStats()의 isLoading/isFetching 상태로 실시간 갱신 여부를 시각화한다.
 */

import { Activity, Cpu } from 'lucide-react'
import { useStats } from '@/hooks/useInspectionData'

export default function Header() {
  const { isFetching, dataUpdatedAt } = useStats()

  /* dataUpdatedAt: 마지막으로 서버에서 데이터를 받은 Unix 타임스탬프(ms) */
  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString('ko-KR')
    : '--:--:--'

  return (
    <header className="h-16 bg-gray-900 border-b border-gray-800 flex items-center px-6 shrink-0">

      {/* 서비스 로고 + 이름 */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
          <Cpu size={16} className="text-white" />
        </div>
        <div>
          <h1 className="text-sm font-bold text-white leading-none">PCB 비전 검사</h1>
          <p className="text-xs text-gray-500 mt-0.5">Edge Vision Inspection Station</p>
        </div>
      </div>

      {/* 오른쪽 영역: 라이브 상태 + 갱신 시각 */}
      <div className="ml-auto flex items-center gap-4">

        {/* 실시간 폴링 상태 인디케이터 */}
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              isFetching ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'
            }`}
          />
          <span className="text-xs text-gray-400">
            {isFetching ? '갱신 중...' : 'LIVE'}
          </span>
        </div>

        {/* 마지막 데이터 갱신 시각 */}
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <Activity size={12} />
          <span>최종 갱신: {lastUpdated}</span>
        </div>
      </div>
    </header>
  )
}
