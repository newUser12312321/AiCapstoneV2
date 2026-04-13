/**
 * 검사 상세 뷰어 — 보정 전/후 이미지에 피듀셜(F1·F2)과 결함 박스를 오버레이한다.
 */

import { useRef, useState, useEffect, type ReactNode } from 'react'
import { X, ImageOff, AlertCircle } from 'lucide-react'
import { useInspectionById } from '@/hooks/useInspectionData'
import type { InspectionLog } from '@/types/inspection'
import { DEFECT_COLOR, defectDisplayName } from '@/types/inspection'

// ── 이미지 로드 전 기본값 (로드 후 naturalWidth/Height 사용) ───────────────
const DEFAULT_REF_WIDTH = 1920
const DEFAULT_REF_HEIGHT = 1080

/** F1·F2 중심 좌표가 모두 있을 때 화면 픽셀 기준 거리 */
function fiducialDistancePx(log: {
  fiducial1X: number | null
  fiducial1Y: number | null
  fiducial2X: number | null
  fiducial2Y: number | null
}): number | null {
  const { fiducial1X: x1, fiducial1Y: y1, fiducial2X: x2, fiducial2Y: y2 } = log
  if (x1 == null || y1 == null || x2 == null || y2 == null) return null
  return Math.hypot(x2 - x1, y2 - y1)
}

/**
 * 엣지 `alignment.compute_alignment`: 피듀셜이 2개 미만이면 angle_error_deg = 999.
 * 이 경우 Stage2(결함) 검사는 실행되지 않으며, 결함 박스 데이터도 없다.
 */
function isFiducialAlignmentSentinel(log: InspectionLog): boolean {
  const a = log.angleErrorDeg
  return a != null && a >= 500
}

// ── 피듀셜/결함 오버레이 ───────────────────────────────────────────────────────

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
      {/* 중심 좌표 (원본 픽셀) — 배경·큰 글자 */}
      <rect
        x={sx - 88}
        y={sy + arm + 2}
        width={176}
        height={28}
        rx={6}
        fill="rgba(15,23,42,0.95)"
        stroke="rgba(56,189,248,0.85)"
        strokeWidth={1.5}
      />
      <text
        x={sx}
        y={sy + arm + 21}
        fill="#f0f9ff"
        fontSize={14}
        fontWeight={700}
        textAnchor="middle"
        fontFamily="ui-monospace, monospace"
      >
        {`(${Math.round(x)}, ${Math.round(y)}) px`}
      </text>
    </g>
  )
}

function DefectBox({
  x,
  y,
  w,
  h,
  label,
  confidence,
  color,
  scaleX,
  scaleY,
}: {
  x: number
  y: number
  w: number
  h: number
  label: string
  confidence: number
  color: string
  scaleX: number
  scaleY: number
}) {
  const sx = x * scaleX
  const sy = y * scaleY
  const sw = Math.max(1, w * scaleX)
  const sh = Math.max(1, h * scaleY)
  const cap = `${label} ${(confidence * 100).toFixed(0)}%`
  const tw = Math.min(220, Math.max(88, cap.length * 7.2))
  const ty = sy > 22 ? sy - 21 : sy + 3

  return (
    <g>
      <rect x={sx} y={sy} width={sw} height={sh} rx={2} fill="none" stroke={color} strokeWidth={2} />
      <rect x={sx} y={ty} width={tw} height={17} rx={4} fill="rgba(15,23,42,0.86)" stroke={color} strokeWidth={1.1} />
      <text
        x={sx + 6}
        y={ty + 12}
        fill={color}
        fontSize={11}
        fontWeight={700}
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
  const f12DistancePx = log != null ? fiducialDistancePx(log) : null
  const defects = log?.defects ?? []

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
            검사 상세 (피듀셜)
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

      {log && isFiducialAlignmentSentinel(log) && (
        <div className="px-4 py-2.5 bg-amber-950/50 border-b border-amber-900/40 text-[11px] text-amber-100/95 leading-relaxed">
          <strong className="text-amber-200">정렬(피듀셜) 단계에서 실패했습니다.</strong> 마크가 2개
          이상 잡히지 않아 기울기 값이 999°로 기록됩니다. 이 상태에서는{' '}
          <strong>결함 검사가 실행되지 않습니다</strong> — 표시할 결함 박스가 없는 것이 정상입니다.
          <span className="text-amber-200/80">
            {' '}
            엣지 <code className="text-amber-300/90">YOLO_FIDUCIAL_CONFIDENCE_THRESHOLD</code>를
            0.2~0.35로 낮추거나, 학습 이미지와 비슷한 밝기·구도로 촬영해 보세요.
          </span>
        </div>
      )}

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
                  <PanelBadge>보정 후 · 피듀셜 + 결함</PanelBadge>
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
                        {defects.map((d, i) => (
                          <DefectBox
                            key={`${d.defectType}-${d.bboxX}-${d.bboxY}-${i}`}
                            x={d.bboxX}
                            y={d.bboxY}
                            w={d.bboxWidth}
                            h={d.bboxHeight}
                            label={defectDisplayName(d.defectType)}
                            confidence={d.confidence}
                            color={DEFECT_COLOR[d.defectType] ?? '#f87171'}
                            scaleX={scaleX}
                            scaleY={scaleY}
                          />
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
                  {defects.map((d, i) => (
                    <DefectBox
                      key={`${d.defectType}-${d.bboxX}-${d.bboxY}-${i}`}
                      x={d.bboxX}
                      y={d.bboxY}
                      w={d.bboxWidth}
                      h={d.bboxHeight}
                      label={defectDisplayName(d.defectType)}
                      confidence={d.confidence}
                      color={DEFECT_COLOR[d.defectType] ?? '#f87171'}
                      scaleX={scaleX}
                      scaleY={scaleY}
                    />
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
                value={
                  log.angleErrorDeg == null
                    ? '—'
                    : isFiducialAlignmentSentinel(log)
                      ? `${log.angleErrorDeg.toFixed(2)}° — 피듀셜 2개 미탐지(결함검사 생략)`
                      : `${log.angleErrorDeg.toFixed(2)}° (보정 전)`
                }
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
              {log.fiducial1X != null && log.fiducial1Y != null && (
                <MetaCoordRow
                  label="F1 중심 (px)"
                  value={`(${log.fiducial1X}, ${log.fiducial1Y})`}
                />
              )}
              {log.fiducial2X != null && log.fiducial2Y != null && (
                <MetaCoordRow
                  label="F2 중심 (px)"
                  value={`(${log.fiducial2X}, ${log.fiducial2Y})`}
                />
              )}
              {f12DistancePx != null && (
                <MetaRow label="F1–F2 거리" value={`${f12DistancePx.toFixed(1)} px`} />
              )}
              <MetaRow label="추론 시간"   value={log.inferenceTimeMs != null ? `${log.inferenceTimeMs}ms` : '—'} />
              <MetaRow label="총 처리"     value={log.totalTimeMs != null ? `${log.totalTimeMs}ms` : '—'} />
              <MetaRow label="검출 수"     value={`${defects.length}건`} />
            </dl>

            {defects.length > 0 && (
              <div className="mt-4 border-t border-gray-800 pt-3">
                <h4 className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  검출 좌표
                </h4>
                <div className="max-h-56 overflow-y-auto space-y-2 pr-1">
                  {defects.map((d, i) => {
                    const cx = d.bboxX + Math.round(d.bboxWidth / 2)
                    const cy = d.bboxY + Math.round(d.bboxHeight / 2)
                    const color = DEFECT_COLOR[d.defectType] ?? '#f87171'
                    return (
                      <div
                        key={`${d.defectType}-${d.bboxX}-${d.bboxY}-${i}`}
                        className="rounded-md border border-gray-700/80 bg-gray-950/80 px-2.5 py-2"
                      >
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="text-[11px] font-semibold truncate" style={{ color }}>
                            {i + 1}. {defectDisplayName(d.defectType)}
                          </span>
                          <span className="text-[11px] font-mono text-gray-400">
                            {(d.confidence * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="text-[11px] font-mono text-gray-300 leading-relaxed">
                          <div>좌상단: ({d.bboxX}, {d.bboxY})</div>
                          <div>크기: {d.bboxWidth}×{d.bboxHeight}px</div>
                          <div className="text-sky-300">중심: ({cx}, {cy})</div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
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

/** 피듀셜 중심 좌표 — 패널에서 가장 눈에 띄게 */
function MetaCoordRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1.5 rounded-lg border-2 border-sky-600/50 bg-slate-950 px-3 py-2.5 shadow-lg shadow-sky-950/40">
      <dt className="text-[11px] font-semibold text-sky-200/90 tracking-wide">{label}</dt>
      <dd className="text-base sm:text-lg font-bold font-mono text-sky-300 tabular-nums tracking-tight break-all">
        {value}
      </dd>
    </div>
  )
}
