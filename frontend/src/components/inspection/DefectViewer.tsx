/**
 * 결함 바운딩박스 오버레이 뷰어 컴포넌트
 *
 * 선택된 검사 이력의 캡처 이미지 위에 YOLO 탐지 결과(바운딩박스)를
 * SVG 오버레이로 렌더링한다.
 *
 * 동작 원리:
 *   1. useInspectionById(id)로 단건 검사 상세 데이터를 로드
 *   2. imagePath가 있으면 <img>로 캡처 이미지를 표시
 *      없으면 회색 플레이스홀더를 표시
 *   3. 이미지 위에 <svg>를 absolute 포지셔닝으로 겹쳐서
 *      각 결함의 bboxX/Y/Width/Height를 <rect>로 그린다.
 *   4. 이미지 원본 해상도(1920×1080)와 표시 크기의 비율을 계산하여
 *      좌표를 스케일 변환한다.
 *
 * 이미지가 없을 때는 더미 좌표 그리드를 대신 표시한다.
 */

import { useRef, useState, useEffect } from 'react'
import { X, ImageOff, AlertCircle } from 'lucide-react'
import { useInspectionById } from '@/hooks/useInspectionData'
import { DEFECT_COLOR, DEFECT_LABEL } from '@/types/inspection'
import type { DefectDetail } from '@/types/inspection'

// ── 원본 이미지 해상도 (라즈베리파이 캡처 설정과 동일하게 유지) ───────────────
const ORIGINAL_WIDTH  = 1920
const ORIGINAL_HEIGHT = 1080

// ── 바운딩박스 단일 렌더러 ────────────────────────────────────────────────────

interface BboxOverlayProps {
  defect:  DefectDetail
  scaleX:  number  // 표시 너비 / 원본 너비
  scaleY:  number  // 표시 높이 / 원본 높이
}

function BboxOverlay({ defect, scaleX, scaleY }: BboxOverlayProps) {
  const color  = DEFECT_COLOR[defect.defectType] ?? '#9ca3af'
  const label  = DEFECT_LABEL[defect.defectType] ?? defect.defectType
  const conf   = `${(defect.confidence * 100).toFixed(0)}%`

  /* 원본 좌표 → 표시 좌표 스케일 변환 */
  const x = defect.bboxX     * scaleX
  const y = defect.bboxY     * scaleY
  const w = defect.bboxWidth  * scaleX
  const h = defect.bboxHeight * scaleY

  return (
    <g>
      {/* 바운딩박스 테두리 */}
      <rect
        x={x} y={y} width={w} height={h}
        fill="transparent"
        stroke={color}
        strokeWidth={2}
        strokeDasharray="4 2"
      />

      {/* 상단 레이블 배경 */}
      <rect
        x={x} y={y - 18}
        width={label.length * 8 + conf.length * 7 + 16}
        height={17}
        fill={color}
        rx={3}
      />

      {/* 레이블 텍스트 */}
      <text
        x={x + 5} y={y - 5}
        fill="white"
        fontSize={11}
        fontWeight="600"
      >
        {label} {conf}
      </text>

      {/* 모서리 강조 포인트 */}
      {[[x, y], [x + w, y], [x, y + h], [x + w, y + h]].map(([cx, cy], i) => (
        <circle key={i} cx={cx} cy={cy} r={3} fill={color} />
      ))}
    </g>
  )
}

// ── 피듀셜 마크 오버레이 ──────────────────────────────────────────────────────

function FiducialMarker({
  x, y, label, scaleX, scaleY,
}: {
  x: number; y: number; label: string; scaleX: number; scaleY: number
}) {
  const sx = x * scaleX
  const sy = y * scaleY
  return (
    <g>
      {/* 십자선 */}
      <line x1={sx - 10} y1={sy} x2={sx + 10} y2={sy} stroke="#818cf8" strokeWidth={1.5} />
      <line x1={sx} y1={sy - 10} x2={sx} y2={sy + 10} stroke="#818cf8" strokeWidth={1.5} />
      {/* 원 */}
      <circle cx={sx} cy={sy} r={6} fill="transparent" stroke="#818cf8" strokeWidth={1.5} />
      {/* 레이블 */}
      <text x={sx + 10} y={sy - 8} fill="#a5b4fc" fontSize={10} fontWeight="600">{label}</text>
    </g>
  )
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────

interface DefectViewerProps {
  inspectionId: number
  onClose:      () => void
}

function resolveImageSrc(imagePath: string | null): string | null {
  if (!imagePath) return null
  if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) return imagePath
  if (imagePath.startsWith('/captures/')) return imagePath
  if (imagePath.startsWith('captures/')) return `/${imagePath}`

  const capturesIndex = imagePath.indexOf('/captures/')
  if (capturesIndex >= 0) return imagePath.slice(capturesIndex)
  return imagePath
}

export default function DefectViewer({ inspectionId, onClose }: DefectViewerProps) {
  const { data: log, isLoading } = useInspectionById(inspectionId)
  const imageSrc = resolveImageSrc(log?.imagePath ?? null)

  /* 표시 중인 이미지 엘리먼트의 실제 렌더링 크기를 추적 */
  const imgRef = useRef<HTMLImageElement>(null)
  const [imgSize, setImgSize] = useState({ w: ORIGINAL_WIDTH, h: ORIGINAL_HEIGHT })

  /* 이미지가 로드되거나 창 크기가 변경되면 실제 크기 재측정 */
  useEffect(() => {
    const measure = () => {
      if (imgRef.current) {
        setImgSize({
          w: imgRef.current.clientWidth,
          h: imgRef.current.clientHeight,
        })
      }
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [log])

  /* 원본 → 표시 크기 스케일 비율 */
  const scaleX = imgSize.w  / ORIGINAL_WIDTH
  const scaleY = imgSize.h  / ORIGINAL_HEIGHT

  return (
    <div className="mt-4 bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">

      {/* 헤더 바 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <AlertCircle size={15} className="text-indigo-400" />
          <span className="text-sm font-semibold text-gray-200">
            결함 상세 뷰어
            {log && (
              <span className="ml-2 text-xs text-gray-500 font-normal">
                #{log.id} — {log.result === 'PASS' ? '✅ PASS' : '❌ FAIL'}
              </span>
            )}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-gray-800 text-gray-500 hover:text-white transition-colors"
          aria-label="닫기"
        >
          <X size={16} />
        </button>
      </div>

      {/* 본문 */}
      {isLoading ? (
        /* 로딩 스켈레톤 */
        <div className="h-64 animate-pulse bg-gray-800/50" />
      ) : !log ? (
        <div className="h-32 flex items-center justify-center text-gray-500 text-sm">
          데이터를 불러올 수 없습니다.
        </div>
      ) : (
        <div className="flex flex-col lg:flex-row gap-0">

          {/* 좌측: 이미지 + SVG 오버레이 */}
          <div className="relative flex-1 bg-gray-950 min-h-48">
            {imageSrc ? (
              /* 실제 캡처 이미지 */
              <img
                ref={imgRef}
                src={imageSrc}
                alt="검사 캡처 이미지"
                className="w-full h-auto"
                onLoad={() => {
                  if (imgRef.current) {
                    setImgSize({ w: imgRef.current.clientWidth, h: imgRef.current.clientHeight })
                  }
                }}
              />
            ) : (
              /* 이미지 없음 플레이스홀더 */
              <div
                ref={imgRef as React.RefObject<HTMLDivElement> as React.RefObject<any>}
                className="w-full aspect-video bg-gray-800/60 flex flex-col items-center justify-center gap-2"
              >
                <ImageOff size={32} className="text-gray-600" />
                <p className="text-xs text-gray-500">캡처 이미지 없음</p>
                <p className="text-xs text-gray-600">(더미 모드에서는 이미지가 저장되지 않습니다)</p>
              </div>
            )}

            {/* SVG 오버레이: 이미지 위에 정확히 겹침 */}
            <svg
              className="absolute inset-0 w-full h-full pointer-events-none"
              viewBox={`0 0 ${imgSize.w} ${imgSize.h}`}
            >
              {/* 피듀셜 마크 1 */}
              {log.fiducial1X != null && log.fiducial1Y != null && (
                <FiducialMarker
                  x={log.fiducial1X} y={log.fiducial1Y}
                  label="F1" scaleX={1} scaleY={1}
                />
              )}

              {/* 피듀셜 마크 2 */}
              {log.fiducial2X != null && log.fiducial2Y != null && (
                <FiducialMarker
                  x={log.fiducial2X} y={log.fiducial2Y}
                  label="F2" scaleX={1} scaleY={1}
                />
              )}

              {/* 결함 바운딩박스 */}
              {log.defects.map((d, i) => (
                <BboxOverlay key={i} defect={d} scaleX={scaleX} scaleY={scaleY} />
              ))}
            </svg>
          </div>

          {/* 우측: 검사 메타데이터 패널 */}
          <div className="w-full lg:w-64 border-t lg:border-t-0 lg:border-l border-gray-800 p-4 shrink-0">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              검사 정보
            </h3>

            <dl className="space-y-2.5 text-xs">
              <MetaRow label="검사 ID"     value={`#${log.id}`}              />
              <MetaRow label="디바이스"    value={log.deviceId}              />
              <MetaRow label="검사 시각"   value={new Date(log.inspectedAt).toLocaleString('ko-KR')} />
              <MetaRow label="오차 각도"   value={log.angleErrorDeg != null ? `${log.angleErrorDeg.toFixed(2)}°` : '—'} />
              <MetaRow label="추론 시간"   value={log.inferenceTimeMs != null ? `${log.inferenceTimeMs}ms` : '—'} />
              <MetaRow label="총 처리"     value={log.totalTimeMs != null ? `${log.totalTimeMs}ms` : '—'} />
            </dl>

            {/* 결함 목록 */}
            {log.defects.length > 0 && (
              <>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mt-4 mb-2">
                  탐지 결함 ({log.defects.length}건)
                </h3>
                <ul className="space-y-1.5">
                  {log.defects.map((d, i) => (
                    <li
                      key={i}
                      className="flex items-center gap-2 text-xs"
                    >
                      <span
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ backgroundColor: DEFECT_COLOR[d.defectType] ?? '#9ca3af' }}
                      />
                      <span className="text-gray-300">
                        {DEFECT_LABEL[d.defectType] ?? d.defectType}
                      </span>
                      <span className="ml-auto text-gray-500 font-mono">
                        {(d.confidence * 100).toFixed(0)}%
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/** 검사 메타 정보 행 */
function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-gray-500 shrink-0">{label}</dt>
      <dd className="text-gray-300 font-mono text-right truncate">{value}</dd>
    </div>
  )
}
