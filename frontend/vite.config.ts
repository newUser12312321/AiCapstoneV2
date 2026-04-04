import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const edgeCaptureUrl =
    env.VITE_EDGE_CAPTURE_URL?.trim() || 'http://192.168.0.7:8000'

  return {
    plugins: [react()],
    resolve: {
      alias: {
        // tsconfig.json의 paths 설정과 일치시켜
        // import '@/components/...' 형태의 절대 경로 임포트를 활성화한다.
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      // Spring Boot API 프록시 설정 (CORS 우회)
      // /api/inspections → http://localhost:8080/api/inspections 로 포워딩
      proxy: {
        '/api': {
          target: 'http://localhost:8080',
          changeOrigin: true,
        },
        // 엣지 FastAPI (/edge/*) — 모델 비교 등. VITE_EDGE_CAPTURE_URL 과 동일 호스트
        '/edge': {
          target: edgeCaptureUrl,
          changeOrigin: true,
        },
        // 브라우저는 /captures/... 만 요청 → Vite가 라즈베리파이 FastAPI로 넘김
        '/captures': {
          target: edgeCaptureUrl,
          changeOrigin: true,
        },
        '/demo_samples': {
          target: edgeCaptureUrl,
          changeOrigin: true,
        },
      },
    },
  }
})
