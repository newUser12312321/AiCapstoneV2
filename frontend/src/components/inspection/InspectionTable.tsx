/**
 * 검사 이력 테이블 컴포넌트
 *
 * 검사 이력 목록을 테이블로 표시하며, 행 클릭 시 DefectViewer를 열어
 * 바운딩박스 상세 정보를 확인할 수 있다.
 *
 * 기능:
 * - PASS/FAIL 뱃지 색상 구분
 * - 결함 종류 태그 (단선, 까짐 등)
 * - 각도 오차 표시
 * - 클릭으로 상세 DefectViewer 연동
 */

import { useState } from 'react'
import { ChevronRight, AlertCircle } from 'lucide-react'
import clsx from 'clsx'
import type { InspectionLog } from '@/types/inspection'
import { defectDisplayName, DEFECT_COLOR } from '@/types/inspection'
import DefectViewer from './DefectViewer'

// ── 보조 컴포넌트 ─────────────────────────────────────────────────────────────

/** PASS / FAIL 결과 뱃지 */
function ResultBadge({ result }: { result: 'PASS' | 'FAIL' }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold',
        result === 'PASS'
          ? 'bg-green-500/15 text-green-400 ring-1 ring-green-500/30'
          : 'bg-red-500/15 text-red-400 ring-1 ring-red-500/30'
      )}
    >
      {result}
    </span>
  )
}

/** 결함 종류 태그 목록 */
function DefectTags({ defects }: { defects: InspectionLog['defects'] }) {
  if (!defects.length) {
    return <span className="text-xs text-gray-600">—</span>
  }

  const grouped = new Map<
    string,
    { count: number; color: string }
  >()
  defects.forEach((d) => {
    const label = defectDisplayName(d.defectType)
    const prev = grouped.get(label)
    if (prev) {
      prev.count += 1
      return
    }
    grouped.set(label, {
      count: 1,
      color: DEFECT_COLOR[d.defectType] ?? '#9ca3af',
    })
  })

  return (
    <div className="flex flex-wrap gap-1">
      {Array.from(grouped.entries()).map(([label, meta]) => (
        <span
          key={label}
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium"
          style={{
            backgroundColor: `${meta.color}22`,
            color: meta.color,
          }}
        >
          <AlertCircle size={10} />
          {`${label} X${meta.count}`}
        </span>
      ))}
    </div>
  )
}

/** 날짜/시각 포맷 유틸 */
function formatDateTime(iso: string): { date: string; time: string } {
  const d = new Date(iso)
  return {
    date: d.toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' }),
    time: d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
  }
}

// ── 스켈레톤 ─────────────────────────────────────────────────────────────────

function TableSkeleton() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <tr key={i} className="border-b border-gray-800 animate-pulse">
          {Array.from({ length: 8 }).map((_, j) => (
            <td key={j} className="px-4 py-3">
              <div className="h-3.5 bg-gray-800 rounded w-3/4" />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────

interface InspectionTableProps {
  /** 표시할 검사 이력 데이터 */
  logs: InspectionLog[]
  /** 데이터 로딩 중 여부 */
  isLoading?: boolean
  /** 결과 필터 (undefined이면 전체 표시) */
  resultFilter?: 'PASS' | 'FAIL' | undefined
}

export default function InspectionTable({
  logs,
  isLoading = false,
  resultFilter,
}: InspectionTableProps) {
  /* 클릭된 검사 ID — DefectViewer에 전달 */
  const [selectedId, setSelectedId] = useState<number | undefined>()

  /* 결과 필터 적용 */
  const filtered = resultFilter
    ? logs.filter((l) => l.result === resultFilter)
    : logs

  return (
    <>
      <div className="overflow-x-auto rounded-xl border border-gray-800">
        <table className="w-full text-sm">
          {/* 헤더 */}
          <thead>
            <tr className="bg-gray-900 text-left">
              {['ID', '시각', '검사 PCB명', '결과', '검출 클래스', '오차 (°)', '추론 (ms)', ''].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>

          {/* 바디 */}
          <tbody className="divide-y divide-gray-800/60">
            {isLoading ? (
              <TableSkeleton />
            ) : filtered.length === 0 ? (
              /* 데이터 없음 */
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center text-gray-500 text-sm">
                  검사 이력이 없습니다.
                </td>
              </tr>
            ) : (
              filtered.map((log) => {
                const { date, time } = formatDateTime(log.inspectedAt)
                return (
                  <tr
                    key={log.id}
                    className={clsx(
                      'bg-gray-900/60 hover:bg-gray-800/60 cursor-pointer transition-colors',
                      /* 선택된 행: 인디고 좌측 테두리 강조 */
                      selectedId === log.id && 'ring-1 ring-inset ring-indigo-500/40'
                    )}
                    onClick={() => setSelectedId(log.id)}
                  >
                    {/* ID */}
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">
                      #{log.id}
                    </td>

                    {/* 시각 */}
                    <td className="px-4 py-3">
                      <p className="text-gray-300 text-xs">{date}</p>
                      <p className="text-gray-500 text-xs font-mono">{time}</p>
                    </td>

                    {/* 디바이스 */}
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">
                      {log.deviceId}
                    </td>

                    {/* 결과 뱃지 */}
                    <td className="px-4 py-3">
                      <ResultBadge result={log.result} />
                    </td>

                    {/* 결함 태그 */}
                    <td className="px-4 py-3">
                      <DefectTags defects={log.defects} />
                    </td>

                    {/* 오차 각도 */}
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">
                      {log.angleErrorDeg != null
                        ? `${log.angleErrorDeg.toFixed(2)}°`
                        : '—'}
                    </td>

                    {/* 추론 시간 */}
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">
                      {log.inferenceTimeMs != null ? `${log.inferenceTimeMs}ms` : '—'}
                    </td>

                    {/* 상세 버튼 */}
                    <td className="px-4 py-3">
                      <ChevronRight
                        size={16}
                        className={clsx(
                          'transition-colors',
                          selectedId === log.id ? 'text-indigo-400' : 'text-gray-600'
                        )}
                      />
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 행 클릭 시 DefectViewer 슬라이드다운 */}
      {selectedId !== undefined && (
        <DefectViewer
          inspectionId={selectedId}
          onClose={() => setSelectedId(undefined)}
        />
      )}
    </>
  )
}
