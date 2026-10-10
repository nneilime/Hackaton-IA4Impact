# Frontend : Sporadar (veille homologations LPC)

Application Angular 22 (composants standalone, signals), Tailwind 4, Spartan NG, Vitest, pnpm.
Une seule page : on pose une question réglementaire, la réponse choisit son gabarit selon l'`intent`
renvoyé par `POST /ask`, et chaque valeur ouvre sa preuve. Le cahier de développement est dans
`../docs/cahier-frontend.md`, les écrans dans `../docs/wireframes.html`.

## Lancer en développement

Depuis `frontend/` (une fois : `pnpm install`).

### Sans back : mock Prism (la commande de tous les jours)

```bash
pnpm start:mock
```

Lance Prism (port 4010, contrat `../openapi.proposed.yaml`, réponses fictives de `../mocks/examples.yaml`) et l'app sur
<http://localhost:4200>. Un bandeau « Mock : données fictives » reste visible.
Prism met environ une minute à démarrer : tant qu'il n'est pas prêt, l'app affiche « Le service ne répond pas » (« Réessayer »).

- Le mock ne filtre rien : toutes les routes renvoient les données de LALGUARD M52 OD.
- Pour les questions cliquées (exemples, suggestions), l'app demande l'exemple de leur `intent` (en-tête `Prefer: example=<intent>`).
  Une question tapée librement est associée à un exemple par mots-clés (`src/app/core/api/mock-intent.ts`), réservé au mock.
- Forcer une erreur pour développer les états d'erreur : ajouter `&mockCode=401` à l'URL (mock uniquement).
- `pnpm mock` lance Prism seul.

### Avec le vrai back local

```bash
pnpm start
```

L'app (<http://localhost:4200>) transmet `/api/...` au back sur `localhost:${BACK_PORT}` (défaut 3000), préfixe compris.
Le proxy de dev (`proxy.back.mjs`) ajoute `X-API-Key` avec `API_KEY` du `.env` racine : la clé n'est jamais dans le code Angular.

Pour viser le back d'équipe déployé au lieu d'un back local : `BACK_URL=http://64.176.83.254:3000` dans le `.env` racine (`FRONT_API_URL` reste `/api` : le navigateur parle à son propre domaine, pas de CORS). Idem en Docker : `docker compose up -d --build` (front seul) suffit, nginx transmet au back d'équipe.

### Démo hors ligne (filet de sécurité du pitch)

Dans le `.env` racine : `FRONT_OFFLINE_DEMO=true`, puis `pnpm start` ou `pnpm build`.
Les appels sont rejoués depuis les exemples fictifs, sans aucun serveur, avec le bandeau « Démo hors ligne, données fictives ».
Jamais actif par défaut.

## Docker

```bash
docker compose --profile backend up -d --build   # depuis la racine du repo
```

L'app est servie par nginx sur <http://localhost:8080>. nginx transmet `/api/` au back et **ajoute lui-même** l'en-tête
`X-API-Key` (`API_KEY` du `.env`) : aucune clé n'arrive dans le navigateur. Tout ce qui s'appelle `FRONT_*` finit dans
le JavaScript public : n'y mettez jamais de secret.

## Variables (`.env` racine → `src/environments/environment.ts`)

`environment.ts` est **généré** par `scripts/generate-env.mjs` : ne pas l'éditer.

| Variable | Rôle |
|---|---|
| `FRONT_API_URL` | Base d'URL de l'API vue du navigateur (défaut `/api`). |
| `BACK_URL` | Où le proxy de dev (`pnpm start`) et nginx (Docker) envoient `/api`, **sans** `/api` à la fin. Vide = back local. Back d'équipe : `http://64.176.83.254:3000`. |
| `FRONT_MOCK` | `true` = mode mock (en-tête `Prefer`). `pnpm start:mock` l'active tout seul. |
| `FRONT_OFFLINE_DEMO` | `true` = démo hors ligne. |

## Contrat d'API et mocks

- `pnpm gen:api` régénère les types TypeScript (`src/app/core/api/schema.d.ts`) depuis `../openapi.proposed.yaml`.
  À relancer quand le contrat change ; ne jamais écrire ces types à la main.
- `pnpm gen:mocks` convertit `../mocks/examples.yaml` en `src/app/core/mock/examples.json` (tests et démo hors ligne).
  `pnpm test` le fait déjà. Le JSON est versionné car le build Docker n'a pas accès à `../mocks`.

## Tests et build

```bash
pnpm test    # Vitest : un test de rendu par gabarit sur sa réponse d'exemple, règles d'affichage, états, FR/EN
pnpm build   # build de production dans dist/
```

## Où est quoi

```
src/app/
  core/api/        types générés, client d'API (un service par groupe de routes), intercepteurs mock et démo hors ligne
  core/state/      AnswerStore (question, réponse, état, preuve ouverte ; l'URL est la source de vérité)
  core/i18n/       textes FR / EN (les valeurs des sources ne sont jamais traduites)
  shared/          badge d'état unique, panneau de preuve, confiance IA, badges fictif / figé, case vide…
  features/answer/ la page : cadre commun + un gabarit par intent (templates/)
  ui/              composants Spartan « helm » (thème Atlas Homologations)
```

Règle : le front affiche, il ne décide pas. Couverture, états des cases, priorités, différences entre pays et statuts
viennent du back ; le front peut seulement compter et trier ce qu'il reçoit.
