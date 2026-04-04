/**
 * 모델 비교 — 엣지의 동일 촬영으로 여러 weights/*.pt 결과를 표로 표시
 * (PC 브라우저 → Vite /edge 프록시 → 라즈베리파이 :8000)
 */

import { useEffect, useState } from 'react'
import { GitCompare, Loader2, AlertCircle, X } from 'lucide-react'
import { postCompareModels } from '@/api/edgeApi'
import type { CompareModelsResponse } from '@/types/edgeCompare'

function parseWeights(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean)
}

export default function ModelComparePage() {
  const [weightsText, setWeightsText] = useState('best_a.pt\nbest_b.pt')
  const [imagePath, setImagePath] = useState('')
  const [cameraIndex, setCameraIndex] = useState('')
  const [conf, setConf] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CompareModelsResponse | null>(null)
  const [previewLightbox, setPreviewLightbox] = useState<{ src: string; title: string } | null>(null)

  useEffect(() => {
    if (!previewLightbox) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPreviewLightbox(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [previewLightbox])

  const run = async () => {
    const weights = parseWeights(weightsText)
    if (weights.length === 0) {
      setError('가중치 파일명을 한 줄에 하나씩 입력하세요 (edge/weights 기준).')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    let camIndex: number | null = null
    if (cameraIndex.trim() !== '') {
      const n = Number.parseInt(cameraIndex.trim(), 10)
      if (Number.isNaN(n)) {
        setError('카메라 장치 인덱스는 정수만 입력하세요.')
        setLoading(false)
        return
      }
      camIndex = n
    }
    try {
      const data = await postCompareModels({
        weights,
        image: imagePath.trim() || null,
        conf: conf.trim() ? Number(conf) : null,
        camera_index: camIndex,
      })
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full max-w-[min(100%,96rem)]">
      <div>
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <GitCompare size={22} className="text-indigo-400" />
          모델 비교 (실제 촬영)
        </h2>
        <p className="text-xs text-gray-500 mt-1">
          라즈베리파이에 <code className="text-gray-400">weights/</code> 아래로 팀원{' '}
          <code className="text-gray-400">.pt</code> 를 넣은 뒤, 파일명을 입력하고 실행합니다.
          Vite 프록시(<code className="text-gray-400">VITE_EDGE_CAPTURE_URL</code>)가 엣지로 연결됩니다.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm text-gray-400">가중치 (한 줄에 하나, edge/weights 기준)</label>
          <textarea
            className="w-full h-36 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-200 font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500"
            value={weightsText}
            onChange={(e) => setWeightsText(e.target.value)}
            placeholder="alice_best.pt&#10;bob_best.pt"
            spellCheck={false}
          />
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-sm text-gray-400">캡처 이미지 대신 쓸 경우 (edge/captures 기준)</label>
            <input
              type="text"
              className="mt-1 w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              value={imagePath}
              onChange={(e) => setImagePath(e.target.value)}
              placeholder="비우면 카메라로 즉시 1장 촬영"
            />
          </div>
          <div>
            <label className="text-sm text-gray-400">카메라 장치 인덱스 (선택)</label>
            <input
              type="text"
              inputMode="numeric"
              className="mt-1 w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              value={cameraIndex}
              onChange={(e) => setCameraIndex(e.target.value)}
              placeholder="비우면 엣지 .env 의 CAMERA_DEVICE_INDEX — 오류 시 0 입력"
            />
            <p className="text-[11px] text-gray-600 mt-1">
              USB 웹캠은 보통 <code className="text-gray-500">0</code> (/dev/video0). Pi 카메라 모듈은 환경에 따라 0 또는 10 등.
            </p>
          </div>
          <div>
            <label className="text-sm text-gray-400">conf (선택)</label>
            <input
              type="text"
              className="mt-1 w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              value={conf}
              onChange={(e) => setConf(e.target.value)}
              placeholder="기본: 엣지 설정값"
            />
          </div>
          <button
            type="button"
            onClick={run}
            disabled={loading}
            className="w-full md:w-auto px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium flex items-center justify-center gap-2"
          >
            {loading ? <Loader2 size={18} className="animate-spin" /> : null}
            {loading ? '추론 중…' : '지금 비교 실행'}
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg p-3">
          <AlertCircle size={18} className="shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {result && (
        <div className="space-y-3">
          <p className="text-xs text-gray-500">
            입력: <span className="text-gray-400">{result.input_source}</span>
            {' · '}
            conf {result.conf}, 회전 보정 한도 ≤{' '}
            {result.max_deskew_angle_deg ?? result.max_angle_error_deg}°
          </p>
          <div className="overflow-x-auto rounded-lg border border-gray-800">
            <table className="w-full text-sm text-left">
              <thead className="bg-gray-900 text-gray-400">
                <tr>
                  <th className="px-3 py-2 font-medium">가중치</th>
                  <th className="px-3 py-2 font-medium">피듀셜</th>
                  <th className="px-3 py-2 font-medium">정렬</th>
                  <th className="px-3 py-2 font-medium">각도°</th>
                  <th className="px-3 py-2 font-medium">결함</th>
                  <th className="px-3 py-2 font-medium">평균 conf</th>
                  <th className="px-3 py-2 font-medium">ms</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {result.rows.map((r, i) => (
                  <tr key={`${r.weightsLabel}-${i}`} className="text-gray-200">
                    <td className="px-3 py-2 font-mono text-xs">{r.weightsLabel}</td>
                    <td className="px-3 py-2">{r.fiducial_count}</td>
                    <td className="px-3 py-2">{r.aligned ? 'OK' : '—'}</td>
                    <td className="px-3 py-2">{r.angle_error_deg.toFixed(2)}</td>
                    <td className="px-3 py-2">{r.defect_count}</td>
                    <td className="px-3 py-2">
                      {r.defect_conf_mean != null ? r.defect_conf_mean.toFixed(3) : '—'}
                    </td>
                    <td className="px-3 py-2">{r.infer_ms_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <h3 className="text-sm font-medium text-gray-300 mb-1">피듀셜 검출 미리보기 (동일 촬영)</h3>
            <p className="text-[11px] text-gray-500 mb-3">이미지를 클릭하면 화면에 맞게 크게 볼 수 있습니다.</p>
            <div className="flex flex-col gap-6">
              {result.rows.map((r, i) => (
                <div
                  key={`preview-${r.weightsLabel}-${i}`}
                  className="rounded-lg border border-gray-800 bg-gray-950/50 overflow-hidden"
                >
                  <p className="px-3 py-2 text-xs font-mono text-gray-300 border-b border-gray-800/80 break-all">
                    {r.weightsLabel}
                  </p>
                  {r.fiducial_preview_path ? (
                    <button
                      type="button"
                      className="block w-full text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-inset"
                      onClick={() =>
                        setPreviewLightbox({
                          src: `/captures/${r.fiducial_preview_path}`,
                          title: r.weightsLabel,
                        })
                      }
                      aria-label={`${r.weightsLabel} 미리보기 크게 보기`}
                    >
                      <div className="flex justify-center bg-black/50 p-1 sm:p-2">
                        <img
                          src={`/captures/${r.fiducial_preview_path}`}
                          alt={`피듀셜 검출 ${r.weightsLabel}`}
                          className="w-full max-w-full h-auto max-h-[min(85vh,920px)] object-contain cursor-zoom-in"
                          loading="lazy"
                        />
                      </div>
                    </button>
                  ) : (
                    <div className="min-h-[12rem] flex items-center justify-center text-xs text-gray-600 px-2">
                      미리보기 없음 (엣지 최신 코드 필요)
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <p className="text-[11px] text-gray-600 leading-relaxed">{result.note}</p>
        </div>
      )}

      {previewLightbox && (
        <div
          className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-black/90 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="미리보기 확대"
          onClick={() => setPreviewLightbox(null)}
        >
          <div className="flex w-full max-w-[min(100vw,120rem)] items-center justify-between gap-2 px-1 pb-2 text-gray-300">
            <p className="text-xs font-mono truncate pr-2" title={previewLightbox.title}>
              {previewLightbox.title}
            </p>
            <button
              type="button"
              className="shrink-0 rounded-lg p-2 text-gray-400 hover:bg-white/10 hover:text-white"
              onClick={() => setPreviewLightbox(null)}
              aria-label="닫기"
            >
              <X size={22} />
            </button>
          </div>
          <img
            src={previewLightbox.src}
            alt=""
            className="max-h-[min(92vh,1200px)] max-w-full w-auto object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  )
}
