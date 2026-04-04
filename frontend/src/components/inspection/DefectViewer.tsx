/**
 * 결함 바운딩박스 오버레이 뷰어 컴포넌트
 *
 * 선택된 검사 이력의 캡처 이미지 위에 YOLO 탐지 결과(바운딩박스)를
 * SVG 오버레이로 렌더링한다.
 *
 * 동작 원리:
 *   1. useInspectionById(id)로 단건 검사 상세 데이터를 로드
 *   2. imagePath가 `*_deskew.*`이면 같은 이름의 원본과 보정 후를 나란히 표시하고,
 *      피듀셜/결함 오버레이는 보정 후에만 그린다.
 *   3. 이미지 위에 <svg>를 absolute 포지셔닝으로 겹쳐서
 *      각 결함의 bboxX/Y/Width/Height를 <rect>로 그린다.
 *   4. 로드된 이미지의 naturalWidth/Height(보정 후 캔버스 확대 등 반영)와 표시 크기 비율로
 *      좌표를 스케일 변환한다.
 *
 * 이미지가 없을 때는 더미 좌표 그리드를 대신 표시한다.
 */

import { useRef, useState, useEffect, type ReactNode } from 'react'
import { X, ImageOff, AlertCircle } from 'lucide-react'
import { useInspectionById } from '@/hooks/useInspectionData'
import { DEFECT_COLOR, DEFECT_LABEL } from '@/types/inspection'
import type { DefectDetail } from '@/types/inspection'

// ── 이미지 로드 전 기본값 (로드 후 naturalWidth/Height 사용) ───────────────
const DEFAULT_REF_WIDTH = 1920
const DEFAULT_REF_HEIGHT = 1080

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
  x,
  y,
  label,
  confidence,
  scaleX,
  scaleY,
}: {
  x: number
  y: number
  label: string
  confidence: number | null | undefined
  scaleX: number
  scaleY: number
}) {
  const sx = x * scaleX
  const sy = y * scaleY
  const color = '#38bdf8'
  const gap = 5
  const arm = 16
  const cap =
    confidence != null && !Number.isNaN(confidence)
      ? `${label} ${(confidence * 100).toFixed(0)}%`
      : label
  const tw = Math.min(160, Math.max(44, cap.length * 6.2))
  const labelY = sy - 14

  return (
    <g>
      {/* 십자선 — 중앙은 비움 (실제 마크가 보이도록) */}
      <line
        x1={sx - arm}
        y1={sy}
        x2={sx - gap}
        y2={sy}
        stroke={color}
        strokeWidth={1.75}
        strokeLinecap="round"
      />
      <line
        x1={sx + gap}
        y1={sy}
        x2={sx + arm}
        y2={sy}
        stroke={color}
        strokeWidth={1.75}
        strokeLinecap="round"
      />
      <line
        x1={sx}
        y1={sy - arm}
        x2={sx}
        y2={sy - gap}
        stroke={color}
        strokeWidth={1.75}
        strokeLinecap="round"
      />
      <line
        x1={sx}
        y1={sy + gap}
        x2={sx}
        y2={sy + arm}
        stroke={color}
        strokeWidth={1.75}
        strokeLinecap="round"
      />
      <circle cx={sx} cy={sy} r={11} fill="none" stroke={color} strokeWidth={1.75} />
      {/* 라벨·신뢰도 — 마크 위쪽으로만 배치 (마크 가리지 않음) */}
      <rect
        x={sx - tw / 2}
        y={labelY - 12}
        width={tw}
        height={14}
        rx={4}
        fill="rgba(15,23,42,0.78)"
        stroke="rgba(56,189,248,0.5)"
        strokeWidth={1}
      />
      <text
        x={sx}
        y={labelY - 1}
        fill="#e0f2fe"
        fontSize={10}
        fontWeight={600}
        textAnchor="middle"
        fontFamily="ui-monospace, monospace"
      >
        {cap}
      </text>
    </g>
  )
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────

interface DefectViewerProps {
  inspectionId: number
  onClose:      () => void
}

/**
 * 캡처 이미지 URL — 항상 `/captures/...` 상대 경로만 사용한다.
 * `npm run dev` 시 Vite가 `vite.config.ts`의 프록시로 라즈베리파이 :8000에 넘긴다.
 * (브라우저가 Pi에 직접 접속하면 PC 방화벽/망 설정에 따라 실패하기 쉬움)
 */
function resolveImageSrc(imagePath: string | null): string | null {
  if (!imagePath) return null
  const p = imagePath.replace(/\\/g, '/')
  if (p.startsWith('http://') || p.startsWith('https://')) return p

  let relative: string
  if (p.startsWith('/captures/')) {
    relative = p
  } else if (p.startsWith('captures/')) {
    relative = `/${p}`
  } else {
    const capturesIndex = p.indexOf('/captures/')
    relative = capturesIndex >= 0 ? p.slice(capturesIndex) : p
  }

  if (relative.startsWith('/')) return relative
  return relative.startsWith('captures/') ? `/${relative}` : relative
}

/**
 * 엣지 저장 규칙: `타임스탬프_deskew.jpg` ↔ 원본 `타임스탬프.jpg`
 * 보정 전 이미지 URL을 유추한다. 패턴이 아니면 null (구 이력·정렬 FAIL 등).
 */
function deriveRawImagePathFromStored(stored: string | null): string | null {
  if (!stored) return null
  const p = stored.replace(/\\/g, '/')
  const last = p.lastIndexOf('/')
  const dir = last >= 0 ? p.slice(0, last + 1) : ''
  const file = last >= 0 ? p.slice(last + 1) : p
  const m = file.match(/^(.+)_deskew(\.[^.]+)$/)
  if (!m) return null
  return `${dir}${m[1]}${m[2]}`
}

function PanelBadge({ children }: { children: ReactNode }) {
  return (
    <span className="absolute top-2 left-2 z-10 text-[10px] font-semibold uppercase tracking-wide bg-black/65 text-gray-100 px-2 py-0.5 rounded border border-gray-700/80">
      {children}
    </span>
  )
}

export default function DefectViewer({ inspectionId, onClose }: DefectViewerProps) {
  const { data: log, isLoading } = useInspectionById(inspectionId)
  const deskewSrc = resolveImageSrc(log?.imagePath ?? null)
  const rawStored = deriveRawImagePathFromStored(log?.imagePath ?? null)
  const rawSrc = rawStored ? resolveImageSrc(rawStored) : null
  const showSideBySide = Boolean(rawSrc && deskewSrc)

  /* 오버레이는 보정 후 이미지 기준 */
  const imgRef = useRef<HTMLImageElement>(null)
  const [imgSize, setImgSize] = useState({ w: DEFAULT_REF_WIDTH, h: DEFAULT_REF_HEIGHT })
  const [refPixels, setRefPixels] = useState({ w: DEFAULT_REF_WIDTH, h: DEFAULT_REF_HEIGHT })
  const [deskewLoadError, setDeskewLoadError] = useState(false)
  const [rawLoadError, setRawLoadError] = useState(false)

  useEffect(() => {
    setDeskewLoadError(false)
    setRawLoadError(false)
    setRefPixels({ w: DEFAULT_REF_WIDTH, h: DEFAULT_REF_HEIGHT })
  }, [inspectionId, deskewSrc, rawSrc])

  /* 이미지가 로드되거나 창 크기가 변경되면 실제 크기 재측정 (보정 후 패널만) */
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
  }, [log, showSideBySide])

  /* 픽셀 좌표 → 표시 크기 스케일 비율 */
  const scaleX = imgSize.w / Math.max(1, refPixels.w)
  const scaleY = imgSize.h / Math.max(1, refPixels.h)

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

          {/* 좌: 보정 전 / 우: 보정 후(+오버레이) — 또는 단일 이미지 */}
          <div
            className={
              showSideBySide
                ? 'flex flex-col sm:flex-row flex-1 min-w-0 border-b lg:border-b-0 lg:border-r border-gray-800'
                : 'relative flex-1 bg-gray-950 min-h-48 border-b lg:border-b-0 lg:border-r border-gray-800'
            }
          >
            {showSideBySide ? (
              <>
                <div className="relative flex-1 min-w-0 bg-gray-950 border-b sm:border-b-0 sm:border-r border-gray-800/90">
                  <PanelBadge>보정 전</PanelBadge>
                  {rawSrc && !rawLoadError ? (
                    <img
                      src={rawSrc}
                      alt="촬영 원본"
                      className="w-full h-auto block"
                      onError={() => setRawLoadError(true)}
                    />
                  ) : (
                    <div className="w-full min-h-32 flex flex-col items-center justify-center gap-2 px-4 py-8 bg-gray-900/50">
                      <ImageOff size={28} className="text-gray-600" />
                      <p className="text-xs text-gray-500">원본 이미지를 불러오지 못했습니다.</p>
                    </div>
                  )}
                </div>
                <div className="relative flex-1 min-w-0 bg-gray-950">
                  <PanelBadge>보정 후 · 피듀셜/결함</PanelBadge>
                  {deskewSrc && !deskewLoadError ? (
                    <>
                      <img
                        ref={imgRef}
                        src={deskewSrc}
                        alt="기울기 보정 후"
                        className="w-full h-auto block"
                        onLoad={(e) => {
                          const el = e.currentTarget
                          setRefPixels({
                            w: el.naturalWidth || DEFAULT_REF_WIDTH,
                            h: el.naturalHeight || DEFAULT_REF_HEIGHT,
                          })
                          setImgSize({ w: el.clientWidth, h: el.clientHeight })
                        }}
                        onError={() => setDeskewLoadError(true)}
                      />
                      <svg
                        className="absolute inset-0 w-full h-full pointer-events-none"
                        viewBox={`0 0 ${imgSize.w} ${imgSize.h}`}
                      >
                        {log.fiducial1X != null && log.fiducial1Y != null && (
                          <FiducialMarker
                            x={log.fiducial1X}
                            y={log.fiducial1Y}
                            label="F1"
                            confidence={log.fiducial1Confidence ?? null}
                            scaleX={scaleX}
                            scaleY={scaleY}
                          />
                        )}
                        {log.fiducial2X != null && log.fiducial2Y != null && (
                          <FiducialMarker
                            x={log.fiducial2X}
                            y={log.fiducial2Y}
                            label="F2"
                            confidence={log.fiducial2Confidence ?? null}
                            scaleX={scaleX}
                            scaleY={scaleY}
                          />
                        )}
                        {log.defects.map((d, i) => (
                          <BboxOverlay key={i} defect={d} scaleX={scaleX} scaleY={scaleY} />
                        ))}
                      </svg>
                    </>
                  ) : (
                    <div className="w-full aspect-video bg-gray-800/60 flex flex-col items-center justify-center gap-2 px-4 text-center">
                      <ImageOff size={32} className="text-gray-600" />
                      <p className="text-xs text-gray-400">보정 이미지를 불러오지 못했습니다.</p>
                    </div>
                  )}
                </div>
              </>
            ) : deskewSrc && !deskewLoadError ? (
              <div className="relative w-full">
                <img
                  ref={imgRef}
                  src={deskewSrc}
                  alt="검사 캡처 이미지"
                  className="w-full h-auto"
                  onLoad={(e) => {
                    const el = e.currentTarget
                    setRefPixels({
                      w: el.naturalWidth || DEFAULT_REF_WIDTH,
                      h: el.naturalHeight || DEFAULT_REF_HEIGHT,
                    })
                    setImgSize({ w: el.clientWidth, h: el.clientHeight })
                  }}
                  onError={() => setDeskewLoadError(true)}
                />
                <svg
                  className="absolute inset-0 w-full h-full pointer-events-none"
                  viewBox={`0 0 ${imgSize.w} ${imgSize.h}`}
                >
                  {log.fiducial1X != null && log.fiducial1Y != null && (
                    <FiducialMarker
                      x={log.fiducial1X}
                      y={log.fiducial1Y}
                      label="F1"
                      confidence={log.fiducial1Confidence ?? null}
                      scaleX={scaleX}
                      scaleY={scaleY}
                    />
                  )}
                  {log.fiducial2X != null && log.fiducial2Y != null && (
                    <FiducialMarker
                      x={log.fiducial2X}
                      y={log.fiducial2Y}
                      label="F2"
                      confidence={log.fiducial2Confidence ?? null}
                      scaleX={scaleX}
                      scaleY={scaleY}
                    />
                  )}
                  {log.defects.map((d, i) => (
                    <BboxOverlay key={i} defect={d} scaleX={scaleX} scaleY={scaleY} />
                  ))}
                </svg>
              </div>
            ) : deskewSrc && deskewLoadError ? (
              <div className="w-full aspect-video bg-gray-800/60 flex flex-col items-center justify-center gap-2 px-4 text-center">
                <ImageOff size={32} className="text-gray-600" />
                <p className="text-xs text-gray-400">캡처 이미지를 불러오지 못했습니다.</p>
                <p className="text-xs text-gray-500">
                  <code className="text-indigo-300">frontend/vite.config.ts</code>의{' '}
                  <code className="text-indigo-300">/captures</code> 프록시가 Pi IP와 맞는지,
                  Pi에서 <code className="text-indigo-300">uvicorn</code>이 떠 있는지 확인하세요.
                </p>
              </div>
            ) : (
              <div
                ref={imgRef as React.RefObject<HTMLDivElement> as React.RefObject<any>}
                className="w-full aspect-video bg-gray-800/60 flex flex-col items-center justify-center gap-2"
              >
                <ImageOff size={32} className="text-gray-600" />
                <p className="text-xs text-gray-500">캡처 이미지 없음</p>
                <p className="text-xs text-gray-600">(더미 모드에서는 이미지가 저장되지 않습니다)</p>
              </div>
            )}
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
              <MetaRow
                label="촬영 시 기울기"
                value={log.angleErrorDeg != null ? `${log.angleErrorDeg.toFixed(2)}° (보정 전)` : '—'}
              />
              {(log.fiducial1Confidence != null || log.fiducial2Confidence != null) && (
                <MetaRow
                  label="피듀셜 conf"
                  value={[
                    log.fiducial1Confidence != null
                      ? `F1 ${(log.fiducial1Confidence * 100).toFixed(0)}%`
                      : null,
                    log.fiducial2Confidence != null
                      ? `F2 ${(log.fiducial2Confidence * 100).toFixed(0)}%`
                      : null,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                />
              )}
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
