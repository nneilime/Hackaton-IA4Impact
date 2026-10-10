# 🤖 Documentation Technique — Moteur IA de Gestion de Crise
## `IA_NEED_IS` — Optimisation d'Affectation d'Équipes par LTR + Algorithme Hongrois + SHAP

> **Contexte** : Hackathon Enedis 2026 — *Si plusieurs territoires sont touchés et que toutes les équipes ne peuvent pas partir partout, où les positionner et à quels incidents les affecter pour rétablir le plus vite possible, en sécurité et en gardant la décision explicable ?*

---

## Table des matières

1. [Problème & Formulation Mathématique](#1-problème--formulation-mathématique)
2. [Architecture Hybride : LTR + Algorithme Hongrois](#2-architecture-hybride--ltr--algorithme-hongrois)
3. [Phase 1 — Learning-to-Rank (LTR) : HistGradientBoosting](#3-phase-1--learning-to-rank-ltr--histgradientboosting)
4. [Phase 2 — Algorithme Hongrois (Kuhn-Munkres)](#4-phase-2--algorithme-hongrois-kuhn-munkres)
5. [Phase 3 — Explicabilité SHAP (TreeSHAP)](#5-phase-3--explicabilité-shap-treeshap)
6. [Moteur de Simulation Temporelle](#6-moteur-de-simulation-temporelle)
7. [Comparaison des Stratégies & Validation](#7-comparaison-des-stratégies--validation)
8. [Human-in-the-Loop & Perspectives](#8-human-in-the-loop--perspectives)

---

## 1. Problème & Formulation Mathématique

### 1.1 Objectif métier

Minimiser les **Clients-Heures de Coupure** sur l'ensemble d'une crise, formellement :

$$\text{Minimiser} \sum_{i \in \text{Incidents}} N_i \times T_i$$

où :
- $N_i$ = nombre de clients coupés par l'incident $i$  
- $T_i = T^{\text{attente}}_i + T^{\text{route}}_i + T^{\text{dépannage}}_i$ = temps de coupure total

### 1.2 Pourquoi c'est NP-difficile

Ce problème appartient à la classe des **Problèmes d'Ordonnancement Pondéré** (`1||ΣwⱼCⱼ` en notation de Graham). Dans une crise multi-territoires, sa complexité explose car :

- Les équipes ont des **positions dynamiques** (elles restent là où elles terminent une réparation)  
- Elles ont une **amplitude maximale de service** (réglementation : 12h, puis 11h de repos)  
- Les incidents **arrivent en flux continu** (pas tous connus dès le début)  
- Le problème d'appariement optimal est **NP-difficile au sens strict** pour une crise complète

**Notre solution** : une approche hybride en deux phases — *LTR* pour scorer les paires, puis l'*Algorithme Hongrois* pour l'optimum global instantané.

---

## 2. Architecture Hybride : LTR + Algorithme Hongrois

```
Données Historiques ──► Entraînement LTR ──► Modèle GBDT
(100 crises réelles)     Knowledge Distillation  HistGradientBoosting

        A l'instant T de la crise :

Incidents actifs ]                       ┌──► Matrice de Scores M×K
                  ├──► Scoring GBDT ─────┤
Équipes libres   ]                       └──► Algorithme Hongrois
                                                    │
                                                    ▼
                                         Affectations Optimales Globales
                                                    │
                                                    ▼
                                         SHAP Explicabilité Locale
                                                    │
                                                    ▼
                                         Recommandations Justifiées
```

L'IA s'exécute **à chaque pas de temps** de la simulation (toutes les 30 minutes), ce qui lui permet de s'adapter dynamiquement à l'état de crise.

---

## 3. Phase 1 — Learning-to-Rank (LTR) : HistGradientBoosting

### 3.1 Paradigme : Knowledge Distillation (Distillation de Connaissances)

Le modèle n'est **pas entraîné sur des données artificielles**. Il apprend une **fonction de priorité experte** à partir des données réelles fournies par Enedis. C'est la technique dite de *Surrogate Modeling* ou *Knowledge Distillation* :

> **L'idée** : un expert métier encode sa règle de décision dans une fonction cible. Le GBDT apprend à approximer cette fonction sur les données réelles, ce qui lui permet ensuite de généraliser sur de nouvelles situations non vues.

### 3.2 Construction du dataset d'entraînement

```python
# Chargement des vrais historiques Enedis
coupures = pd.read_csv("coupures_v2_100_crises.csv", sep=";")
postes   = pd.read_csv("poste_v2.csv", sep=";")
agents   = pd.read_csv("agents_v2.csv", sep=";")

# 10 000 paires (Incident réel × Site d'équipe réel)
df_sample = df_incidents.sample(n=10_000, random_state=42)
```

**Features (variables d'entrée)** pour chaque paire `(équipe e, incident i)` :

| # | Feature | Description |
|---|---------|-------------|
| 1 | `Clients impactés` | `nb_clients` — nombre de foyers coupés |
| 2 | `Poste sensible` | 1 si hôpital, EHPAD ou infrastructure critique |
| 3 | `Durée dépannage (h)` | Durée estimée de la réparation |
| 4 | `Temps de trajet (h)` | Estimé par la formule de Haversine × coeff_détour |
| 5 | `Distance (km)` | Distance routière réelle estimée |

### 3.3 Fonction cible — Règle de Smith Adaptée

La cible est dérivée de la **Règle de Smith** (résultat d'ordonnancement optimal pour minimiser `ΣwⱼCⱼ`) :

```
                 N_i × 50 + S_i × 2000
score(e, i)  =  ─────────────────────────────────
                 T_route(e,i) + T_dépannage(i) + 0.5
```

où `S_i = 1` si le poste est sensible (hôpital/EHPAD), `0` sinon.

**Interprétation** : un incident avec beaucoup de clients **et** traitable rapidement obtient un score élevé. C'est exactement la logique qui minimise les Clients-Heures. Le dénominateur pousse à prioriser les équipes proches et les pannes rapides.

### 3.4 Distance géographique — Formule de Haversine

Le temps de trajet entre deux points GPS est calculé par :

```python
# Distance à vol d'oiseau (km)
a = sin²(Δlat/2) + cos(lat1)·cos(lat2)·sin²(Δlon/2)
d = 2 × R × atan2(√a, √(1−a))    # R = 6371 km

# Distance routière estimée
d_route = d × coeff_détour         # coeff_détour = 1.3
temps_h = d_route / vitesse_kmh    # vitesse = 60 km/h
```

### 3.5 Modèle : HistGradientBoostingRegressor

```python
model = HistGradientBoostingRegressor(
    max_iter=45,       # 45 arbres
    max_depth=5,       # Profondeur maximale
    learning_rate=0.1, # Shrinkage (régularisation)
    random_state=42,
)
```

**Pourquoi ce modèle ?**
- Inspiré de **LightGBM** : utilise des histogrammes pour les splits (très rapide)
- **Natif sklearn** : pas de dépendance externe additionnelle
- Compatible **TreeSHAP** pour l'explicabilité locale
- Robuste aux **valeurs manquantes** (gestion native)

### 3.6 Inférence à l'instant T

À chaque décision, on construit la **matrice de scores** de toutes les paires possibles :

```python
# Pour M équipes libres et K incidents en attente → M×K paires
X_paires       = np.array(lignes_features)         # shape (M*K, 5)
scores_pred    = model.predict(X_paires)            # shape (M*K,)
scores_matrice = scores_pred.reshape((M, K))        # shape (M, K)
```

---

## 4. Phase 2 — Algorithme Hongrois (Kuhn-Munkres)

### 4.1 Formulation du problème d'affectation

On cherche l'**affectation bijective optimale** entre M équipes et K incidents :

```
Trouver σ : Équipes → Incidents  tel que  Σ score(i, σ(i)) est maximal
```

C'est un **Problème d'Affectation Bipartite** (Bipartite Matching), résolu de façon **exacte et polynomiale** en O(n³) par l'Algorithme Hongrois.

### 4.2 Implémentation

```python
# Minimiser le coût négatif = maximiser le score
cost_matrix = -scores_matrice.copy()

# Masquer les paires infaisables (contrainte d'amplitude de service)
cost_matrix[invalide_masque] = 1e9

# Algorithme Hongrois (scipy implémentation C optimisée)
row_indices, col_indices = linear_sum_assignment(cost_matrix)
```

### 4.3 Contrainte d'amplitude de service (règle 12h/11h)

Avant de scorer, on **interdit** toute paire où l'équipe ne peut pas :

1. Aller jusqu'à l'incident : `T_route(e → i)`
2. Effectuer la réparation : `T_dépannage(i)`
3. **Rentrer à sa base d'attache** : `T_route(i → base(e))`

…dans son amplitude de service restante :

```
T_route(e→i) + T_dépannage(i) + T_route(i→base(e))  ≤  H_restantes(e)
```

```python
if temps_trajet + duree_dep + retour > heures_restantes:
    invalide_masque[i, j] = True  # Mission refusée
```

### 4.4 Pourquoi l'Algorithme Hongrois est supérieur à l'heuristique greedy

|  | Greedy ("premier arrivé") | **Algorithme Hongrois** |
|---|---|---|
| **Optimum** | Local (1 paire à la fois) | **Global simultané** |
| **Complexité** | O(n log n) | O(n³) |
| **Exemple pitfall** | Envoie la meilleure équipe vers un petit incident | **Réserve la meilleure équipe** pour l'incident le plus impactant |

> **Exemple concret** : Si l'équipe A est proche de l'incident X (50 clients) et de l'incident Y (200 clients), et l'équipe B n'est proche que de Y, le greedy envoie A vers X. L'Hongrois envoie A vers Y et B vers X — minimisant les clients-heures totaux.

---

## 5. Phase 3 — Explicabilité SHAP (TreeSHAP)

### 5.1 Principe des valeurs de Shapley

Les valeurs SHAP (SHapley Additive exPlanations) décomposent la prédiction du modèle pour une observation donnée en **contributions individuelles de chaque feature**, basées sur la théorie des jeux coopératifs (Shapley, 1953) :

```
f(x) = φ₀ + Σⱼ φⱼ

φ₀  = valeur de base (prédiction moyenne du modèle)
φⱼ  = contribution marginale de la feature j
```

**Propriétés garanties** : Efficience, Symétrie, Linéarité, Absence fictive (Dummy).

### 5.2 TreeSHAP : implémentation exacte

Pour les modèles d'arbres, TreeSHAP calcule les valeurs de Shapley **exactes** (pas d'approximation) en temps polynomial grâce à la structure des arbres de décision :

```python
# Entraînement de l'explainer une seule fois (partagé, singleton)
IAOptimizer._explainer_partage = shap.TreeExplainer(model)

# Explication locale pour chaque affectation choisie
shap_vals = explainer.shap_values(X_selected)  # shape (n_affectations, 5)
```

### 5.3 Génération de l'explication humaine (AI Act)

```python
# Top features positives (hausse de priorité)
top_pos = sorted([(nom, v) for nom, v in shap_vals.items() if v > 0],
                 key=lambda x: x[1], reverse=True)

# Explication naturelle générée automatiquement
synth_shap = "Clients impactés (+1240 pts) | Temps de trajet (-320 pts)"
```

**Exemple d'explication produite** :
```
ML+Hongrois (SITE_12, 18 min).
Justification SHAP : Clients impactés (+842 pts) + Poste sensible (+200 pts)
                   | Durée dépannage (-90 pts)
```

### 5.4 Conformité AI Act

L'explicabilité locale par SHAP répond directement aux exigences de l'AI Act Européen pour les systèmes IA à **haut risque** (gestion d'infrastructures critiques) :

- ✅ Décision **auditable** à posteriori
- ✅ Décision **contestable** par le coordinateur humain
- ✅ Contribution de chaque facteur **quantifiée et signée**
- ✅ Prédictions **comparables** entre incidents et crises

---

## 6. Moteur de Simulation Temporelle

### 6.1 Boucle principale

```
Pour chaque pas t (30 min par défaut) sur 48h :
  ├── 1. Appliquer les aléas (saturation trafic, perte équipes, double crise)
  ├── 2. Mettre à jour positions : équipes arrivées → repos (11h réglementaire)
  ├── 3. Libérer équipes dont repos terminé
  ├── 4. Détecter nouvelles pannes apparues
  ├── 5. Clore missions terminées → calculer Clients-Heures
  ├── 6. Construire liste équipes libres + pannes en attente
  ├── 7. IA → Scorer toutes les paires (M×K features)
  ├── 8. Algorithme Hongrois → Affectations optimales globales
  ├── 9. Vérifier contrainte 12h pour chaque affectation
  └── 10. Démarrer missions retenues
```

### 6.2 Gestion dynamique des positions des techniciens

Après chaque réparation, **l'équipe ne rentre pas à sa base** — elle reste sur place, ce qui reflète la réalité opérationnelle :

```python
# Fin de mission : position mise à jour au poteau réparé
equipe["latitude"]  = float(panne["latitude"])
equipe["longitude"] = float(panne["longitude"])
```

Le calcul du temps de trajet pour la panne suivante part donc du **dernier poteau réparé**, pas de la base. C'est ce qui rend l'enchaînement des interventions optimal géographiquement.

### 6.3 États des techniciens

```
libre ──► en_mission ──► retour_site ──► au_repos ──► libre
                                         (11h réglementaires)
                         ↑ si amplitude 12h atteinte
```

### 6.4 Scénarios de robustesse

| Scénario | Modélisation |
|----------|-------------|
| `nominal` | Conditions standards |
| `saturation_trafic` | Vitesse × 0.7 (embouteillages tempête) |
| `perte_equipes` | 50% des équipes libres → `indisponible` à X% de la crise |
| `double_crise` | Doublement des incidents avec décalage temporel |

---

## 7. Comparaison des Stratégies & Validation

### 7.1 Stratégies comparées

| Stratégie | Mécanisme |
|-----------|-----------|
| `distance` | Équipe la plus proche pour chaque panne (greedy) |
| `score_pondere` | Score linéaire pondéré (clients, sensible, durée, distance) |
| `premier_arrive` | Première panne arrivée = première traitée (FIFO) |
| **`ia_optimale`** | **LTR (Smith Rule) + Algorithme Hongrois + SHAP** |

### 7.2 Métrique officielle

```
Score = Σᵢ Nᵢ × Tᵢ     (à MINIMISER — moins = mieux)
```

Chaque client-heure de coupure en moins est une famille qui récupère l'électricité plus tôt.

### 7.3 Test unitaire automatisé

```bash
python -m pytest tests/test_performance.py
```

Ce test vérifie formellement, sur les vraies données Enedis, que :

```python
assert score_ia <= score_distance       # IA bat Distance minimale
assert score_ia <= score_score_pondere  # IA bat Score Pondéré
```

---

## 8. Human-in-the-Loop & Perspectives

### 8.1 Architecture actuelle (mode batch)

L'IA tourne en **simulation complète** sur les 48h de crise, permettant de comparer toutes les stratégies à posteriori et d'afficher des métriques comparatives.

### 8.2 Architecture cible (HITL)

```
Horloge T s'arrête sur vague de pannes
         │
         ▼
IA génère recommandations + justifications SHAP
         │
         ▼
Interface Streamlit : st.data_editor (tableau modifiable)
   Le coordinateur : valide / refuse / modifie manuellement
         │
         ▼
Bouton "Appliquer" → st.session_state mis à jour
         │
         ▼
Simulation reprend jusqu'à la prochaine décision
```

> L'IA et le modèle ML ne nécessitent **aucune modification** pour le HITL — seule l'orchestration Streamlit évolue pour gérer l'état pas à pas via `st.session_state`.

### 8.3 Améliorations futures du modèle

| Axe | Description |
|-----|-------------|
| **Nouvelles features** | Accessibilité terrain, risque réseau, météo en temps réel |
| **Apprentissage continu** | Réentraînement sur les crises réelles passées (feedback loop) |
| **Multi-objectif** | Pareto-optimal entre Clients-Heures et équité territoriale |
| **Horizon glissant** | Recuit simulé pour explorer l'espace des solutions sur 48h complets |

---

## Annexe — Stack Technique

```
Python 3.11
├── scikit-learn             → HistGradientBoostingRegressor (LTR)
├── shap                     → TreeSHAP (explicabilité locale)
├── scipy                    → linear_sum_assignment (Algorithme Hongrois)
├── pandas / numpy           → Manipulation des données
├── streamlit                → Interface de visualisation & pilotage
└── pytest                   → Tests unitaires de performance
```

| Fichier | Rôle |
|---------|------|
| `crise/strategies/ia_optimizer.py` | Coeur IA : LTR + Hongrois + SHAP |
| `crise/simulation/moteur.py` | Moteur de simulation temporelle |
| `crise/metrics/indicateurs.py` | Calcul des métriques Clients-Heures |
| `crise/geo/distance.py` | Haversine + estimation temps de trajet |
| `tests/test_performance.py` | Tests unitaires de performance |

---

*IA_NEED_IS — Hackathon Enedis 2026*

