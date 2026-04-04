/**
 * 루트 애플리케이션 컴포넌트
 *
 * React Router의 라우팅 트리와 전체 레이아웃(Header + Sidebar + 콘텐츠)을 정의한다.
 *
 * 레이아웃 구조:
 * ┌──────────────────────────── Header (h-16) ──────────────────────────────┐
 * │ ┌─ Sidebar ─┐  ┌──────────── <Outlet /> ──────────────────────────────┐ │
 * │ │  (w-56)   │  │  DashboardPage / HistoryPage / SettingsPage           │ │
 * │ │           │  │                                                        │ │
 * │ └───────────┘  └────────────────────────────────────────────────────────┘ │
 * └─────────────────────────────────────────────────────────────────────────┘
 */

import { Routes, Route, Navigate } from 'react-router-dom'
import Header from '@/components/common/Header'
import Sidebar from '@/components/common/Sidebar'
import DashboardPage from '@/pages/DashboardPage'
import HistoryPage from '@/pages/HistoryPage'
import ModelComparePage from '@/pages/ModelComparePage'

/** 아직 구현되지 않은 경로를 위한 플레이스홀더 페이지 */
function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-center h-full">
      <p className="text-gray-500 text-sm">{title} — 준비 중</p>
    </div>
  )
}

export default function App() {
  return (
    /* 전체 화면을 채우는 flex 컨테이너 */
    <div className="flex flex-col h-screen bg-gray-950 text-gray-100 overflow-hidden">

      {/* 상단 고정 헤더 */}
      <Header />

      {/* 헤더 아래 본문 영역: 사이드바 + 페이지 */}
      <div className="flex flex-1 overflow-hidden">

        {/* 좌측 고정 사이드바 */}
        <Sidebar />

        {/* 우측 페이지 콘텐츠 (스크롤 가능) */}
        <main className="flex-1 overflow-hidden bg-gray-950">
          <Routes>
            {/* 기본 경로: 대시보드 */}
            <Route path="/"         element={<DashboardPage />} />

            {/* 검사 이력 */}
            <Route path="/history"  element={<HistoryPage />} />

            {/* 모델 비교 (엣지 동일 촬영) */}
            <Route path="/compare" element={<ModelComparePage />} />

            {/* 설정 (플레이스홀더) */}
            <Route path="/settings" element={<PlaceholderPage title="설정" />} />

            {/* 정의되지 않은 경로는 루트로 리다이렉트 */}
            <Route path="*"         element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
