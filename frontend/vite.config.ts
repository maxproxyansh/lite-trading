import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api/v1/ws': {
        target: 'wss://lite-options-api-production.up.railway.app',
        ws: true,
      },
      '/api': {
        target: 'https://lite-options-api-production.up.railway.app',
        changeOrigin: true,
      },
    },
  },
})
