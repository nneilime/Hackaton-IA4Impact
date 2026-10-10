# Contrat API v0.2.1 : ce qui change et pourquoi

*English version below.*

## En bref

- `openapi.proposed.yaml` étend le contrat du starter (v0.1.0) **sans rien casser** : les 5 routes, leurs `operationId`, leurs paramètres, les champs obligatoires et leurs types sont identiques. Tout ce qui est nouveau est optionnel ou une nouvelle route.
- **v0.2.1 : aligné sur la base PostgreSQL de l'équipe (`db/schema.sql`). Aucune table ni colonne à ajouter.** Chaque champ du contrat vient d'une colonne existante, d'une jointure, ou d'un calcul fait par l'API au moment de la requête (détail dans « Impact sur la base »).
- Vérifié automatiquement : spec OpenAPI 3.1 valide, compatibilité ascendante avec `openapi.yaml` contrôlée champ par champ, génération des modèles Pydantic v2 avec `datamodel-code-generator` qui passe, et l'exemple de réponse `/ask` se valide contre le modèle `Answer` généré.
- `connector/power-platform.swagger.yaml` est une version Swagger 2.0 réduite à 4 opérations pour le connecteur personnalisé Power Platform / Copilot Studio (validée Swagger 2.0).
- Les wireframes (`docs/wireframes.html`) montrent, pour chaque type de question, quel champ de l'API alimente quel élément de l'écran.

| Fichier | Rôle |
|---|---|
| `openapi.yaml` / `schema/openapi.yaml` | Contrat du starter, inchangé (référence d'origine) |
| `openapi.proposed.yaml` | **Nouveau contrat de référence** (OpenAPI 3.1) |
| `connector/power-platform.swagger.yaml` | Import dans Power Platform (Swagger 2.0) |
| `docs/wireframes.html` | Gabarits de réponse par type de question |
| `mocks/examples.yaml` | 19 réponses d'exemple fictives (une par type de question et par route), référencées par le contrat et servies par Prism |

## Le raisonnement : deux points de vue

**Côté IA (l'agent qui répond).** Pour répondre honnêtement, l'agent a besoin de trois choses que l'ancien contrat ne donnait pas : savoir *où et sous quels noms* on a cherché (sinon « rien trouvé » devient « non homologué », le comportement interdit de T01), pouvoir *relier chaque phrase à sa preuve* (T05), et recevoir des données *déjà structurées par type de question* pour ne pas avoir à les inventer ou les reformater. L'IA comprend la question et rédige la conclusion ; le code remplit tout le reste.

**Côté interface (l'écran qui présente).** L'interface choisit un gabarit selon le type de question : liste de pays (T01), tableau aligné par code EPPO (T02), file de travail (T03), cartes d'hypothèses (T04), panneau de preuve sur chaque valeur (T05). Pour ça, elle a besoin de `intent`, du bloc de données correspondant, de l'original à côté du normalisé, et d'un état explicite pour chaque case vide.

## Les changements, un par un

| # | Ajout | Pourquoi | Impact back-end |
|---|---|---|---|
| 1 | `CountryCoverage` (`coverage[]`) sur `/products/{id}/registrations`, `/compare`, `/ask` | T01 interdit de conclure « non homologué » faute de résultat. `outcome` distingue `found`, `not_found`, `source_unavailable`, `not_covered`, avec les sources, la date de collecte et les noms cherchés. | Calculé à la requête : liste des marchés cibles en config, `source_registry` (pays de chaque source), `collection_runs` (dernière collecte et son statut), noms cherchés via `normalize.search_terms_for()`. Règles plus bas. |
| 2 | `Answer` enrichi : `intent`, `answerStatus`, `parameters`, `facts`, un champ typé par intention (`registrations`, `comparison`, `products`, `issues`, `sisterCandidates`, `expirations`, `sources`), `suggestedQuestions`, `clarificationOptions`, `generator` | L'interface choisit le gabarit avec `intent` et affiche « ce que l'IA a compris ». Les champs typés (plutôt qu'un `data` libre) passent dans la génération Pydantic et dans Swagger 2.0. | Le pipeline `/ask` (section dédiée) : classification + extraction par le LLM, puis appel des mêmes fonctions que les routes REST. Rien n'est stocké. |
| 3 | `Fact` avec `evidenceIds`, et `Evidence.evidenceId` | T05 : « la source de chaque donnée ». Une liste de preuves à plat ne dit pas quelle preuve appuie quelle phrase. | Id construit depuis les clés existantes : `registration:{registration_id}`, `use:{use_id}`, `field:{field_evidence.evidence_id}`. Les faits sont construits **par le code** à partir des lignes renvoyées, jamais par le LLM. |
| 4 | Originaux : `Registration.statusOriginal`, `productNameOriginal`, `activeEntityOriginal` (+ `doseUnitOriginal` du starter) | Règle d'or « garder l'original à côté du normalisé ». L'écran affiche les deux. | Rien à ajouter : `status_original` est en base, et `productNameOriginal` / `activeEntityOriginal` sont les colonnes du produit de l'enregistrement (chaque source charge ses propres lignes `products`). |
| 5 | Conditions d'emploi : `doseUnitNormalized`, `applicationMethod`, `maxApplications`, `applicationIntervalDays`, `phiDays`, `reiHours`, dates `approvalDate`, `expirationDate` | Le cahier demande doses et conditions d'emploi comparables. Ces colonnes sont **déjà en base** (`uses`, `registrations`) mais absentes de l'OpenAPI du starter. | Exposer les colonnes. Pas de conversion d'unité (`field_dictionary.csv` : « Do not alter meaning ») : `doseValue` reste dans son unité, deux unités différentes sont signalées comme une différence. |
| 6 | `MatchedVia` sur `Registration`, `Product.aliases[]` | Le piège du défi : M52 s'appelle F52 ou *M. anisopliae* ailleurs. L'utilisateur doit voir quand une correspondance repose sur un alias encore « à vérifier ». | `normalize.search_terms_for()` donne déjà les synonymes ; la requête retient par quel nom chaque ligne a été trouvée. `aliases[]` = `product_aliases` + `product_name_mapping` + `active_entity_mapping`. Calculé à la volée. |
| 7 | `cropMappingStatus`, `targetMappingStatus` (`validated`, `to_verify`, `unmapped`) | Normalisation EPPO (15 pts) : montrer quand un code est fiable, incertain ou absent. | Jointure `uses.eppo_crop_code` → `eppo_crop_mapping.mapping_status` (code UNIQUE, idem cibles) ; `unmapped` si l'original est rempli et le code vide. |
| 8 | `ComparisonResponse.rows[]` → `ComparisonRow` → `ComparisonCell` (`state`, `uses` du pays seulement), `differsAcrossCountries` | T02 interdit de mélanger les valeurs des pays. Le back aligne les lignes par code EPPO, une cellule par pays. | Regroupement en Python sur `uses` + `registrations` (algorithme plus bas). `registrations[]` reste rempli comme avant. |
| 9 | `Evidence` : `sourceName`, `sourceRecordUrl`, `confidence`, `isFrozenExtract`, `isSynthetic`, `languageOriginal` | Lien direct vers la fiche officielle, confiance IA **séparée** du statut de validation, extraits figés et données fictives visibles. | Tout existe : voir le tableau « Impact sur la base ». |
| 10 | Nouvelles routes : `/products/{id}/sisters`, `/issues`, `/expirations`, `/sources`, `/reviews` (optionnelle) | T04 + bonus produits sœurs ; T03 en file de travail ; bonus « alerte d'expiration » ; fraîcheur des sources dans l'en-tête ; validation humaine (fonction avancée, optionnelle). | Chaque route est un `SELECT` sur l'existant. `/sisters` (nom prévu dans `CLAUDE.md`) lit `product_aliases`, déjà rempli par `write_sisters()` de `load_db.py`. |
| 11 | `/products` : filtres `activeEntity`, `crop`, `target`, `country`, `includeCompetitors`. `/compare` : `crop`, `target`, `format=csv` | Question R&D « quels produits avec telle souche sur la tomate » et question terrain. CSV exploitable dans Excel / Power Automate. | Filtres SQL (index déjà présents sur `eppo_crop_code`, `eppo_target_code`, `country_code`) ; CSV = une ligne par pays × usage avec les colonnes de preuve. |
| 12 | Sécurité `X-API-Key` (sauf `/health`), `servers` corrigés, 404 clarifié | Le connecteur Power Platform a besoin d'une auth déclarée. Le back écoute sur `BACK_PORT=3000`, routes sous `/api` (cf. nginx du front). | Middleware : si `API_KEY` est vide, pas de contrôle (dev local) ; sinon 401. Ajouter `API_KEY=` dans `.env.example`. Le 404 ne sert qu'à un `productId` inconnu. |
| 13 | Énumérations nommées (`ValidationStatus`, `RegistrationStatus`, `CoverageOutcome`, `Intent`…) en `$ref` | Demande du fil archi : des modèles Pydantic propres avec `datamodel-code-generator`. | `datamodel-codegen --input openapi.proposed.yaml --input-file-type openapi --output-model-type pydantic_v2.BaseModel --output models.py` |

## Ce que ça change pour le back, par priorité

**P0, nécessaire pour la démo T01 → T05**
1. Générer les modèles Pydantic depuis `openapi.proposed.yaml`.
2. Exposer les originaux déjà stockés et construire `evidenceId` à partir des clés existantes.
3. Recherche par noms et alias sur toutes les sources (voir « Points d'attention »), `matchedVia` rempli.
4. `coverage` calculé sur `/products/{id}/registrations` et dans `/ask`.
5. `/ask` avec `intent`, `parameters`, `facts`, `coverage` et le champ typé de l'intention (pipeline ci-dessous).

**P1, ce qui fait la différence sur T02, T03, T04**
6. `/compare` avec `rows` alignées par EPPO.
7. `/issues` (règles ci-dessous).
8. `/products/{id}/sisters` depuis `product_aliases` et `product_name_mapping`.

**P2, bonus et confort**
9. `/expirations`, `/sources`, `format=csv` sur `/compare`, filtres de `/products`.

**P3, si le temps le permet**
10. `/reviews` (validation humaine).

## Le pipeline `/ask` : l'IA comprend, le code remplit

1. **Comprendre (LLM, sortie structurée).** Le LLM reçoit la question et renvoie uniquement `{intent, productIds, countries, activeEntity, crop, target, referenceDate}`. Il ne voit aucune donnée à ce stade. Si le produit est ambigu : `answerStatus = needs_clarification` + `clarificationOptions`.
2. **Résoudre les noms (code).** Produits et entités actives → alias (`normalize.search_terms_for()`) ; culture et cible → codes EPPO (`normalize_crop()`, `normalize_target()`).
3. **Interroger (code).** Appeler la fonction de la route correspondante (tableau dans les wireframes, section « Intention → API ») et calculer `coverage`.
4. **Construire les faits (code).** Chaque `Fact` est créé depuis une ligne de la base avec ses `evidenceIds`. Les compteurs (validés, à vérifier, pas trouvés, non couverts) sont calculés par le code.
5. **Rédiger (LLM).** Le LLM reçoit les faits, la couverture et les compteurs, et écrit `answer` en une ou deux phrases. Consigne : n'utiliser que ces faits, dire l'incertitude, ne jamais écrire « non homologué » pour un pays `not_found`.
6. **Contrôler (code).** Retirer tout fait sans preuve existante, ajouter un `warning` ; si `answer` contient une négation d'homologation pour un pays `not_found`, la remplacer par une formulation sûre générée par le code. Ajouter `disclaimer` et `suggestedQuestions` (selon l'intention : T01 → comparer, T02 → champs incertains, etc.).

Fournisseur et modèle viennent de `AI_BASE_URL` / `AI_MODEL` (cf. `.env`) et sont renvoyés dans `generator`. Sans clé IA, `/ask` répond en mode dégradé (intention par mots-clés, phrase générée par gabarit). Pas de recherche web dans `/ask`.

## Règles de calcul

**`coverage[].outcome` (par pays cible)**
- `not_covered` : aucune source de ce pays n'a de collecte réussie dans `collection_runs`. Attention, `source_registry` liste aussi BE, US, BR, UY, MX : être listé ne veut pas dire être intégré.
- `source_unavailable` : la dernière collecte de toutes les sources du pays a le statut `failed` ou `source_unavailable`.
- `found` : au moins un enregistrement trouvé (par nom ou alias).
- `not_found` : collecte réussie, aucun résultat. Toujours accompagné de `searchedTerms` et `lastCollectedAt`.

**`ComparisonCell.state`**
- Clé de ligne : `(eppoCropCode, eppoTargetCode)` ; à défaut, `(cropNormalized, targetNormalized)` en minuscules ; à défaut, les originaux.
- `present` : le pays a au moins un usage sur cette ligne.
- `absent_in_extracted_uses` : le pays a un enregistrement mais aucun usage extrait sur cette ligne (peut être un trou d'extraction, d'où ce libellé prudent).
- `registration_not_found`, `source_unavailable`, `not_covered` : repris de `coverage`.
- `differsAcrossCountries` : les couples (`doseValue`, `doseUnitNormalized`) diffèrent entre les seuls pays qui ont une valeur (un pays sans usage extrait n'est pas une différence ; son état est dans `cells[].state`).
- `alignedBy` (hors contrat, à reporter par Damien) : clé d'alignement de la ligne, `eppo` (code EPPO), `normalized_name` (nom normalisé, insensible à la casse) ou `original` (valeur d'origine).

**`/issues`**
- `missing` : champ canonique attendu à `NULL` (statut, dose, culture, cible, numéro, dates).
- `uncertain` : `field_evidence.confidence < 0.7` ou `product_aliases.confidence < 0.7`.
- `not_validated` : `validation_status` vaut `automatically_extracted` ou `to_verify`.
- `unmapped` : original rempli mais pas de code EPPO pour la culture ou la cible.
- `conflicting` : deux sources donnent des valeurs différentes pour le même champ.
- `source_unavailable` : dernière ligne de `collection_runs` en `failed` ou `source_unavailable`.
- `issueId` déterministe : `{issueType}:{entityType}:{entityId}:{field}`.
- Priorité : `high` pour un alias à vérifier utilisé dans `matchedVia` ou un statut non validé ; `medium` pour une dose ou un code EPPO ; `low` pour le reste.

## Impact sur la base

**Structure : aucun changement.** Pas de `CREATE`, pas d'`ALTER`. Le contrat a été ajusté pour coller à `db/schema.sql`, pas l'inverse.

| Champ du contrat | D'où il vient |
|---|---|
| `Product.*` | `products` ; `isLpcProduct` = le produit ou son nom figure dans `product_name_mapping` ; `aliases[]` = `product_aliases` + `product_name_mapping` + `active_entity_mapping` |
| `Registration.statusOriginal`, `approvalDate`, `expirationDate` | `registrations` |
| `Registration.productNameOriginal`, `activeEntityOriginal` | `products.commercial_name`, `products.active_entity_original` du produit de l'enregistrement |
| `Registration.matchedVia`, `missingFields`, `warnings` | Calculés par la requête (terme qui a matché, colonnes `NULL`) |
| `AuthorizedUse.*` (dose, unités, PHI, REI, méthode…) | `uses` |
| `cropMappingStatus`, `targetMappingStatus` | `eppo_crop_mapping.mapping_status`, `eppo_pest_mapping.mapping_status` par `eppo_code` |
| `Evidence.sourceId`, `sourceRecordUrl`, `collectedAt`, `validationStatus`, `isSynthetic` | `registrations` (les usages héritent de la source de leur enregistrement) |
| `Evidence.sourceName`, `sourceUrl` | `source_registry.official_name`, `base_url` |
| `Evidence.confidence`, `excerpt` | `field_evidence` (par `entity_type`, `entity_id`, `field_name`) |
| `Evidence.isFrozenExtract` | `collection_runs.input_file` renseigné (chez vous, tout passe par des CSV : `true`) |
| `Evidence.languageOriginal` | Table pays → langue dans le code (FR → fr, DE → de, CA → en) |
| `CountryCoverage`, `SourceInfo` | `source_registry` + `collection_runs` (statut, `finished_at`, `rows_written`) |
| `SisterCandidate` | `product_aliases` (`sister_product_candidate`, `confirmed_sister_product`) + `product_name_mapping` |
| `ExpirationItem` | `registrations.expiration_date` (index `idx_reg_expiration` déjà là) |
| `Fact`, `Answer`, `ComparisonRow`, `DataIssue` | Calculés à chaque requête, rien n'est stocké |

**Retiré du contrat en v0.2.1 parce que la base ne le stocke pas** : `Product.holder`, `Registration.holderOriginal`, `AuthorizedUse.doseOriginal`, `AuthorizedUse.doseValueNormalized`. **Corrigé** : `SourceInfo.accessMethod` accepte les valeurs combinées de `source_registry` (`api/web`, `api/download`), `SourceInfo.baseUrl` peut être `null` (MX-COFEPRIS-TBD), `SisterCandidate.confidenceScore` et `evidenceSummary` peuvent être `null` (colonnes facultatives de `product_aliases`).

**Points d'attention (pas de changement de schéma, mais à savoir côté back)**
- **Un même produit a un `product_id` par source.** Le chargement E-Phy crée un produit par homologation (13 569 / 13 569). `GET /products/P-LPC-M52/registrations` qui filtrerait seulement sur `product_id` ne trouverait que les lignes rattachées à cet id. Il faut chercher par noms et alias sur toutes les sources, et c'est exactement ce que `matchedVia` rend visible.
- **`field_evidence.evidence_id` est un `BIGSERIAL`** : stable tant que `reset_DANGER.sql` n'est pas lancé. Après un reset, les `evidenceId` en `field:` changent ; le front ne doit pas les garder d'une session à l'autre.
- **`v_comparison` n'expose pas** `dose_unit_normalized`, `phi_days`, `application_method`… Soit `/compare` lit les tables, soit on ajoute ces colonnes **à la fin** de la vue (`CREATE OR REPLACE VIEW` l'accepte). Facultatif.
- **`/reviews` (P3) sans nouvelle table** : mettre à jour `validation_status` ou `review_status` de la ligne visée. L'ETL ne l'écrase pas (`keep` dans `load_db.py`, et `WHERE review_status = 'to_verify'` sur les alias). Garder l'historique (qui, quand, commentaire) demanderait une table : hors périmètre.

## Power Platform

> Procédure à jour (hôte HTTPS, import du `.json` généré, Copilot Studio, Power Automate) : `docs/power-platform.md`. Les étapes ci-dessous (tunnel ngrok sur le port 8080) sont l'ancienne version.

1. Lancer la stack, puis un tunnel HTTPS (ngrok ou cloudflared) vers le port du front (`8080`) : il sert l'app **et** `/api`.
2. Dans `connector/power-platform.swagger.yaml`, remplacer `host` par le domaine du tunnel.
3. Power Apps / Copilot Studio → Connecteurs personnalisés → Importer un fichier OpenAPI → ce fichier. Authentification : clé API, en-tête `X-API-Key`.
4. Dans Copilot Studio, ajouter l'action `askRegulatoryQuestion` à l'agent. Sa description demande déjà de citer source et statut.

L'URL gratuite de ngrok change à chaque relance : lancer le tunnel une fois et ne plus y toucher avant la démo.

## Lien avec `evaluate_submission.py`

Le script lit un fichier de soumission JSON, pas l'API. Il attend du snake_case (`source_id`, `source_url`, `collected_at`, `validation_status`, `disclaimer`, `warnings`, `m365_integration`, `known_limitations`). Prévoir un petit script qui pose les 5 questions test à `/ask` et convertit `Answer` → format de soumission (`sourceId` → `source_id`, etc.). Avec `m365_integration.mechanism = "copilot_studio"` et `documentation_url` pointant vers ce document.

## Points ouverts

- **`CLAUDE.md` désigne encore l'ancien contrat** (« contrat EXACT de schema/openapi.yaml » et « API : schema/openapi.yaml (ne pas le modifier) »). Tant que ces deux lignes restent, un Claude qui code le back implémentera l'ancien contrat. Remplacement proposé : « API : openapi.proposed.yaml (v0.2.1, étend schema/openapi.yaml sans le casser ; schema/openapi.yaml reste intact) ».
- `/export` prévu dans `CLAUDE.md` fait doublon avec `/compare?format=csv` : en garder un seul.
- Nom du champ : `intent` (vocabulaire de `business_questions.csv`) plutôt que `answerType` évoqué par le fil archi. À trancher, le reste ne change pas.
- Liste des marchés cibles affichés comme « non couverts » : CA, US, MX, BR, UY, FR, DE, BE, ES, IT par défaut.
- `/reviews` est optionnel ; à ne coder que si P0 à P2 sont finis.

---

# API contract v0.2.1: what changed and why

## Summary

- `openapi.proposed.yaml` extends the starter contract (v0.1.0) **without breaking it**: the 5 routes, their `operationId`, parameters, required fields and types are unchanged. Everything new is optional or a new route.
- **v0.2.1: aligned on the team PostgreSQL schema (`db/schema.sql`). No table or column to add.** Every contract field comes from an existing column, a join, or a value computed by the API at query time.
- Checked automatically: valid OpenAPI 3.1, field-by-field backward compatibility with `openapi.yaml`, Pydantic v2 generation with `datamodel-code-generator` works, and the `/ask` example validates against the generated `Answer` model.
- `connector/power-platform.swagger.yaml` is a Swagger 2.0 file reduced to 4 operations for the Power Platform custom connector / Copilot Studio (validated as Swagger 2.0).
- The wireframes (`docs/wireframes.html`) show, for each question type, which API field drives which part of the screen.

## The reasoning: two points of view

**AI side (the agent answering).** To answer honestly, the agent needs three things the old contract lacked: knowing *where and under which names* we searched (otherwise "nothing found" turns into "not registered", T01's forbidden behaviour), linking *every sentence to its evidence* (T05), and receiving data *already structured per question type* so it never invents or reshapes it. The AI understands the question and writes the conclusion; code fills everything else.

**UI side (the screen presenting).** The UI picks a template from the question type: country list (T01), EPPO-aligned table (T02), work queue (T03), hypothesis cards (T04), evidence panel on every value (T05). It needs `intent`, the matching data block, the original next to the normalized value, and an explicit state for every empty cell.

## Changes

1. **`CountryCoverage`** on registrations, compare and ask: `found`, `not_found`, `source_unavailable`, `not_covered`, with sources, collection date and searched names. Computed from `source_registry`, `collection_runs` and `normalize.search_terms_for()`.
2. **`Answer` extended**: `intent`, `answerStatus`, `parameters`, `facts`, one typed field per intent, `suggestedQuestions`, `clarificationOptions`, `generator`. Typed fields instead of a free `data` object so Pydantic generation and Swagger 2.0 work.
3. **`Fact` + `evidenceId`**: each statement points to its evidence (T05). Ids are built from existing keys (`registration:…`, `use:…`, `field:…`). Facts are built by code from database rows, never by the LLM.
4. **Originals**: `statusOriginal`, `productNameOriginal`, `activeEntityOriginal` (plus the starter's `doseUnitOriginal`), all read from existing columns.
5. **Conditions of use**: `doseUnitNormalized`, application method, max applications, interval, PHI, REI, approval and expiry dates, already stored in `uses` and `registrations`. No unit conversion.
6. **`MatchedVia` and `Product.aliases`**: shows when a match relies on an alias still to verify (F52 / Ma 43). Computed at query time from the mapping tables.
7. **EPPO mapping status** on crop and target (`validated`, `to_verify`, `unmapped`), joined from the EPPO mapping tables.
8. **Comparison rows**: rows keyed on `(eppoCropCode, eppoTargetCode)`, one cell per country with an explicit `state`; country values are never merged (T02).
9. **Evidence extras**: `sourceName`, `sourceRecordUrl`, AI `confidence` (from `field_evidence`) kept separate from `validationStatus`, `isFrozenExtract`, `isSynthetic`, `languageOriginal`.
10. **New routes**: `/products/{id}/sisters` (T04 + bonus, name taken from `CLAUDE.md`), issues (T03), expirations (bonus), sources (freshness), reviews (optional).
11. **Filters**: `/products` by active entity, crop, target, country; `/compare` by crop and target, plus `format=csv`.
12. **Security and servers**: `X-API-Key` on everything but `/health` (disabled when `API_KEY` is empty), servers on port 3000 under `/api`, 404 only for an unknown `productId`.
13. **Named enums with `$ref`** for clean Pydantic models.

## Backend priorities

- **P0 (demo T01 → T05)**: generate models; expose stored originals and build evidence ids; search by names and aliases across sources with `matchedVia`; `coverage`; `/ask` pipeline.
- **P1**: `/compare` rows, `/issues`, `/sisters`.
- **P2**: `/expirations`, `/sources`, CSV, `/products` filters.
- **P3**: `/reviews`.

## `/ask` pipeline

1. LLM structured output: `{intent, productIds, countries, activeEntity, crop, target, referenceDate}` only, no data.
2. Code resolves aliases and EPPO codes (`normalize.py`).
3. Code calls the same functions as the REST routes and computes coverage.
4. Code builds facts with evidence ids and counters.
5. LLM writes `answer` from those facts only, stating uncertainty, never "not registered" for `not_found`.
6. Code drops facts without evidence (adds a warning), replaces any unsafe negation, adds disclaimer and suggested questions.

Provider and model come from `AI_BASE_URL` / `AI_MODEL` and are echoed in `generator`. Without an AI key, `/ask` runs in degraded mode. No web search in `/ask`.

## Database impact

**No schema change.** The contract was adjusted to `db/schema.sql`: `holder`, `holderOriginal`, `doseOriginal` and `doseValueNormalized` were removed; `accessMethod` accepts combined values (`api/web`); `baseUrl`, sister `confidenceScore` and `evidenceSummary` may be `null`. Things to know: the same product has one `product_id` per source, so lookups must search by names and aliases across sources; `field_evidence.evidence_id` changes after `reset_DANGER.sql`; `v_comparison` lacks some use columns (query the tables or append columns to the view). The field-by-field mapping table is in the French section.

## Power Platform, submission script, open points

See the French sections above: the 4-step connector import (tunnel on port 8080, set `host`, import, add the `askRegulatoryQuestion` action), the snake_case conversion script for `evaluate_submission.py`, and open points (`CLAUDE.md` still names the old contract, `/export` vs `/compare?format=csv`, `intent` vs `answerType`).

## Added outside the contract: `granularity` on `/compare` (for Damien to report)

- Query parameter `granularity` = `use` (default, one row per crop × target, unchanged) | `crop` (one row per normalized crop).
- Response: top-level `granularity`; in `crop` mode `rows[].targetNormalized` / `eppoTargetCode` are `null` and each present cell has `summary`: `{useCount, targetsOriginal[], doses[{unitOriginal, min, max}]}`. Doses are per ORIGINAL unit, never converted or mixed. "Authorized yes/no" = `state` (`present` or not).
- When `use` level has no row with values in 2+ countries but a crop exists in 2 countries, `warnings` suggests `granularity=crop`.
- `/ask` (`use_comparison`) switches to crop level automatically in that case and says so in the first sentence.

## Added outside the contract: `GET /opportunities` and intent `market_opportunity` (for Damien to report)

"Free spaces for biocontrol": per country × normalized crop × normalized target, how many distinct ACTIVE chemical vs biological products (and uses) exist. Read-only, decision support only. Code: `backend/app/opportunities.py`.

**Request**: `GET /opportunities?country=FR&crop=&target=&productId=&lpcOnly=false&minChemicalUses=5&limit=20` (`lpcOnly=true` keeps only pairs where an LPC product, a sister candidate or a same-substance product is already authorized; `limit` 1-100, `country` optional ISO code, `crop` / `target` EPPO code or name in any language, `productId` = LPC product, e.g. `P-LPC-M52`). Also available under `/api/opportunities`. Unknown `productId` → 404.

**Response** `OpportunitiesResponse`: `items[]`, `evidence[]` (the contract `Evidence` objects), `warnings[]`, `categoryMethod` (`rule_based`), `scoreFormula`, `minChemicalUses`, `disclaimer`. Each `items[]` entry (`Opportunity`):

| Field | Meaning |
|---|---|
| `countryCode`, `cropNormalized`, `targetNormalized` | the pair (only uses that have BOTH normalized) |
| `chemicalUses`, `biologicalUses`, `unknownCategoryUses` | active uses by category (rule-based, see below); information only, not used in the score |
| `chemicalProducts`, `biologicalProducts`, `unknownCategoryProducts` | distinct products behind those uses; the score is computed on these (in Germany one product often has several uses on the same pair, which inflated a score computed on uses) |
| `chemicalToBiologicalRatio` | `chemicalProducts / biologicalProducts`, `null` when there is no biological product |
| `biocontrolSpaceScore` | `chemicalProducts / (1 + biologicalProducts)`; the list is sorted by it, descending (ties: more chemical products, then more chemical uses) |
| `usesWithUnknownRegistrationStatus` | uses of registrations whose source gives no status (DE). They are counted as present, not as "active" |
| `lpcProducts[]` | LPC products, sister candidates and same-active-substance products authorized on the pair: `relation` (`lpc_product` / `sister_candidate` / `same_active_substance`), `reviewStatus` (anything but `lpc_product` is `to_verify` = hypothesis), `productCategory`, `categoryMethod`, `evidenceIds` |
| `withdrawnSameSubstance` | see below, `null` when the country has no "withdrawn" status in its source |
| `evidenceIds`, `chemicalEvidenceIds`, `biologicalEvidenceIds` | `use:` / `registration:` ids present in the top-level `evidence[]` (up to 2 sample uses per category: the counts are over all uses, the evidence is a sample) |
| `productCategoryMethod`, `disclaimer` | `rule_based`; "Aide à l'analyse, pas une décision réglementaire ; classification biologique/chimique par règle, à vérifier." |

**What the data does NOT say** (also in `warnings`): no source provides withdrawn USES (FR `RETIRE` registrations have no use rows; DE has no status). The ranking shows today's state, not a decline over time.

**Biological / chemical classification** (`productCategory`, always `categoryMethod = rule_based`, a hypothesis and never an official category): `biological` if the ORIGINAL active entity contains a micro-organism genus (Bacillus, Trichoderma, Clonostachys, Coniothyrium, Metarhizium, Beauveria, Pseudomonas, Streptomyces, Saccharomyces, Paecilomyces… plus "virus" for insect viruses) or if the product is an LPC product; `unknown` if the active entity is empty; `chemical` otherwise. So `chemical` means "not identified as a micro-organism": copper, sulphur, pyrethrins are in it. The list is `BIO_GENERA` in `opportunities.py`.

**`withdrawnSameSubstance`** (product-level indicator, never a withdrawn use): `{countryCode, withdrawnProducts, substancesCompared, note, evidenceIds}`. Counts the WITHDRAWN products of the same country that contain a substance of the chemical products active on the pair (exact substance name). It has no link to the crop × target. The `note` says so.

**`/ask`**: new `intent` value `market_opportunity` (questions such as "Où les usages chimiques reculent-ils sur la vigne ?", "Quelles opportunités pour LALGUARD M52 ?"). `Answer.opportunities` carries the top 5 pairs (same `Opportunity` objects); the sentence uses only the facts built from them and ends with the reminder above. With a product, the pairs are those where the product's substance is already authorized in at least one country but not in the country listed. `Answer.suggestedQuestions[].intent` accepts the new value too. Frontend: `Intent` needs the new enum value.
