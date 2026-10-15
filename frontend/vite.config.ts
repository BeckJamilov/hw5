import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The backend (FastAPI, port 8000) only allows this origin via CORS, so keep the port fixed.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  preview: { port: 5173, strictPort: true },
})
