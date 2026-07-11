import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies /api and the bare API routes to the FastAPI backend so the
// frontend can use same-origin fetches during development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Mirror production: the frontend calls /api/*; strip the prefix so the
    // backend (which serves /auth, /jobs, /info, ...) matches in dev too.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
