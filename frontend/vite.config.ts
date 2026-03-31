import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
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
    },
  },
})
