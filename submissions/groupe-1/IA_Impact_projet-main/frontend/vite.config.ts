import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En dev, /api est relayé vers le backend FastAPI (uvicorn sur le port 8000).
export default defineConfig({
  plugins: [react()],
  // Le moteur de carte (~1 Mo) dans son propre fichier : mis en cache à part, il ne se retélécharge pas à chaque déploiement du site
  build: { rollupOptions: { output: { manualChunks: { map: ["maplibre-gl", "pmtiles", "@protomaps/basemaps"] } } }, chunkSizeWarningLimit: 1200 },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", rewrite: (p) => p.replace(/^\/api/, "") } },
  },
});
