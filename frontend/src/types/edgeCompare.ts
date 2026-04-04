/** POST /edge/compare-models 요청·응답 (라즈베리파이 FastAPI) */

export interface CompareModelsRequest {
  weights: string[]
  defect_weights?: string[] | null
  image?: string | null
  conf?: number | null
  camera_index?: number | null
}

export interface CompareModelRow {
  weights: string
  weightsLabel: string
  mode: string
  fiducial_count: number
  aligned: boolean
  angle_error_deg: number
  defect_count: number
  defect_conf_mean: number | null
  defect_conf_max: number | null
  infer_ms_stage1: number
  infer_ms_stage2: number
  infer_ms_total: number
  /** 엣지 captures/compare_*.jpg 파일명 — 브라우저는 `/captures/<파일명>` 으로 로드 */
  fiducial_preview_path?: string | null
}

export interface CompareModelsResponse {
  input_source: string
  /** 회전 보정 허용 상한 (°), 이하이면 deskew 후 ROI 검사 */
  max_deskew_angle_deg: number
  /** 레거시 필드 (과거 정렬 FAIL 임계값). 파이프라인은 max_deskew_angle_deg 기준 */
  max_angle_error_deg: number
  conf: number
  rows: CompareModelRow[]
  note: string
}
