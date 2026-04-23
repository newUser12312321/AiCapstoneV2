/**
 * 라즈베리파이 FastAPI 엣지 API (Vite 프록시 `/edge` → VITE_EDGE_CAPTURE_URL)
 */

/**
 * 수동 PCB 검사 1회 실행 (백그라운드). 결과는 Spring Boot DB에 적재된다.
 */
export type Stage2SourceMode = 'aligned' | 'raw'

export async function triggerEdgeInspection(
  stage2Source: Stage2SourceMode
): Promise<{ message: string }> {
  const res = await fetch(`/edge/inspect/trigger?stage2Source=${stage2Source}`, { method: 'POST' })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<{ message: string }>
}

/** edge/demo_samples 아래 시연용 이미지 목록 */
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
export async function triggerInspectionFromFile(
  path: string,
  stage2Source: Stage2SourceMode
): Promise<{ message: string }> {
  const res = await fetch(`/edge/inspect/from-file?stage2Source=${stage2Source}`, {
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

/** 브라우저 파일 업로드로 검사 1회 (백그라운드). 결과는 Spring DB에 적재 */
export async function triggerInspectionFromUpload(
  file: File,
  stage2Source: Stage2SourceMode
): Promise<{ message: string }> {
  const formData = new FormData()
  formData.append('image', file)

  const res = await fetch(`/edge/inspect/upload?stage2Source=${stage2Source}`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<{ message: string }>
}
