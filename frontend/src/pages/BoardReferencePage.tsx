import { useMemo, useState } from 'react'
import { BOARD_REFERENCES, toCountRows } from '@/config/boardReference'

export default function BoardReferencePage() {
  const [selectedKey, setSelectedKey] = useState<string>(BOARD_REFERENCES[0]?.key ?? '')
  const [imageError, setImageError] = useState(false)

  const selected = useMemo(
    () => BOARD_REFERENCES.find((b) => b.key === selectedKey) ?? BOARD_REFERENCES[0],
    [selectedKey]
  )

  const rows = selected ? toCountRows(selected.expectedCounts) : []

  if (!selected) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-gray-400">
        등록된 기판 기준 정보가 없습니다.
      </div>
    )
  }

  return (
    <div className="h-full overflow-auto p-6 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-gray-100">기판 기준 정보</h1>
          <p className="text-xs text-gray-400 mt-1">
            정상 라벨링 기준 이미지와 클래스 정상 개수를 보드별로 확인합니다.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-400">기판 선택</label>
          <select
            value={selected.key}
            onChange={(e) => {
              setSelectedKey(e.target.value)
              setImageError(false)
            }}
            className="bg-gray-900 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-gray-100"
          >
            {BOARD_REFERENCES.map((b) => (
              <option key={b.key} value={b.key}>
                {b.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        <section className="xl:col-span-3 border border-gray-800 rounded-xl bg-gray-900/60 p-3">
          <h2 className="text-sm text-gray-300 font-semibold mb-3">정상 라벨링 기준 이미지</h2>
          {!imageError ? (
            <img
              src={selected.imageUrl}
              alt={`${selected.label} 기준`}
              className="w-full h-auto rounded-md border border-gray-800 bg-gray-950"
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="h-72 rounded-md border border-dashed border-gray-700 flex items-center justify-center text-xs text-gray-500 px-4 text-center">
              기준 이미지를 불러오지 못했습니다. 이미지 경로를 확인하세요: {selected.imageUrl}
            </div>
          )}
        </section>

        <section className="xl:col-span-2 border border-gray-800 rounded-xl bg-gray-900/60 p-3">
          <h2 className="text-sm text-gray-300 font-semibold mb-3">정상 클래스 개수</h2>
          <div className="space-y-2">
            {rows.map((row) => (
              <div
                key={row.cls}
                className="flex items-center justify-between rounded-md border border-gray-800 bg-gray-950/60 px-3 py-2"
              >
                <span className="text-sm text-gray-200">{row.label}</span>
                <span className="text-sm font-mono text-cyan-300">X{row.count}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

