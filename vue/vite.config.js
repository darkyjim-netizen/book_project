import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve, sep } from 'node:path'

function reloadPublicFiles() {
  return {
    name: 'reload-public-files',
    configureServer(server) {
      const publicDir = resolve(process.cwd(), 'public')
      const publicPrefix = `${publicDir}${sep}`.toLowerCase()
      const reloadIfPublicFile = file => {
        if (resolve(file).toLowerCase().startsWith(publicPrefix)) {
          server.ws.send({ type: 'full-reload', path: '*' })
        }
      }

      server.watcher.add(publicDir)
      server.watcher.on('change', reloadIfPublicFile)
      server.watcher.on('add', reloadIfPublicFile)
      server.watcher.on('unlink', reloadIfPublicFile)
    }
  }
}

export default defineConfig({
  plugins: [vue(), reloadPublicFiles()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api/': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/auth': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/members': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/admin': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true }
    }
  }
})
