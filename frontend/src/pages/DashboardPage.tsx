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

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Camera, FolderOpen, Loader2, Trash2 } from 'lucide-react'
import StatCardGroup from '@/components/dashboard/StatCard'
import PassFailChart from '@/components/dashboard/PassFailChart'
import TrendChart from '@/components/dashboard/TrendChart'
import InspectionTable from '@/components/inspection/InspectionTable'
import { deleteAllInspections } from '@/api/inspectionApi'
import { triggerEdgeInspection, triggerInspectionFromUpload, type Stage2SourceMode } from '@/api/edgeApi'
import { useRecentInspections } from '@/hooks/useInspectionData'

export default function DashboardPage() {
  const queryClient = useQueryClient()
  const [actionMsg, setActionMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [stage2Source, setStage2Source] = useState<Stage2SourceMode>('deskew')
  const [previewTick, setPreviewTick] = useState<number>(Date.now())

  /* 최근 15건 — 대시보드 하단 실시간 피드 테이블 */
  const { data: recentLogs = [], isLoading } = useRecentInspections(15)

  useEffect(() => {
    const timer = window.setInterval(() => {
      setPreviewTick(Date.now())
    }, 1000)
    return () => window.clearInterval(timer)
  }, [])

  const livePreviewSrc = useMemo(
    () => `/edge/camera/preview.jpg?t=${previewTick}`,
    [previewTick]
  )

  const invalidateInspections = () => {
    queryClient.invalidateQueries({ queryKey: ['inspections'] })
  }

  const triggerMutation = useMutation({
    mutationFn: () => triggerEdgeInspection(stage2Source),
    onSuccess: (data) => {
      setActionMsg({ type: 'ok', text: data.message })
      setTimeout(() => invalidateInspections(), 2500)
      setTimeout(() => invalidateInspections(), 6000)
    },
    onError: (e: Error) => {
      setActionMsg({ type: 'err', text: e.message || '검사 트리거 실패' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteAllInspections,
    onSuccess: () => {
      setActionMsg({ type: 'ok', text: '검사 이력이 모두 삭제되었습니다.' })
      invalidateInspections()
    },
    onError: (e: Error) => {
      setActionMsg({ type: 'err', text: e.message || '삭제 실패' })
    },
  })

  const uploadInspectMutation = useMutation({
    mutationFn: (file: File) => triggerInspectionFromUpload(file, stage2Source),
    onSuccess: (data) => {
      setActionMsg({ type: 'ok', text: data.message })
      setUploadFile(null)
      setTimeout(() => invalidateInspections(), 2500)
      setTimeout(() => invalidateInspections(), 6000)
    },
    onError: (e: Error) => {
      setActionMsg({ type: 'err', text: e.message || '업로드 검사 실패' })
    },
  })

  const handleDeleteHistory = () => {
    if (
      !window.confirm(
        '저장된 검사 이력과 결함 기록을 모두 삭제합니다. 계속할까요?'
      )
    ) {
      return
    }
    deleteMutation.mutate()
  }

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">

      {/* 페이지 제목 + 엣지 액션 */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-white">실시간 대시보드</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            5초마다 자동 갱신 · 라즈베리파이 엣지 노드 연결 중
          </p>
        </div>
        <div className="flex flex-col items-stretch sm:items-end gap-2 shrink-0 min-w-[min(100%,280px)]">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-gray-500">Stage2 입력</span>
            <select
              value={stage2Source}
              onChange={(e) => setStage2Source(e.target.value as Stage2SourceMode)}
              className="bg-gray-900 border border-gray-700 rounded-md px-2 py-1 text-gray-200"
            >
              <option value="deskew">deskew (보정 후)</option>
              <option value="raw">raw (원본)</option>
            </select>
          </div>
          <div className="flex flex-wrap items-center gap-2 justify-end">
          <button
            type="button"
            onClick={() => {
              setActionMsg(null)
              triggerMutation.mutate()
            }}
            disabled={triggerMutation.isPending}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white transition-colors"
          >
            {triggerMutation.isPending ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Camera size={16} />
            )}
            지금 검사
          </button>
          <button
            type="button"
            onClick={handleDeleteHistory}
            disabled={deleteMutation.isPending}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-gray-800 hover:bg-red-950/80 border border-gray-700 hover:border-red-900 text-gray-200 disabled:opacity-50 transition-colors"
          >
            {deleteMutation.isPending ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Trash2 size={16} />
            )}
            이력 전체 삭제
          </button>
          </div>
          <div className="flex flex-col gap-2 w-full sm:max-w-md">
            <label className="text-[11px] text-gray-500 font-medium uppercase tracking-wide block">
              로컬 이미지 업로드로 검사
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="file"
                accept=".jpg,.jpeg,.png,.bmp,.webp,image/*"
                onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                className="block w-full text-xs text-gray-300 file:mr-2 file:px-2 file:py-1.5 file:rounded-md file:border-0 file:bg-gray-800 file:text-gray-200"
              />
              <button
                type="button"
                onClick={() => {
                  if (!uploadFile) return
                  setActionMsg(null)
                  uploadInspectMutation.mutate(uploadFile)
                }}
                disabled={!uploadFile || uploadInspectMutation.isPending}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-sky-700 hover:bg-sky-600 disabled:opacity-50 text-white transition-colors"
              >
                {uploadInspectMutation.isPending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <FolderOpen size={16} />
                )}
                업로드 검사
              </button>
            </div>
            <p className="text-[11px] text-gray-600 leading-snug">
              업로드 파일은 엣지 서버의{' '}
              <code className="text-gray-400">edge/captures/</code>에 저장됩니다.
            </p>
          </div>
        </div>
      </div>

      {actionMsg && (
        <p
          className={
            actionMsg.type === 'ok'
              ? 'text-xs text-emerald-400/90'
              : 'text-xs text-red-400/90'
          }
        >
          {actionMsg.text}
        </p>
      )}

      {/* 실시간 카메라 프리뷰 */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-3">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-gray-300">실시간 웹캠 프리뷰</h3>
          <span className="text-[11px] text-gray-500">1초 주기 자동 갱신</span>
        </div>
        <div className="w-full aspect-video rounded-lg overflow-hidden bg-black/70 border border-gray-800">
          <img
            src={livePreviewSrc}
            alt="라즈베리파이 카메라 실시간 프리뷰"
            className="w-full h-full object-contain"
            onError={() => {
              // 네트워크 끊김/엣지 미가동 시 다음 tick 에 자동 재시도
            }}
          />
        </div>
      </div>

      {/* 1행: 통계 카드 4개 */}
      <StatCardGroup />

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
