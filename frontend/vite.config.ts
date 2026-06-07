import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
      '/submit': 'http://localhost:5000',
      '/run-tests': 'http://localhost:5000',
      '/hint': 'http://localhost:5000',
      '/mcq': 'http://localhost:5000',
      '/generate': 'http://localhost:5000',
    }
  }
})
