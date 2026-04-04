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
}

export interface CompareModelsResponse {
  input_source: string
  max_angle_error_deg: number
  conf: number
  rows: CompareModelRow[]
  note: string
}
