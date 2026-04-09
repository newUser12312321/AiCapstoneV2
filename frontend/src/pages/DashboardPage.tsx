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

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, FolderOpen, Loader2, Trash2 } from 'lucide-react'
import StatCardGroup from '@/components/dashboard/StatCard'
import PassFailChart from '@/components/dashboard/PassFailChart'
import TrendChart from '@/components/dashboard/TrendChart'
import InspectionTable from '@/components/inspection/InspectionTable'
import { deleteAllInspections } from '@/api/inspectionApi'
import {
  fetchDemoSamplePaths,
  triggerEdgeInspection,
  triggerInspectionFromFile,
  triggerInspectionFromUpload,
} from '@/api/edgeApi'
import { useRecentInspections } from '@/hooks/useInspectionData'

export default function DashboardPage() {
  const queryClient = useQueryClient()
  const [actionMsg, setActionMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [demoPath, setDemoPath] = useState('')
  const [captureFile, setCaptureFile] = useState('')
  const [uploadFile, setUploadFile] = useState<File | null>(null)

  /* 최근 15건 — 대시보드 하단 실시간 피드 테이블 */
  const { data: recentLogs = [], isLoading } = useRecentInspections(15)

  const { data: demoSamplePaths = [], isLoading: demoListLoading } = useQuery({
    queryKey: ['edge-demo-samples'],
    queryFn: fetchDemoSamplePaths,
    staleTime: 60_000,
  })

  const invalidateInspections = () => {
    queryClient.invalidateQueries({ queryKey: ['inspections'] })
  }

  const triggerMutation = useMutation({
    mutationFn: triggerEdgeInspection,
    onSuccess: (data) => {
      setActionMsg({ type: 'ok', text: data.message })
      setTimeout(() => invalidateInspections(), 2500)
      setTimeout(() => invalidateInspections(), 6000)
    },
    onError: (e: Error) => {
      setActionMsg({ type: 'err', text: e.message || '검사 트리거 실패' })
    },
  })

  const fileInspectMutation = useMutation({
    mutationFn: triggerInspectionFromFile,
    onSuccess: (data) => {
      setActionMsg({ type: 'ok', text: data.message })
      setTimeout(() => invalidateInspections(), 2500)
      setTimeout(() => invalidateInspections(), 6000)
    },
    onError: (e: Error) => {
      setActionMsg({ type: 'err', text: e.message || '파일 검사 실패' })
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
    mutationFn: triggerInspectionFromUpload,
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
          <div className="flex flex-col gap-1.5 w-full sm:max-w-md">
            <label className="text-[11px] text-gray-500 font-medium uppercase tracking-wide">
              시연 · demo_samples 이미지로 검사
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={demoPath}
                onChange={(e) => setDemoPath(e.target.value)}
                disabled={demoListLoading || demoSamplePaths.length === 0}
                className="flex-1 min-w-[12rem] text-sm bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-gray-200"
              >
                <option value="">
                  {demoListLoading
                    ? '목록 불러오는 중…'
                    : demoSamplePaths.length === 0
                      ? 'demo_samples/ 비어 있음'
                      : '샘플 선택…'}
                </option>
                {demoSamplePaths.map((p) => (
                  <option key={p} value={p}>
                    {p.replace(/^demo_samples\//, '')}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => {
                  const path = demoPath || captureFile.trim()
                  if (!path) return
                  setActionMsg(null)
                  fileInspectMutation.mutate(path)
                }}
                disabled={(!demoPath && !captureFile.trim()) || fileInspectMutation.isPending}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-teal-700 hover:bg-teal-600 disabled:opacity-50 text-white transition-colors"
              >
                {fileInspectMutation.isPending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <FolderOpen size={16} />
                )}
                샘플 검사
              </button>
            </div>
            <input
              type="text"
              value={captureFile}
              onChange={(e) => setCaptureFile(e.target.value)}
              placeholder="또는 captures/ 파일명 (예: 20260404_220236_723508.jpg)"
              className="w-full text-sm bg-gray-900/80 border border-gray-700 rounded-lg px-2 py-1.5 text-gray-300 placeholder:text-gray-600"
            />
            <p className="text-[11px] text-gray-600 leading-snug">
              Pi의 <code className="text-gray-400">edge/demo_samples/</code>에 합성 이미지를 넣고
              페이지를 새로고침하면 위 목록이 채워집니다. 이미 촬영된 파일은{' '}
              <code className="text-gray-400">captures/</code> 기준 파일명만 입력해도 됩니다.
            </p>
            <div className="pt-2 border-t border-gray-800 mt-1 space-y-2">
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
                팀원 PC에서 이미지를 바로 올려 검사할 수 있습니다. 업로드 파일은 엣지 서버의{' '}
                <code className="text-gray-400">edge/captures/</code>에 저장됩니다.
              </p>
            </div>
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
