# Backend du copilote des sorties scolaires liO

API FastAPI qui sert le contrat de `API_CONTRACT.md` (racine du repo), sous le préfixe `/api`, pour le
front Vite sur `http://localhost:5173`.

## Lancer

```bash
cd backend
python3 -m venv .venv                      # Python 3.14 testé
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Au premier démarrage, si `backend/lio.db` n'existe pas, l'API la construit :

- depuis les **vrais fichiers SNCF** s'ils sont dans `data/` (racine du repo) ou `backend/data/` :
  `desserte.csv`, `Data_Hackathon.csv`, `gares.json` (+ un fichier « trains groupes » optionnel) ;
- sinon depuis le **jeu de démonstration** (`etl/seed_demo.py`).

`GET /api/sante` le dit honnêtement : `donnees: "sncf"` ou `"demo"`, et `mode: "llm"` si
`ANTHROPIC_API_KEY` est définie, sinon `"demo"`.

Pour repartir d'une base neuve (références de dossier à `LIO-2026-000001`, jauges d'origine) :
supprimez `backend/lio.db` ou lancez `.venv/bin/python -m etl.seed_demo --reset`.
Pour forcer la construction depuis les fichiers SNCF : `.venv/bin/python -m etl.build_db`.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```

Ils couvrent le parseur (message du scénario), les règles R1 à R10 et la jauge, l'indice de
confiance, le garde-fou des explications du LLM, l'ETL des fichiers SNCF et le scénario complet
via `TestClient`.

## Variables d'environnement

| Variable | Effet |
|---|---|
| `ANTHROPIC_API_KEY` | Active le mode `llm` (sinon mode `demo`, entièrement déterministe) |
| `LIO_LLM_MODEL` | Modèle Claude des appels classiques (défaut `claude-opus-5-5`) |
| `LIO_LLM_MODEL_SCENE` | Modèle Claude de la scène Tchouette (défaut `claude-sonnet-5-5`) |
| `LIO_LLM_DELAI_SCENE` | Délai max d'un appel de la scène, en secondes (défaut `8`) |
| `LIO_DB_PATH` | Chemin de la base SQLite (défaut `backend/lio.db`) |
| `LIO_DATA_DIR` | Dossier supplémentaire où chercher les fichiers SNCF |
| `LIO_AUJOURDHUI` | Date du jour forcée (`AAAA-MM-JJ`), pour des démos et tests reproductibles |
| `LIO_GEOCODAGE_EN_LIGNE=0` | Coupe l'appel à l'API Adresse (table locale des communes seulement) |

## Architecture

```text
app/main.py              routes FastAPI, CORS, erreurs { "detail": "…" } en français
app/schemas.py           contrat d'API en Pydantic (champ pour champ)
app/llm.py               les 3 appels au LLM : comprendre, recommander, expliquer
app/db.py                schéma SQLite (livrables/05-mcd-mld.md), connexion, initialisation
app/services/
  chat.py                Tchouette : une question de relance à la fois, suggestions
  comprendre.py          parseur français, gare par son nom, géocodage, champs manquants
  geo.py                 communes d'Occitanie, API Adresse (2 s, repli local), gare la plus proche
  recommander.py         3 destinations du catalogue (hors commune de départ)
  trains.py              recherche SQL des trains groupes, jour type, correspondance ≥ 10 min
  controles.py           règles R1 à R10 et jauge (jamais l'identité des autres groupes)
  confiance.py           indice sur 100 (cahier des charges §5)
  propositions.py        aller-retour, créneau de visite, alternative d'une proposition rouge
  expliquer.py           explication claire (gabarits, ou LLM avec garde-fou)
  dossiers.py            OPTION -> PRE_RESERVATION, référence LIO-AAAA-NNNNNN, réponse simulée
  retours.py             retour d'expérience, critère satisfaction avant/après
etl/build_db.py          vrais fichiers SNCF -> lio.db
etl/seed_demo.py         jeu de démonstration -> lio.db
etl/catalogue.py         sites culturels réels d'Occitanie (temps de marche approximatifs)
etl/reseau_demo.py       gares réelles, trains liO fictifs, options simulées
```

## Ce que fait (et ne fait pas) le LLM

Le LLM ne calcule jamais d'horaire, de place ni de score. Il sert à 3 endroits : extraire la demande
(sortie structurée), noter et justifier des sites **du catalogue** (identifiants validés), et
reformuler l'explication d'une proposition à partir des chiffres calculés. Chaque explication passe
un garde-fou (aucun horaire ni nombre absent des faits, jamais « confirmé ») ; sinon on garde le
gabarit. En cas d'erreur réseau, de refus ou de sortie invalide, on retombe sur le mode démo.

## Activer l'IA

```bash
export ANTHROPIC_API_KEY=…        # avant de lancer le back
.venv/bin/uvicorn app.main:app --reload --port 8000
curl -s localhost:8000/api/sante  # -> "mode": "llm" (sans clé : "mode": "demo")
```

La scène Tchouette (`POST /api/scene`) utilise **Claude Sonnet 5.5** (`claude-sonnet-5-5`, effort
`low`) : rapide et économique, il suffit pour comprendre une phrase et reformuler une réplique
courte. Au plus **2 appels par message libre** (comprendre l'intention et les champs, en sortie
structurée, puis reformuler la réplique scriptée), **aucun appel sur un clic de carte**. Délai de 8 s
sans nouvel essai : au-delà, sur erreur réseau ou refus, ce tour repart en mode démo. Chaque tour
est journalisé sur `lio.llm` (nombre d'appels, latence, jetons, cache). Le code est dans
`app/services/scene_llm.py` ; les tests (`tests/test_scene_llm.py`) simulent le client, sans clé.

## Hypothèses de calcul (à connaître pour la démo)

- **Jour type** : la grille couvre février à juin 2026. Une date hors grille est ramenée au même jour
  de la semaine (le jour de ce type qui compte le plus de circulations), et le message le dit.
- **Temps de marche d'un groupe** : individuel × 1,3 + 5 min. Les temps du catalogue sont approximatifs.
- **Créneau de visite** : premier créneau indicatif (tous les quarts d'heure à partir de l'ouverture)
  laissant 30 min de marge (R4). À la journée, on reste sur place la durée de visite + 1 h de pause
  déjeuner, puis on prend le premier retour qui ramène le groupe avant l'heure maximale (R5, marche
  gare → établissement comprise).
- **Plage 9h-16h (R6)** et **J-21 (R7)** : vigilance, jamais bloquantes.
- **Alternative** d'une proposition rouge : train suivant (ou autre retour), sinon même trajet un
  autre jour dans les 7 jours. Elle repasse par les mêmes contrôles.
- **Pré-réservation** : revérifie la jauge, pose une option (positionnement) sur chaque train, puis
  transmet la demande. `CONFIRMATION` n'arrive que par `simuler-reponse`.

## Jeu de démonstration

Tout ce qui est simulé est marqué (`est_simule = 1`) : trains et horaires (numéros fictifs), indicateurs
mensuels, options d'autres groupes, quelques retours d'expérience. Les gares et les sites culturels
sont réels ; les codes UIC sont des codes de démonstration. Sur le scénario (collège de Foix, 5e,
Moyen Âge, 42 élèves + 4 accompagnateurs, jeudi 12 novembre 2026), une option simulée de 10 places sur
le premier train du matin Foix → Toulouse rend sa jauge rouge et déclenche l'alternative.
