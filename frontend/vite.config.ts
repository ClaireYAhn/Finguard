import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Backend address for the dev proxy. If port 8000 is taken: FINGUARD_API=http://localhost:8010 npm run dev
const target = process.env.FINGUARD_API ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target, changeOrigin: true },
      '/v1': { target, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
