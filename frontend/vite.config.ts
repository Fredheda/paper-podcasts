import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: 'localhost',
    port: 5173,
    open: true,
    // Mirrors server.js's prod proxy: the browser only ever talks to this
    // dev server (same-origin), which forwards /api and /health to the
    // backend server-side -- so CORS never comes up in dev either.
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true }
    }
  }
});
