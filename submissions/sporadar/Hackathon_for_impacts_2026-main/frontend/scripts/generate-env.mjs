// Génère src/environments/environment.ts à partir des variables FRONT_*.
//
// Angular ne lit pas les fichiers .env. Ce script fait le pont :
//   1. en local : il lit le `.env` situé à la RACINE du repo
//   2. dans Docker : le `.env` n'est pas dans le contexte de build, les valeurs
//      arrivent via process.env (build args du docker-compose.yml)
// Les variables déjà présentes dans process.env sont prioritaires.
//
// Options :
//   --mock   force le mode mock (données fictives servies par Prism), utilisé par `pnpm start:mock`
//
// ATTENTION : tout ce qui est écrit ici finit dans le JavaScript public. Jamais de clé ni de secret.
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const rootEnvFile = resolve(root, '.env');

if (existsSync(rootEnvFile)) {
  process.loadEnvFile(rootEnvFile); // n'écrase pas les variables déjà définies
}

const isTrue = (value) => ['1', 'true', 'yes', 'on'].includes(String(value ?? '').toLowerCase());

// Si BACK_URL est renseigné, le navigateur appelle le back DIRECTEMENT (BACK_URL + /api), sans passer par le proxy nginx.
// Le back autorise le CORS, donc pas de souci côté navigateur. Sinon : FRONT_API_URL (par défaut /api, via nginx).
const backUrl = (process.env.BACK_URL ?? '').trim().replace(/\/+$/, '');

const environment = {
  apiUrl: backUrl ? `${backUrl}/api` : (process.env.FRONT_API_URL ?? '/api'),
  // Mode mock : le front ajoute l'en-tête `Prefer: example=<nom>` pour choisir la réponse de Prism.
  mock: process.argv.includes('--mock') || isTrue(process.env.FRONT_MOCK),
  // Mode démo hors ligne : rejoue les exemples fictifs sans aucun serveur (filet de sécurité du pitch).
  offlineDemo: isTrue(process.env.FRONT_OFFLINE_DEMO),
};

const target = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'environments', 'environment.ts');
mkdirSync(dirname(target), { recursive: true });
writeFileSync(
  target,
  `// FICHIER GÉNÉRÉ par scripts/generate-env.mjs - ne pas éditer (modifier le .env racine)\nexport const environment = ${JSON.stringify(environment, null, 2)} as const;\n`,
);
console.log(
  `[env] ${target} généré (apiUrl=${environment.apiUrl}, mock=${environment.mock}, offlineDemo=${environment.offlineDemo})`,
);
