import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
      '/health': 'http://localhost:8000',
      '/account': 'http://localhost:8000',
      '/alerts': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/risk': 'http://localhost:8000',
      '/orders': 'http://localhost:8000',
      '/signals': 'http://localhost:8000',
      '/strategies': 'http://localhost:8000',
      '/instruments': 'http://localhost:8000',
      '/audit': 'http://localhost:8000',
      '/backtest': 'http://localhost:8000',
      '/validation': 'http://localhost:8000',
    },
  },
})
