import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// API target: override with VITE_API_TARGET when needed
const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Bind the IPv4 loopback explicitly. Left unset, Vite listens on [::1] only,
    // so the literal `127.0.0.1:5173` is refused (a literal IP cannot fall back
    // the way the name `localhost` does) — which silently broke the e2e suite.
    // Binding here keeps the server local-only while serving both names.
    host: '127.0.0.1',
    port: 5173,
    // Fail loudly instead of drifting to 5174, which the API's CORS list may not allow.
    strictPort: true,
    proxy: {
      '/api': apiTarget,
      '/health': apiTarget,
    },
  },
})
