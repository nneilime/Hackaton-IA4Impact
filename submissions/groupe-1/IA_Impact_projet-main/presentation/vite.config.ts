import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";

// Toute modification recharge la page entière (sur la même slide, son numéro est dans l'URL) : le moteur
// d'animation travaille sur le DOM, un remplacement à chaud partiel le laisserait dans un état bancal
const fullReload = (): Plugin => ({
  name: "rechargement-complet",
  handleHotUpdate({ server }) {
    server.ws.send({ type: "full-reload" });
    return [];
  },
});

// base "./" : le diapo construit (dist/) s'ouvre depuis n'importe quel dossier, sans serveur particulier
export default defineConfig({
  base: "./",
  plugins: [react(), fullReload()],
  server: { port: 4321, strictPort: true, host: true },
  preview: { port: 4321, strictPort: true },
  build: { chunkSizeWarningLimit: 600 }, // three.js seul fait ~510 ko, chargé à part et seulement pour l'intro 3D
});
