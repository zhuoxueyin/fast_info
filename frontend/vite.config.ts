import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// API 端口走 env(FASTINFO_API_PORT,默认 8000 本地)
// Docker 预发要访问 staging API 时:
//   FASTINFO_API_PORT=18000 npm run dev
// 容器内 dev(用服务名):  VITE_API_TARGET=http://api:8000 npm run dev
const API_TARGET = process.env.VITE_API_TARGET
  || `http://127.0.0.1:${process.env.FASTINFO_API_PORT || 8000}`

// https://vite.dev/config/
export default defineConfig({
  build: {
    sourcemap: 'hidden',
  },
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
      '/swagger': {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: () => '/docs',
      },
      '/redoc': {
        target: API_TARGET,
        changeOrigin: true,
      },
      '/openapi.json': {
        target: API_TARGET,
        changeOrigin: true,
      },
      '/docs': {
        target: 'http://127.0.0.1:5174',
        changeOrigin: true,
      },
    },
  },
})
