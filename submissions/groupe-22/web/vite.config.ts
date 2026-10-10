import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In dev, the page is served by Vite and the API by uvicorn (uv run uvicorn server:app).
// ws: the text chat's WebSocket (/api/chat).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": "/src" } }, // "@/lib/...": web/src/lib/...
  server: { proxy: { "/api": { target: "http://127.0.0.1:8000", ws: true } } },
});
