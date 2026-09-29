import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite config: tells Vite to use React and run on port 5173
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
})
