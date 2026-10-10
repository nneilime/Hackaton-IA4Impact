import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Le front appelle /api, que Vite redirige vers l'API FastAPI lancée sur le port 8000.
// `host: true` ouvre le serveur au réseau local : les téléphones des élèves rejoignent
// le vote en classe en scannant le QR code (http://<ip-locale>:5173/vote/CODE).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    // Codespaces / dev cloud : l'URL publique du port est en *.app.github.dev.
    allowedHosts: ['.app.github.dev'],
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
