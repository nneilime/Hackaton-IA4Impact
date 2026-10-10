# SporaDar — Le radar réglementaire du biocontrôle

**SporaDar** est un agent IA qui collecte, normalise, compare et restitue les homologations de produits de protection des
plantes (**produit × pays × usage**) à partir de bases officielles (France, Allemagne, Canada), et répond en langage naturel
**avec la source, la date de collecte et le statut de validation de chaque donnée**. Réalisé pour le défi Lallemand Plant Care
(Hackathon IA for Impact 2026).

> **Avertissement réglementaire.** SporaDar est une **preuve de concept**, pas une source officielle. Les informations extraites
> doivent être validées par Regulatory Affairs avant tout usage réglementaire, commercial ou opérationnel.
> **Une absence de résultat n'est jamais une preuve d'absence d'homologation.**

## Essayer la version déployée

| Quoi | Adresse |
|---|---|
| Application (front Angular) | <http://64.176.83.254:8080> |
| API | <http://64.176.83.254:3000/api> (santé : `/api/health`, documentation interactive : <http://64.176.83.254:3000/docs>) |

Trois questions d'exemple (à saisir dans l'application, ou via `POST /api/ask`) :

1. « Dans quels pays LALSTOP G46 est-il homologué ? »
2. « Quand expire LALGUARD M52 OD en Allemagne ? »
3. « Quelles opportunités pour LALGUARD M52 ? »

Appeler l'API directement (remplacer le serveur par `http://localhost:3000` pour un lancement local) :

```bash
# Linux / macOS / Git Bash
curl -X POST http://64.176.83.254:3000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Dans quels pays LALSTOP G46 est-il homologué ?"}'
```

```powershell
# Windows PowerShell
$body = @{ question = "Dans quels pays LALSTOP G46 est-il homologué ?" } | ConvertTo-Json
$r = Invoke-RestMethod -Method Post -Uri http://64.176.83.254:3000/api/ask `
       -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$r.answer          # la réponse ; voir aussi $r.facts, $r.evidence, $r.coverage, $r.generator.mode
```

La réponse contient le texte (`answer`), les faits sourcés (`facts`), les preuves (`evidence` : `sourceId`, `sourceRecordUrl`,
`collectedAt`, `validationStatus`), la couverture par pays (`coverage` : `found` / `not_found` / `not_covered` /
`source_unavailable`) et le mode de rédaction (`generator.mode` : `llm` ou `keyword`).

## Comment ça marche

```text
 Sources officielles                 Adaptateurs (écrivent en base)         PostgreSQL
 ┌──────────────────────┐            ┌───────────────────────────┐       ┌────────────────────────┐
 │ FR  ANSES E-Phy (CSV)│──────────▶ │ backend/etl/adapters/     │       │ products, registrations│
 │ DE  BVL PSM API(JSON)│──────────▶ │   france/ germany/ canada/│─────▶ │ uses, field_evidence,  │
 │ CA  Santé Canada PPID│──────────▶ │ (+ journal collection_runs)│       │ collection_runs, …     │
 └──────────────────────┘            └───────────────────────────┘       └───────────┬────────────┘
                                                                                      │ normalisation
                                     backend/etl/normalize.py + load_db.py --normalize-db
                                     (EPPO, substances actives, produits sœurs ; *_original jamais modifiés)
                                                                                      │
                       ┌──────────────────────────────────────────────────────────────▼───────────┐
                       │ API FastAPI (backend/app, contrat openapi.proposed.yaml, lecture seule)   │
                       │  /products /compare /expirations /issues /sources /opportunities …       │
                       │  POST /ask : agent  comprendre → chercher en SQL → rédiger → vérifier    │
                       │  (IA interchangeable via .env ; sans clé IA : mode mots-clés)            │
                       └───────────────┬─────────────────────────────────────┬────────────────────┘
                                       ▼                                     ▼
                       Front Angular (frontend/)             Connecteur Microsoft 365
                       réponse + preuve cliquable            (Power Platform / Copilot Studio,
                                                              connector/power-platform.swagger.yaml)
```

Principes non négociables : chaque donnée porte `source_id`, `source_record_url`, `collected_at` et `validation_status` ;
rien n'est inventé (absent = vide, `unknown` ou `not_found`) ; les colonnes `*_original` ne sont jamais modifiées
(les transformations sont dans `*_normalized`) ; les produits sœurs sont des **hypothèses** (`to_verify`) ; les données
fictives sont marquées `is_synthetic=true`. Dans `/ask`, le code (pas le modèle) vérifie que les preuves citées existent,
que les chiffres viennent des faits et qu'un résultat vide ne devient jamais « non homologué ».

## Relancer le projet soi-même

Prérequis : Python 3.11+, Git ; Docker (pour la base locale, les adaptateurs France/Allemagne et le front) ; Node + pnpm
seulement pour développer le front hors Docker. **Aucune clé personnelle n'est nécessaire.**

### 1. Installer

```powershell
# Windows PowerShell
git clone <url-du-depot> ; cd <dossier-du-depot>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

```bash
# Linux / macOS
git clone <url-du-depot> && cd <dossier-du-depot>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Dans `.env`, renseigner :

| Variable | Obligatoire | Rôle |
|---|---|---|
| `DATABASE_URL` | **oui** | Base PostgreSQL, format `postgresql+psycopg://utilisateur:motdepasse@hôte:5432/base`. Base locale : voir ci-dessous. Ne jamais commiter `.env`. |
| `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL` | non | Fournisseur d'IA au format du SDK `openai` (interchangeable). `AI_FALLBACK_MODEL` : modèle de secours. **Laissés vides : l'application fonctionne en mode mots-clés** (`generator.mode = "keyword"`). |
| `API_KEY` | non | Vide = API ouverte (développement). Renseignée = en-tête `X-API-Key` obligatoire. |
| `BACK_PORT` | non | Port de l'API (3000 par défaut). |

### 2. Base de données

- **Base d'équipe** : mettre son `DATABASE_URL` dans `.env` (fourni par l'équipe, jamais dans git).
- **Base locale vide** (autonome) : `docker compose --profile localdb up -d postgres` crée PostgreSQL 16 avec le schéma
  `db/schema.sql`. Puis dans `.env` :
  `DATABASE_URL=postgresql+psycopg://lallemand:lallemand@localhost:5432/lallemand`.

> ⚠️ Ne jamais exécuter `db/schema.sql` ni `db/reset_DANGER.sql` sur une base partagée.

### 3. Charger les données (base locale ou vide uniquement)

Ordre à respecter : **référentiels → adaptateurs → normalisation**.

```bash
python backend/etl/load_db.py --no-test            # 1. sources, produits pilotes LPC, dictionnaires

# 2. adaptateurs (chacun écrit directement en base)
#    France et Allemagne : un dossier et un .env chacun (DATABASE_URL au format postgresql://…)
cd backend/etl/adapters/france  && cp .env.example .env && docker compose build && docker compose run --rm france python main.py --once ; cd ../../../..
cd backend/etl/adapters/germany && cp .env.example .env && docker compose build && docker compose run --rm germany python main.py --once ; cd ../../../..
#    Canada (lit DATABASE_URL du .env racine ; options : python -m etl.run --help)
cd backend && python -m etl.run canada ; cd ..

python backend/etl/load_db.py --normalize-db       # 3. normalisation (EPPO, cultures, cibles ; plusieurs minutes)
```

Dans les `.env` des adaptateurs (Docker), `localhost` désigne le conteneur : pour la base locale, utiliser `host.docker.internal`
à la place (`postgresql://lallemand:lallemand@host.docker.internal:5432/lallemand`).
Détails, dépannage et exports CSV sans base : [backend/etl/adapters/README.md](backend/etl/adapters/README.md).
Sous Windows, remplacer `cp` par `Copy-Item` et enchaîner les commandes ligne par ligne ; en cas d'erreur d'affichage,
définir `PYTHONIOENCODING=utf-8`.

### 4. Lancer l'API

```bash
uvicorn backend.app.main:app --port 3000
```

Santé : <http://localhost:3000/api/health> · documentation interactive : <http://localhost:3000/docs>. Docker :
`docker compose --profile backend up -d --build`.

### 5. Lancer le front

- **Docker** (comme en production) : `docker compose up -d --build` → <http://localhost:8080>. Le front transmet `/api/…` au
  back (`BACK_URL` dans `.env`, par défaut le service `backend` ; avec `--profile backend` le back est lancé aussi).
  Pour viser le back déployé de l'équipe : `BACK_URL=http://64.176.83.254:3000` dans `.env`.
- **Développement** : `cd frontend && pnpm install && pnpm start` (back local) ou `pnpm start:mock` (mock sans back).
  Détails : [frontend/README.md](frontend/README.md).

### 6. Tester

```bash
python -m pytest -q                                   # tests (voir la note ci-dessous)
python scripts/run_gold.py                            # pose les questions de référence à l'agent, écrit evaluation/our_submission.json
python scripts/evaluate_submission.py evaluation/our_submission.json   # score automatique attendu : 70 / 70
python scripts/validate_data.py                       # contrôle des CSV du starter
```

Note : les tests qui lisent la base (dont `tests/test_opportunities.py`) demandent un `DATABASE_URL` pointant sur une base
**chargée** ; sans base, ces tests échouent et les autres passent. `run_gold.py` fonctionne sans clé IA (mode mots-clés) et
utilise l'IA si elle est configurée.

## Documentation

| Document | Contenu |
|---|---|
| [docs/limitations.md](docs/limitations.md) | Limites connues, chiffres vérifiés, impact et pistes |
| [docs/regulatory_validation.md](docs/regulatory_validation.md) | Comment Regulatory Affairs valide les données |
| [docs/demo_cases.md](docs/demo_cases.md) | Cas de démonstration (requêtes exactes et résultats) |
| [docs/deploy.md](docs/deploy.md) | Déploiement de l'API (image Docker) |
| [data/source_registry.csv](data/source_registry.csv) | Sources officielles, licences et limites d'usage |
| [connector/power-platform.swagger.yaml](connector/power-platform.swagger.yaml) | Connecteur Microsoft 365 (Power Platform / Copilot Studio) |
| [openapi.proposed.yaml](openapi.proposed.yaml) | Contrat de l'API (v0.2.1) ; détails dans [docs/openapi-changes.md](docs/openapi-changes.md) |

### Microsoft 365

Le connecteur personnalisé Power Platform est décrit dans `connector/power-platform.swagger.yaml` (Swagger 2.0, 4 opérations
dont `askRegulatoryQuestion`) : importer le fichier dans Power Apps / Copilot Studio (Connecteurs personnalisés → Importer un
fichier OpenAPI), puis ajouter l'action `askRegulatoryQuestion` à l'agent. Il pointe sur l'API déployée en **HTTP** ; si
Power Platform exige HTTPS, ouvrir un tunnel HTTPS (ngrok ou cloudflared) et y remplacer `host` et `schemes` (procédure :
[docs/openapi-changes.md](docs/openapi-changes.md), section « Power Platform »). Cette intégration est **documentée, non
testée de bout en bout** dans un tenant Microsoft 365.

## Checklist finale

Coché seulement quand c'est vrai et vérifiable ; ◐ = partiel.

| | Critère | Preuve / commentaire |
|---|---|---|
| ◐ | La solution démarre depuis une machine vierge avec ce README | Installation des dépendances et import de l'API vérifiés dans un environnement neuf ; il faut ensuite une base PostgreSQL (locale via Docker, puis chargement des données, section 3). Non rejoué de bout en bout sur une machine vierge. |
| ✅ | Aucun secret personnel n'est requis | Aucune clé d'IA n'est nécessaire (mode mots-clés, testé : [tests/test_agent.py](tests/test_agent.py)) ; [.env.example](.env.example) ne contient aucun secret ; seul `DATABASE_URL` est à fournir ou à créer en local. |
| ✅ | Sources, licences et limites documentées | [data/source_registry.csv](data/source_registry.csv), [docs/limitations.md](docs/limitations.md) |
| ✅ | Données officielles, dérivées et fictives distinguables | `*_original` / `*_normalized`, `validation_status`, `is_synthetic` : [data/field_dictionary.csv](data/field_dictionary.csv), [docs/db_schema.md](docs/db_schema.md) |
| ✅ | L'API suit le contrat documenté | [openapi.proposed.yaml](openapi.proposed.yaml), [docs/openapi-changes.md](docs/openapi-changes.md), tests : [tests/test_api.py](tests/test_api.py) |
| ✅ | Le script d'évaluation fonctionne | `python scripts/evaluate_submission.py evaluation/our_submission.json` → 70 / 70 ([evaluation/our_submission.json](evaluation/our_submission.json)) |
| ✅ | Limites connues et avertissement réglementaire visibles | Avertissement en tête de ce README, champ `disclaimer` dans chaque réponse de l'API, [docs/limitations.md](docs/limitations.md) |
| ✅ | Intégration Microsoft 365 documentée | [connector/power-platform.swagger.yaml](connector/power-platform.swagger.yaml) (documentée ; non testée dans un tenant) |

## L'équipe

| Personne | Rôle |
|---|---|
| **Youness** | Coordination, backend et agent IA |
| **Dyland** | Adaptateur Canada et recherche data  |
| **Nhan** | Adaptateurs France et déploiement |
| **Damien** | Frontend, contrat d'API, connecteur Microsoft 365 |
| **Hanane** | Adaptateur Allemagne, recherche Azure |

---

# Starter kit d'origine

Le reste de ce fichier est le README du starter kit fourni par les organisateurs, conservé tel quel (hors checklist, remplacée
plus haut), suivi de l'ajout de l'équipe sur la stack Docker et le front.

## LPC Global Regulatory AI Starter Kit

Starter repository for the Lallemand Plant Care challenge at Hackathon IA for Impact 2026.

## Mission
Build a functional proof of concept that collects, structures, normalizes and compares official plant protection product registration information across markets. Any technology may be used, but the result must expose a credible Microsoft 365 integration path.

## Minimum success criteria
1. Integrate at least **3 official sources** from at least **2 regions**.
2. Produce a product x country x use comparison.
3. Preserve original values alongside normalized values.
4. Cite the official source and collection timestamp for every regulatory assertion.
5. Make uncertainty, missing fields and validation status visible.
6. Demonstrate or document Microsoft 365 interoperability.
7. Deliver a repository restartable from this README without personal API keys.

> **Regulatory disclaimer:** This repository and any prototype built from it are not official regulatory sources. Extracted information requires Regulatory Affairs validation before official, commercial or operational use. No result must not be interpreted automatically as no registration.

## Repository map
```text
.
├── README.md / QUICKSTART.md / LICENSE.md / CONTRIBUTING.md
├── data/          # CSV templates and starter records
├── schema/        # Canonical model, JSON Schema and OpenAPI
├── evaluation/    # Rubric, gold questions and output contract
├── scripts/       # Data validation and scoring
├── business/      # Questions and glossary
├── sources/       # Source-use and attribution guidance
├── examples/      # Sample API and submission payloads
└── tests/         # Smoke test
```

## Start
```bash
git clone <repository-url>
cd lpc-global-regulatory-ai-starter
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
cp .env.example .env
python scripts/validate_data.py
python scripts/evaluate_submission.py examples/sample_submission.json
```
No third-party Python package is required for the starter scripts.

## Before development
- Select the 3 official sources and 2 regions.
- Select pilot products or active entities.
- Document the normalization and human-review workflow.
- Choose the Microsoft 365 integration mechanism.
- Test every access and prepare a frozen fallback extract.

## Data rules
- Never modify `*_original` values.
- Put transformations in `*_normalized` fields.
- Regulatory assertions require `source_id`, `source_record_url`, `collected_at` and `validation_status`.
- Use `unknown` or `not_found` rather than inventing information.
- Sister-product matches are hypotheses until reviewed.
- Synthetic data must use `is_synthetic=true`.

## Canonical contract
- Field definitions: `data/field_dictionary.csv`
- Data model: `schema/canonical_data_model.md`
- JSON Schema: `schema/canonical.schema.json`
- Minimal API: `schema/openapi.yaml`

Teams may extend the contract but must not silently remove traceability fields.

## EPPO mappings
The included mapping files are deliberately small. Candidate codes are marked `to_verify`; teams must verify them against EPPO before changing the status to `validated`.

## Microsoft 365 interoperability
Power Platform custom connector (Copilot Studio / Power Automate): see `docs/power-platform.md`.

Demonstrate or document at least one: REST API importable as a custom connector, Dataverse export, SharePoint/Power Automate JSON or CSV flow, Copilot Studio action, Azure/Entra ID design, or Teams/SharePoint interface.

## Final checklist
Voir la [checklist finale](#checklist-finale) plus haut (cochée selon l'état réel du projet, avec les preuves).

---

## Stack Docker et front (ajout de l'équipe)

Le front Angular et le `docker-compose.yml` viennent du coéquipier front. Dossiers : `frontend/` et `backend/`. Les commandes ci-dessous sont reprises telles quelles de son README.

# Hackathon Lallemand

```
.
├── frontend/            Angular 22 + Tailwind 4 + Spartan NG (front only, pnpm)
├── backend/             Backend (techno à définir)
├── docker-compose.yml   Lance toute la stack (commenté, à lire !)
├── .env.example         Modèle des variables d'environnement (front + back + docker)
└── .env                 Tes valeurs locales (non commité)
```

## Démarrage

```bash
cp .env.example .env          # 1 fois, puis ajuster les valeurs

# Option A - tout avec Docker (comme en production)
docker compose up -d --build  # front sur http://localhost:8080

# Option B - dev front avec rechargement à chaud
cd frontend && pnpm install && pnpm start   # http://localhost:4200
```

Back + front : `docker compose --profile backend up -d --build` (la base est le PostgreSQL d'équipe, `DATABASE_URL` du `.env`).

### Base PostgreSQL locale (optionnelle, installation autonome)

Sans accès au serveur d'équipe : `docker compose --profile localdb up -d postgres` crée une base vide
(PostgreSQL 16, `db/schema.sql` exécuté une seule fois à la création du volume `pg_data`). Ensuite, dans `.env` :
`DATABASE_URL=postgresql+psycopg://lallemand:lallemand@localhost:5432/lallemand`, puis recharger les données
(`python backend/etl/load_db.py --no-test`, adaptateurs, `--normalize-db`). Ne jamais lancer ce profil pour remplacer la base d'équipe.

## Variables d'environnement

Un seul fichier : `.env` à la racine.
- Docker Compose et le back le lisent directement.
- Angular ne lit pas les `.env` : `frontend/scripts/generate-env.mjs` (lancé automatiquement par `pnpm start/build/test`) convertit les variables `FRONT_*` en `frontend/src/environments/environment.ts` (fichier généré, non commité).
- Tout ce qui est `FRONT_*` est public (embarqué dans le JS du navigateur) : aucun secret.

Ajouter une variable front : la déclarer `FRONT_XXX` dans `.env.example` et `.env`, l'ajouter dans `generate-env.mjs`, et dans les `args` du service `frontend` (`docker-compose.yml`) + `ARG/ENV` du `frontend/Dockerfile`.

## Déployer sur un serveur (rappel Docker)

1. Installer Docker + le plugin compose sur le serveur, cloner le repo.
2. `cp .env.example .env` et **changer les mots de passe**.
3. `docker compose --profile backend up -d --build`
4. Mise à jour : `git pull && docker compose --profile backend up -d --build`

Le front appelle `/api/...` : nginx (dans le conteneur front) redirige vers le service `backend`.

## UI : Tailwind + Spartan NG

- Styles globaux dans `frontend/src/styles.css` (Tailwind 4 + thème Spartan, via `.postcssrc.json`).
- Les composants Spartan sont **copiés dans le repo** (`frontend/src/app/ui/`, modifiables) et importés via l'alias `@spartan-ng/helm/<composant>`.
- Ajouter un composant : `cd frontend && pnpm exec ng g @spartan-ng/cli:ui <nom>` (ex : `input`, `dialog`).

## Back-end Python : API et agent `/ask`

```powershell
python -m venv .venv ; .venv\Scripts\Activate.ps1 ; pip install -r requirements.txt   # 1 fois
copy .env.example .env      # puis renseigner DATABASE_URL (base PostgreSQL de l'équipe)
uvicorn backend.app.main:app --port 3000                     # docs : http://localhost:3000/docs
```

`POST /ask` (aussi sous `/api/ask`) répond en langage naturel **uniquement à partir de la base**, avec preuves vérifiées :

```powershell
curl.exe -X POST http://localhost:3000/api/ask -H "Content-Type: application/json" -d '{\"question\":\"Dans quels pays LALSTOP G46 est-il homologue ?\"}'
```

- **Sans clé IA** (`AI_API_KEY` vide dans `.env`) : tout marche en mode dégradé (compréhension par mots-clés, phrases par gabarit, `generator.mode = "keyword"`).
- **Avec IA** : renseigner `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL` (tout fournisseur compatible avec le SDK `openai`). Le LLM comprend la question et rédige 1 à 3 phrases ; le code fournit les faits et **vérifie** le texte (preuves citées existantes, chiffres présents dans les faits, jamais « non homologué » sur un résultat vide). Si un contrôle échoue, la réponse devient « Résumé indisponible — voir le tableau sourcé ci-dessous ».
- Code : `backend/app/agent.py` (pipeline en 6 étapes) et `backend/app/llm.py` (client IA).
- Tests : `pytest -q` (avec ou sans clé IA). Score du jeu de questions de référence : `python scripts/run_gold.py` (écrit `evaluation/our_submission.json`).
