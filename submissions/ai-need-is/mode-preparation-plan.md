# Mode Préparation — Plan d'implémentation (v2)

## Vue d'ensemble

### Objectif

Transformer le Mode Préparation en un véritable outil de **prépositionnement des équipes face à des incidents prévus**. À partir d'une crise historique (CSV) représentant le scénario météo attendu, le système doit calculer **où déplacer préventativement les équipes** avant que les pannes ne surviennent, afin de réduire les temps de trajet le jour J.

Le responsable opérationnel doit pouvoir :
1. Sélectionner un scénario de crise historique (le scénario météo prévu est représenté par ce jeu d'incidents).
2. Choisir un horizon temporel : seuls les incidents déclenchés dans les `h` premières heures sont pris en compte.
3. Obtenir deux types de recommandations de la part du système :
   - **Affectations prévisionnelles** : quelle équipe pour quel incident prévu (déjà partiellement présent).
   - **Prépositionnements spatiaux** : vers quel point géographique stratégique déplacer chaque équipe libre pour minimiser les temps de trajet sur la zone d'incidents.
4. Arbitrer, cocher/décocher les propositions retenues, désigner les équipes en réserve.
5. Valider le plan, qui est transmis au Mode Jour J via `st.session_state["plan_preparation"]`.

### Ce qui existe déjà et fonctionne

L'étape (1) et (2) sont **déjà implémentées** dans `app/views/preparation.py` :
- `preparer_pannes()` filtre et prépare les incidents.
- `IncidentAllocator.affecter_incidents()` produit des affectations prévisionnelles.
- L'arbitrage humain (data_editor, réserve, commentaire, validation) est en place.

**Ce qui manque** : l'étape de prépositionnement spatial — calculer des **points de repli géographiques optimaux** pour les équipes non directement affectées à un incident, de façon à les rapprocher de la zone de crise avant qu'elle ne démarre.

### Périmètre minimal

- **Nouveau fichier** : `crise/preparation/prepositionnement.py`
- **Fichier modifié (ajout uniquement)** : `crise/preparation/jointure.py` (nouvelle fonction de carte)
- **Fichier modifié** : `app/views/preparation.py` (intégration du tableau de prépositionnement)
- **Nouveaux tests** : `tests/test_prepositionnement.py`, `tests/test_preparation_integration.py`
- **Fichiers non touchés** : tout le reste (moteur, pilotage, allocateur, jour_j, rejeu, tests existants)

### Approche

Zéro régression. Les nouvelles briques sont des **fonctions pures** dans `crise/preparation/`. Le contrat `plan_preparation` transmis à Jour J est étendu par ajout de clés additionnelles uniquement — `pilotage.py` n'accède à ce dict que via `.get("equipes_en_reserve", [])` et ne sera pas affecté.

---

## Cartographie de l'architecture actuelle

### Briques existantes et opérationnelles

| Module | Rôle | Statut |
|---|---|---|
| `crise/loaders/loaders.py` | Charge les 4 CSV (agents, postes, coupures, insee) | ✅ Opérationnel |
| `crise/preparation/jointure.py` | Jointure, parsing, expansion équipes, points carte | ✅ Opérationnel |
| `crise/geo/distance.py` | Haversine + temps trajet | ✅ Opérationnel |
| `crise/strategies/allocator.py` | 4 stratégies d'affectation greedy / ML | ✅ Opérationnel |
| `crise/simulation/moteur.py` | Boucle temporelle complète | ✅ Opérationnel |
| `crise/simulation/pilotage.py` | Orchestration humain-dans-la-boucle | ✅ Opérationnel |
| `crise/metrics/indicateurs.py` | KPIs, objectif 48h | ✅ Opérationnel |
| `app/views/preparation.py` | Affectations prévisionnelles + arbitrage humain | ⚠️ Partiel — prépositionnement spatial absent |
| `app/views/jour_j.py` | Arbitrage temps réel | ✅ Opérationnel |
| `app/views/rejeu.py` | Comparaison stratégies | ✅ Opérationnel |

### Flux de données Mode Préparation — état actuel

```
coupures_df + postes_df + numero_crise
    → preparer_pannes()
    → pannes (DataFrame complet de la crise)
    → previsionnelles = pannes filtrées sur [T0, T0 + horizon_h]
    → IncidentAllocator.affecter_incidents(equipes, previsionnelles, strategie)
    → decisions (list[dict])  ← affectations prévisionnelles
    → brouillon_preparation (session_state)
    → arbitrage humain : data_editor + multiselect réserve + commentaire
    → plan_preparation (session_state)  → Jour J
```

### Flux cible après implémentation

```
coupures_df + postes_df + numero_crise
    → preparer_pannes()
    → pannes + previsionnelles
    → IncidentAllocator.affecter_incidents()
    → decisions  ← (inchangé)
    → calculer_barycentre_incidents(previsionnelles)
    → point_repli_optimal(previsionnelles)
    → recommander_prepositionnement(equipes_libres, previsionnelles)
    → prepositionnements  ← NOUVEAU
    → brouillon_preparation  ← étendu avec prepositionnements
    → arbitrage humain : data_editor decisions + data_editor prepositionnements + réserve + commentaire
    → plan_preparation  ← étendu avec prepositionnements_retenus
    → Jour J (contrat non rompu)
```

### Contrat plan_preparation — avant / après

**Avant** (consommé par `creer_session_pilotage()` dans [`pilotage.py:51`](crise/simulation/pilotage.py)):
```python
{
    "numero_crise": str,
    "horizon_h": int,
    "strategie": str,
    "pannes": pd.DataFrame,
    "pannes_previsionnelles": pd.DataFrame,
    "equipes": pd.DataFrame,
    "decisions": list[dict],         # affectations retenues
    "equipes_en_reserve": list[str], # seule clé lue par pilotage.py
    "commentaire_humain": str,
    "statut": "VALIDE_PAR_L_HUMAIN",
}
```

**Après** (ajout additif uniquement) :
```python
{
    # toutes les clés existantes inchangées
    "prepositionnements_retenus": [  # NOUVEAU — ignoré par pilotage.py
        {
            "id_equipe": str,
            "lat_cible": float,
            "lon_cible": float,
            "temps_deplacement_h": float,
            "distance_km": float,
        },
        ...
    ],
}
```

`pilotage.py` accède à `plan_preparation` uniquement via `.get("equipes_en_reserve", [])` → ajout de clés sans aucun impact.

---

## Plan d'action séquentiel

---

### Sous-tâche 1 — Créer `crise/preparation/prepositionnement.py`

**Status** : `[ ] pending`

**Intent**

Créer un module de calcul du prépositionnement spatial, entièrement découplé de l'UI. La logique centrale est : à partir des incidents prévisionnels connus (lat/lon, nb_clients), calculer le **barycentre pondéré** de la zone de crise, puis **recommander à chaque équipe libre un point de déplacement préventif** minimisant son temps de trajet moyen vers les incidents de la zone.

Le module ne génère rien de synthétique : il travaille exclusivement sur les incidents réels extraits des CSV.

**Expected Outcomes**

- `crise/preparation/prepositionnement.py` existe, importable, sans import Streamlit.
- `calculer_barycentre_incidents(incidents_df) -> tuple[float, float]` : retourne le barycentre (lat, lon) pondéré par `nb_clients`. Si le DataFrame est vide ou sans `nb_clients`, retourne la moyenne géométrique simple.
- `recommander_prepositionnement(equipes_df, incidents_df, coeff_detour, vitesse_kmh) -> list[dict]` : pour chaque équipe libre (non déjà affectée à un incident dans `decisions`), calcule la distance au barycentre et retourne une liste de dicts `{id_equipe, commune, lat_origine, lon_origine, lat_cible, lon_cible, temps_deplacement_h, distance_km}`.
- Les tests unitaires de `tests/test_prepositionnement.py` passent.

**Todo List**

1. Créer `crise/preparation/prepositionnement.py` avec :
   - Import de `calculer_distance_haversine` et `estimer_temps_trajet` depuis `crise.geo.distance`.
   - Fonction `calculer_barycentre_incidents(incidents_df: pd.DataFrame) -> tuple[float, float]` :
     - Requiert colonnes `latitude`, `longitude`. Colonne `nb_clients` optionnelle (si absente ou nulle, poids = 1).
     - Retourne `(lat_barycentre, lon_barycentre)`.
     - Si `incidents_df` est vide ou n'a pas de coordonnées valides, retourne `(float("nan"), float("nan"))`.
   - Fonction `recommander_prepositionnement(equipes_df: pd.DataFrame, incidents_df: pd.DataFrame, coeff_detour: float = 1.3, vitesse_kmh: float = 60.0) -> list[dict]` :
     - Calcule d'abord le barycentre via `calculer_barycentre_incidents`.
     - Si barycentre est NaN (pas d'incidents), retourne liste vide.
     - Pour chaque ligne de `equipes_df` (colonnes attendues : `id_equipe`, `commune`, `latitude`, `longitude`), calcule `distance_km` et `temps_deplacement_h` vers le barycentre.
     - Retourne la liste triée par `temps_deplacement_h` croissant.
     - Chaque élément : `{"id_equipe": str, "commune": str, "lat_origine": float, "lon_origine": float, "lat_cible": float, "lon_cible": float, "temps_deplacement_h": float, "distance_km": float}`.
2. Créer `tests/test_prepositionnement.py` avec :
   - Test `calculer_barycentre_incidents` sur 2 incidents équipondérés → point médian.
   - Test `calculer_barycentre_incidents` sur incidents pondérés asymétriquement → barycentre tiré vers l'incident plus peuplé.
   - Test `calculer_barycentre_incidents` sur DataFrame vide → retourne `(nan, nan)`.
   - Test `recommander_prepositionnement` avec 2 équipes, 1 incident → liste de 2 éléments avec `temps_deplacement_h > 0`.
   - Test `recommander_prepositionnement` avec `equipes_df` vide → liste vide.
   - Test `recommander_prepositionnement` avec `incidents_df` vide → liste vide.

**Relevant Context**

- [`crise/geo/distance.py`](crise/geo/distance.py) : `calculer_distance_haversine(lat1, lon1, lat2, lon2) -> float` et `estimer_temps_trajet(lat1, lon1, lat2, lon2, coeff_detour, vitesse_kmh) -> float`.
- [`crise/preparation/jointure.py:102`](crise/preparation/jointure.py) : structure de `derouler_equipes` → colonnes `id_equipe`, `id_site`, `commune`, `latitude`, `longitude`, `disponible`.
- [`crise/strategies/allocator.py`](crise/strategies/allocator.py) : la méthode privée `_plus_proche()` (ligne ~200) montre le pattern de recherche du plus proche — s'en inspirer sans l'importer.

---

### Sous-tâche 2 — Ajouter `construire_points_preparation` dans `jointure.py`

**Status** : `[ ] pending`

**Intent**

La carte de la vue Préparation doit afficher à la fois les incidents prévisionnels **et** le point de barycentre (point de repli cible). La fonction existante `construire_points_carte` ne gère que "panne" et "site" — on lui ajoute une variante dédiée à la vue Préparation sans modifier la signature existante (pour ne pas impacter Rejeu ni Jour J).

**Expected Outcomes**

- [`crise/preparation/jointure.py`](crise/preparation/jointure.py) contient une nouvelle fonction `construire_points_preparation(incidents_previsionnels, sites, barycentre_lat, barycentre_lon) -> pd.DataFrame`.
- La fonction existante `construire_points_carte` est **inchangée**.
- Les tests existants de `tests/test_jointure.py` passent toujours sans modification.

**Todo List**

1. Dans [`crise/preparation/jointure.py`](crise/preparation/jointure.py), ajouter la constante `COULEUR_BARYCENTRE = "#9467bd"` (violet — distinct des couleurs existantes).
2. Ajouter la fonction `construire_points_preparation(incidents_previsionnels: pd.DataFrame, sites: pd.DataFrame, barycentre_lat: float, barycentre_lon: float) -> pd.DataFrame` :
   - Mêmes colonnes que `construire_points_carte` : `latitude`, `longitude`, `type`, `color`, `libelle`.
   - Bloc 1 — incidents prévisionnels : `color = COULEUR_PANNE`, `type = "incident_previsionnel"`.
   - Bloc 2 — sites équipes : `color = COULEUR_SITE`, `type = "site"`.
   - Bloc 3 — barycentre : si `barycentre_lat` n'est pas NaN, ajouter une ligne unique `{latitude: barycentre_lat, longitude: barycentre_lon, type: "point_repli", color: COULEUR_BARYCENTRE, libelle: "Point de repli optimal"}`.
   - Retourne `pd.DataFrame` avec les colonnes même si tous les inputs sont vides/NaN.
3. Dans `app/views/preparation.py` (Sous-tâche 3), utiliser `construire_points_preparation` à la place de `construire_points_carte`.

**Relevant Context**

- [`crise/preparation/jointure.py:141-172`](crise/preparation/jointure.py) : `construire_points_carte` — pattern exact à suivre.
- Couleurs existantes ligne 25-28 : `COULEUR_PANNE = "#d62728"`, `COULEUR_SITE = "#1f77b4"`, `COULEUR_EN_COURS = "#ff7f0e"`, `COULEUR_RESOLUE = "#2ca02c"` — choisir une couleur non utilisée pour le barycentre.

---

### Sous-tâche 3 — Enrichir `app/views/preparation.py`

**Status** : `[ ] pending`

**Intent**

Intégrer le calcul de prépositionnement dans la vue Préparation existante. La structure de la page est conservée ; on ajoute un second tableau d'arbitrage "Prépositionnements recommandés" en dessous du tableau d'affectations existant, et on enrichit la carte avec le barycentre. Lors de la validation, les prépositionnements retenus sont ajoutés à `plan_preparation`.

**Expected Outcomes**

- La page Préparation affiche un second tableau éditable "Prépositionnements recommandés" avec colonnes : Retenir, Équipe, Commune, Trajet (h), Distance (km).
- La carte affiche incidents prévisionnels (rouge) + sites (bleu) + point de repli optimal (violet).
- `plan_preparation` après validation contient la clé additionnelle `prepositionnements_retenus` (liste des mouvements cochés, équipes en réserve exclues).
- Le Mode Jour J reste fonctionnel sans aucune modification : `plan_preparation["equipes_en_reserve"]` est inchangé.
- Tous les tests existants passent.

**Todo List**

1. Dans [`app/views/preparation.py`](app/views/preparation.py), ajouter les imports en tête de fichier :
   - `from crise.preparation.prepositionnement import recommander_prepositionnement, calculer_barycentre_incidents`
   - `from crise.preparation.jointure import construire_points_carte, construire_points_preparation, derouler_equipes, preparer_pannes`
   - (remplacer l'import `construire_points_carte` seul par les deux fonctions)
2. Dans le bloc `if st.button("Générer les propositions de préparation", ...)`, après le calcul de `decisions` existant, ajouter :
   ```python
   prepositionnements = recommander_prepositionnement(
       equipes,
       previsionnelles,
       float(params["geo"]["coeff_detour"]),
       float(params["geo"]["vitesse_moyenne_kmh"]),
   )
   barycentre = calculer_barycentre_incidents(previsionnelles)
   ```
   Et stocker dans le brouillon : `"prepositionnements": prepositionnements, "barycentre": barycentre`.
3. Dans la section d'affichage du plan, remplacer l'appel à `construire_points_carte` par `construire_points_preparation` :
   ```python
   lat_b, lon_b = plan.get("barycentre", (float("nan"), float("nan")))
   points = construire_points_preparation(plan["pannes_previsionnelles"], agents_df, lat_b, lon_b)
   ```
4. Dans la colonne `arbitrage` (après le `data_editor` des affectations), ajouter un second sous-bloc "Prépositionnements recommandés" :
   - Si `plan["prepositionnements"]` est non vide, construire un DataFrame d'affichage : `{"Retenir": True, "Équipe": id_equipe, "Commune": commune, "Trajet (h)": temps_deplacement_h arrondi à 2, "Distance (km)": distance_km arrondi à 1}`.
   - Afficher via `st.data_editor` avec les colonnes Équipe/Commune/Trajet/Distance désactivées, clé `"prep_prepos_editor"`.
   - Si vide, afficher `st.info("Aucun prépositionnement calculé (toutes les équipes sont déjà affectées à un incident).")`.
5. Dans le bloc `if st.button("Valider le plan humain", ...)`, récupérer les prépositionnements retenus :
   ```python
   prepos_retenus = []
   if plan.get("prepositionnements") and not edite_prepos.empty:
       ids_equipes_retenues_prepos = set(edite_prepos.loc[edite_prepos["Retenir"], "Équipe"].astype(str))
       prepos_retenus = [
           p for p in plan["prepositionnements"]
           if str(p["id_equipe"]) in ids_equipes_retenues_prepos
           and str(p["id_equipe"]) not in reserve
       ]
   valide = {
       **plan,
       "decisions": retenues,
       "equipes_en_reserve": reserve,
       "commentaire_humain": commentaire.strip(),
       "prepositionnements_retenus": prepos_retenus,
       "statut": "VALIDE_PAR_L_HUMAIN",
   }
   ```

**Relevant Context**

- [`app/views/preparation.py`](app/views/preparation.py) : code complet (71 lignes) — toutes les modifications sont des ajouts ou des substitutions localisées.
- [`crise/simulation/pilotage.py:51`](crise/simulation/pilotage.py) : `reserve = set((plan_preparation or {}).get("equipes_en_reserve", []))` — seul accès au dict, non affecté par les nouvelles clés.
- [`app/views/jour_j.py:17-20`](app/views/jour_j.py) : lit `plan["numero_crise"]` et `plan["equipes_en_reserve"]` seulement — non affecté.

---

### Sous-tâche 4 — Tests d'intégration et validation de non-régression

**Status** : `[ ] pending`

**Intent**

Vérifier que tous les tests existants (47) passent sans modification, et ajouter un test d'intégration couvrant le flux complet de la Sous-tâche 1 + 2 + 3 ensemble.

**Expected Outcomes**

- `pytest tests/ -v` : 0 échec, aucun test existant modifié.
- `tests/test_preparation_integration.py` créé avec au moins 4 assertions couvrant le flux de bout-en-bout.

**Todo List**

1. Exécuter `pytest tests/ -v` une fois après la Sous-tâche 1, une fois après la Sous-tâche 2, une fois après la Sous-tâche 3.
2. Créer `tests/test_preparation_integration.py` avec :
   - **Test flux complet** : charger de vrais CSV (ou fixtures minimales), appeler `preparer_pannes` + `derouler_equipes`, puis `recommander_prepositionnement` + `calculer_barycentre_incidents`, vérifier que le dict `plan_preparation` résultant contient les clés `decisions`, `equipes_en_reserve`, `prepositionnements_retenus`, `statut`.
   - **Test non-régression Jour J** : construire un `plan_preparation` avec la nouvelle clé `prepositionnements_retenus` et vérifier que `creer_session_pilotage(plan_preparation=plan)` ne lève pas d'erreur et marque bien les équipes en réserve correctement.
   - **Test carte** : `construire_points_preparation` avec 2 incidents + 1 site + barycentre valide → vérifier que le DataFrame résultant contient les 3 types ("incident_previsionnel", "site", "point_repli").
   - **Test carte barycentre NaN** : `construire_points_preparation` avec barycentre NaN → le type "point_repli" est absent du DataFrame résultant.

**Relevant Context**

- [`tests/test_pilotage_humain.py`](tests/test_pilotage_humain.py) : test existant de `creer_session_pilotage` avec `plan_preparation` — à exécuter sans modification pour valider la non-régression.
- [`crise/simulation/pilotage.py:51-52`](crise/simulation/pilotage.py) : seul accès à `plan_preparation` dans le moteur.

---

## Résumé des fichiers

| Action | Fichier | Raison |
|---|---|---|
| **Créer** | `crise/preparation/prepositionnement.py` | Calcul du barycentre et des prépositionnements |
| **Créer** | `tests/test_prepositionnement.py` | Tests unitaires du module ci-dessus |
| **Créer** | `tests/test_preparation_integration.py` | Test d'intégration flux complet |
| **Modifier** (ajout) | `crise/preparation/jointure.py` | Nouvelle fonction `construire_points_preparation` + constante `COULEUR_BARYCENTRE` |
| **Modifier** | `app/views/preparation.py` | Intégrer prépositionnement dans UI (tableau + carte + validation) |

## Fichiers garantis non touchés

- `crise/simulation/moteur.py`
- `crise/simulation/pilotage.py`
- `crise/strategies/allocator.py`
- `crise/strategies/ia_optimizer.py`
- `crise/metrics/indicateurs.py`
- `crise/models/models.py`
- `crise/geo/distance.py`
- `crise/loaders/loaders.py`
- `config/params.yaml`
- `app/views/jour_j.py`
- `app/views/rejeu.py`
- `app/main.py`
- `app/components/*`
- Tous les tests existants (aucune modification)
