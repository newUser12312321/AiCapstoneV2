/**
 * 모델 비교 — 엣지의 동일 촬영으로 여러 weights/*.pt 결과를 표로 표시
 * (PC 브라우저 → Vite /edge 프록시 → 라즈베리파이 :8000)
 */

import { useState } from 'react'
import { GitCompare, Loader2, AlertCircle } from 'lucide-react'
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
    <div className="p-6 space-y-6 overflow-y-auto h-full max-w-5xl">
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
            conf {result.conf}, 정렬 허용 각도 ≤ {result.max_angle_error_deg}°
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
          <p className="text-[11px] text-gray-600 leading-relaxed">{result.note}</p>
        </div>
      )}
    </div>
  )
}
