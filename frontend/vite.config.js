import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies /api and the bare API routes to the FastAPI backend so the
// frontend can use same-origin fetches during development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/jobs': 'http://localhost:8000',
      '/info': 'http://localhost:8000',
    },
  },
})
