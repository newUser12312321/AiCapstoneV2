import { defectDisplayName } from '@/types/inspection'

export interface BoardReference {
  key: string
  label: string
  imageUrl: string
  expectedCounts: Record<string, number>
}

// 확장 포인트:
// - 다른 기판이 추가되면 아래 배열에 항목만 추가하면 UI 선택 목록에 자동 반영된다.
export const BOARD_REFERENCES: BoardReference[] = [
  {
    key: 'GT_125A',
    label: 'GT-125A',
    imageUrl: '/board-ref/gt125a_ref.png',
    expectedCounts: {
      mount_hole: 4,
      fiducial: 2,
      ic_chip: 2,
      smd_array_block: 2,
      edge_connector_zone: 2,
    },
  },
]

export function toCountRows(expectedCounts: Record<string, number>) {
  return Object.entries(expectedCounts).map(([cls, count]) => ({
    cls,
    label: defectDisplayName(cls),
    count,
  }))
}

