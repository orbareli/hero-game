import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: 'all',   // ← allows ngrok (and any other tunnel)
    host: true,            // ← makes Vite listen on 0.0.0.0, not just localhost
  },
})
