import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { TanStackRouterVite } from '@tanstack/router-plugin/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    // Must be before react() so router plugin transforms files first
    TanStackRouterVite({
      target: 'react',
      autoCodeSplitting: true,
    }),
    react(),
  ],
  // react-dom is installed in web/frontend/node_modules, not the hoisted root, so
  // hoisted deps (e.g. @radix-ui/react-portal) can't resolve it without dedupe.
  resolve: { dedupe: ['react', 'react-dom'] },
  server: {
    port: 5173,
    proxy: {
      // Page-agent chat lives on the dashboard; must precede the generic /api entry
      '/api/page-chat': {
        target: 'http://piserver:3000',
        changeOrigin: true
      },
      '/api': {
        target: 'http://localhost:8642',
        changeOrigin: true
      },
      '/custom_emojis': {
        target: 'http://localhost:8642',
        changeOrigin: true
      },
      '/stream': {
        target: 'http://localhost:8001',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  }
})
