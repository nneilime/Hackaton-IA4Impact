# Contexte projet — Hackathon IA for Impact 2026, défi Lallemand Plant Care

## Le sujet
Lallemand Plant Care (LPC) fabrique des microorganismes (champignons, bactéries) qui protègent les plantes.
Chaque pays publie ses homologations de produits de protection des plantes (PPP) dans sa propre base,
avec sa langue et son format. LPC veut un prototype d'agent IA qui collecte, normalise, compare et restitue
ces homologations (produit × pays × usage), interrogeable en langage naturel, avec la source de chaque donnée.
C'est une preuve de concept, pas un système réglementaire officiel.

## Périmètre MVP
- Sources : Canada (Santé Canada PPID, CSV, source_id CA-PPID), France (ANSES E-Phy open data, CSV/XML, FR-EPHY),
  Allemagne (BVL PSM API, JSON, DE-BVL). Plan B si l'Allemagne bloque : US EPA PPLS API.
- Produits pilotes (chercher par ingrédient, pas seulement par marque) :
  - LALSTOP CONTANS WG → Coniothyrium minitans (souche CON/M/91-08)
  - LALSTOP G46 WG → Clonostachys rosea J1446 (ancien nom : Gliocladium catenulatum J1446)
  - LALGUARD M52 OD → Metarhizium brunneum F52 / Ma 43 (anciens noms : Metarhizium anisopliae, M. anisopliae var. anisopliae)

## Règles non négociables (exigences LPC)
1. Chaque donnée réglementaire a : source_id, source_record_url, collected_at (UTC ISO 8601), validation_status.
2. Aucune donnée inventée. Absent = vide / "unknown" / "not_found".
3. Une absence de résultat n'est JAMAIS une preuve d'absence d'homologation.
4. Ne jamais modifier les colonnes *_original ; les transformations vont dans *_normalized.
5. Produits sœurs = hypothèses (review_status "to_verify") tant que non validées.
6. Données fictives : is_synthetic=true, toujours visibles.
7. Aucune clé d'API personnelle requise : le prototype doit tourner sans clé IA (mode dégradé).
8. Fournisseur d'IA interchangeable via .env (AI_BASE_URL, AI_API_KEY, AI_MODEL).
9. Le dépôt doit se relancer depuis le seul README.
10. Ne pas contourner authentification, quotas ou restrictions des sources ; ne pas scraper si une API/un téléchargement officiel existe.

## Architecture
sources officielles → backend/etl/adapters/{france,germany,canada}/ (écrivent directement en base)
→ backend/etl/normalize.py (normalisation EPPO / ingrédients / produits sœurs, sans base)
→ backend/etl/load_db.py (charge les CSV dans PostgreSQL)
→ PostgreSQL (serveur d'équipe, URL dans DATABASE_URL du .env ; jamais d'identifiants dans le code).
  Tables = celles du starter kit : products, product_aliases, registrations, uses, source_registry,
  eppo_crop_mapping, eppo_pest_mapping, active_entity_mapping, product_name_mapping
  + collection_runs (journal des collectes) + field_evidence (preuve champ par champ, confiance, méthode, modèle)
  + vue v_comparison (tableau produit × pays × usage). Schéma exporté dans db/schema.sql.
→ backend/app/ (FastAPI) : contrat EXACT de openapi.proposed.yaml (v0.2.1, étend schema/openapi.yaml sans le casser ; inclut /products/{id}/sisters, /export y est remplacé par /compare?format=csv). Détail : docs/cahier-backend.md.
  Routes exposées à la fois à la racine (/products…) et sous /api (/api/products…) car le nginx du frontend transmet /api/ sans retirer le préfixe.
  Port = variable BACK_PORT (défaut 3000). backend/Dockerfile pour docker compose (profil "backend").
→ /ask : agent LLM à outils + garde-fous (citations d'ID vérifiées, chiffres vérifiés, résultat vide = message fixe)
→ frontend/ (Angular, Damien) : appelle /api/... ; développe d'abord sur un mock Prism de openapi.proposed.yaml (exemples dans mocks/examples.yaml). Détail : docs/cahier-frontend.md.
→ intégration Microsoft 365 (connecteur Power Automate / Copilot Studio, export Excel).
Ne pas toucher frontend/ (sauf demande explicite). Ne pas modifier les fichiers du starter kit.

## Contrats à respecter
- Colonnes : data/field_dictionary.csv, data/products.csv, data/registrations.csv, data/uses.csv
- API : openapi.proposed.yaml (v0.2.1, fait foi pour le front et le back). schema/openapi.yaml = contrat d'origine du starter, à ne pas modifier, ne plus coder dessus.
- Évaluation : evaluation/gold_questions.csv, scripts/evaluate_submission.py

## Environnement
Windows / PowerShell, Python 3.11+, venv .venv. Équipe débutante : code simple, commenté, expliqué.
Sous Windows : lancer les scripts avec PYTHONIOENCODING=utf-8 si erreur d'affichage.

## État actuel (mis à jour 07:30) — fait foi
### Données (base PostgreSQL partagée)
- FR-EPHY : ~13 500 homologations (1 687 actives avec 18 023 usages ; 11 882 retirées SANS usages ; aucune date d'expiration ; tous les usages "Autorisé").
- DE-BVL : ~2 165 homologations, 82 239 usages ; toutes "active" avec expiration_date (l'API BVL ne publie que les produits autorisés) ; status_original vide (à compléter). Ex. LALGUARD M52 OD expire le 2027-04-30, LALSTOP G46 WG le 2035-03-31.
- CA-PPID : ~3 000 homologations (2 089 actives + 937 retirées avec date de fin), ~125 000 usages ; AUCUNE dose (limite de source).
- Aucune donnée de test en base (rechargé avec --no-test). P-DEMO-COMP-01 (kit) est is_synthetic.
- product_aliases.related_product_id : lien EXACT vers le produit sœur ; ne JAMAIS joindre produits et sœurs par le nom.
- ⚠️ Ne JAMAIS exécuter db/schema.sql ni db/reset_DANGER.sql sur la base partagée. Aucun DELETE/DROP/TRUNCATE. db/schema.sql est sans DROP (testé par tests/test_schema_sql.py).

### Chargement et normalisation
- Adaptateurs (écrivent directement en base) : backend/etl/adapters/france/ (Nhan), germany/ (Nhan), canada/ (Dyland).
- Ordre de rechargement : `python backend/etl/load_db.py --no-test` (sources, produits pilotes LPC, dictionnaires) → adaptateurs → `python backend/etl/load_db.py --normalize-db`.
- Normalisation : mappings LPC (prioritaires) puis dictionnaire IA data/ai_term_mapping.csv (method ai_suggested, review_status to_verify). Couverture finale : cultures 87 %, cibles 83 % des lignes. Voir docs/ai_term_mapping.md.

### API et agent
- Contrat : openapi.proposed.yaml (v0.2.1, Damien) + docs/openapi-changes.md. Hors contrat (à reporter par Damien) : matchedVia (/products), generator.mode (/ask), cropGroup/targetGroup, alignedBy, rowsComparable, granularity (/compare), /opportunities.
- backend/app/ : main.py, services.py, db.py (lecture seule), models.py (GÉNÉRÉ par datamodel-codegen), schemas.py, agent.py, llm.py. Routes à la racine ET sous /api. Port BACK_PORT (3000).
- /compare : alignement eppo → normalized_name → original ; granularity=use|crop. Meilleurs cas de démo : docs/demo_cases.md (LALGUARD M52 OD multi-pays ; G46 pour les produits sœurs).
- /ask : pipeline 6 étapes, garde-fous dans le code ; Groq (AI_MODEL=openai/gpt-oss-120b, AI_FALLBACK_MODEL) avec retry + cache ; 3 phrases max ; phrases distinctes not_found / not_covered / source_unavailable ; sans clé → mode keyword. run_gold.py : 70/70, 5/5 en mode llm.
- /opportunities fait (backend/app/opportunities.py) + intention /ask market_opportunity : "espaces libres pour le biocontrôle" par culture × cible et pays (usages chimiques actifs vs biologiques, score, produits LPC/sœurs autorisés, lpcOnly=true). Classification biologique/chimique par règle (hypothèse ; "chemical" = non identifié comme micro-organisme). withdrawnSameSubstance = produits retirés de même substance, SANS lien culture × cible (FR seulement). Usages retirés : CA seulement (champs withdrawn*), mais vides car aucune ligne CA n'a culture ET cible. Lent à froid (8–15 s), cache 2 min.
- Tests : `python -m pytest -q` depuis la racine.

### Déploiement et frontend
- API en production : http://64.176.83.254:3000/api (image construite SUR le serveur par Nhan). Elle lit la base en direct ; après un changement de CODE ou de data/ → Nhan met à jour (git pull + docker build + docker rm -f lpc-api + docker run). Voir docs/deploy.md. API ouverte (API_KEY vide).
- Aucun secret dans git ni dans les images (.dockerignore exclut .env).
- docker-compose : sans MySQL ; postgres local optionnel (profil "localdb").
- Frontend Angular (Damien) fusionné dans main ; doit pointer vers l'API du serveur.
- Phrase de démo : Tomate × taches brunes (FR) = 51 usages chimiques vs 4 biologiques, PRESTOP (sœur de G46) autorisé → GET /opportunities?country=FR&lpcOnly=true&limit=5
- Normalisation finale (lancée sur le serveur) : cultures 87 %, cibles 83 % des lignes. On ne normalise plus.
- CA : +937 produits retirés (historique PPID, avec date de fin), 37 126 usages. ⚠️ Aucune ligne uses CA n'a culture ET cible ensemble (16 025 culture seule / 21 101 cible seule / 0 les deux) → /opportunities?country=CA renvoie items: []. Code withdrawn* prêt (023d1d5). Ne pas inventer de lien, ne pas recharger avant la démo.
- Démo : Tomate × acariens (FR) = 22 produits chimiques vs 2 biologiques, LALGUARD M52 OD autorisé (score = chemicalProducts / (1 + biologicalProducts)). Préchauffage : backend/app/warmup.py.
- Normalisation lourde : SUR LE SERVEUR (docker exec lpc-api python backend/etl/load_db.py --normalize-db). On ne normalise plus.
- 09:31 : fix 500 /ask (2b0a028 : openai dans backend/requirements.txt + client dans try → repli keyword). Redéployé par Nhan à 09:50.
- 09:45 : evaluation/our_submission.json régénéré (FR+DE+CA) et commité.
- 09:50 : mot de passe DB changé par Nhan → DATABASE_URL à jour dans chaque .env (serveur + locaux). Jamais dans git.
- Hébergement : serveur Vultr (Nhan). Pas de migration Azure ; Azure = argument de reprise (image Docker portable).
- Hanane absente : docs/limitations.md + docs/regulatory_validation.md faits par Claude Code.
- Connecteur Power Platform : import de `connector/power-platform.swagger.json` (généré depuis le .yaml par `scripts/build_connector.py`, testé par tests/test_connector.py), hôte `https://sporadar.nhanlenguyen.dev/api` (HTTPS par Nhan). Doc : docs/power-platform.md.
- BACKEND GELÉ : seulement les bugs qui bloquent la démo. Gel total 13:00.