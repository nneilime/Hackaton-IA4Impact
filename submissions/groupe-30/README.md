# Maintenance prédictive — Action Logement / BatIA

La fiche présente les points à contrôler et les repères réparation/remplacement. La page **Arbitrages budgétaires** rapproche les dépannages répétés, les tournées communes et le plan de rénovation ; les enveloppes et la sélection sont partagées dans Supabase. Le [guide des arbitrages](docs/ARBITRAGES_BUDGETAIRES.md) précise les sources, les limites des coûts et le simulateur de prévention.

## Démarrage rapide de l’app et de l’API (Windows)

Utiliser Python **3.11**, dans un environnement dédié. Configurer le `.env` serveur et les membres Supabase comme indiqué dans le [guide de la base et des imports](docs/BASE_ET_IMPORTS.md).

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Entraînement explicite depuis un instantané cohérent de Supabase :
.\.venv\Scripts\python.exe -m scripts.train_from_database
# Démarrage seul, sans réentraînement :
.\.venv\Scripts\python.exe -m uvicorn scripts.api:app --host 127.0.0.1 --port 8000
```

Dans un deuxième terminal, démarrer le front avec `npm run dev` depuis `front/`. Se connecter avec un compte membre invité. La fiche équipement appelle `POST /api/predict` avec le jeton Supabase Auth ; elle affiche les trois symptômes possibles et les coûts pour l’horizon sélectionné. Le classement partagé est calculé par `POST /api/calculs` et publié en base après réussite.

Les imports mettent à jour les données utilisées pour l’inférence ; ils ne réentraînent pas les modèles. `python -m scripts.train_from_database --types-only` entraîne uniquement les modèles de symptômes en conservant les modèles de risque existants. Relancer le calcul après un entraînement pour publier sa nouvelle version.

Les scripts `train_all.sh` et les commandes CSV ci-dessous restent disponibles pour entraîner le modèle indépendamment de la base sous WSL/Linux. L’API de l’app lit toujours Supabase.

Ce projet vise à anticiper les pannes des équipements du parc immobilier afin de prioriser les visites préventives et de préparer les interventions des prestataires. Il exploite les données fictives du kit BatIA pour estimer le risque de panne d'un équipement à **90 jours**, **180 jours**, **un an (365 jours)** et **deux ans (730 jours)**.

La chaîne actuelle comprend trois scripts Python : construction d'une table d'apprentissage mensuelle, entraînement et évaluation de modèles CatBoost, puis inférence pour un équipement à une date donnée. L’app React consulte Supabase via l’API FastAPI locale ; les sources, résultats et décisions de l’équipe sont partagés. Voir le [guide de mise en service et de la base](docs/BASE_ET_IMPORTS.md) pour la connexion Auth, les imports et le démarrage complet.

## Organisation du projet

```text
.
├── scripts/
│   ├── build_monthly_training_table.py  # Préparation des variables et des cibles
│   ├── train_failure_model.py           # Entraînement et évaluation chronologique du risque
│   ├── train_failure_types.py           # Symptômes par famille, avec purge des horizons
│   ├── train_from_database.py           # Instantané Supabase et entraînement des quatre horizons
│   ├── predict_equipment.py             # Inférence à 90, 180, 365 et 730 jours
│   └── api.py                           # API HTTP FastAPI
├── requirements.txt
├── DATA 2 _le kit étudiants/
│   └── BatIA_Kit_Hackathon/
│       ├── donnees/                     # CSV sources
│       ├── BatIA_notebook_demarrage.ipynb
│       ├── BatIA_Hackathon_Donnees_Fictives.xlsx
│       └── rapports_prestataire/
├── table_apprentissage_mensuelle_90.csv   # Généré pour l'horizon 90 jours
├── table_apprentissage_mensuelle_180j.csv # Généré pour l'horizon 180 jours
└── artifacts/
    ├── 90d/                             # Modèle, métriques et résultats
    └── 180d/
```

Les tables générées, leurs métadonnées, les modèles et l'environnement `.venv/` sont exclus du suivi Git par `.gitignore`. Ils doivent être reconstruits lorsqu'ils ne sont pas disponibles localement. Les documents et le notebook du kit complètent les CSV ; les trois scripts utilisent directement les CSV.

## Installation

Utiliser Python 3.11 dans un environnement dédié et exécuter les commandes depuis la racine du projet.

Sous Windows / PowerShell :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si l'activation est indisponible, appeler directement `.\.venv\Scripts\python.exe` à la place de `python` dans les commandes suivantes. L’environnement local utilise Python 3.11 sous Windows.

Sous Linux / macOS :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Les dépendances du modèle comprennent CatBoost, pandas et scikit-learn ; l’API utilise FastAPI, Uvicorn et psycopg. Installer `requirements.txt` avant de préparer les tables : leur calcul des 27 variables est partagé avec l’inférence.

## Données et cible prédite

Le dossier source par défaut est `DATA 2 _le kit étudiants/BatIA_Kit_Hackathon/donnees/`. Les fichiers nécessaires sont :

| Fichier | Utilisation |
| --- | --- |
| `04_equipements.csv` | Identifiants, famille, rattachement, date de pose, durée de vie de référence et périmètre de prédiction |
| `05_demandes_locataires.csv` | Historique des demandes rattachées aux équipements via les interventions |
| `06_interventions.csv` | Dates, types, résultats, gravité et symptômes des interventions |

Seuls les équipements dont `dans_perimetre_prediction` vaut `Oui` sont retenus. Les CSV sont lus avec des en-têtes, un séparateur virgule et un encodage UTF-8, avec ou sans BOM.

Une ligne d'apprentissage représente **un équipement au premier jour d'un mois**. La cible `target_failure_within_horizon` vaut 1 lorsqu'au moins une intervention de type `Dépannage` ou `Remplacement` survient entre la date de référence incluse et la fin de l'horizon exclue. Il s'agit donc d'un risque d'intervention assimilée à une panne.

La table contient aussi `target_critical_failure_within_horizon`, qui décrit si la **première** panne future est un `Arrêt total` ou un `Remplacement`, ainsi que `days_to_next_failure`. Ces deux colonnes ne servent pas à entraîner les modèles actuels. Les nouvelles cibles `target_failure_symptom` et `target_failure_intervention` servent aux modèles de symptômes, et sont exclues des variables explicatives.

Les 27 variables explicatives couvrent notamment :

- la famille et le niveau de rattachement de l'équipement ;
- l'âge et son rapport à la durée de vie de référence ;
- les nombres d'interventions sur 30, 90, 180 et 365 jours ;
- les dépannages, remplacements, entretiens préventifs et anomalies ;
- les délais depuis les dernières interventions ;
- le type, le résultat, la gravité et le symptôme de la dernière intervention ;
- les demandes locataires liées et les réouvertures.

Les interventions et demandes utilisées comme variables sont strictement antérieures à la date de référence. Les cibles, les identifiants et la date de référence sont exclus des variables du modèle. L'âge est laissé manquant lorsqu'aucune date de pose connue à cette date n'est disponible.

## 1. Construire les tables d'apprentissage

```powershell
python scripts/build_monthly_training_table.py --horizon-days 90
python scripts/build_monthly_training_table.py --horizon-days 180
python scripts/build_monthly_training_table.py --horizon-days 365
python scripts/build_monthly_training_table.py --horizon-days 730
```

Chaque commande produit un CSV et un fichier `.metadata.json` décrivant le périmètre, les périodes, l'horizon et les effectifs. Les noms par défaut sont `table_apprentissage_mensuelle_90.csv` et `table_apprentissage_mensuelle_180j.csv`.

Pour changer les sources ou la destination :

```powershell
python scripts/build_monthly_training_table.py --data-dir "chemin/vers/donnees" --horizon-days 90 --output "table_personnalisee.csv"
```

Les métadonnées présentes lors de l'analyse indiquent 1 285 équipements : 120 790 lignes mensuelles à 90 jours (janvier 2018 à octobre 2025) et 116 935 lignes à 180 jours (janvier 2018 à juillet 2025).

La table à 90 jours porte le nom `table_apprentissage_mensuelle_90.csv`, attendu par défaut par les scripts de préparation et d'entraînement. Ses métadonnées sont dans `table_apprentissage_mensuelle_90.metadata.json`. L'option `--input` permet d'utiliser explicitement une autre table.

## 2. Entraîner et évaluer les modèles

```powershell
python scripts/train_failure_model.py --horizon-days 90
python scripts/train_failure_model.py --horizon-days 180
python scripts/train_failure_model.py --horizon-days 365
python scripts/train_failure_model.py --horizon-days 730
```

Le modèle est un `CatBoostClassifier` avec pondération automatique des classes, graine aléatoire 42, profondeur 6 et jusqu'à 1 000 itérations. Un arrêt anticipé de 100 itérations utilise le jeu de validation.

Le découpage est chronologique : les deux dernières années disponibles servent à la validation et au test, et les années précédentes à l’entraînement. Pour les horizons 90 et 180 jours du kit :

| Jeu | Dates des observations mensuelles |
| --- | --- |
| Entraînement | Jusqu'à fin 2023 (à partir de 2018 dans le kit) |
| Validation | 2024 |
| Test | 2025 |

Le seuil d'alerte est choisi sur la validation pour maximiser le rappel parmi les seuils atteignant la précision minimale demandée, fixée à 50 % par défaut. Si aucun seuil ne satisfait cet objectif, le script utilise 0,5. Cet objectif ne garantit pas la même précision sur de nouvelles données.

```powershell
python scripts/train_failure_model.py --input "table_personnalisee.csv" --horizon-days 90 --minimum-precision 0.60 --artifacts-dir "artifacts/90d"
```

`--horizon-days` détermine les noms des fichiers et l'horizon déclaré ; il ne recalcule pas les cibles de la table fournie. Il faut donc utiliser une table construite avec le même horizon.

Chaque dossier `artifacts/90d/`, `artifacts/180d/`, `artifacts/365d/` ou `artifacts/730d/` contient :

| Fichier | Contenu |
| --- | --- |
| `catboost_failure_<horizon>d.cbm` | Modèle entraîné |
| `metrics.json` | Métriques de validation et de test, seuil d'alerte et configuration |
| `test_predictions_<annee_test>.csv` | Scores, alertes et niveaux de risque sur le test |
| `test_metrics_by_family.csv` | Effectifs, pannes observées, alertes et score moyen par famille |
| `feature_importance.csv` | Importance des variables explicatives |

### Résultats du nouvel entraînement depuis Supabase

Les quatre modèles ont été entraînés sur l’instantané de révision 2, version `b53f1018c03480c38b8f`. Les jeux longs utilisent 2023 en validation et 2024 en test, avec uniquement les horizons entièrement observés.

| Horizon | ROC AUC test | Précision des alertes | Rappel | Seuil |
|---|---:|---:|---:|---:|
| 90 jours | 0,801935 | 55,61 % | 30,11 % | 0,761799 |
| 180 jours | 0,787230 | 55,13 % | 43,03 % | 0,630272 |
| 365 jours | 0,810786 | 55,30 % | 64,96 % | 0,513845 |
| 730 jours | 0,840373 | 51,63 % | 97,20 % | 0,229534 |

Ces résultats décrivent les données fictives du kit, sans calibration des scores.

La précision mesure la part des alertes suivies d'une panne ; le rappel mesure la part des observations positives détectées. Les lignes sont des observations mensuelles : leurs effectifs ne représentent pas un nombre d'équipements distincts ou de pannes uniques.

## 3. Prédire le risque d'un équipement

L'inférence nécessite **les quatre modèles et leurs fichiers `metrics.json`**, dans les sous-dossiers `90d/`, `180d/`, `365d/` et `730d/` du dossier d'artefacts.

Les tables des nouveaux horizons sont `table_apprentissage_mensuelle_365j.csv` et `table_apprentissage_mensuelle_730j.csv`. Les modèles correspondants sont `artifacts/365d/catboost_failure_365d.cbm` et `artifacts/730d/catboost_failure_730d.cbm`. Un an et deux ans représentent des durées fixes de 365 et 730 jours.

La préparation conserve uniquement les dates dont l’horizon futur est entièrement observé. Les horizons longs se terminent donc plus tôt dans le kit ; l’entraînement adapte les années de validation et de test aux années disponibles. Le fichier des prédictions de test s’appelle `test_predictions_<annee_test>.csv`. Les résultats 90/180 jours présentés plus haut ne décrivent pas les modèles 365/730 jours.

La commande CLI et la requête API restent identiques. Le JSON ajoute `failure_probability_365d`, `alert_threshold_365d`, `predicted_alert_365d`, `risk_level_365d` et les quatre champs correspondants avec le suffixe `730d`. L’action recommandée prend l’horizon en alerte le plus court : visite prioritaire à 90 jours, dans les six mois à 180 jours, dans les douze mois à 365 jours, ou inscription au plan de maintenance des deux prochaines années à 730 jours.

```powershell
python scripts/predict_equipment.py --equipment-id EQP-00001 --as-of-date 2025-01-01
```

Pour enregistrer le résultat :

```powershell
python scripts/predict_equipment.py --equipment-id EQP-00001 --as-of-date 2025-01-01 --output prediction_EQP-00001.json
```

Le script reconstruit les variables à partir des CSV puis affiche un JSON contenant les identifiants, la date de référence, les scores `failure_probability_90d`, `failure_probability_180d`, `failure_probability_365d` et `failure_probability_730d`, les seuils, les booléens d'alerte, les niveaux de risque et une action recommandée. Le dossier parent de `--output` doit déjà exister.

Les options `--data-dir` et `--artifacts-dir` permettent de changer les sources et le dossier contenant les quatre sous-dossiers de modèles.

Les niveaux de risque suivent cet ordre de décision :

| Condition | Niveau |
| --- | --- |
| Score supérieur ou égal au seuil du modèle | `critique` |
| Sinon, score supérieur ou égal à 0,50 | `eleve` |
| Sinon, score supérieur ou égal à 0,20 | `modere` |
| Sinon | `faible` |

Une alerte à 90 jours recommande une visite préventive prioritaire ; sinon, une alerte à 180 jours recommande une visite dans les six prochains mois, à 365 jours dans les douze prochains mois, et à 730 jours une inscription au plan de maintenance des deux prochaines années. Sans alerte, le script recommande de conserver le cycle d'entretien habituel. Le niveau `critique` désigne ici le franchissement du seuil d'alerte de panne, et non une prédiction spécifique de panne grave.

## 4. API Python pour le front React

Sous WSL/Linux, `bash scripts/start_api.sh` réutilise `.venv-training/` et vérifie la connexion PostgreSQL et les artefacts. `TRAINING_VENV`, `HOST`, `PORT` et les arguments Uvicorn permettent de configurer le démarrage ; aucun entraînement n’est lancé.

Après installation de `requirements.txt` et préparation des **quatre modèles** (étapes 1 et 2), lancer depuis la racine :

```powershell
python -m uvicorn scripts.api:app --host 127.0.0.1 --port 8000 --reload
```

FastAPI lit un instantané cohérent de Supabase et réutilise les mêmes 27 variables que la commande CSV. Les routes métier exigent un jeton Supabase Auth et une entrée dans `membres`. Le corps et les anciens champs de réponse de `/api/predict` sont conservés ; les objets `failure_types_<horizon>d` ajoutent les symptômes et les coûts. Les scores ne sont pas calibrés. `--reload` sert au développement. La documentation interactive est accessible sur `http://127.0.0.1:8000/docs` et le schéma OpenAPI sur `/openapi.json`.

| Route | Description |
| --- | --- |
| `GET /health` | Retourne `{"status":"ok"}` ; vérifie uniquement que le serveur répond |
| `POST /api/predict` | Prédiction pour un équipement aux horizons 90, 180, 365 et 730 jours |

Corps JSON requis :

```json
{"equipment_id": "EQP-00001", "as_of_date": "2025-01-01"}
```

L’identifiant doit être non vide (128 caractères maximum). La date doit être valide au format strict `YYYY-MM-DD`. Les champs supplémentaires sont refusés. La réponse HTTP 200 contient les mêmes champs que le script : identifiants, date, famille, probabilités, seuils, alertes, niveaux de risque, symptômes possibles, coûts estimés et action recommandée. Les probabilités s’expriment entre 0 et 1.

### Comprendre précisément la réponse de `POST /api/predict`

La réponse concerne **un équipement à une date de référence**, aux horizons **90, 180, 365 et 730 jours**. Une panne désigne ici une intervention de type `Dépannage` ou `Remplacement`. L'entretien préventif n'est pas une panne. L'horizon commence à `as_of_date` à minuit, date incluse, et se termine après le nombre de jours indiqué, borne finale exclue. Les données historiques utilisées comme variables précèdent la date de référence.

#### Informations communes

| Champ | Type JSON | Signification |
| --- | --- | --- |
| `equipment_id` | chaîne | Identifiant de l'équipement demandé, par exemple `EQP-00001`. |
| `as_of_date` | chaîne | Date de référence au format `YYYY-MM-DD`, à partir de laquelle on estime les risques futurs. |
| `residence_id` | chaîne | Résidence à laquelle appartient l'équipement. |
| `batiment_id` | chaîne | Bâtiment de rattachement, selon les données sources. |
| `libelle_famille` | chaîne | Famille de l'équipement, par exemple `Chaudière gaz individuelle`. |
| `recommended_action` | chaîne | Conseil de maintenance déterminé par le plus court horizon en alerte. |

#### Risque global pour chaque horizon

Dans les noms ci-dessous, `<horizon>` vaut `90`, `180`, `365` ou `730`. Ainsi, `failure_probability_90d` et `failure_probability_365d` sont deux champs distincts, présents dans la même réponse.

| Champ | Type JSON | Signification |
| --- | --- | --- |
| `failure_probability_<horizon>d` | nombre | Score estimant le risque d'au moins une panne pendant l'horizon. Multiplier par 100 pour afficher un pourcentage. |
| `alert_threshold_<horizon>d` | nombre | Seuil sélectionné lors de la validation du modèle pour déclencher une alerte. Il peut différer selon l'horizon et changer après réentraînement. |
| `predicted_alert_<horizon>d` | booléen | `true` lorsque le score est supérieur ou égal au seuil ; `false` sinon. |
| `risk_level_<horizon>d` | chaîne | Niveau calculé selon les règles ci-dessous : `critique`, `eleve`, `modere` ou `faible`. |
| `failure_types_<horizon>d` | objet | Symptômes possibles de la première panne et estimations de coûts, détaillés ci-dessous. |

Les règles de niveau de risque sont appliquées **dans cet ordre** :

1. Score supérieur ou égal au seuil d'alerte : `critique`.
2. Sinon, score supérieur ou égal à `0.50` : `eleve`.
3. Sinon, score supérieur ou égal à `0.20` : `modere`.
4. Sinon : `faible`.

Un risque `eleve` peut donc être associé à `predicted_alert: false`. Par exemple, un score de **58,86 %** reste sous un seuil de **77,55 %**. Le niveau `critique` indique le franchissement du seuil ; **il ne prédit pas la gravité de la panne**. Si le seuil est inférieur à 50 %, la première règle s'applique quand même.

#### Objet `failure_types_<horizon>d`

| Champ | Type JSON | Signification |
| --- | --- | --- |
| `status` | chaîne | `available` si un modèle de symptômes est disponible pour cette famille et cet horizon ; `unavailable` sinon. Cela n'indique pas si une panne est certaine. |
| `predictions` | liste | Jusqu'à trois couples intervention/symptôme, classés par probabilité conditionnelle décroissante. La liste peut contenir moins de trois éléments si le modèle connaît moins de classes. |
| `other_conditional_probability` | nombre | Somme des probabilités conditionnelles des classes non affichées. Les probabilités affichées et cette valeur totalisent environ 1, aux arrondis près, quand le modèle est disponible. |
| `expected_price_if_failure` | nombre ou `null` | Coût moyen estimé de la première panne **si une panne survient**, en euros TTC. |
| `expected_cost_within_horizon` | nombre ou `null` | Coût moyen estimé de la première panne éventuelle sur l'horizon, en euros TTC, en tenant compte du risque global de panne. |

Chaque élément de `predictions` contient :

| Champ | Type JSON | Signification |
| --- | --- | --- |
| `type_intervention` | chaîne | `Dépannage` ou `Remplacement` pour la première panne future. |
| `type_panne` | chaîne | Symptôme probable, par exemple `Perte de pression circuit`. `Non renseigné` signifie que le symptôme n'était pas renseigné dans les observations correspondantes. |
| `conditional_probability` | nombre | Probabilité de ce **couple intervention/symptôme**, sachant qu'au moins une panne survient dans l'horizon. |
| `joint_probability` | nombre | Score global estimé pour que la première panne dans l'horizon corresponde à ce couple. Il combine le risque global et la probabilité conditionnelle. |
| `prix` | nombre ou `null` | Prix indicatif en euros TTC, lu dans `prix_interventions` pour l’API et dans le catalogue `extra/` pour la CLI. `null` si le couple n’a pas de prix. |

Le modèle prédit un **symptôme**, pas nécessairement la cause technique exacte. Les trois propositions ne constituent pas trois pannes annoncées : ce sont des possibilités alternatives pour **la première panne éventuelle**. Les classes jamais rencontrées à l'apprentissage ne peuvent pas être proposées.

#### Exemple à 90 jours et calculs

Voici un **extrait limité aux résultats à 90 jours**, issu d'une prédiction pour `EQP-00001` au `2025-01-01`. La réponse API complète contient aussi les identifiants de rattachement, les trois autres horizons et `recommended_action`. Les valeurs peuvent changer après réentraînement.

```json
{
  "equipment_id": "EQP-00001",
  "as_of_date": "2025-01-01",
  "failure_probability_90d": 0.588574,
  "alert_threshold_90d": 0.775533,
  "predicted_alert_90d": false,
  "risk_level_90d": "eleve",
  "failure_types_90d": {
    "status": "available",
    "predictions": [
      {
        "type_intervention": "Dépannage",
        "type_panne": "Perte de pression circuit",
        "conditional_probability": 0.152383,
        "joint_probability": 0.089689,
        "prix": 250.0
      },
      {
        "type_intervention": "Dépannage",
        "type_panne": "Défaut carte électronique",
        "conditional_probability": 0.141027,
        "joint_probability": 0.083005,
        "prix": 450.0
      },
      {
        "type_intervention": "Dépannage",
        "type_panne": "Mise en sécurité / défaut allumage",
        "conditional_probability": 0.13344,
        "joint_probability": 0.078539,
        "prix": 250.0
      }
    ],
    "other_conditional_probability": 0.573149,
    "expected_price_if_failure": 281.7,
    "expected_cost_within_horizon": 165.8
  }
}
```

Pour la perte de pression, **15,24 %** est la probabilité conditionnelle si une panne survient. Le score global correspondant est **58,86 % × 15,24 % ≈ 8,97 %**. La formule appliquée à chaque classe est :

```text
joint_probability = failure_probability × conditional_probability
```

Les trois propositions représentent environ **42,69 %** des possibilités conditionnelles ; les autres classes totalisent **57,31 %**. Le premier résultat est le plus probable individuellement, mais il n'est pas majoritaire et ne constitue pas un diagnostic certain.

Les coûts utilisent la distribution de **toutes les classes du modèle**, y compris celles qui ne figurent pas parmi les trois résultats :

```text
expected_price_if_failure = somme(conditional_probability_i × prix_i)
expected_cost_within_horizon = failure_probability × expected_price_if_failure
```

Dans cet exemple, le coût moyen estimé si une panne survient est **281,70 €**. Le coût pondéré sur les 90 jours est **0,588574 × 281,70 € ≈ 165,80 €**. Ce dernier montant est une moyenne estimée, pas une facture attendue de 165,80 €. Il ne couvre ni plusieurs pannes successives ni toutes les interventions de maintenance. Les probabilités sont arrondies à six décimales et les coûts moyens à deux décimales ; les calculs utilisent les probabilités non arrondies, ce qui peut créer de petits écarts lors d'un recalcul à partir du JSON.

Si **au moins une classe du modèle n'a pas de prix**, les deux coûts moyens sont `null`, même si les trois résultats affichés ont tous un prix. Les probabilités restent disponibles. Quand `status` vaut `unavailable`, `predictions` est vide et les deux coûts sont `null` ; l'API renvoie alors `other_conditional_probability: 0.0` par défaut. Cette valeur ne signifie pas un risque nul : aucune distribution de symptômes n'est disponible.

#### Action recommandée et limites d'interprétation

L'action recommandée utilise le **plus court horizon dont `predicted_alert` vaut `true`** : visite prioritaire à 90 jours, visite dans les six mois à 180 jours, dans les douze mois à 365 jours, ou inscription au plan de maintenance des deux prochaines années à 730 jours. Sans alerte, elle recommande le cycle d'entretien habituel. Le symptôme et le coût ne modifient pas encore cette action.

Les scores ne sont pas calibrés et les modèles sont entraînés sur des données fictives. Les prix sont des hypothèses de simulation, pas des factures réelles. La gravité future et la durée d'arrêt ne sont pas prédites. Les modèles des quatre horizons sont indépendants : leurs scores peuvent ne pas augmenter avec la durée. Une réponse HTTP 200 ou un statut `available` ne garantit donc pas l'exactitude du diagnostic proposé.

Exemples avec un jeton de session Supabase Auth dans la variable `token` :

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/predict" -Headers @{Authorization="Bearer $token"} -ContentType "application/json" -Body '{"equipment_id":"EQP-00001","as_of_date":"2025-01-01"}'
```

Exemple Linux avec `curl` (serveur démarré sur le port 8000) :

```bash
curl --fail-with-body -X POST 'http://127.0.0.1:8000/api/predict' \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $token" \
  -d '{"equipment_id":"EQP-00001","as_of_date":"2025-01-01"}'
```

Exemple pour un service ou un gestionnaire de formulaire React :

```javascript
async function predictEquipment(equipmentId, asOfDate, token) {
  const response = await fetch("http://127.0.0.1:8000/api/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
    body: JSON.stringify({ equipment_id: equipmentId, as_of_date: asOfDate }),
  });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(typeof result.detail === "string"
      ? result.detail : "Vérifiez l’identifiant et la date.");
  }
  return result;
}
// const prediction = await predictEquipment("EQP-00001", "2025-01-01");
// Score non calibré : prediction.failure_probability_90d
```

Les erreurs retournent un JSON avec `detail` : 401 sans session valide, 403 pour un membre non autorisé, 404 pour un équipement inconnu, 422 pour une requête invalide ou un équipement hors périmètre, 503 si la base ou les modèles sont indisponibles, 500 pour une erreur interne (détails dans les logs).

Configuration par variables d’environnement, lues au démarrage :

| Variable | Valeur par défaut |
| --- | --- |
| `DATABASE_URL` | Connexion PostgreSQL serveur requise ; .env ignoré par Git |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | Configuration Auth publique ; alias NEXT_PUBLIC_* acceptés |
| `PREDICTION_ARTIFACTS_DIR` | `artifacts/` à la racine, avec `90d/`, `180d/`, `365d/` et `730d/` |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000` |

Les origines autorisent le front React à appeler l’API depuis un autre port ([documentation CORS FastAPI](https://fastapi.tiangolo.com/tutorial/cors/)). Pour personnaliser les chemins et origines avant le lancement :

```powershell
$env:CORS_ORIGINS = "http://localhost:5173,https://front.example.com"
$env:PREDICTION_ARTIFACTS_DIR = "C:/modeles/batia"
python -m uvicorn scripts.api:app --host 127.0.0.1 --port 8000
```

Les chemins relatifs personnalisés sont résolus depuis le répertoire de lancement. L’API lit Supabase et charge les quatre modèles en mémoire une fois par version. Les commandes CLI conservent leurs entrées CSV. Les calculs par lot et leur progression sont persistés en base ; les imports et dossiers passent par les routes authentifiées décrites dans `/docs`.

## Limites actuelles

### Prédiction du symptôme et estimation du coût

Les horizons restent **90, 180, 365 et 730 jours**. Pour chacun, la réponse contient maintenant `failure_types_<horizon>d` avec les trois couples intervention/symptôme les plus probables, leur `conditional_probability` (si une panne survient), leur `joint_probability` (score global de panne × probabilité conditionnelle), et leur `prix` estimé en euros TTC. Le champ `other_conditional_probability` contient la masse des possibilités restantes. Ces scores ne sont pas calibrés.

La cible est le couple `type_intervention` / `symptome` de la **première panne future** dans l'horizon, pas une liste de toutes les pannes futures. Les entretiens préventifs ne sont pas des pannes ; les symptômes absents des dépannages ou remplacements sont « Non renseigné ». Les nouveaux champs cibles sont exclus des variables de tous les modèles.

Après reconstruction des quatre tables avec les commandes de l'étape 1, entraîner les modèles de symptômes :

```powershell
python -m scripts.train_failure_types --horizon-days 90
python -m scripts.train_failure_types --horizon-days 180
python -m scripts.train_failure_types --horizon-days 365
python -m scripts.train_failure_types --horizon-days 730
```

Les modèles sont entraînés sur les observations positives, séparément par famille. Les deux dernières années sont réservées à la validation et au test ; un intervalle égal à l'horizon purge les frontières des jeux pour ces nouveaux modèles. Les fichiers `artifacts/<horizon>d/failure_types/manifest.json` donnent les effectifs, l'exactitude du premier choix, celle des trois premiers choix, la référence du symptôme majoritaire et les classes de test absentes de l'apprentissage. Une famille sans données d'apprentissage retourne `status: unavailable`. Une classe jamais observée à l'apprentissage ne peut pas être prédite.

Avec cette validation limitée à une année, la purge vide le jeu de validation aux horizons 365 et 730 jours : ces modèles de symptômes s’entraînent sans arrêt anticipé. L’algorithme du collègue est conservé ; une évaluation plus robuste des horizons longs nécessitera une fenêtre de validation plus large. Certaines familles ont peu de cas de test ou des symptômes absents de l’apprentissage : consulter leurs métriques avant d’interpréter les propositions.

Le catalogue des prix est `extra/11_equipements_interventions_pannes_possibles_avec_prix.csv`, configurable avec `--price-catalog` en CLI. Dans l’API, les prix proviennent de la table partagée `prix_interventions` de Supabase. Les montants sont des hypothèses de simulation. `expected_price_if_failure` pondère les prix de **toutes** les classes du modèle, puis `expected_cost_within_horizon` multiplie ce montant par le score global de panne. Cela représente le coût estimé de la première panne, et non un budget de toutes les interventions. Si un prix manque, ces deux estimations sont nulles. Les gravités du catalogue ne constituent pas une prédiction de gravité.

Les manifestes et modèles de symptômes complètent les quatre modèles de risque. Si un manifeste ou une famille est absent, les scores de risque restent disponibles et les symptômes retournent `status: unavailable`. Un artefact présent mais invalide fait échouer le calcul. L'action de maintenance existante reste déterminée par le risque global. La qualité des symptômes doit être examinée par famille avant de les utiliser pour une décision opérationnelle.

- Les données du kit sont fictives. Les résultats doivent être réévalués sur les historiques réels avant une utilisation opérationnelle.
- Les modèles de risque existants ne purgent pas les horizons des cibles aux frontières des jeux : une observation de fin 2023 peut avoir une cible dépendant d’interventions de 2024. Une évaluation plus stricte doit introduire un intervalle adapté à l’horizon. Les nouveaux modèles de symptômes appliquent cette purge.
- Le rattachement des demandes aux équipements repose sur les liens présents dans l'ensemble des interventions. Même si les dates des demandes sont filtrées, ces liens peuvent provenir d'interventions futures ; leur disponibilité historique doit être vérifiée.
- Les quatre horizons utilisent des modèles indépendants : les scores ne sont pas contraints à augmenter avec l’horizon. Les scores n'ont pas de calibration explicite, et le modèle utilise une pondération des classes.
- La commande CSV et `/api/predict` traitent un équipement ; le classement de l’app est calculé par lot. Les inspections sont des dossiers de préparation partagés ; aucun rendez-vous réel n’est envoyé au prestataire.

## Aide des scripts

```powershell
python scripts/build_monthly_training_table.py --help
python scripts/train_failure_model.py --help
python scripts/predict_equipment.py --help
```
