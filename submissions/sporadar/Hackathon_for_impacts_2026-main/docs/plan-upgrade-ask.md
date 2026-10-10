# Plan d'upgrade du back — fiabilité de `/ask`

> Rédigé le 2026-10-10 à partir du banc de robustesse (`scripts/run_robustness.py`, 54 questions).
> **Rien de ce plan n'est appliqué.** Le backend est gelé (voir CLAUDE.md) : chaque lot se décide en équipe.
> Toutes les causes ci-dessous ont été **vérifiées** dans le code et dans la base (requêtes en lecture seule).

## 1. Point de départ

| Mesure | Avec IA (prod, Groq) | Sans IA (mode mots-clés) |
|---|---|---|
| Score du banc | **42/54 (78 %)** | **32/54 (59 %)** |
| Catégorie la plus faible | culture × cible : 5/12 | culture × cible : 3/12 |
| Catégories à 100 % | comparaison, échéances, sœurs, hors périmètre | produit, opportunités, hors périmètre |

Rapports : `evaluation/robustness/report_20261010-101833_prod.md` et `report_20261010-102759_local-nollm.md`.

Relancer le banc :
```powershell
python scripts/run_robustness.py --url http://64.176.83.254:3000/api --sleep 2   # prod
python scripts/run_robustness.py                                                 # code local, avec IA
python scripts/run_robustness.py --no-llm                                        # code local, sans IA
```

## 2. Causes racines (vérifiées)

| # | Cause | Preuve | Questions touchées | Où |
|---|---|---|---|---|
| R1 | `/ask` garde les **8 premiers produits par ordre alphabétique** trouvés au niveau produit (culture ET cible vérifiées séparément), PUIS exige le couple sur une même ligne d'usage. Des produits CA sans couple occupent les 8 places et les vrais couples FR/DE sont perdus. | Colza × *Sclerotinia* : 102 couples en DE. Vigne × thrips : 20 en FR et 6 en DE. Pourtant `/ask` répond `no_data`. | C07, C11 (dans les deux modes) | `agent.run_ingredient_search`, `services.search_products` (un `EXISTS` par critère) |
| R2 | Quand la culture ou la cible a un code EPPO, le filtre se fait **sur le code seul**. Or en France, seuls **37 % des usages ont un code culture et 3 % un code cible**. | La tomate FR (638 usages, « Tomate - Aubergine » → « Tomato; Eggplant ») n'a **aucun** code `LYPES` : `crop=LYPES&country=FR` renvoie 0. | C04, O02, et toute question FR avec culture ou cible résolue | `services.fetch_uses`, `services.search_products` |
| R3 | Les libellés **français courants** ne sont pas traduits. La résolution cherche une correspondance exacte, et le dictionnaire IA ne contient que les libellés d'origine (anglais pour le Canada). | `normalize_target` renvoie `None` pour : rouille asiatique (du soja), acariens, botrytis, thrips, taupins, pucerons, mildiou, rouille, *Phakopsora pachyrhizi*. `normalize_crop` renvoie `None` pour : patates, fraise. | C01, C10 ; mode sans IA : C01–C03, C06, C12 | `backend/etl/normalize.py` (`_eppo_lookup`, `_ai_lookup`) |
| R4 | La cible extraite par l'IA **contient la culture** (« rouille du blé »), ou bien **n'est pas une cible** (« nos produits biologiques »). Le filtre texte ne trouve alors rien. | `TRZAX × '%rouille du blé%'` donne 0 ligne, `TRZAX × '%rouille%'` en donne 151 en FR. | C12, O02 | `agent.UNDERSTAND_SYSTEM`, `agent.resolve` |
| R5 | L'IA **oublie un champ**, et rien ne le rattrape. | T03 : cible absente, donc l'agent liste des produits sur soja en France (AGIL, ANGELUS…) comme s'ils traitaient la rouille asiatique. | T03 | `agent.understand` |
| R6 | Les **souches** (F52, J1446, Ma 43, CON/M/91-08) ne sont pas reconnues seules, et les **fautes de frappe** sur les produits ne sont pas tolérées. | « souche F52 » → 0 produit (la colonne `strain` du mapping n'est pas indexée). « Lalgard M52 » → « pas dans notre catalogue ». | S04, P03 ; mode sans IA : S05 | `normalize.search_terms_for`, `agent.entity_vocabulary`, `agent.resolve_product` |
| R7 | Le texte rédigé affirme **à tort qu'une information manque**. L'intention choisie (`data_quality`) ne fournit pas la date de collecte, et l'IA en conclut qu'elle n'existe pas. | D04 : « Aucune date de collecte n'est indiquée », alors que **chaque** preuve a un `collectedAt`. | D04 | `agent.WRITE_SYSTEM`, `agent.verify_text` |
| R8 | **Canada** : aucune ligne d'usage n'a culture ET cible ensemble (listes séparées au niveau produit, limite de la source PPID). | Soja × rouille asiatique : 0 couple, alors que 106 usages CA ciblent la rouille et 761 visent le soja. | C01, C03 | Données CA (`uses`) : limite de la source, pas un bug |
| R9 | Mode sans IA : règles d'intention trop étroites et vocabulaire limité aux produits LPC. | « vs », « différences », « équivalents », « même souche », « d'où viennent », « renouvellements », « Et en Allemagne ? » sont mal classés. *Beauveria* n'est pas reconnu. | M02, M03, M05, SI02, SI03, D02, E04, T02, T05, C10, S06 | `agent.keyword_intent`, `agent.entity_vocabulary` |
| R10 | « oïdium » se résout vers **une seule espèce** (`GOLOOR`, mapping du starter kit), alors que 3 256 usages sont notés « Powdery mildew ». | C08 réussit, mais avec un périmètre réduit sans le dire. | C08 (écart silencieux) | `data/eppo_pest_mapping.csv` (starter kit, à ne pas modifier) |

## 3. Lots de correction, par ordre de priorité (gain / coût)

Coût : **S** = moins d'une heure, **M** = une demi-journée. Les gains sont des **estimations** à mesurer avec le banc.

### Lot 1 — Couples culture × cible filtrés dans SQL (R1) · S · risque faible
- **Changement** : nouvelle fonction `services.search_products_by_use(entity, crop, target, country, limit)`. Elle cherche les produits qui ont **au moins une ligne d'usage** avec la culture ET la cible ensemble : un seul `EXISTS` sur `uses`, au lieu d'un par critère. Le tri se fait par nombre d'usages correspondants (produits LPC en premier), plus par ordre alphabétique. `run_ingredient_search` l'utilise quand la question a une culture et une cible. Le comportement de `GET /products` ne change pas (contrat).
- **Gain** : C07, C11 dans les deux modes (**+2**).
- **Tests** : test d'intégration « colza × *Sclerotinia sclerotiorum* » renvoie des homologations DE.

### Lot 2 — Correspondance à plusieurs niveaux : code EPPO **ou** nom normalisé (R2) · M · risque moyen
- **Changement** : une seule fonction `services.concept_condition(kind, value, params)`, utilisée par `fetch_uses`, `search_products` et le Lot 1. Pour une valeur résolue en concept, elle construit la condition :
  `u.eppo_X_code = :code OR (u.eppo_X_code IS NULL AND (u.X_name_normalized ~* :mot OR u.X_name_original ~* :mot))`
  avec des limites de mot PostgreSQL (`\m…\M`) sur le nom normalisé du mapping (« Tomato ») et les alias. C'est le même principe que l'alignement de `/compare` (eppo → normalized_name → original).
- **Pourquoi des limites de mot** : « Tomato » doit trouver « Tomato; Eggplant » sans élargir sans contrôle.
- **Gain** : C04 (+1), et une meilleure couverture de **toute** question FR avec culture ou cible (seuls 3 % des cibles FR ont un code).
- **Risque** : résultats plus larges. Il faut contrôler les cas de démo (`docs/demo_cases.md`) et `scripts/run_gold.py`, qui doit rester à 70/70.

### Lot 3 — Synonymes de requête FR/EN (R3) · S · risque faible
- **Changement** : nouveau fichier `data/query_synonyms.csv` (`kind, term, eppo_code, normalized_name, note`), lu par `normalize_crop` et `normalize_target` en **dernier recours**, après le mapping LPC et le dictionnaire IA. Il ne sert **qu'à la lecture des questions** : aucune renormalisation de la base (« on ne normalise plus »). Chaque ligne vise un nom qui **existe en base** (vérifié le 2026-10-10) :

  | Terme(s) | Concept | Présence en base |
  |---|---|---|
  | rouille asiatique (du soja), *Phakopsora pachyrhizi* | `PHAKPA` / « Asian soybean rust (Phakopsora pachyrhizi) » | CA 106 |
  | acariens, acarien | « Mites » | FR 466, DE 144, CA 45 |
  | thrips | « Thrips » | FR 315, DE 515, CA 71 |
  | taupins | « Wireworms » | DE 49 |
  | pucerons | « Aphids » | FR 708, DE 4 731, CA 135 |
  | mildiou | « Downy mildew » | FR 764, DE 501 |
  | rouille | « Rust » | FR 716, DE 356, CA 47 |
  | botrytis, pourriture grise | `BOTRCI` | déjà résolu pour « pourriture grise » |
  | sclérotinia | `SCLESC` | CA 292, DE 777, FR 153 |
  | patate(s) | `SOLTU` | 1 706 usages codés |
  | fraise, fraisier | `FRAAN` | 1 580 usages codés |
- **Gain** : C10 (+1, avec le Lot 2 : les taupins DE n'ont pas de code cible). C'est aussi un prérequis pour C01 et T03. En mode sans IA : C01–C03, C06, C12.
- **Règle** : méthode `query_synonym`, `review_status = to_verify`, comme le dictionnaire IA.

### Lot 4 — Nettoyer la culture et la cible extraites (R4) · S · risque faible
- **Changement** :
  1. Consigne de `UNDERSTAND_SYSTEM` : « target = le ravageur, la maladie ou l'adventice SEUL, sans la culture ; null si ce n'est pas un organisme nuisible (ex. « nos produits biologiques ») ».
  2. Filet dans `resolve` : si la cible n'est pas résolue et contient la culture (« rouille du blé »), on retire « du/de la/des <culture> » et on réessaie.
  3. Une cible qui ne se résout pas et ne contient aucun mot de plus de 3 lettres connu en base est **ignorée**, avec une note visible : « cible non reconnue : X ».
- **Gain** : C12, O02 (**+2**).

### Lot 5 — Compléter la compréhension de l'IA par les mots-clés (R5) · S · risque faible
- **Changement** : dans `understand`, si l'IA laisse vide `crop`, `target`, `activeEntity` ou `productNames`, on reprend la valeur trouvée par `keyword_understanding`, qui existe déjà et ne contient rien d'inventé (seulement du vocabulaire connu).
- **Gain** : T03 (+1, avec le Lot 3 : la cible « rouille asiatique » est retrouvée, la réponse FR devient un `no_data` propre au lieu d'une liste hors sujet). La robustesse générale augmente aussi.

### Lot 6 — Souches et fautes de frappe (R6) · S · risque faible
- **Changement** :
  1. `search_terms_for` et `entity_vocabulary` indexent aussi la colonne `strain` de `active_entity_mapping.csv` : « F52 » → *Metarhizium brunneum*, « J1446 » → *Clonostachys rosea*.
  2. `resolve_product` : si rien n'est trouvé, on compare par jeton (« M52 » est déjà une clé connue) puis par ressemblance (`difflib`, seuil ≥ 0,85) avec les clés de `known_products()`. Un seul candidat → on le retient, **avec une note** « interprété comme LALGUARD M52 OD ». Plusieurs → clarification.
- **Gain** : S04, P03 (**+2**) ; en mode sans IA : S05.

### Lot 7 — Garde-fous de rédaction (R7, et R5 côté texte) · S · risque faible
- **Changement** :
  1. Nouveau contrôle dans `verify_text` : toute phrase qui dit qu'une date de collecte ou une source **manque** (« aucune date de collecte », « pas de source ») est remplacée. C'est toujours faux, puisque chaque preuve porte `collectedAt` et `sourceId`.
  2. `UNDERSTAND_SYSTEM` : « date de collecte », « d'où viennent les données » → `source_lookup`.
  3. Si la question vise une cible (« contre », « pour traiter », « against ») mais qu'aucune cible n'a été retenue, la réponse le dit (note + gabarit) au lieu de répondre en silence pour la culture seule.
- **Gain** : D04 (+1), et T03 n'induit plus en erreur.

### Lot 8 — Canada : listes culture et cible au niveau produit (R8) · M · **décision Regulatory Affairs requise**
- **Constat** : pour le Canada, la source publie cultures et cibles en **listes séparées** par produit. Le couple n'existe pas dans les données. La règle actuelle (« ne pas inventer de lien ») fait répondre `no_data`.
- **Option proposée** : si le filtre strict ne donne rien et qu'une homologation CA a **à la fois** la culture et la cible dans ses listes, renvoyer `partial` avec l'avertissement : « Health Canada publie les cultures et les cibles en listes séparées : le produit mentionne le soja ET la rouille asiatique, mais l'association n'est pas confirmée par la source. Vérifier l'étiquette officielle. » Chaque usage cité garde `validation_status = to_verify`. On ne crée aucune ligne d'usage et on n'affirme aucun couple.
- **Gain** : C01, C03 (**+2**). O04 (opportunités CA) reste vide : c'est voulu.
- **À trancher** avant de coder : cette présentation respecte-t-elle la règle 3 et l'esprit de « ne pas inventer de lien » ?

### Lot 9 — Mode sans IA (R9) · S · priorité basse (la prod tourne avec l'IA)
- **Changement** :
  - Dans `keyword_intent` : « vs », « différence », « mêmes doses » → comparaison ; « équivalent », « même souche » → sœurs ; « d'où viennent », « collect » → sources ; « renouvel », « à échéance » → échéances.
  - Un `productId` de contexte et un pays seul (« Et en Allemagne ? ») → `registration_lookup`.
  - « dans quels pays » prime sur « source officielle ».
  - Le vocabulaire des substances est complété par les noms distincts de `products.active_entity_normalized` (*Beauveria bassiana*…).
- **Gain** : environ +10 questions en mode sans IA (32 → environ 42/54).

## 4. Points à trancher (hors code)

1. **Lot 8** : présentation des listes canadiennes (Regulatory Affairs / LPC).
2. **R10, oïdium** : le mapping du starter kit (à ne pas modifier) envoie « oïdium » vers `GOLOOR`. Faut-il faire primer un synonyme de requête « oïdium → Powdery mildew » sur ce mapping, uniquement pour la lecture des questions ?
3. **Gel du backend** : quels lots passent avant la démo ? Les parcours de démo par `/opportunities` et `/compare` passent au banc (O01, O03, M01). **Attention** : C04 « Quels produits contre les acariens sur tomate en France ? » échoue (`no_data`). C'est le couple de la phrase de démo, posé en langage naturel. Si cette question risque d'être posée en direct, le Lot 2 devient bloquant pour la démo. Sinon, passer par la question « opportunités » (O01), qui fonctionne.

## 5. Gain attendu (estimation)

| Après | Avec IA | Sans IA |
|---|---|---|
| Aujourd'hui | 42/54 | 32/54 |
| Lots 1 à 7 | environ 52/54 (il reste C01, C03 : limite CA) | environ 38/54 |
| + Lot 8 | environ 54/54 | environ 40/54 |
| + Lot 9 | — | environ 50/54 |

## 6. Ordre de mise en œuvre et vérification

Ordre : **1 → 2 → 3 → 4 → 5 → 6 → 7**, puis 8 après décision, puis 9. Après **chaque** lot :
1. Tests unitaires ciblés dans `tests/test_agent.py` / `tests/test_normalize.py`. Les fonctions pures (synonymes, nettoyage de la cible, ressemblance des noms) se testent sans base.
2. `python -m pytest -q` : tout doit rester vert (161 tests aujourd'hui).
3. `python scripts/run_gold.py` : doit rester à **70/70**.
4. `python scripts/run_robustness.py` puis `--no-llm` : comparer au rapport de départ. Aucune question `ok` ne doit régresser.
5. Les cas de démo de `docs/demo_cases.md` (LALGUARD M52 OD multi-pays, opportunités tomate × acariens) répondent comme avant. Après le Lot 2, C04 doit en plus passer.

Déploiement : code et `data/` modifiés, donc Nhan redéploie (`docs/deploy.md` : git pull + docker build + docker rm -f lpc-api + docker run). Puis on relance le banc sur la prod.

## 7. Ce qu'on ne fait PAS
- Aucune renormalisation ni écriture en base : les Lots 2 et 3 n'agissent qu'au moment de la lecture.
- Aucune modification des fichiers du starter kit (`eppo_*_mapping.csv`, `schema/openapi.yaml`, `gold_questions.csv`).
- Aucun couple culture × cible inventé (Lot 8 : avertissement explicite, sur décision).
- Aucun changement du contrat `openapi.proposed.yaml` : `GET /products` garde son comportement. Seul `/ask` change ses requêtes internes.
