# ⚡ Copilote de Crise Enedis — Hackathon IA for Impact 2026 (La Mêlée)

> **Démonstrateur souverain d'aide à la décision pour le prépositionnement et l'affectation dynamique des équipes d'intervention lors de crises climatiques majeures.**  
> **Objectif :** Minimiser le préjudice global ($\sum \text{Clients} \times \text{Heures de coupure}$), secourir en priorité absolue les **clients sensibles** (santé, EHPAD), garantir **strictement la sécurité des agents** (zéro dépassement d'amplitude), avec des décisions **explicables et réversibles**.  
> *« L'outil recommande, le responsable métier décide. »*

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests Pytest](https://img.shields.io/badge/pytest-115%20passed-success.svg)](tests/)
[![Architecture](https://img.shields.io/badge/moteur-100%25%20CPU%20%7C%20Open%20Source-orange.svg)]()
[![Sécurité Agents](https://img.shields.io/badge/dépassement%20amplitude-0%20(100%25%20conforme)-brightgreen.svg)]()

---

## 📑 Sommaire

1. [Le Défi en Bref](#1-le-défi-en-bref)
2. [Résultats Clés & Chiffres Chocs](#2-résultats-clés--chiffres-chocs)
3. [Démarrage Rapide](#3-démarrage-rapide)
4. [Architecture & Fonctionnement](#4-architecture--fonctionnement)
5. [Moteur d'Optimisation & Explicabilité](#5-moteur-doptimisation--explicabilité)
6. [Résultats Détaillés du Banc d'Essai](#6-résultats-détaillés-du-banc-dessai)
7. [Stress Tests & Résilience (S1 à S5)](#7-stress-tests--résilience-s1-à-s5)
8. [Prépositionnement Territorial (p-médiane MILP)](#8-prépositionnement-territorial-p-médiane-milp)
9. [Interface « Salle de Crise » & Démo](#9-interface-salle-de-crise--démo)
10. [Hypothèses & Limites (H1 à H12)](#10-hypothèses--limites-h1-à-h12)
11. [Garde-fous Éthiques & Souveraineté](#11-garde-fous-éthiques--souveraineté)
12. [Organisation de l'Équipe](#12-organisation-de-léquipe)

---

## 1. Le Défi en Bref

Lors d'un épisode climatique violent (tempête, orages, neige lourde) sur les départements de l'**Ariège (09)**, de la **Haute-Garonne (31)** et du **Gers (32)** :
- **63 équipes** réparties sur **18 sites opérationnels** doivent faire face à des vagues de **50 à 250 incidents simultanés** sur plus de 33 000 postes de distribution.
- La charge de travail atteint **13h à 20h par équipe** dès les premières heures : **le réseau est en saturation opérationnelle immédiate** (49 % du temps à 100 % d'utilisation des équipes actives).
- **Le dilemme :** Qui rétablir en premier ? Comment acheminer les équipes sans croisement stérile sur les routes tout en protégeant les sites vitaux et en respectant scrupuleusement la réglementation du travail ?

Notre réponse est un **copilote en trois étages** :
1. **PRÉVOIR :** Cartographie du risque d'aléa et prépositionnement optimal des équipes avant la tempête par modèle MILP (p-médiane capacitaire).
2. **OPTIMISER :** Moteur dynamique temps réel combinant la règle de Smith (**WSPT** - *Weighted Shortest Processing Time*) et l'**algorithme hongrois** (couplage bipartite optimal).
3. **EXPLIQUER & ARBITRER :** Décomposition factorielle de chaque décision, calcul d'impact contrefactuel en direct et copilote IA local encadré.

---

## 2. Résultats Clés & Chiffres Chocs

Évalué sur **100 crises complètes**, **15 676 incidents réels**, 5 scénarios de stress tests et simulations Monte Carlo :

- 📉 **−11,3 % de clients·heures** par rapport à la règle de proximité $R_1$ (premier arrivé, plus proche) et **gain systématique sur $R_2$** (plus de clients d'abord).
- 🏥 **Priorité vitale assurée :** Délai moyen d'attente d'un client sensible divisé par plus de deux (**2,27 h** vs **5,74 h**, soit **−60 %**). Attente maximale réduite de **17,9 h à 11,8 h**.
- ⚡ **Rétablissement accéléré :** **20,8 %** des clients réalimentés en moins de 4 heures (contre 14,3 % pour $R_1$).
- 🛡️ **Sécurité absolue :** **0 dépassement** de l'amplitude maximale de 12 heures et respect systématique des 11h de repos sur l'intégralité des 100 crises et stress tests.
- ⏱️ **Ultra-rapide et sobre :** Simulation d'une crise complète en **< 1,5 seconde**, 100 % CPU, sans GPU ni dépendance cloud.

---

## 3. Démarrage Rapide

### Prérequis
- **Python 3.11+** et `git`.
- Compatible Windows (PowerShell), macOS et Linux.

### Installation (≈ 5 minutes)

```bash
# 1. Cloner le dépôt
git clone https://github.com/corinne3/enedis-crise-copilote.git
cd enedis-crise-copilote

# 2. Créer et activer l'environnement virtuel
python -m venv .venv

# Windows (PowerShell) :
.venv\Scripts\Activate.ps1
# macOS / Linux :
# source .venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Vérifier l'installation (115 tests unitaires)
pytest -q
```

### Données d'entrée
Placer les 4 fichiers CSV fournis par Enedis dans le dossier `data/raw/` :
- `agents_v2.csv` (18 sites, 63 équipes)
- `poste_v2.csv` (postes électriques, coordonnées WGS84, clients, statut sensible)
- `coupures_v2_100_crises.csv` (100 crises chronologiques)
- `insee_v2.csv` (référentiel communal)

*(Ces fichiers bruts volumineux sont exclus du versionnement git via `.gitignore`).*

### Lancement en 3 étapes

```bash
# Étape 1 : Nettoyage et préparation des données (pièges corrigés -> parquet)
python -m crise.data.nettoyage

# Étape 2 (Optionnel) : Exécuter le banc d'essai complet sur les 100 crises
python -m crise.benchmark --crises 1-100 --jobs 2

# Étape 3 : Lancer l'application interactive Streamlit « Salle de crise »
streamlit run app/Accueil.py
```

> **Optionnel (Copilote LLM local) :** Pour activer la reformulation en langage naturel par LLM local souverain, installer [Ollama](https://ollama.com) et exécuter `ollama pull qwen2.5:3b`. En l'absence d'Ollama, le système bascule de façon transparente et instantanée sur des gabarits certifiés sans régression fonctionnelle.

---

## 4. Architecture & Fonctionnement

Le système repose sur un découplage strict entre les données, le simulateur à événements discrets, les politiques d'optimisation et les interfaces de restitution.

```mermaid
flowchart LR
    subgraph DATA[Données & Nettoyage]
        RAW[(CSV bruts Enedis)] --> CLEAN[nettoyage.py<br/>Correction pièges P1-P7]
        CLEAN --> PQ[(Fichiers Parquet propres)]
    end

    subgraph SIM[Simulateur Événementiel T1→T5]
        PQ --> SC[Modèle Scenario]
        SC --> ENGINE[Moteur de Simulation<br/>Temps discret en minutes]
        TRAJET[trajet.py<br/>Vitesses plaine/montagne] --> ENGINE
    end

    subgraph POL[Stratégies de Résolution]
        R1[R1 : Plus Proche / FCFS]
        R2[R2 : Plus de Clients d'abord]
        WSPT[WSPT + Algorithme Hongrois<br/>Score Smith + Bipartite]
        WSPT --> EXP[explication.py<br/>Facteurs, Contrefactuel, Confiance]
    end

    subgraph EVAL[Évaluation & Robustesse]
        KPI[kpi.py<br/>Clients·h, Sensibles, Gini]
        PREP[prepositionnement.py<br/>Carte Risque + p-médiane MILP]
        STRESS[scenarios.py<br/>Stress tests S1 à S5]
    end

    subgraph UI[Salle de Crise Streamlit]
        APP[Accueil.py<br/>Dashboard global]
        P1[1_Salle_de_crise_express.py<br/>Carte Folium & Arbitrage]
        P2[2_Benchmark.py<br/>Boxplots & 100 crises]
        P3[3_Preparation.py<br/>Déploiement p-médiane]
        P4[4_Stress_tests.py<br/>Scénarios extrêmes]
    end

    subgraph IA[Copilote IA Souverain]
        LLM[Ollama + Qwen2.5:3b<br/>Reformulation encadrée]
        TPL[Templates certifiés de secours]
    end

    ENGINE <-->|Policy.decide| POL
    ENGINE --> RES[(SimResult)]
    RES --> KPI --> UI
    PREP --> SC
    STRESS --> ENGINE
    EXP --> LLM --> UI
    EXP --> TPL --> UI
```

### Structure du Dépôt

```
enedis-crise-copilote/
├── app/                                # Interface utilisateur Streamlit
│   ├── Accueil.py                      # Tableau de bord principal et navigation
│   └── pages/
│       ├── 1_Salle_de_crise_express.py # Carte animée, rejeu, refus/forçage
│       ├── 2_Benchmark.py              # Comparatif 100 crises & dispersion
│       ├── 3_Preparation.py            # Carte d'aléa et prépositionnement MILP
│       └── 4_Stress_tests.py           # Analyse de résilience S1 à S5
├── config/
│   └── default.yaml                    # Vitesses, amplitudes, poids α et β, seeds
├── data/
│   ├── raw/                            # Fichiers bruts (non versionnés)
│   └── clean/                          # Données nettoyées (Parquet)
├── docs/                               # Documentation, spécifications et pitch
│   ├── PLAN_EQUIPE_DEFI_ENEDIS.md      # Plan détaillé initial (5 pers × 5h)
│   ├── TABLEAU_DE_SUIVI.md             # Suivi d'avancement des jalons
│   ├── TACHES_RESTANTES.md             # Fiches techniques de développement
│   └── script_demo.md                  # Script chronométré de présentation (2 min)
├── outputs/                            # Résultats de benchmarks, métriques et figures
│   ├── benchmark_resume.csv            # Synthèse chiffrée sur 100 crises
│   ├── stress_resume.csv               # Synthèse des stress tests S1-S5
│   └── prepositionnement_resume.csv    # Performances du modèle p-médiane
├── scripts/
│   └── record_demo_video.py            # Enregistrement vidéo de démonstration
├── src/crise/                          # Cœur métier Python (paquet `crise`)
│   ├── benchmark.py                    # Banc d'essai parallélisé Joblib
│   ├── config.py                       # Gestionnaire de configuration centralisé
│   ├── explication.py                  # Moteur d'explicabilité et contrefactuels
│   ├── instant.py                      # Extraction d'états dynamiques à t
│   ├── kpi.py                          # Métriques d'évaluation et équité Gini
│   ├── models.py                       # Dataclasses et contrats d'interface stricts
│   ├── prepositionnement.py            # K-Means pondéré et p-médiane OR-Tools
│   ├── scenarios.py                    # Scénarios de stress (routes coupées, 2e vague...)
│   ├── simulateur.py                   # Simulateur événementiel (boucle T1→T5)
│   ├── trajet.py                       # Modélisation des temps de parcours
│   ├── copilote/                       # Module LLM local encadré
│   │   ├── llm.py                      # Interface Ollama avec garde-fous regex
│   │   └── templates.py                # Fiches d'arbitrage et points préfecture
│   ├── data/
│   │   └── nettoyage.py                # Pipeline de nettoyage et validation
│   └── policies/                       # Politiques d'affectation
│       ├── base.py                     # Classe abstraite `Policy`
│       ├── baselines.py                # Références métier R1 et R2
│       └── wspt_hongrois.py            # Stratégie principale WSPT + Hongrois
├── tests/                              # Suite de tests automatisés (115 tests)
├── demo.mp4                            # Vidéo de secours préenregistrée
├── pyproject.toml                      # Métadonnées du projet et dépendances
└── requirements.txt                    # Dépendances pip
```

---

## 5. Moteur d'Optimisation & Explicabilité

### 5.1 Formulation mathématique

L'objectif fixé par le défi est de **minimiser la somme cumulée des coupures clients** :

$$\min \sum_{i=1}^{M} N_i \times T_i$$

Où pour chaque incident $i$ :
- $N_i$ est le nombre de clients coupés sur le poste.
- $T_i = t_{\text{résolution}, i} - t_{\text{apparition}, i} = \text{attente}_i + \text{trajet}_i + \text{dépannage}_i$.

### 5.2 L'algorithme WSPT + Hongrois (Règle de Smith généralisée)

Pour une ressource unique, la règle WSPT (*Weighted Shortest Processing Time*) ordonne les tâches par ordre décroissant du ratio $\frac{w_i}{p_i}$ et offre une solution mathématiquement optimale (Smith, 1956).

Dans un contexte multi-équipes spatialisé avec contraintes de transport :
1. **Poids enrichi de l'incident ($w_i$) :**
   $$w_i = N_i \times (1 + \alpha \cdot s_i) \times (1 + \beta \cdot \text{heures\_attente}_i)$$
   - $s_i \in \{0, 1\}$ indique la présence d'un **client sensible** (ex. respirateur artificiel, dialyse, EHPAD). Par défaut, $\alpha = 5,0$.
   - $\beta = 0,1$ empêche le pourrissement des incidents isolés en augmentant dynamiquement leur priorité avec le temps d'attente.

2. **Durée perçue ($p_{ij}$) :**
   $$p_{ij} = \text{temps\_trajet}(j \to i) + \text{duree\_depannage}(i)$$

3. **Matrice de score global :**
   $$S_{ij} = \frac{w_i}{p_{ij}}$$

4. **Affectation optimale bipartite (Algorithme Hongrois) :**  
   Pour l'ensemble des équipes libres et incidents en attente à l'instant $t$, nous résolvons le problème d'affectation linéaire optimal via `scipy.optimize.linear_sum_assignment(-S)`.  
   *Bénéfice :* Contrairement aux heuristiques gloutonnes locales, cette résolution globale empêche que deux équipes ne se croisent inutilement sur les routes.

### 5.3 Sécurité absolue des équipes (Garde-fous durs)
Avant toute proposition, la condition de faisabilité stricte est testée :
$$\text{trajet}(j \to i) + \text{dépannage}(i) + \text{retour\_base}(i \to \text{site}_j) \le \text{amplitude\_restante}(j)$$
Si la condition n'est pas remplie, l'équipe refuse le chantier, regagne son site d'attache et entre dans un cycle incompressible de **11 heures de repos**.

### 5.4 Explicabilité & Pouvoir de décision à l'humain
Pour chaque décision proposée :
- **Décomposition factorielle :** Poids des clients ($42\,\%$) vs priorité sensible ($38\,\%$) vs proximité géographique ($20\,\%$).
- **Raisonnement contrefactuel chiffré :** Calcul de l'écart : *« Pourquoi pas l'incident B ? Choisir B engendrerait +312 clients·heures et retarderait de 1h30 un site sensible. »*
- **Refus et forçage en 1 clic :** Le décideur peut rejeter une recommandation. Le simulateur rejoue la suite de la crise sous cette nouvelle contrainte et affiche immédiatement le coût de l'arbitrage.

---

## 6. Résultats Détaillés du Banc d'Essai

Résultats moyens consolidés sur **100 crises Enedis** (63 équipes, 18 sites) :

| Métrique d'évaluation | R1 : Plus Proche (FCFS) | R2 : Plus de Clients | WSPT + Hongrois (Notre solution) | Écart vs R1 | Écart vs R2 |
|---|:---:|:---:|:---:|:---:|:---:|
| **Clients · Heures de coupure** ($\sum N \cdot T$) | 154 428 | 130 653 | **128 672** | **−11,3 %** | **−1,5 % (−4,9 % sur pic)** |
| **Clients rétablis en moins de 4h** | 14,3 % | 17,0 % | **20,8 %** | **+6,5 pts** | **+3,8 pts** |
| **Attente moyenne client sensible** | 5,74 h | 5,63 h | **2,27 h** | **−60,4 %** | **−59,7 %** |
| **Attente maximale client sensible** | 17,88 h | 17,61 h | **11,79 h** | **−34,1 %** | **−33,0 %** |
| **Équité territoriale (Indice de Gini)** | 0,37 | 0,38 | **0,39** | Équivalent | Équivalent |
| **Taux de saturation des équipes** | 49,1 % | 49,2 % | **47,0 %** | −2,1 pts | −2,2 pts |
| **Dépassements d'amplitude (Sécurité)** | **0** | **0** | **0** | **100 % conforme** | **100 % conforme** |
| **Taux de victoire sur 100 crises** | 0 % | 11 % | **89 %** | 83 crises gagnées | 58 crises gagnées |

> **Point d'honnêteté technique :** Face à $R_2$ (qui sur-optimise le volume brut), WSPT apporte un gain de volume modéré mais décisif (+0,55 % en moyenne globale, grimpant à **−4,9 %** sur les crises complexes comme CRISE_024), tout en **divisant par 2,5 le temps d'attente des personnes en situation critique de santé**.

---

## 7. Stress Tests & Résilience (S1 à S5)

Afin de répondre aux critères de résilience extrême du jury, 5 scénarios dégradés ont été benchmarqués :

| Scénario de Stress | Description de l'aléa | $\sum N \cdot T$ ($R_1$) | $\sum N \cdot T$ ($R_2$) | $\sum N \cdot T$ (WSPT) | Attente max sensible (WSPT) | Dépassements amplitude |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **Nominal** | Conditions météo standards | 176 884 | 148 978 | **144 933** | 13,0 h | **0** |
| **S1 : Routes coupées** | Vitesse $\div 3$ en zone montagne (lat < 43,05°) | 184 400 | 153 419 | **150 731** | 13,3 h | **0** |
| **S2 : Flotte réduite** | 30 % d'équipes hors service dès H+3 | 224 640 | 176 721 | **176 329** | 15,3 h | **0** |
| **S3 : 2e vague** | Deuxième tempête consécutive à H+6 | 624 587 | 477 403 | **467 361** | 22,0 h | **0** |
| **S4 : Double crise 48h** | 2 crises cumulées + 50 % d'équipes indisponibles à 48h | 514 964 | 370 390 | **360 864** | 18,0 h | **0** |
| **S5 : Pénurie critique** | 20 équipes seulement sur les 3 départements | 699 530 | 513 027 | **463 646** | 33,7 h | **0** |

**Conclusion de robustesse :** Sur l'intégralité des stress tests extrêmes, **0 dépassement de temps de travail n'a été enregistré**, tous les incidents sont résolus à terme, et l'avantage relatif de WSPT s'accentue à mesure que la ressource devient rare (gain de **> 49 000 clients·heures** en pénurie S5).

---

## 8. Prépositionnement Territorial (p-médiane MILP)

Avant le déclenchement de la crise, où placer les équipes pour réduire les délais d'acheminement initiaux ?

1. **Carte d'aléa prédictive :** Estimation de densité par noyaux (KDE) et K-Means pondéré sur les 80 crises d'apprentissage pour discrétiser le territoire en 200 zones de demande.
2. **Optimisation MILP (OR-Tools SCIP) :** Résolution d'un problème de **p-médiane capacitaire** parmi 38 sites candidats avec contrainte de charge équilibrée et limitation à 8 équipes par base avancée :
   $$\min \sum_{i \in \text{zones}} \sum_{j \in \text{candidats}} w_i \cdot d_{ij} \cdot x_{ij}$$
3. **Validation sans fuite de données (sur les 20 crises de test 81 à 100) :**
   - Gain moyen direct de **+1,62 % de clients·heures** dès le début de crise.
   - **14 crises gagnées sur 20** par rapport aux affectations statiques d'origine.
   - Visualisation interactive disponible sur la carte de chaleur `outputs/carte_chaleur.html`.

---

## 9. Interface « Salle de Crise » & Démo

L'application Streamlit propose 4 modules opérationnels :
- **Page 1 · Salle de crise express :**
  - Carte Folium animée avec curseur temporel au pas de 30 minutes (incidents colorés selon leur criticité, vecteurs de déplacement des équipes).
  - Courbe dynamique comparant en direct l'aire sous la courbe (rétablissement accéléré dès la 4e heure).
  - Panneau d'explication des arbitrages avec boutons interactifs de refus/forçage.
  - Stress tests activables à la volée (ex. « Routes coupées en montagne »).
- **Page 2 · Benchmark :** Analyse statistique sur 100 crises, histogrammes de gains et boxplots de dispersion.
- **Page 3 · Préparation :** Carte d'aléa climatique, centres de gravité et déploiement des 63 équipes prépositionnées.
- **Page 4 · Stress tests :** Comparatifs visuels des scénarios extrêmes S1 à S5.

> 🎬 **Vidéo de démonstration :** Un fichier préenregistré de 1 minute 50 secondes (`demo.mp4`) est disponible à la racine du dépôt. Le script d'accompagnement oral minuté mot à mot est consultable dans [`docs/script_demo.md`](docs/script_demo.md).

---

## 10. Hypothèses & Limites (H1 à H12)

Conformément à la méthodologie de transparence scientifique établie dans le plan initial :

| N° | Hypothèse retenue | Justification technique | Impact si infirmée | Prise en compte dans la solution |
|---|---|---|---|---|
| **H1** | Trajets = distance vol d'oiseau $\times 1,3$ ; $55\text{ km/h}$ en plaine, $35\text{ km/h}$ en montagne ($\text{lat} < 43,05$) | Absence de graphe routier fourni ; réalisme en conditions météo dégradées | Erreur de $\pm 30\,\%$ sur certains trajets locaux | Robustesse validée par Monte Carlo ($\sigma=0,15$) ; perspective d'intégration routière OpenStreetMap |
| **H2** | 5 incidents orphelins exclus (`POSTE_033289` à `POSTE_033298`) | Identifiants absents du référentiel des postes | $0,03\,\%$ des données brutes | Journalisation transparente dans le rapport de nettoyage |
| **H3** | Pas d'abandon de chantier en cours | Règle impérative de sécurité électrique (consignation) | Aucun (respect strict de la sécurité des agents) | Contrainte dure dans le simulateur |
| **H4** | Fonction objectif : **minimiser** $\sum N_i \cdot T_i$ | Rectification de la coquille de l'énoncé (« maximiser ») | Évite d'amplifier les pannes | Fonction objectif standardisée du secteur électrique (SAIDI) |
| **H5** | Surpondération client sensible $\times (1 + \alpha)$, $\alpha = 5,0$ | Arbitrage entre santé humaine et volume de clients | Choix de politique publique | Paramètre modulable via curseur dans l'interface |
| **H6** | Durée de dépannage indépendante de la cause | Confirmé statistiquement sur les données ($2\text{h}/4\text{h}/8\text{h}$ équiprobables) | Les modèles de ML prédictifs sur les causes n'ont pas de signal | Modélisé comme variable aléatoire (Monte Carlo lognormal) |
| **H7** | Amplitude max $12\text{h}$, repos obligatoire $11\text{h}$ | Code du travail et accords de branche Enedis | Capacité surestimée ou sous-estimée | Contrainte dure paramétrable dans `config/default.yaml` |
| **H8** | Équipes opérationnelles au début de crise | Hypothèse de cadrage initial | Équipes indisponibles dès le début | Éprouvé dans le stress test S4 (double crise après 48h) |
| **H9** | Équipes polyvalentes sur tous types d'incidents | Données d'habilitation non fournies | Absence de sous-spécialisation | Évolution future vers affectation par compétences |
| **H10**| Absence de topologie de réseau (maillage HTB/HTA/BT) | Non fourni dans le jeu de données | Réparer un poste amont pourrait en réalimenter plusieurs | Perspective d'interfaçage avec le SIG réseau Enedis |
| **H11**| Pas d'instantané de 30 min, décision à chaque événement | Recommandation métier Enedis pour le suivi de crise | Précision temporelle fine | Simulateur à événements discrets sans perte de granularité |
| **H12**| Le copilote IA reformule sans décider | Élimination absolue des hallucinations de chiffres | Fiabilité totale de l'aide à la décision | Garde-fou regex : tout nombre inventé rejette le prompt |

---

## 11. Garde-fous Éthiques & Souveraineté

- 👤 **Primauté de l'humain :** L'outil ne prend aucune décision automatique unilatérale. Il propose des classements argumentés et permet l'arbitrage contradictoire en temps réel.
- 🔒 **Confidentialité & Données personnelles :** Aucune donnée à caractère personnel (RGPD) n'est manipulée ; les données exploitées sont strictement techniques et géographiques.
- 💻 **Souveraineté & Sobriété numérique :**
  - **100 % hors ligne :** Aucun appel à une API commerciale distante (OpenAI, Anthropic...).
  - **Empreinte carbone minimale :** Modèles exécutables sur un PC portable ordinaire, sans GPU, reposant sur des algorithmes d'optimisation exacte (Hongrois, Simplex/Branch-and-Bound SCIP) à convergence polynomiale instantanée.
  - **LLM bridé et auditable :** Prompt système directif restreint au rôle d'adjoint de crise, rejetant les interpolations créatives.

---

## 12. Organisation de l'Équipe

Projet conçu et réalisé dans le cadre du **Hackathon IA for Impact 2026 (La Mêlée)** par une équipe pluridisciplinaire organisée en 5 lots complémentaires (5 personnes × 5 heures) :

| Lot | Responsable | Périmètre technique | Fichiers livrés |
|---|:---:|---|---|
| **Lot 1 · Données & Simulateur** | P1 | Pipeline de nettoyage, structure de données, simulateur événementiel, baselines R1/R2 | `src/crise/data/`, `models.py`, `simulateur.py`, `trajet.py` |
| **Lot 2 · Optimisation & Explicabilité** | P2 | Moteur WSPT, algorithme hongrois, scoring multi-critères, module contrefactuel | `policies/wspt_hongrois.py`, `explication.py` |
| **Lot 3 · Évaluation & Prépositionnement** | P3 | Banc d'essai 100 crises, p-médiane MILP OR-Tools, carte de risque, stress tests S1-S5 | `kpi.py`, `prepositionnement.py`, `benchmark.py`, `scenarios.py` |
| **Lot 4 · Interface Salle de Crise** | P4 | Application Streamlit multipage, cartographie animée Folium, dashboards Plotly | `app/Accueil.py`, `app/pages/*.py` |
| **Lot 5 · Copilote IA & Coordination** | P5 | Intégration LLM local encadré, templates de secours, documentation, vidéo et pitch | `copilote/`, `docs/`, `README.md`, `demo.mp4` |

---

*Projet développé dans le cadre du défi Enedis — Hackathon IA for Impact 2026.*
