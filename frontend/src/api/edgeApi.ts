/**
 * 라즈베리파이 엣지 FastAPI 직접 호출 (Vite 프록시 /edge → VITE_EDGE_CAPTURE_URL)
 */

import type { CompareModelsRequest, CompareModelsResponse } from '@/types/edgeCompare'

async function parseError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: string | { msg?: string }[] }
    if (typeof j.detail === 'string') return j.detail
    if (Array.isArray(j.detail)) return j.detail.map((d) => d.msg ?? '').join(', ')
  } catch {
    /* ignore */
  }
  return res.statusText || `HTTP ${res.status}`
}

export async function postCompareModels(
  body: CompareModelsRequest
): Promise<CompareModelsResponse> {
  const res = await fetch('/edge/compare-models', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw new Error(await parseError(res))
  }
  return res.json() as Promise<CompareModelsResponse>
}
