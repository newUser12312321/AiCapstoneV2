/**
 * React 애플리케이션 진입점
 *
 * 다음 세 가지 전역 프로바이더를 최상위에 배치한다:
 *
 * 1. BrowserRouter (React Router):
 *    URL 기반 클라이언트 사이드 라우팅을 활성화한다.
 *
 * 2. QueryClientProvider (TanStack React Query):
 *    전역 쿼리 캐시와 설정을 제공한다.
 *    - staleTime: 0  → 모든 쿼리를 기본적으로 즉시 stale 처리
 *    - refetchOnWindowFocus: true → 탭 포커스 시 자동 갱신
 *
 * 3. ReactQueryDevtools (개발 환경 전용):
 *    브라우저 하단에 쿼리 캐시 상태를 시각화하는 디버그 패널.
 *    빌드 시 자동 제거된다.
 */

import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import App from './App'
import './index.css'

/* React Query 전역 클라이언트 설정 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      /* 네트워크 오류 발생 시 자동 재시도: 1회만 */
      retry: 1,
      /* 탭이 다시 포커스되면 stale 쿼리 자동 갱신 */
      refetchOnWindowFocus: true,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {/* URL 라우팅 컨텍스트 */}
    <BrowserRouter>
      {/* React Query 전역 캐시 컨텍스트 */}
      <QueryClientProvider client={queryClient}>
        <App />
        {/* 개발 환경에서만 쿼리 디버그 패널 표시 */}
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>
)
