# Cahier de développement : backend LPC Regulatory AI

Ce document dit **quoi** construire. Le **comment** (code, requêtes, découpage fin) est laissé à celui qui code. Il regroupe les décisions prises par l'équipe et le fil « Présentation des réponses ».

## 0. Sources de vérité

| Sujet | Fichier | Règle |
|---|---|---|
| Contrat d'API | `openapi.proposed.yaml` (v0.2.1, OpenAPI 3.1) | **Fait foi.** Il étend `schema/openapi.yaml` (starter) sans le casser. Là où `CLAUDE.md` dit « contrat EXACT de schema/openapi.yaml », ce cahier prévaut. Ne pas modifier `schema/openapi.yaml`. |
| Base de données | `db/schema.sql`, `docs/db_schema.md` | Schéma figé : aucune table ni colonne à ajouter. |
| Normalisation | `backend/etl/normalize.py` | À réutiliser tel quel (synonymes, EPPO, substances actives, produits sœurs). |
| Ce que l'écran affiche | `docs/wireframes.html` | Un gabarit par type de question, avec les champs d'API qui l'alimentent. |
| Justification du contrat | `docs/openapi-changes.md` | Pourquoi chaque champ existe et d'où il vient en base. |
| Réponses attendues | `mocks/examples.yaml` | Un exemple fictif par type de question et par route : la forme exacte du JSON à produire. Le front tourne dessus avec Prism en attendant le back. Pour vérifier le back contre le contrat : `prism proxy openapi.proposed.yaml http://localhost:3000`. |
| Règles du projet | `CLAUDE.md` | Toujours valables, sauf la ligne sur le contrat. |
| Évaluation | `evaluation/gold_questions.csv`, `evaluation/evaluation_rubric.csv`, `scripts/evaluate_submission.py` | Ce sur quoi le jury et le script notent. |

## 1. Ce qu'on attend de l'application

### Le besoin

Lallemand Plant Care vend des microorganismes de biocontrôle dans plusieurs pays. Chaque pays publie ses homologations dans sa propre base, sa langue et son format. L'application répond en langage naturel à des questions réglementaires, à partir de ces données collectées et normalisées, **avec la source officielle de chaque valeur**. C'est un prototype d'aide à la décision, pas un système réglementaire : chaque réponse rappelle qu'une validation par les Affaires réglementaires est nécessaire.

Utilisateurs : Affaires réglementaires (vérifier, valider), R&D (chercher par souche, culture, cible), équipes terrain (savoir ce qui est autorisé où).

Une seule API sert deux clients : le front Angular et un agent Copilot Studio (Microsoft 365) via un connecteur Power Platform. Les deux reçoivent le même JSON.

### Les types de question (champ `intent`)

| `intent` | Question type | Ce que l'utilisateur doit obtenir |
|---|---|---|
| `registration_lookup` | Dans quels pays le produit X est-il homologué ? | Une ligne par pays cible : trouvé (statut, numéro, dates, source), cherché sans résultat, source indisponible ou pays non couvert. |
| `use_comparison` | Comparer les usages de X entre deux pays | Un tableau culture × cible aligné par code EPPO, une colonne par pays, doses et restrictions, jamais de valeur fusionnée. |
| `ingredient_search` | Quels produits avec le microorganisme X sur la tomate ? Quel produit contre l'oïdium ? | Les produits (LPC et concurrents) avec leurs homologations correspondantes, cherchés par substance, culture ou cible. |
| `expiry_watch` | Quelles autorisations expirent dans les 12 prochains mois ? | Liste triée par date d'expiration, avec jours restants et source. |
| `data_quality` | Quels champs sont manquants ou incertains pour X ? | Une file de travail priorisée : champ, problème, confiance IA, statut de validation, preuve. |
| `sister_product` | Quels produits pourraient être des produits sœurs de X ? | Des hypothèses avec ce qui les rapproche, score de confiance et statut de revue. Jamais présentées comme des faits. |
| `source_lookup` | Donne la source de chaque donnée | Chaque valeur citée avec sa source, son lien direct, sa date de collecte et son statut. |
| `other` | Hors sujet ou impossible à traiter | Une réponse honnête (`out_of_scope`) et des questions suggérées. |

### Les questions test du jury

| Test | Question | Doit contenir | Interdit |
|---|---|---|---|
| T01 | Dans quels pays le produit pilote est-il homologué ? | pays, statut, URL source, date de collecte, statut de validation | Conclure « non homologué » parce qu'on n'a rien trouvé |
| T02 | Comparer les usages entre deux pays | culture, cible, dose, restrictions, preuves | Mélanger les valeurs de deux pays |
| T03 | Quels champs sont incertains ? | champs manquants, alertes, statut de validation | Cacher l'incertitude |
| T04 | Quels produits pourraient être des produits sœurs ? | candidat, preuve, confiance, statut de revue | Présenter une hypothèse comme un fait |
| T05 | Donne la source officielle de chaque donnée | source_id, URL, date de collecte | Répondre sans preuve |

Produits pilotes : LALSTOP CONTANS WG (*Coniothyrium minitans*), LALSTOP G46 WG (*Clonostachys rosea* J1446, ex *Gliocladium catenulatum*), LALGUARD M52 OD (*Metarhizium brunneum* F52 / Ma 43, ex *M. anisopliae*). Le piège : le même produit ou la même souche porte d'autres noms selon le pays.

### Ce qui est noté (rubrique sur 100)

Qualité des données 20, traçabilité 20, normalisation EPPO 15, IA ancrée dans les données 15, Microsoft 365 15, architecture (relançable, sans clé perso, fournisseur IA remplaçable) 10, expérience utilisateur 5, bonus (détection de changements ou workflow produits sœurs) 5.

## 2. Règles non négociables

Elles s'appliquent à toutes les routes, y compris `/ask`.

1. Toute valeur réglementaire renvoyée porte sa preuve : `sourceId`, `sourceRecordUrl` (ou à défaut `sourceUrl`), `collectedAt`, `validationStatus`.
2. Aucune donnée inventée. Ce qui n'est pas en base est `null`, `unknown` ou `not_found`, jamais deviné.
3. Une absence de résultat n'est **jamais** présentée comme une absence d'homologation, ni dans les données ni dans le texte.
4. L'original est toujours renvoyé à côté du normalisé (statut, culture, cible, unité de dose, substance active).
5. Les valeurs de deux pays ne sont jamais fusionnées, moyennées ni converties pour être comparables. Pas de conversion d'unité de dose.
6. Confiance IA (`confidence`) et statut de validation humaine (`validationStatus`) sont deux champs séparés, jamais combinés.
7. Les produits sœurs et les alias non validés sont des hypothèses : leur statut de revue est toujours visible.
8. Les données fictives (`isSynthetic = true`) restent visibles comme telles.
9. Chaque réponse porte un `disclaimer` (validation par les Affaires réglementaires requise) et ses `warnings`.
10. L'application tourne sans clé IA (mode dégradé) et sans identifiant dans le code.

## 3. Périmètre

**À construire :** l'API FastAPI de `backend/app/` qui implémente tout `openapi.proposed.yaml`, le pipeline `/ask`, l'authentification par clé, le `Dockerfile`, les tests, un script qui produit le fichier de soumission pour `evaluate_submission.py`, et la partie back du README.

**Hors périmètre :** les ingesteurs par pays et le chargement (`scripts/`, `backend/etl/`, gérés par d'autres), le schéma de la base, le front (`frontend/`), les fichiers du starter kit, la recherche web, une base vectorielle.

## 4. Architecture

### Vue d'ensemble

```
sources officielles → ingesteurs (équipe) → normalize.py / load_db.py → PostgreSQL
                                                                           │
                                     backend FastAPI (ce cahier) ◄─────────┘
                                       │                        │
                     nginx du front (/api) → Angular       connecteur Power Platform → Copilot Studio
```

### Choix imposés

- Python 3.11+, FastAPI, modèles Pydantic v2 **générés** depuis `openapi.proposed.yaml` avec `datamodel-code-generator` (ne pas les écrire à la main ; les régénérer si le contrat change).
- Accès base via `DATABASE_URL` (PostgreSQL de l'équipe). Lecture seule, sauf `/reviews`. Le service MySQL du `docker-compose.yml` n'est pas utilisé par le back.
- Port `BACK_PORT` (3000). Routes exposées à la racine **et** sous `/api` : le nginx du front transmet `/api/...` sans retirer le préfixe.
- `backend/Dockerfile`, lancé par `docker compose --profile backend up -d --build`.
- Fournisseur IA interchangeable par `.env` (`AI_PROVIDER`, `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY`). Aucun SDK de fournisseur ailleurs que dans le module IA.
- Pas de base vectorielle dans le MVP : les questions portent sur des données structurées. Si elle arrive plus tard, elle sert à retrouver des extraits d'étiquette, jamais à conclure sur une homologation.
- Code simple, commenté, lisible par une équipe débutante (`CLAUDE.md`).

### Découpage en couches

| Couche | Responsabilité |
|---|---|
| Routes | Fines : lire les paramètres, vérifier la clé, appeler un service, renvoyer le modèle du contrat ou une erreur `Problem`. |
| Services métier | Un par domaine : recherche de produits (avec synonymes et `matchedVia`), homologations + couverture, comparaison, problèmes de qualité, produits sœurs, expirations, sources. **Chaque service sert à la fois sa route REST et `/ask`.** |
| Accès aux données | Requêtes sur les tables existantes. Aucune écriture hors `/reviews`. |
| Normalisation | Réutilise `normalize.py` pour les synonymes (`search_terms_for`), les codes EPPO et les substances actives. |
| Module IA | Seul endroit qui appelle un LLM : comprendre la question (sortie structurée) et rédiger la phrase de conclusion. Remplaçable par configuration. |
| Garde-fous | Contrôles après rédaction (section 7). |
| Configuration | Variables d'environnement uniquement. |

### Comment le back sert le front

- **Contrat d'abord.** Le front développe sur un mock Prism de `openapi.proposed.yaml`. Le back doit renvoyer exactement les formes du contrat : chaque réponse doit se valider contre le schéma, testé automatiquement.
- **Même donnée en REST et via `/ask`.** Une question posée en langage naturel et l'appel REST équivalent renvoient les mêmes enregistrements, parce qu'ils passent par le même service.
- **Un gabarit par intention.** `/ask` renvoie `intent` et remplit le bloc typé qui correspond :

| `intent` | Service | Route REST équivalente | Bloc de `Answer` | Gabarit (wireframes) |
|---|---|---|---|---|
| `registration_lookup` | homologations + couverture | `GET /products/{id}/registrations` | `registrations`, `coverage` | T01, lignes par pays |
| `use_comparison` | comparaison | `GET /compare` | `comparison`, `coverage` | T02, tableau EPPO |
| `ingredient_search` | recherche produits | `GET /products?activeEntity=&crop=&target=` | `products` | matrice produits × pays |
| `expiry_watch` | expirations | `GET /expirations` | `expirations` | liste d'échéances |
| `data_quality` | qualité | `GET /issues` | `issues` | T03, file de travail |
| `sister_product` | produits sœurs | `GET /products/{id}/sisters` | `sisterCandidates` | T04, cartes d'hypothèses |
| `source_lookup` | sources + preuves | `GET /sources` | `sources`, `facts`, `evidence` | T05, panneau de preuve |

- **Chaque valeur affichée est cliquable vers sa preuve.** Tout `evidenceId` cité dans `facts` ou dans un usage existe dans le tableau `evidence` de la même réponse.
- **Aucun vide muet.** Un pays sans résultat a un `coverage.outcome`, une case de comparaison vide a un `state`, une réponse sans donnée a un `answerStatus`. Jamais de tableau vide sans explication.
- **Langue.** `language` (fr ou en) pilote le texte de `answer`, les libellés de `facts` et les questions suggérées. Les valeurs originales ne sont jamais traduites.
- **Ordre stable.** Pays dans l'ordre demandé, puis ordre de la liste des marchés cibles ; lignes de comparaison triées ; ids déterministes d'un appel à l'autre.
- **Erreurs.** 401 si la clé manque ou est fausse ; 404 uniquement pour un `productId` inconnu (jamais pour « pas d'homologation ») ; 422 pour un paramètre invalide ; corps au format `Problem`.
- **Temps de réponse.** Routes REST rapides sur les données de démo ; `/ask` en quelques secondes, au plus deux appels au LLM.
- **CORS.** Inutile derrière nginx. En dev, autoriser seulement `http://localhost:4200`.

## 5. Données

### Tables disponibles (rien à créer)

`products`, `product_aliases`, `registrations`, `uses`, `source_registry`, `product_name_mapping`, `active_entity_mapping`, `eppo_crop_mapping`, `eppo_pest_mapping`, `collection_runs` (journal des collectes), `field_evidence` (preuve champ par champ, confiance, méthode, modèle), vue `v_comparison`.

### D'où vient chaque champ du contrat

| Champ du contrat | Source |
|---|---|
| `Product.*` | `products` ; `isLpcProduct` = le produit ou son nom figure dans `product_name_mapping` ; `aliases` = `product_aliases` + `product_name_mapping` + `active_entity_mapping` |
| `Registration.*` (statut original et normalisé, dates, numéro) | `registrations` |
| `Registration.productNameOriginal`, `activeEntityOriginal` | colonnes du produit auquel l'enregistrement est rattaché |
| `Registration.matchedVia`, `missingFields`, `warnings` | calculés par la recherche |
| `AuthorizedUse.*` | `uses` |
| `cropMappingStatus`, `targetMappingStatus` | `mapping_status` des tables EPPO, par code EPPO |
| `Evidence` (source, lien, date, statut, fictif) | `registrations` ; les usages héritent de leur enregistrement |
| `Evidence.sourceName`, `sourceUrl` | `source_registry` |
| `Evidence.confidence`, `excerpt` | `field_evidence` |
| `Evidence.isFrozenExtract` | collecte faite depuis un fichier daté (`collection_runs.input_file`) |
| `Evidence.languageOriginal` | correspondance pays → langue en configuration |
| `CountryCoverage`, `SourceInfo` | `source_registry` + `collection_runs` |
| `SisterCandidate` | `product_aliases` (types sœurs, déjà remplis par `load_db.py`) + `product_name_mapping` |
| `ExpirationItem` | `registrations.expiration_date` |
| `Fact`, `Answer`, `ComparisonRow`, `DataIssue` | calculés à chaque requête, jamais stockés |

### Pièges connus

- **Un même produit a un `product_id` par source.** L'import E-Phy crée un produit par homologation. Chercher les homologations d'un produit uniquement par son id ne trouve qu'un pays : il faut chercher par ses noms, alias et substance active sur toutes les sources, et dire par quel nom chaque ligne a été trouvée (`matchedVia`).
- **`source_registry` liste des pays non intégrés** (BE, US, BR, UY, MX…). Être listé ne veut pas dire être couvert : la couverture se juge sur les collectes réussies.
- **Les ids de `field_evidence` changent** si la base est réinitialisée (`reset_DANGER.sql`).
- **`v_comparison` n'a pas toutes les colonnes d'usage** (unité normalisée, DAR, méthode…). Lire les tables directement si besoin.
- **D'autres coéquipiers écrivent en parallèle** dans la base : ne jamais figer des compteurs ou des listes en dur.
- **Un mot courant peut couvrir plusieurs cibles.** « Oïdium » désigne plusieurs champignons (vigne : *Erysiphe necator*, cucurbitacées : *Podosphaera xanthii*…). Dans `data/eppo_pest_mapping.csv`, le mot seul « oïdium » n'est rattaché qu'à *Golovinomyces orontii*. Filtrer sur ce seul code EPPO raterait la vigne : chercher aussi dans les cibles d'origine (texte) et prendre tous les concepts dont un nom ou un alias contient le mot.

## 6. Routes à coder

Toutes les routes sauf `/health` exigent l'en-tête `X-API-Key`. Formes exactes : `openapi.proposed.yaml`.

| Route | Rôle | Jalon |
|---|---|---|
| `GET /health` | État de l'API et de la connexion base, sans clé | 1 |
| `GET /products` | Recherche par nom ou alias (`q`) ; filtres `activeEntity`, `crop`, `target`, `country`, `includeCompetitors` | 1 (`q`), 3 (filtres) |
| `GET /products/{id}/registrations` | Homologations par pays avec usages, preuves, `matchedVia` et `coverage` sur les marchés cibles | 1 |
| `GET /compare` | Comparaison des usages entre pays, `rows` alignées par EPPO, `coverage` ; `format=csv` | 2 (JSON), 3 (CSV) |
| `GET /issues` | Problèmes de qualité, filtrables par produit, pays, type | 2 |
| `GET /products/{id}/sisters` | Candidats produits sœurs avec preuves, confiance, statut de revue | 2 |
| `POST /ask` | Question en langage naturel → réponse structurée (section 7) | 2 |
| `GET /expirations` | Homologations qui expirent dans `withinMonths` mois à partir de `referenceDate` | 3 |
| `GET /sources` | Sources, fraîcheur, disponibilité, nombre d'enregistrements | 3 |
| `POST /reviews` | Décision humaine sur un enregistrement, un usage, un alias ou un candidat sœur | 4 (optionnel) |

Précisions :

- **`/products/{id}/registrations`** : `coverage` contient une entrée par marché cible, même sans source. Le filtre `country` restreint les homologations, pas la liste de couverture.
- **`/compare`** : `registrations` reste rempli comme dans le contrat du starter, `rows` s'y ajoute. Le CSV contient une ligne par pays × usage avec les colonnes de preuve, pour Excel et Power Automate. Il remplace la route `/export` évoquée dans `CLAUDE.md`.
- **`/issues`** : sans filtre, tout le périmètre ; `countsByType` donne le total par type.
- **`/sisters`** : jamais d'affirmation ; si aucune preuve officielle n'appuie un candidat, il reste en hypothèse avec un avertissement.
- **`/reviews`** : met à jour le statut de validation ou de revue de la ligne visée (le chargement ne l'écrase pas). Pas d'historique : il demanderait une table, hors périmètre.

## 7. Le pipeline `/ask` : l'IA comprend, le code remplit

| Étape | Qui | Ce qui se passe |
|---|---|---|
| 1. Comprendre | LLM | Reçoit la question seule, renvoie en sortie structurée l'intention et les paramètres (`productIds`, `countries`, `activeEntity`, `crop`, `target`, `referenceDate`). Ne voit aucune donnée. |
| 2. Résoudre | code | Noms de produits et substances → synonymes ; cultures et cibles → codes EPPO. Si `productId` ou `countries` sont fournis dans la requête, ils priment. Produit ambigu → `answerStatus = needs_clarification` avec `clarificationOptions`, sans chercher plus loin. |
| 3. Interroger | code | Appelle le service de l'intention (tableau section 4), calcule la couverture. |
| 4. Construire les faits | code | Chaque `Fact` vient d'une ligne de la base et cite ses `evidenceIds`. Les compteurs (validés, à vérifier, non trouvés, non couverts) sont calculés ici. |
| 5. Rédiger | LLM | Reçoit uniquement les faits, la couverture et les compteurs ; écrit `answer` en une ou deux phrases dans la langue demandée, en disant l'incertitude. |
| 6. Contrôler | code | Retire tout fait sans preuve existante (avec un `warning`). Si le texte nie une homologation dans un pays `not_found`, le remplace par une formulation sûre. Vérifie que les chiffres et ids cités existent dans les faits. Ajoute `disclaimer`, `suggestedQuestions`, `generator`. |

Exigences :

- **Mode dégradé** (pas de clé IA ou fournisseur en erreur) : intention détectée par mots-clés, phrase de conclusion produite par gabarit à partir des compteurs, `generator` l'indique. Les cinq questions test doivent passer dans ce mode.
- **`answerStatus`** : `answered` si tout est trouvé et validé, `partial` si une partie manque ou reste à vérifier, `no_data` si rien n'est trouvé dans nos sources (sans conclure à une absence d'homologation), `out_of_scope` hors périmètre, `needs_clarification` si ambigu.
- **`suggestedQuestions`** : deux ou trois suites logiques selon l'intention (après une recherche par pays : comparer ; après une comparaison : voir les champs incertains ; etc.).
- **Pas de recherche web**, pas de connaissance générale du LLM dans la réponse : uniquement ce que la base contient.
- La conclusion commence par la réponse et son niveau de certitude (« trouvé dans 2 pays sur 4 cherchés, dont 1 à vérifier »), jamais par une généralité.

## 8. Règles de calcul

- **Marchés cibles** : liste en configuration, par défaut CA, US, MX, BR, UY, FR, DE, BE, ES, IT.
- **`coverage.outcome`** : `not_covered` si aucune source du pays n'a de collecte réussie ; `source_unavailable` si la dernière collecte de toutes ses sources a échoué ou est marquée indisponible ; `found` si au moins un enregistrement est trouvé par un nom ou un alias ; `not_found` sinon, toujours avec `searchedTerms` et `lastCollectedAt`.
- **`matchedVia`** : le nom qui a permis de trouver la ligne et sa nature (nom commercial, alias produit, substance active, alias de substance, numéro d'homologation), avec le statut de revue et la confiance de l'alias quand il y en a un.
- **Lignes de comparaison** : une ligne par couple (code EPPO culture, code EPPO cible) ; à défaut de code, par noms normalisés ; à défaut, par noms originaux.
- **État d'une case** : `present` si le pays a un usage sur la ligne ; `absent_in_extracted_uses` s'il a une homologation mais pas cet usage dans les données extraites ; sinon l'état de couverture du pays (`registration_not_found`, `source_unavailable`, `not_covered`).
- **`differsAcrossCountries`** : vrai si la ligne n'est pas présente partout, ou si la dose ou son unité normalisée diffère.
- **`/issues`** : `missing` (champ attendu vide : statut, numéro, dates, culture, cible, dose) ; `uncertain` (confiance < 0,7) ; `not_validated` (statut `automatically_extracted` ou `to_verify`) ; `unmapped` (original rempli sans code EPPO) ; `conflicting` (deux sources donnent des valeurs différentes pour le même champ) ; `source_unavailable`. Priorité haute pour un alias à vérifier qui sert à une correspondance et pour un statut non validé, moyenne pour une dose ou un code EPPO, basse sinon. `issueId` déterministe (type, entité, id, champ).
- **`evidenceId`** : construit depuis les clés existantes (`registration:…`, `use:…`, `field:…`), stable d'un appel à l'autre.
- **`cropMappingStatus` / `targetMappingStatus`** : statut de la table EPPO pour le code ; `unmapped` si pas de code.
- **`daysUntilExpiration`** : jours entre `referenceDate` (aujourd'hui par défaut) et la date d'expiration.
- **Recherche sans produit nommé** (« quel produit utiliser contre l'oïdium ? » → `ingredient_search`) :
  - l'application ne recommande jamais : elle liste ce qui est homologué, avec l'alerte « Homologué ne veut pas dire recommandé : le choix relève d'un conseiller » ;
  - sans pays ni culture, ne pas bloquer en `needs_clarification` : répondre groupé par pays puis par culture, produits LPC d'abord ;
  - si aucun produit LPC ne correspond, le dire en première phrase (c'est le cas de l'oïdium pour CONTANS, G46 et M52) ;
  - au plus 20 lignes dans `/ask`, le total réel dans le texte de la réponse, et des `suggestedQuestions` pour préciser la culture et le pays. La liste complète passe par `GET /products?target=…`.

## 9. Configuration et sécurité

| Variable | Usage |
|---|---|
| `DATABASE_URL` | Connexion PostgreSQL (jamais d'identifiant dans le code) |
| `BACK_PORT` | Port d'écoute (3000) |
| `API_KEY` | Clé attendue dans `X-API-Key` ; vide = pas de contrôle (dev local). À ajouter dans `.env.example`. |
| `AI_PROVIDER`, `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY` | Fournisseur IA ; clé vide = mode dégradé |
| `TARGET_MARKETS` | Liste des marchés cibles (valeur par défaut ci-dessus) |

Ne jamais journaliser une clé ni la chaîne de connexion. En production, l'authentification visée est Entra ID ; on se contente de la clé pour le prototype et on le documente.

## 10. Microsoft 365

- Le connecteur Power Platform s'importe depuis `connector/power-platform.swagger.json`, généré par `scripts/build_connector.py` à partir de `connector/power-platform.swagger.yaml` (Swagger 2.0, 4 opérations : `askRegulatoryQuestion`, `searchProducts`, `getProductRegistrations`, `compareProductUses`). Ne jamais changer ces `operationId` ni le sens de leurs champs ; si le contrat évolue sur ces 4 opérations, mettre ce fichier à jour.
- Copilot lit surtout `answer` : la phrase doit se suffire à elle-même et citer pays, statut et source.
- Démo : API publiée en HTTPS sur `https://sporadar.nhanlenguyen.dev/api` (mise en place par Nhan). Procédure complète : `docs/power-platform.md`.

## 11. Définition de « terminé »

- [ ] Toutes les routes des jalons 1 à 3 répondent, et chaque réponse se valide contre `openapi.proposed.yaml` (tests automatiques).
- [ ] T01 à T05 passent via `/ask` sur LALGUARD M52 OD, LALSTOP G46 WG et LALSTOP CONTANS WG, avec et sans clé IA, sans aucun comportement interdit.
- [ ] Un pays `not_found` n'est jamais décrit comme « non homologué » (test dédié).
- [ ] Une correspondance via alias à vérifier (F52, *M. anisopliae*) est visible dans `matchedVia` et remonte dans `/issues`.
- [ ] Un script pose les cinq questions test à `/ask` et écrit le fichier de soumission au format de `evaluation/expected_output_template.json` (snake_case, `m365_integration.mechanism = copilot_studio`, `known_limitations`), et `scripts/evaluate_submission.py` le valide.
- [ ] `docker compose --profile backend up -d --build` démarre le back ; le README explique la relance depuis zéro sans clé personnelle.
- [ ] `backend/README.md` décrit la techno, les variables, les commandes et les limites connues.

## 12. À ne pas faire

- Modifier le schéma de la base, les fichiers du starter kit ou `frontend/`.
- Écrire en base ailleurs que dans `/reviews`.
- Convertir des unités de dose ou fusionner des valeurs de pays.
- Laisser le LLM produire une valeur, un id ou un chiffre qui ne vient pas de la base.
- Utiliser une recherche web ou la connaissance générale du LLM pour répondre.
- Exiger une clé personnelle pour lancer le projet.

## 13. Décisions prises par défaut (à confirmer par l'équipe)

- Le champ s'appelle `intent` (vocabulaire de `data/business_questions.csv`), pas `answerType`.
- `/export` est remplacé par `GET /compare?format=csv`.
- `CLAUDE.md` doit pointer vers `openapi.proposed.yaml` au lieu de `schema/openapi.yaml`, et `backend/README.md` doit indiquer FastAPI au lieu de « technologie à définir ».
- **Relance par le jury** : la base d'équipe est un serveur distant que le jury n'atteindra pas. Pour que le dépôt se relance depuis le seul README, il faudra un PostgreSQL local (service du compose) initialisé par `db/schema.sql` puis `backend/etl/load_db.py`. À trancher avec l'équipe qui gère la base.
