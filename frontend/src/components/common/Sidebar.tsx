/**
 * 좌측 사이드바 네비게이션 컴포넌트
 *
 * React Router의 NavLink를 사용하여 현재 활성 경로를 강조 표시한다.
 * 각 메뉴 항목은 lucide-react 아이콘 + 한글 레이블로 구성된다.
 */

import { NavLink } from 'react-router-dom'
import { BarChart2, ClipboardList, GitCompare, Settings } from 'lucide-react'
import clsx from 'clsx'

/** 네비게이션 메뉴 항목 정의 */
const NAV_ITEMS = [
  {
    to:    '/',
    icon:  BarChart2,
    label: '대시보드',
    end:   true,  // 루트 경로 정확히 매칭 (하위 경로에서 active 방지)
  },
  {
    to:    '/history',
    icon:  ClipboardList,
    label: '검사 이력',
    end:   false,
  },
  {
    to:    '/compare',
    icon:  GitCompare,
    label: '모델 비교',
    end:   false,
  },
  {
    to:    '/settings',
    icon:  Settings,
    label: '설정',
    end:   false,
  },
]

export default function Sidebar() {
  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col py-4 shrink-0">

      {/* 네비게이션 메뉴 */}
      <nav className="flex flex-col gap-1 px-3">
        {NAV_ITEMS.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  /* 활성 메뉴: 인디고 배경 + 흰 텍스트 */
                  ? 'bg-indigo-600 text-white'
                  /* 비활성 메뉴: 회색 텍스트, 호버 시 배경 */
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              )
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* 하단 디바이스 정보 */}
      <div className="mt-auto px-4 pb-2 border-t border-gray-800 pt-4">
        <p className="text-xs text-gray-600 font-mono">RPI5-LINE-A</p>
        <p className="text-xs text-gray-600">Spring Boot :8080</p>
      </div>
    </aside>
  )
}
