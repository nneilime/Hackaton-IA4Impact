# AGENTS.md — Spec du POC « contrôle bordereau de facturation vs facture »

Ce document est la référence pour les agents IA (et humains) qui travaillent sur l'application. Les briefs détaillés par équipe, avec le contrat d'API partagé, sont dans [PROMPT.md](PROMPT.md), [PROMPT_BACKEND.md](PROMPT_BACKEND.md) et [PROMPT_FRONTEND.md](PROMPT_FRONTEND.md) ; les commandes de lancement sont dans [README.md](README.md).

## 1. Objectif

Détecter les différences entre :
- un **bordereau de facturation Cerfa S3404** (« établissements de santé privés – bordereau de facturation », frais d'hospitalisation), disponible sous forme d'**image** (JPG, lue par OCR) ;
- la **facture reçue**, disponible sous forme de **fichier texte structuré à positions fixes** (format B2).

L'agent (humain) fait les contrôles facture par facture. Principes :
- **Minimiser les actions de l'agent** : tout au clavier.
- **Ne présenter à l'agent que les factures avec au moins une anomalie** (contrôle KO ou À vérifier) ; les factures sans écart sont ignorées.
- L'agent **valide ou rejette** chaque facture (décision par facture ; `overrides` permet de marquer des contrôles comme faux positifs).
- Feature en plus : **dashboard** de vue globale de la anomalie avec estimation des coûts.

## 2. Stack et décisions

| Couche | Choix |
|---|---|
| Backend | Python 3.13 (géré par `uv`), **FastAPI** |
| OCR image → texte | **RapidOCR + OpenVINO** (PP-OCRv6 medium, `lang_type="fr"`, le même modèle que PaddleOCR) : ~20-30 s par scan sur CPU, et sur l'iGPU Intel si le pilote `intel-opencl-icd` est installé (`MELEE_OCR_DEVICE=CPU\|GPU` pour forcer). PaddleOCR a été retiré : plus lent, et oneDNN y plantait sur paddlepaddle 3.3.x. Le modèle *mobile* a été écarté (erreurs de lecture, 153/165 sur `devtools/eval.py`). |
| Extraction des zones | **Par ancres** : on repère les libellés imprimés (`N° LOT`, `sous-total 1+2+3`, en-têtes de colonnes…) et on lit la valeur à côté. Signatures (zones 11, 14) par densité d'encre (OpenCV), sans OCR. |
| Frontend | **Angular** (standalone, signals), Node ≥ 22.22.3 ou ≥ 24.15 |
| Persistance | Lecture locale de `images/` et `receipts/` ; cache OCR dans `backend/cache/` ; factures traitées dans `backend/traitees.txt` (un id par ligne). **Pas d'authentification.** |
| Appariement | 1 image ↔ 1 fichier texte de **même nom** (`Facture1_01.jpg` ↔ `Facture1_01.txt`) |

Équipe (répartition indicative) : désérialisation du fichier texte = Raphaël ; extraction des données de l'image = Guillaume ; frontend = Samy ; data analyst (frontend/backend) = Lucas.

## 3. Structure du repo

```
images/                 # bordereaux JPG (FactureX_NN.jpg), 55 scans
receipts/               # factures B2 (FactureX_NN.txt), appariées par nom
backend/
  main.py               # API FastAPI
  extract.py            # OCR batch (cache/) + extraction des zones par ancres
  checks.py             # contrôles C0–C17 (+ C10b)
  stats.py              # agrégats du dashboard
  deserialization/      # parse_b2.py (parser B2) + b2.schema.json (modèle commun)
  devtools/             # eval.py, expected.json, tests du parser
angular/src/app/
  agent/                # écran de contrôle de l'agent (route '')
  dashboard/            # tableau de bord superviseur (route /dashboard)
  models/               # types du contrat d'API
  services/             # invoice.service (file + décisions), stats.service, shortcut.service
AGENTS.md               # ce fichier (CLAUDE.md pointe dessus)
```

## 4. Architecture

1. **OCR batch** (`extract.py`) : RapidOCR + OpenVINO une fois par scan, résultat mis en cache dans `backend/cache/<nom>.json`. **Lancé automatiquement par `main.py` au démarrage du serveur, puis relancé par un thread de surveillance (toutes les 15 s) s'il manque des scans dans le cache** (cache supprimé, lot planté ; au plus un lancement par minute), dans un processus séparé (verrou `cache/ocr.pid`, journal `cache/ocr.log`, désactivable avec `MELEE_AUTO_OCR=0`). Jamais d'OCR pendant une requête.
2. **Deux sources vers un modèle commun** : `deserialization/b2.schema.json` est le contrat partagé.
   - `parse_b2.parse_file(path)` pour le fichier texte ;
   - `extract.extract(name)` pour le scan, qui ajoute un objet `scan` (zones sans équivalent B2 : n° Cerfa, montants, exécutants, signatures, total, code formulaire, cadres et scores).
3. **Contrôles** (`checks.py`) : C0–C17, plus C10b (C10 a été scindé : montant d'un côté, prestations présentes de l'autre), chacun `OK` / `KO` / `A_VERIFIER` avec `attendu` (B2), `lu` (scan), `zones` et `boxes` (pixels) ; les contrôles de listes (C7, C9, C10b, C11) détaillent en KO chaque acte ou prestation présent dans un seul document (`ecarts`), affiché sur sa propre ligne.
4. **API REST** (`main.py`) consommée par le frontend Angular via le proxy `/api` (voir §8).

## 5. Fichier texte de facture

Chaque ligne est typée par **le 1er caractère** (position 1). Positions ci-dessous **1-indexées**, bornes incluses.

### 5.1 Types de ligne

| Code | Signification |
|---|---|
| 0 | Entête fichier |
| 1 | Début de lot |
| 2 | Début de facture (sous-type `2-S` si pos. 39 = `S`, sinon nouvelle facture) |
| 3 | Lignes prestations hospitalières. `3-S` si pos. 39 = `S` ; `3-H` si pos. 36 = `H` ; sinon `3` = nouvel acte |
| 4 | Lignes actes. `4-S` / `4-M` / `4-B` si pos. 36 = `S` / `M` / `B` ; sinon `4` = nouvel acte |
| 5 | Fin de facture |
| 6 | Fin de lot |

Une facture = lignes 2 à 5 (le lot est défini par les lignes 1 et 6).

### 5.2 Champs utiles

| Donnée | Type de ligne | Position | Format | Obl. | Commentaire |
|---|---|---|---|---|---|
| NumeroTiers | 1 | 2-10 | 9N | O | N° national d'identification du partenaire de santé + clé (= n° FINESS établissement) |
| NumeroLot | 1 | 20-22 | 3N | O | |
| NumeroAssure | 2 | 12-24 | 13A | O | N° d'immatriculation assuré |
| NumeroFacture | 2 | 30-38 | 9N | O | |
| Acte | 3 | 56-60 | (4+1)A | O | Code acte |
| Acte | 4 | 76-80 | (4+1)A | O | Code acte |
| NumeroGH | 3 | 110-113 | 4N | F | N° de GHS / GHT / GMT |
| NumeroGH | 4S | 120-123 | 4N | F | idem |
| CodeCCAM | 4M | 43-55 | 13A | O | 7 car. utiles cadrés à gauche, complétés par des blancs |
| TotalPrestations | 5 | 42-49 | (6+2)N | O | Somme des bases de remboursement des lignes de type 3 (pos. 83-90) |
| TotalHonoraires | 5 | 58-65 | (6+2)N | O | Honoraires dépassements compris des lignes de type 4 (pos. 115-121) |

GHS = Groupe Homogène de Séjour (nature et motif du séjour). Montants `(6+2)N` = 6 chiffres entiers + 2 décimales, sans séparateur.

Ces positions sont implémentées dans `backend/deserialization/parse_b2.py` (ne pas écrire un second parser). `Facture2_06.txt` a un décalage de colonnes volontaire : le parser le signale dans `errors` et C0 passe en KO.

## 6. Bordereau image (zones à extraire)

Les zones sont retrouvées **par ancres** sur l'OCR pleine page (les scans ne sont pas identiques au pixel près : Facture1/2 font environ 1190×1684 px, Facture3 1684×2382 px). Les zones de signature (11, 14) sont détectées par **présence d'encre** (pas d'OCR). Les cadres rouges du Cerfa de référence ne servent qu'à repérer les champs.

| Zone | Contenu | Utilisé pour |
|---|---|---|
| 1 | Identifiant du document (`12278*0`) | 3.1 |
| 2 | N° FINESS établissement | 3.2 |
| 3 | N° de lot | 3.2 |
| 4 | N° de facture | 3.2 |
| 5 | N° d'immatriculation (13 premiers caractères) | 3.2 |
| 6 | Colonne « prestation » + n° GHS (frais de structure et de soins) | 3.3, 3.5 |
| 7 | Colonne « prestation » des produits LPP, spécialités pharma et médicaments | 3.4, 3.5 |
| 8 | Montant « sous-total 1+2+3 » | 3.5, 3.7 |
| 9 | N° d'identification des exécutants | 3.6 |
| 10 | Actes effectués (code acte / lettre-clé) | 3.6 |
| 11 | Signatures des praticiens (cases 1 à 8) | 3.6 |
| 12 | Montant « sous-total 4 » (honoraires) | 3.6, 3.7 |
| 13 | Montant total (1+2+3+4) | 3.7 |
| 14 | Signature du directeur de l'établissement | 3.7 |
| 15 | Code Cerfa (`S 3404`, bas de page) | 3.8 |

Les zones 6, 7, 9, 10 sont des colonnes multi-lignes : les valeurs sont rattachées à une colonne par recouvrement en x avec l'en-tête, puis regroupées en lignes par y. Les valeurs sont gardées brutes (jamais corrigées) ; la normalisation (espaces, `*`, `,`/`.`, zéros de tête) se fait au moment de comparer, dans `checks.py`.

## 7. Contrôles

Règles métier ci-dessous (numérotation du document d'origine). Elles sont implémentées dans `backend/checks.py` sous les codes **C0–C17 + C10b** (C0 = fichier B2 bien formé ; correspondance détaillée dans [PROMPT_BACKEND.md](PROMPT_BACKEND.md)). Chaque contrôle renvoie `OK` / `KO` / `A_VERIFIER` avec les deux valeurs comparées.

### 3.1 Identifiant du document
- Zone 1 == `12278*0`.

### 3.2 Clé d'identification de la facture
- Zone 2 == `NumeroTiers`.
- Zone 3 == `NumeroLot`.
- Zone 4 == `NumeroFacture`.
- Zone 5 (13 premiers caractères) == `NumeroAssure`.

### 3.3 Frais de structure et de soins
- Une prestation **GHS** doit figurer dans la colonne prestation de la zone 6, avec son n° de GHS.
- N° GHS (zone 6) == `NumeroGH` de type 3 de la prestation GHS du fichier.
- Toute prestation de la zone 6 **avec montant facturé renseigné** doit être présente dans le fichier (`Acte` de type 3).
- `NumeroGH` des actes de type 3 autres que GHS == `NumeroGH` de l'acte GHS.

### 3.4 Produits LPP, spécialités pharmaceutiques, médicaments
- `NumeroGH` des actes de type 3 == `NumeroGH` de l'acte GHS (zone 6).
- Toute prestation de la zone 7 est présente dans le fichier (`Acte` de type 3).

### 3.5 Récapitulatif des deux pavés précédents
- Montant zone 8 == `TotalPrestations`.
- Tout `Acte` de type 3 du fichier est présent en zone 6 ou zone 7.

### 3.6 Honoraires médicaux, paramédicaux, laboratoires
- Actes de la zone 10 codifiés sur **≤ 4 caractères** présents dans le fichier (`Acte` de type 4).
- Actes de la zone 10 codifiés sur **7 caractères** présents dans le fichier (`CodeCCAM` de type 4M).
- `NumeroGH` des actes de type 4S == `NumeroGH` de l'acte GHS (zone 6).
- Montant zone 12 == `TotalHonoraires`.
- Pour chaque n° d'exécutant distinct de la zone 9 qui **n'est pas un établissement** (3ᵉ caractère ≠ `0`) : au moins une signature dans une case de la zone 11.
- Tout `Acte` de type 4 / `CodeCCAM` de type 4M du fichier est présent en zone 10.

### 3.7 Conclusion du document
- Zone 13 == zone 8 + zone 12.
- Une signature est présente en zone 14.

### 3.8 Code Cerfa
- Zone 15 == `S3404` (comparer sans espaces).

## 8. API REST

Implémentée dans `backend/main.py`. Contrat détaillé (exemples JSON) dans [PROMPT_FRONTEND.md](PROMPT_FRONTEND.md) : ne pas le modifier sans prévenir l'autre équipe.

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/factures` | File : `[{id, nb_ko, nb_a_verifier, ocr, traitee}]`, triée (non traitées d'abord, puis KO, puis À vérifier) |
| GET | `/api/factures/{id}` | `{id, image: {url, largeur, hauteur}, checks: [...], traitee}` |
| POST | `/api/factures/{id}/decision` | `{statut: 'valide' \| 'rejete', commentaire, overrides}` → `204`, l'id est ajouté à `traitees.txt` (le corps n'est pas conservé) |
| GET | `/api/health` | `{status, ocr: {faits, total, en_cours}}` : avancement du lot OCR |
| GET | `/api/stats` | Agrégats du dashboard (anomalie, établissements) |
| GET | `/api/images/{id}.jpg` | Scan brut |

`{id}` = nom de base (`Facture1_01`), validé contre la liste des fichiers connus. Les contrôles sont calculés au démarrage et gardés en mémoire par (facture, état OCR) : une facture est recalculée dès que son cache OCR apparaît, sans relancer uvicorn. **L'agent ne voit jamais une facture dont le scan n'a pas été analysé** (`ocr: false`).

## 9. Frontend Angular

- **Écran agent** (`/`) : branché sur l'API via `services/invoice.service.ts`. File des factures analysées par l'OCR, non décidées, avec au moins un KO ou À vérifier (sinon message « Aucune facture disponible ») ; tant que l'OCR tourne, les factures nouvellement analysées s'ajoutent en fin de file toutes les 15 s, sans recharger la page ; scan à gauche avec les cadres des contrôles en anomalie (pixels convertis en % de l'image) ; contrôles KO puis À vérifier à droite (`attendu` vs `lu`) ; `V` valide, `R` rejette, puis facture suivante (préchargée).
- **Dashboard** (`/dashboard`) : `GET /api/stats` via `services/stats.service.ts`.
- Reste à faire par rapport au brief frontend : raccourcis complets (navigation entre contrôles, zoom, `Entrée`, aide), recadrages de zone, commentaire au rejet, overrides. Voir l'état détaillé dans [PROMPT_FRONTEND.md](PROMPT_FRONTEND.md).

## 10. Conventions et qualité

- Ne jamais lancer l'OCR dans une requête : uniquement le batch `extract.py` (démarré par le serveur, ou à la main), avec cache et écriture atomique.
- Ne jamais construire un chemin de fichier à partir d'une entrée utilisateur brute (valider l'id contre les fichiers connus).
- Tests : `uv run python checks.py` (autotest C0–C17), `uv run python devtools/eval.py` (justesse par zone), `npm test` dans `angular/` (Vitest, HTTP simulé).
- Le frontend appelle l'API en URL relative (`/api/...`) ; en test, `provideHttpClientTesting()`.
- Pas de secrets ni de données réelles de patients dans le dépôt ; les jeux de test sont fictifs.
- Garder le POC simple : pas d'authentification, pas de base de données.

## 11. Points ouverts

- OCR : ~20-40 s par scan sur CPU (de l'ordre de 25 min pour les 55 scans) : au premier démarrage, les factures arrivent dans la file de l'agent au fil de l'analyse (progression dans `GET /api/health`).
- Règle d'estimation des coûts du dashboard (aujourd'hui : somme des écarts de montants des contrôles KO C10, C13, C15).
- Commentaire au rejet et overrides côté interface.
