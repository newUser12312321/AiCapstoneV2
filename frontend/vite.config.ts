import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiProxyTarget =
    env.VITE_API_PROXY_TARGET?.trim() || 'http://localhost:8080'
  const edgeCaptureUrl =
    env.VITE_EDGE_CAPTURE_URL?.trim() || 'http://192.168.0.7:8000'

  const devProxy = {
    '/api': {
      target: apiProxyTarget,
      changeOrigin: true,
    },
    '/edge': {
      target: edgeCaptureUrl,
      changeOrigin: true,
    },
    '/captures': {
      target: edgeCaptureUrl,
      changeOrigin: true,
    },
    '/demo_samples': {
      target: edgeCaptureUrl,
      changeOrigin: true,
    },
  }

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: devProxy,
    },
    // Docker: npm run preview — 브라우저가 동일 출처로 /api·/captures 요청 시 백엔드·엣지로 전달
    preview: {
      port: 5173,
      strictPort: true,
      proxy: devProxy,
    },
  }
})
