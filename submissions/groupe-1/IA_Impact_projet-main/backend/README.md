# Backend — calcul d'itinéraire

API FastAPI qui renvoie le meilleur itinéraire entre une ville ou gare de départ et une ville ou gare
de destination en Occitanie, à partir des **horaires officiels** SNCF (TER, Intercités, TGV, OUIGO) et
**liO** (cars régionaux de la Région Occitanie).

Un itinéraire est une suite de **trajets directs** (même train ou même car du début à la fin) reliés
par des **correspondances**. Le Dijkstra minimise :

```
temps à bord  +  pour chaque correspondance : 5 min de changement + attente moyenne du véhicule suivant
```

L'attente moyenne est déduite de la fréquence réelle : 16 trains/jour sur une journée de 16 h, c'est un
train par heure, donc 30 min d'attente en moyenne (plafond 2 h). Le premier départ n'est pas pénalisé :
le voyageur choisit son heure — sauf s'il ne circule pas le jour de référence (car du week-end, des
vacances…), qui compte alors l'attente maximale. Les horaires précis ne sont pas modélisés ; la durée est une estimation.

Un arrêt de car liO et une gare SNCF à moins de 400 m sont reliés **à pied** (4,5 km/h) : on peut descendre
du car et prendre le train. La marche ne compte pas comme une correspondance.

Quand on demande une **ville**, toutes ses gares et ses arrêts de car sont candidats, avec un temps d'accès
estimé : 0 min pour la gare qui porte son nom (« Toulouse » → Matabiau), 10 min pour les autres gares et les
gares routières, 20 min pour un arrêt de car quelconque. C'est ce qui permet « Montpellier → Ganges » en
car liO depuis Trifontaine plutôt qu'un détour en train par Nîmes.

## Deux bases

| Dossier | Contenu | Utilisée par |
|---|---|---|
| `data/train_lio/` | **trains TER liO uniquement** : 259 gares, 403 missions, aucun car | l'API et le site, **par défaut** |
| `data/` | base complète : en plus cars TER, cars liO (réseaux départementaux), Intercités, TGV, OUIGO… | `IA_DATASET=full` |

```bash
uvicorn app.main:app --reload                    # trains liO
IA_DATASET=full uvicorn app.main:app --reload    # base complète
```

La copie est produite par `scripts/filter_dataset.py` à partir de la base complète (mêmes fichiers, réduits aux
missions des modes gardés et aux gares qu'elles desservent). Une autre sélection est possible, par exemple
`--out data/ter_lio --modes "Train TER" "Car TER" "Car liO"`.

```
backend/
├── app/
│   ├── main.py                 # API HTTP (FastAPI)
│   └── routing.py              # graphe des trajets directs + Dijkstra, utilisable seul en CLI
├── data/                       # base complète, générée par scripts/build_from_gtfs.py
│   ├── train_lio/              # copie trains liO (même structure), générée par scripts/filter_dataset.py
│   ├── stations_occitanie.csv  # 5 050 arrêts : 360 gares SNCF (id UIC) + ~4 700 arrêts liO (id « L… »)
│   ├── missions_occitanie.csv  # 3 381 missions : suites d'arrêts + temps de passage médians + fréquence
│   ├── walk_links.csv          # 345 correspondances à pied arrêt liO <-> gare SNCF
│   ├── connections_occitanie.csv  # tronçons entre arrêts consécutifs, ancien format (notebook, Neo4j)
│   └── build_info.json         # version et validité des horaires, jour de référence
├── scripts/
│   ├── build_from_gtfs.py      # télécharge les sources et reconstruit data/
│   └── filter_dataset.py       # crée data/train_lio/ (ou une autre sélection de modes)
└── tests/
```

## Lancer

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload       # http://127.0.0.1:8000/docs
```

En ligne de commande, sans serveur et sans dépendance :

```bash
python -m app.routing Toulouse Perpignan                       # trains liO
python -m app.routing Toulouse Tarbes --transfer 10
python -m app.routing Toulouse Lourdes --dataset full --exclude INTERCITES
python -m app.routing Montpellier Ganges --exclude-network "liO 34"
```

## Mettre à jour les horaires

Les horaires SNCF changent (le GTFS actuel est valide du 09/10/2026 au 31/03/2027, voir `GET /info`) :

```bash
python scripts/build_from_gtfs.py --refresh   # ~2 s, ~150 Mo de RAM, sources dans backend/.cache/
python scripts/filter_dataset.py               # puis régénérer la copie trains liO
```

Sources :
- GTFS SNCF TGV + Intercités + TER : `eu.ftp.opendatasoft.com/sncf/plandata/Export_OpenData_SNCF_GTFS_NewTripId.zip`
  (référencé sur transport.data.gouv.fr, « Réseau SNCF TGV, Intercités et TER »)
- GTFS liO : flux publié par la Région Occitanie (transport.data.gouv.fr, « Réseau interurbain liO Occitanie »)
- Liste des gares SNCF (département et commune par code UIC) : ressources.data.sncf.com, jeu `liste-des-gares`
- Contours des départements, pour les arrêts absents de la liste des gares : github.com/gregoiredavid/france-geojson

Ce que fait le script :
1. garde les gares et zones d'arrêt situées dans les 13 départements d'Occitanie (noms liO remis en casse normale) ;
2. découpe chaque train en morceaux contigus à l'intérieur de la région ;
3. regroupe les trains qui desservent les mêmes arrêts dans le même ordre en **missions**, avec les temps de
   passage médians, les arrêts où l'on peut monter ou descendre, et le nombre de circulations le **jour de
   référence** (le mardi/mercredi/jeudi le plus chargé de la période) ;
4. relie à pied les arrêts liO et les gares SNCF à moins de 400 m ;
5. écrit aussi `connections_occitanie.csv` au format historique du projet, pour le notebook et Neo4j
   (le mode est dans `stop_id` : `StopPoint:OCECar liO-L…` pour les cars liO).

Les réseaux urbains (tram de Montpellier, métro de Toulouse…) ne sont pas intégrés.

## Endpoints

| Méthode | Route | Réponse |
|---|---|---|
| GET | `/health` | `{"status": "ok", "stations": 259}` (trains liO) |
| GET | `/info` | source, validité des horaires, jour de référence, volumes |
| GET | `/stations?q=nimes&limit=20` | `{"stations": ["Nîmes Centre", "Nîmes Pont du Gard"]}` |
| GET | `/places` | arrêts avec `id, name, lat, lon, department, commune, network` (`sncf` ou `lio`) |
| GET | `/network` | tronçons entre arrêts consécutifs `from_id, to_id, mode, minutes` |
| GET | `/modes` | `[{"id": "Train TER", "links": 637, "missions": 403}, …]` |
| GET | `/networks` | réseaux liO : `[{"id": "liO 34", "department": "Hérault", "missions": 614}, …]` |
| GET | `/route?from=Montpellier&to=Rodez` | voir ci-dessous |
| POST | `/chat` | assistant du site (voir « Assistant » plus bas) |
| POST | `/transcribe` | dictée du chat : corps brut = l'enregistrement → `{"text"}` |

Paramètres de `/route` :
- `from`, `to` : nom de **ville** (toutes ses gares sont essayées ; « Toulouse » part de Matabiau plutôt
  que d'une gare de banlieue) ou de **gare** précise. Accents, casse et tirets sont ignorés.
- `exclude` (répétable) : type de transport à ignorer, parmi les `id` de `/modes`
  (`Train TER`, `Car TER`, `Car liO`, `Car à réservation`, `INTERCITES`, `INTERCITES de nuit`, `TGV INOUI`, `OUIGO`, `Navette`).
- `exclude_network` (répétable) : réseau de cars liO à ignorer, parmi les `id` de `/networks` : un par département
  (`liO 09`, `liO 11`, … `liO 82`) et `liO TIL` pour les lignes régionales qui traversent plusieurs départements.
- `transfer_min` (défaut 5) : minutes de changement par correspondance, en plus de l'attente estimée.

```json
{
  "from": "Montpellier Saint-Roch", "to": "Rodez",
  "minutes": 339.6, "ride_minutes": 266.0, "transfers": 1, "transfer_min": 5.0,
  "legs": [
    {"mode": "INTERCITES", "line": "Bordeaux - Marseille",
     "from": "Montpellier Saint-Roch", "to": "Toulouse Matabiau", "from_id": "87773002", "to_id": "87611004",
     "minutes": 129.0, "wait_minutes": 0, "stops": ["87773002", "87773200", "…", "87611004"], "trips_per_day": 8},
    {"mode": "Train TER", "line": "Toulouse Matabiau - Rodez",
     "from": "Toulouse Matabiau", "to": "Rodez", "from_id": "87611004", "to_id": "87613422",
     "minutes": 137.0, "wait_minutes": 73.6, "stops": ["87611004", "87615344", "…", "87613422"], "trips_per_day": 7}
  ]
}
```

- `minutes` : durée estimée totale = `access_minutes` + `ride_minutes` + somme des `wait_minutes` + `egress_minutes`
- `access_minutes` / `egress_minutes` : temps estimé pour rejoindre le premier arrêt / quitter le dernier (ville demandée)
- un leg `"mode": "Marche"` est un trajet à pied entre un arrêt de car et une gare (`line` = distance)
- `legs[].stops` : toutes les gares desservies par ce trajet direct, extrémités comprises
- `legs[].trips_per_day` : circulations le jour de référence qui font ce trajet sans changement

Erreurs — `{"detail": {"code", "message"}}` :

| Code HTTP | `code` | Cas |
|---|---|---|
| 404 | `unknown_place` | ville/gare absente du réseau (ex. Paris) |
| 404 | `no_route` | les deux existent mais ne sont pas reliées avec les transports autorisés |
| 400 | `same_place` | départ = destination |
| 400 | `unknown_mode` | valeur de `exclude` absente de `/modes` |
| 400 | `unknown_network` | valeur de `exclude_network` absente de `/networks` |

## Assistant (`POST /chat`)

`app/chat.py` : un modèle OpenAI (`OPENAI_MODEL`, défaut `gpt-4.1-mini`) qui répond en français et appelle le
moteur d'itinéraire comme outil — il ne donne jamais une durée de mémoire. La clé `OPENAI_API_KEY` est lue dans
l'environnement ou dans `backend/.env` (git-ignoré, jamais versionné).

```json
// requête : l'historique + le catalogue des lieux du site (envoyé par le front)
{"messages": [{"role": "user", "content": "Une sortie science depuis Montpellier ?"}],
 "catalog": [{"id": "cite-espace", "title": "Cité de l'espace", "category": "science", "station": "Montaudran", "summary": "…"}]}
// réponse : le texte + ce que le site doit afficher
{"reply": "…", "actions": [{"type": "route", "from": "Montpellier", "to": "Montaudran"},
                           {"type": "places", "items": [{"id": "cite-espace", "reason": "…"}]}]}
```

Garde-fous (la clé est payante, le site public) : 30 messages / 10 min par IP (`429 chat_rate_limit`), 12 derniers
messages envoyés au modèle, 5 tours d'outils au plus. Clé absente ou OpenAI en panne : `503 chat_unavailable`.

### Dictée (`POST /transcribe`)

Le bouton micro du chat enregistre (MediaRecorder, 2 min au plus) et envoie l'audio **brut** dans le corps, avec son
type en `Content-Type` (`audio/webm`, `audio/ogg`, `audio/mp4`…) — pas de multipart, donc pas de dépendance de
plus. Le serveur le passe à l'API de transcription d'OpenAI (`TRANSCRIPTION_MODEL`, défaut
`gpt-4o-mini-transcribe`), en français, avec le vocabulaire du site en contexte, et renvoie `{"text": "…"}`. Le
texte atterrit dans le champ du chat pour être relu avant envoi ; rien n'est conservé. Même quota que `/chat`.
Erreurs : `415 audio_format`, `413 audio_too_large` (10 Mo), `400`/`422 audio_empty`, `503 chat_unavailable`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```
