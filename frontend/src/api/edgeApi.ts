/**
 * 라즈베리파이 FastAPI 엣지 API (Vite 프록시 `/edge` → VITE_EDGE_CAPTURE_URL)
 */

import type { CompareModelsRequest, CompareModelsResponse } from '@/types/edgeCompare'

/**
 * 수동 PCB 검사 1회 실행 (백그라운드). 결과는 Spring Boot DB에 적재된다.
 */
export async function triggerEdgeInspection(): Promise<{ message: string }> {
  const res = await fetch('/edge/inspect/trigger', { method: 'POST' })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<{ message: string }>
}

/** 동일 장면으로 여러 YOLO 가중치 비교 */
/** edge/demo_samples 아래 시연용 이미지 목록 (Pi에 복사 후 사용) */
export async function fetchDemoSamplePaths(): Promise<string[]> {
  const res = await fetch('/edge/inspect/demo-samples')
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `${res.status}`)
  }
  const data = (await res.json()) as { paths?: string[] }
  return data.paths ?? []
}

/** 저장된 이미지 경로로 검사 1회 (백그라운드). 결과는 Spring DB에 적재 */
export async function triggerInspectionFromFile(path: string): Promise<{ message: string }> {
  const res = await fetch('/edge/inspect/from-file', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<{ message: string }>
}

export async function postCompareModels(
  body: CompareModelsRequest
): Promise<CompareModelsResponse> {
  const res = await fetch('/edge/compare-models', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<CompareModelsResponse>
}
