// Proxy de dev vers le vrai back local, utilisé par `pnpm start`.
// Le back expose ses routes sous /api : on garde le préfixe.
// La clé d'API est lue dans le .env racine et ajoutée ICI (proxy de dev), jamais dans le code Angular.
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const rootEnvFile = resolve(dirname(fileURLToPath(import.meta.url)), '..', '.env');
if (existsSync(rootEnvFile)) {
  process.loadEnvFile(rootEnvFile);
}

const headers = process.env.API_KEY ? { 'X-API-Key': process.env.API_KEY } : {};

export default {
  '/api': {
    // BACK_URL (sans /api) : back d'équipe ou autre ; à défaut, le back local.
    target: process.env.BACK_URL || `http://localhost:${process.env.BACK_PORT ?? 3000}`,
    changeOrigin: true,
    headers,
  },
};
