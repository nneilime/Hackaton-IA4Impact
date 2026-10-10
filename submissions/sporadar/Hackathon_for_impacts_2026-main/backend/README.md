# Backend

API FastAPI (`backend/app/`) + chargement/normalisation des données (`backend/etl/`).
Contrat : `openapi.proposed.yaml` (v0.2.1), expliqué dans `docs/openapi-changes.md`. Base : `docs/db_schema.md`.

## Lancer l'API

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --port 3000        # depuis la racine du dépôt
```

- Documentation interactive : http://localhost:3000/docs
- Chaque route existe à la racine (`/health`) **et** sous `/api` (`/api/health`) : le nginx du frontend ne retire pas `/api`.
- Variables (fichier `.env`) : `DATABASE_URL` (obligatoire), `API_KEY` (vide = accès libre ; sinon en-tête `X-API-Key` obligatoire sauf `/health`), `BACK_PORT`.
- Docker : `docker compose --profile backend up -d --build` (le contexte de build est la racine du dépôt, car l'API lit `data/`).

## Routes

| Route | Rôle |
|---|---|
| `GET /health` | Santé (publique) |
| `GET /products` | Recherche par nom, alias, synonymes (`search_terms_for`) et substance active ; `matchedVia` dit comment chaque produit a été trouvé |
| `GET /products/{id}/registrations` | Homologations par pays, originaux + normalisés, preuves, `coverage` par marché |
| `GET /products/{id}/sisters` | Produits sœurs = **hypothèses** (`product_aliases` + `product_name_mapping`) |
| `GET /compare` | Usages alignés par code EPPO, une cellule par pays (jamais de mélange) ; `format=csv` |
| `GET /issues` | Champs manquants, incertains, non validés, sans code EPPO, en conflit |
| `GET /expirations` | Homologations expirées, retirées ou qui expirent bientôt |
| `GET /sources` | Sources officielles et fraîcheur de collecte |
| `POST /ask` | 501 pour l'instant (agent LLM à venir) |

Règles : lecture seule sur la base ; données fictives (`is_synthetic`) masquées sauf `includeSynthetic=true` ; un produit inconnu renvoie
404 « No match. This is not proof of no registration. » ; un pays sans résultat est `not_found` ou `not_covered`, jamais « non homologué ».
Les listes se paginent avec `limit` / `offset` ; `usesLimit` plafonne les usages par homologation.

## Régénérer les modèles Pydantic

`backend/app/models.py` est **généré** à partir du contrat, ne pas l'éditer à la main :

```powershell
datamodel-codegen --input openapi.proposed.yaml --input-file-type openapi `
  --output-model-type pydantic_v2.BaseModel --output backend/app/models.py `
  --use-standard-collections --use-union-operator --target-python-version 3.11
```

## Tests

```powershell
pytest tests/test_api.py -q      # interroge la vraie base en lecture seule (ignoré sans DATABASE_URL)
```

## Lancer les adaptateurs France et Allemagne

Voir le [guide de lancement des adaptateurs](etl/adapters/README.md) : configuration
PostgreSQL, démarrage Docker, exécution Python locale, exports CSV et dépannage.
Chaque pays dispose de son propre fichier Compose dans `backend/etl/adapters/france/`
ou `backend/etl/adapters/germany/`.
