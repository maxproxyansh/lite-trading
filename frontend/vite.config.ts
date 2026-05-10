import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const devBackendOrigin = (process.env.VITE_DEV_BACKEND_ORIGIN ?? 'http://127.0.0.1:8000').replace(/\/+$/, '')
const devBackendWsOrigin = devBackendOrigin.replace(/^http/i, 'ws')

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api/v1/ws': {
        target: devBackendWsOrigin,
        ws: true,
        changeOrigin: true,
      },
      '/api': {
        target: devBackendOrigin,
        changeOrigin: true,
      },
    },
  },
})
