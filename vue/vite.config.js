import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api/': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/auth': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/members': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/admin': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        bypass(req) {
          const path = req.url?.split('?')[0] || ''
          if (req.headers.accept?.includes('text/html') && /^\/admin\/members(?:\/[^/]+)?\/?$/.test(path)) return '/index.html'
        }
      },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true }
    }
  }
})
