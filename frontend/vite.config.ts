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
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
      '/health': 'http://localhost:8000',
      '/account': 'http://localhost:8000',
      '/alerts': 'http://localhost:8000',
      '/chat': {
        target: 'http://localhost:8000',
        bypass(req) {
          const accept = req.headers?.accept
          if (accept && accept.includes('text/html')) return '/index.html'
        },
      },
      '/risk': {
        target: 'http://localhost:8000',
        bypass(req) {
          const accept = req.headers?.accept
          if (accept && accept.includes('text/html')) return '/index.html'
        },
      },
      '/instruments': 'http://localhost:8000',
      '/validation': 'http://localhost:8000',
      // These paths collide with SPA routes. Only proxy XHR/fetch requests,
      // not browser page navigations. Vite passes (req, res, options) to bypass.
      '/orders': {
        target: 'http://localhost:8000',
        bypass(req) {
          const accept = req.headers?.accept
          if (accept && accept.includes('text/html')) return '/index.html'
        },
      },
      '/signals': {
        target: 'http://localhost:8000',
        bypass(req) {
          const accept = req.headers?.accept
          if (accept && accept.includes('text/html')) return '/index.html'
        },
      },
      '/strategies': {
        target: 'http://localhost:8000',
        bypass(req) {
          const accept = req.headers?.accept
          if (accept && accept.includes('text/html')) return '/index.html'
        },
      },
      '/audit': {
        target: 'http://localhost:8000',
        bypass(req) {
          const accept = req.headers?.accept
          if (accept && accept.includes('text/html')) return '/index.html'
        },
      },
      '/backtest': {
        target: 'http://localhost:8000',
        bypass(req) {
          const accept = req.headers?.accept
          if (accept && accept.includes('text/html')) return '/index.html'
        },
      },
    },
  },
})
