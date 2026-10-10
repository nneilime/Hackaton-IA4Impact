# Tâches restantes — mode d'emploi pour l'équipe et vos IA

> **État au 10/10, 10h.** Livraison à **13h**. **Gel du code à 11h30.** Répétition du pitch à 12h.
> Chacun **choisit UNE fiche** ci-dessous, écrit son prénom dans le tableau du §2, la fait avec son IA (Claude, Gemini…),
> puis ouvre une PR. Si vous finissez avant 11h30, prenez-en une autre.

---

## 1. Ce qui marche déjà (ne pas refaire)

| Brique | Fichier(s) | Comment l'utiliser |
|---|---|---|
| Nettoyage des données | `src/crise/data/nettoyage.py` | `python -m crise.data.nettoyage` → `data/clean/*.parquet` |
| Chargement d'une crise | `src/crise/models.py` | `charger_scenario(27)` → `(sites, equipes, incidents)` |
| Temps de trajet | `src/crise/trajet.py` | `faire_trajet_min(cfg, zones=[ZONE_MONTAGNE])` |
| **Simulateur** (amplitude 12h, repos 11h, indispos, décisions forcées/interdites, Monte Carlo) | `src/crise/simulateur.py` | `simuler_crise(27, PlusDeClients())` → `SimResult` |
| Stratégies | `policies/baselines.py` (R1, R2), `policies/wspt_hongrois.py` (WSPT de P2), `policies/wspt_express.py` (secours) | `PlusProcheFCFS()`, `PlusDeClients()`, `WSPTHongroisPolicy()` |
| Explications de chaque décision | `src/crise/explication.py` | calculées automatiquement dans `res.decisions["explication"]` (JSON) |
| Textes copilote sans LLM | `src/crise/copilote/templates.py` | `fiche_arbitrage(...)`, `point_situation(...)` |
| Copilote LLM local | `src/crise/copilote/llm.py` (P5) | voir le fichier |
| KPI | `src/crise/kpi.py` | `calculer_kpi(res)` → dict |
| Banc d'essai | `src/crise/benchmark.py` | `python -m crise.benchmark` → `outputs/benchmark_resume.csv` |
| État à l'instant t (carte animée) | `src/crise/instant.py` | `incidents_a(res, t)`, `equipes_a(res, t)` |
| **Démo** | `app/pages/1_Salle_de_crise_express.py` | `streamlit run app/Accueil.py` → « Salle de crise express » |

**Chiffres actuels (100 crises, 63 équipes, WSPT de P2) :**
- −11,3 % de clients·heures vs R1 (premier arrivé + plus proche), +0,5 % vs R2 (plus de clients d'abord).
- Attente moyenne d'un client sensible **5,6h → 2,3h** ; attente max 17,6h → 11,8h.
- 21 % des clients rétablis en < 4h (14 % pour R1). **0 dépassement d'amplitude.**
- Démo conseillée : **CRISE_024** (WSPT −4,9 % vs R2).

---

## 2. Qui prend quoi (écrire son prénom)

| Fiche | Priorité | Durée | Qui |
|---|---|---|---|
| **A** — Diapositives du pitch | 🔴 obligatoire | 60 min | |
| **B** — README final | 🔴 obligatoire | 40 min | |
| **C** — Script de démo + vidéo de secours | 🔴 obligatoire | 30 min | ATAE |
| **D** — Stress tests S1–S5 + 2e vague (robustesse, critère du jury) | 🔴 obligatoire | 50 min | |
| **E** — Réglage α / β sur les crises d'apprentissage | 🟠 fort impact | 30 min | |
| **F** — Carte de risque + prépositionnement p-médiane | 🟡 bonus | 60 min | |
| **G** — Pages annexes Streamlit (Benchmark, Préparation, Stress) | 🟡 bonus | 40 min | |
| **H** — Copilote LLM dans la démo | 🟡 bonus | 30 min | |
| **I** — Anticipation + réserve dans WSPT | 🟡 bonus | 45 min | |
| **J** — Page d'accueil + finitions de l'interface | 🟡 bonus | 20 min | |

Dépendances : **G** utilise les sorties de **D**, **E** et **F** (mais peut démarrer avec des fichiers vides).

---

## 3. Règles git (les mêmes pour tous)

```powershell
git switch main; git pull
git switch -c tache/D-stress          # une branche par fiche : tache/<lettre>-<mot>
# … travailler …
ruff check . --fix
pytest -q                              # tout doit passer
git add -A; git commit -m "D — stress tests S1-S5"
git push -u origin tache/D-stress
```
Puis ouvrir la PR : `https://github.com/corinne3/enedis-crise-copilote/compare/main...tache/D-stress` → **Create pull request** → attendre la coche verte → **Merge**.

- **Ne modifier que les fichiers listés dans votre fiche.** Si vous devez toucher un autre fichier, prévenez l'équipe.
- Ne jamais pousser directement sur `main`. Ne jamais commiter `data/raw/` ni `data/clean/`.
- Les données : copier les 4 CSV dans `data/raw/` puis `python -m crise.data.nettoyage` (une fois).

---

## 4. Comment travailler avec votre IA

1. Copiez-lui le **BRIEFING IA** (§5) puis **votre fiche** (§6).
2. Donnez-lui le **contenu** des fichiers cités dans « À lire » (elle ne voit pas le dépôt) :
   ```powershell
   Get-Content src\crise\simulateur.py | Set-Clipboard     # puis coller dans le chat
   ```
3. Demandez-lui **le fichier complet** à remplacer (pas des morceaux), et **un test pytest**.
4. Collez le code, lancez `pytest -q` et `ruff check .`, renvoyez-lui les erreurs telles quelles.

---

## 5. BRIEFING IA (à copier tel quel en tête de conversation)

```text
Tu m'aides sur un dépôt Python 3.11 de hackathon : « copilote de crise Enedis ».
But : affecter 63 équipes de dépannage à des incidents électriques pendant une crise climatique
(100 crises simulées, 50 à 250 incidents chacune, Ariège / Haute-Garonne / Gers) pour minimiser
Σ clients × heures de coupure, en respectant la sécurité, avec des décisions explicables.
L'outil recommande, le responsable décide.

Contraintes techniques :
- 100 % open source, gratuit, CPU seulement (pas de GPU, pas d'API payante).
- Bibliothèques disponibles : pandas, numpy, scipy, ortools, scikit-learn, joblib, streamlit, plotly, pydeck, pyyaml, pytest.
- Code dans src/crise/ (paquet « crise »), tests dans tests/ (pytest), style ruff (lignes ≤ 120).
- Temps en MINUTES depuis le début de la crise (entiers). Coordonnées WGS84. Distances en km.
- Ne change PAS les signatures existantes ; ajoute des paramètres optionnels si besoin.
- Donne-moi des fichiers complets, prêts à coller, et au moins un test pytest.

API existante (à réutiliser, ne pas réécrire) :
- crise.config : charger_config() -> dict (config/default.yaml) ; chemin_projet(*parties) -> Path
- crise.models :
    dataclasses Site(id_site, commune, lat, lon, nb_equipes), Equipe(id_equipe, id_site, lat, lon, etat,
    t_debut_service, t_libre, id_incident), Incident(id_incident, id_poste, t_apparition, duree_nominale,
    duree_reelle, cause, nb_clients, sensible, lat, lon, etat, id_equipe, t_affectation, t_arrivee, t_resolution),
    Affectation(id_equipe, id_incident, explication: dict), EtatSimulation(t, equipes_disponibles,
    incidents_en_attente, toutes_equipes, params), SimResult(incidents, activites, decisions, serie, metadata)
    charger_scenario(numero_crise, params=None) -> (sites, equipes, incidents)
        params possibles : {"positions_initiales": {id_equipe: (lat, lon)}, "nb_equipes_max": int}
    lister_crises() -> ["CRISE_001", …, "CRISE_100"]
- crise.trajet : faire_trajet_min(cfg, multiplicateur_zone=1.0, zones=()) -> fonction (lat1, lon1, lat2, lon2) -> minutes
    ZoneRalentie(lat_min, lat_max, lon_min, lon_max, facteur=3.0, nom="") ; ZONE_MONTAGNE (lat < 43,05, ×3)
- crise.policies.base.Policy : classe avec nom: str et decide(etat: EtatSimulation, trajet_min) -> list[Affectation]
- crise.policies.baselines : PlusProcheFCFS (R1), PlusDeClients (R2)
- crise.policies.wspt_hongrois : WSPTHongroisPolicy (stratégie principale)
- crise.simulateur :
    parametres_simulation(cfg=None, **surcharges) -> dict   (ex. alpha_sensible=5.0, beta_attente_par_h=0.1,
        monte_carlo={"actif": True}, seed=3, expliquer=False)
    amplitude_restante(equipe, t, params) ; est_faisable(equipe, incident, trajet, t, params) -> bool
    Indisponibilite(id_equipe, t_debut, t_fin=None)   # l'équipe finit son chantier puis passe hors service
    simuler(sites, equipes, incidents, policy, params=None, trajet_min=None,
            indisponibilites=[], forcees={id_eq: id_inc}, interdites={(id_eq, id_inc)}, meta={}) -> SimResult
    simuler_crise(numero_crise, policy, params=None, scenario=None, trajet_min=None, **mêmes options) -> SimResult
- SimResult :
    incidents : id_incident, id_poste, lat, lon, nb_clients, sensible, commune, departement, t_apparition,
                t_affectation, t_arrivee, t_resolution, id_equipe, duree_reelle, duree_nominale, cause
    activites : id_equipe, type (trajet/chantier/retour/repos/hors_service), t_debut, t_fin, id_incident,
                lat_dep, lon_dep, lat_arr, lon_arr
    decisions : t, id_equipe, id_incident, explication (chaîne JSON)
    serie (toutes les 30 min) : t, clients_coupes, incidents_attente, equipes_occupees, equipes_repos,
                equipes_hs, equipes_disponibles
    metadata : crise, strategie, clients_heures, t_fin_min, non_resolus, rejets, params, …
- crise.kpi : calculer_kpi(res) -> dict (clients_heures, pct_clients_retablis_2h/4h/8h, attente_moy_h,
    attente_max_sensible_h, attente_moy_sensible_h, gini_communes, saturation_pct, fin_crise_h,
    depassements_amplitude, …) ; separer_apprentissage_test(crises) -> (80 premières, 20 dernières)
- crise.benchmark : lancer(crises: list[int], strategies: dict[str, type[Policy]], params=None, seeds=None,
    scenario=None, options=None, n_jobs=-1) -> (kpi_df, series_df) ; resumer(kpi_df) ; sauvegarder(...)
    CLI : python -m crise.benchmark --crises 1-100 --strategies R1,R2,WSPT --monte-carlo 5 --jobs 2
```

---

## 6. Les fiches

### Fiche A — Diapositives du pitch (5 min) 🔴

- **Livrable** : `docs/pitch.pptx` (ou Google Slides partagé), 7 diapositives. Possible sans IA de code.
- **Structure** (plan §11) :
  1. **Le problème** : 250 incidents en 8h, 63 équipes, ≈ 20h de travail par équipe ; on ne peut pas tout faire tout de suite. Qui passe en premier ?
  2. **Ce qu'on a vu dans les données** : objectif écrit « maximiser » au lieu de minimiser ; 43 postes touchés 2 fois ; durées indépendantes de la cause ; saturation 49 % du temps.
  3. **Notre approche** : simulateur à événements → stratégie WSPT (règle de Smith, optimale pour 1 équipe) + algorithme hongrois (affectation globale) → explication de chaque décision. Sécurité : amplitude 12h / repos 11h jamais dépassés.
  4. **Démo** (capture ou en direct, fiche C).
  5. **Résultats** (chiffres du §1, boxplot de la page express) : −11,3 % vs R1 ; clients sensibles secourus 2,5× plus vite ; 0 dépassement. Honnêteté : +0,5 % seulement vs R2 en volume — la valeur, c'est la priorité aux sensibles à efficacité égale.
  6. **Confiance** : l'humain refuse / force, l'outil chiffre le coût ; LLM local qui ne fait que reformuler ; 100 % open source et CPU.
  7. **Limites et suite** : trajets à vol d'oiseau, pas de topologie réseau, compétences non modélisées → routage OSM, groupes électrogènes, prévision météo.
- **Fin quand** : répété une fois à voix haute en < 5 min.

### Fiche B — README final 🔴

- **Fichier** : `README.md` uniquement.
- **À lire** : `README.md` actuel, `docs/PLAN_EQUIPE_DEFI_ENEDIS.md` (§2, §5, §9, §10), `outputs/benchmark_resume.csv` (après `python -m crise.benchmark`).
- **Sections** : 1) Le défi en 3 lignes. 2) Installation (Windows + macOS/Linux, sans venv possible). 3) Lancer : nettoyage → banc d'essai → démo. 4) Architecture (copier le schéma mermaid du plan §3 et le tableau du §1 ci-dessus). 5) Méthode : simulateur, R1/R2, WSPT + hongrois, explicabilité, contraintes de sécurité. 6) **Résultats** (tableau R1/R2/WSPT depuis `benchmark_resume.csv`). 7) **Hypothèses H1–H12** (copier le tableau du plan §9). 8) Limites. 9) Garde-fous éthiques (l'humain décide, pas de données personnelles, LLM encadré). 10) Équipe.
- Inclut aussi les sections « Simulateur » (T1.9) et « Moteur » (T2.8) du plan.
- **Fin quand** : un inconnu peut lancer la démo en suivant le README.

### Fiche C — Script de démo + vidéo de secours 🔴

- **Livrables** : `docs/script_demo.md` + une vidéo `demo.mp4` (≤ 2 min, ne pas commiter si > 50 Mo : la mettre sur un drive).
- **Scénario** (à adapter) : page « Salle de crise express » → CRISE_024 → indicateurs R1/R2/WSPT → courbe des clients coupés → carte : curseur à H+6 (rouge = attente) puis H+20 → section « Décisions expliquées » → filtre « à discuter » → **Refuser** → impact chiffré → stress « Routes coupées » → nouveaux indicateurs.
- **Outil** : OBS Studio (gratuit) → *Sources* → *Capture de fenêtre* (navigateur) → *Démarrer l'enregistrement*.
- **Fin quand** : la vidéo se lit et dure moins de 2 min.

### Fiche D — Stress tests S1–S5 + 2e vague (T1.8, T3.6, T3.7) 🔴

- **Fichiers** : `src/crise/scenarios.py` (actuellement vide), `tests/test_scenarios.py` (nouveau). Optionnel : ajouter `--stress` à `src/crise/benchmark.py` **sans changer le reste**.
- **À lire** : `src/crise/simulateur.py`, `src/crise/models.py`, `src/crise/trajet.py`, `src/crise/benchmark.py`.
- **À faire** :
  1. `deuxieme_vague(numero_crise, decalage_min=360) -> (sites, equipes, incidents)` : incidents de la crise *n* + ceux de la crise *n+1* (crise 1 si *n* = 100) avec `t_apparition += decalage_min` et `id_incident` préfixé `V2_` (unicité).
  2. `construire(nom, numero_crise, cfg=None) -> dict` avec clés `sites, equipes, incidents, trajet_min, options` pour :
     - **S1** routes coupées en montagne : `trajet_min = faire_trajet_min(cfg, zones=[ZONE_MONTAGNE])` ;
     - **S2** 30 % d'équipes hors service à H+3 : `options["indisponibilites"] = [Indisponibilite(e.id_equipe, 180) …]` (1 équipe sur 3) ;
     - **S3** 2e vague à H+6 : `deuxieme_vague(n, 360)` ;
     - **S4** 2 crises successives + 50 % d'équipes indisponibles après 48h : `deuxieme_vague(n, 1440)` + `Indisponibilite(…, 2880)` pour 1 équipe sur 2 ;
     - **S5** 20 équipes seulement : `charger_scenario(n, {"nb_equipes_max": 20})`.
  3. `simuler_scenario(nom, numero_crise, policy, params=None) -> SimResult` qui appelle `simuler(...)`.
  4. Script `python -m crise.scenarios --crises 81-100` : pour S1…S5 × {R1, R2, WSPT}, `calculer_kpi`, sauvegarde `outputs/stress_kpi.csv` + résumé imprimé (moyenne `clients_heures`, `attente_max_sensible_h`, `depassements_amplitude`, `non_resolus`).
  5. Monte Carlo (T3.7) : lancer `python -m crise.benchmark --crises 81-100 --monte-carlo 5 --suffixe _mc --jobs 2` et noter l'intervalle (5e–95e centile) de `clients_heures` par stratégie.
- **Fin quand** : `outputs/stress_kpi.csv` existe, `depassements_amplitude == 0` partout, `non_resolus == 0` partout, test pytest S1 et S5 sur 1 crise.
- **Piège** : `params["interdites"]` est ajouté par le simulateur — toujours repartir de `parametres_simulation()` neuf.

### Fiche E — Réglage α / β (T2.7) 🟠

- **Fichiers** : `src/crise/reglage.py` (nouveau), `config/default.yaml` (seulement `alpha_sensible`, `beta_attente_par_h`).
- **À lire** : `src/crise/benchmark.py`, `src/crise/simulateur.py` (`parametres_simulation`).
- **À faire** : grille α ∈ {0, 2, 5, 10}, β ∈ {0, 0,05, 0,1, 0,2} sur les **crises 1–80** (apprentissage) avec `lancer([...], {"WSPT": WSPTHongroisPolicy}, params=parametres_simulation(alpha_sensible=a, beta_attente_par_h=b, expliquer=False), n_jobs=2)`. Tableau `outputs/reglage_alpha_beta.csv` : α, β, clients_heures moyen, attente_moy_sensible_h, gini. Choisir un couple **compromis** (pas forcément le min de clients·heures), puis **vérifier sur 81–100** (test). Écrire 3 lignes de justification dans le CSV ou le README.
- **Temps** : 16 couples × 80 crises ≈ 10 min de calcul ; commencer avec 20 crises si pressé.
- **Fin quand** : CSV produit + valeurs choisies dans la config + chiffres test 81–100.

### Fiche F — Carte de risque + prépositionnement p-médiane (T3.3, T3.4) 🟢 Terminé

- **Fichiers** : `src/crise/prepositionnement.py`, `tests/test_prepositionnement.py`.
- **Réalisé** :
  1. `carte_risque` (K-Means pondéré 200 zones sur crises 1–80, poids $N \times (1 + 5 \cdot s)$) + export Folium HeatMap (`outputs/carte_chaleur.html`, `outputs/carte_risque.csv`).
  2. MILP p-médiane capacitaire sous OR-Tools SCIP (38 candidats, capacité $\sum w / 63 \times 1.2$, $n_k \le 8$, $\sum n_k = 63$) + affectation optimale bipartite (`linear_sum_assignment`) des 63 équipes par proximité de site d'origine (`outputs/positions_pmediane.csv`).
  3. Référence K-Means à 63 centres.
  4. Banc d'essai sur crises de test 81–100 : gain moyen de +1,62 % de clients·heures vs sites (14 crises gagnées sur 20), sauvegardé dans `outputs/prepositionnement.csv` et `outputs/prepositionnement_resume.csv`.


### Fiche G — Pages annexes Streamlit (T4.8) 🟢 Terminé

- **Fichiers** : `app/pages/2_Benchmark.py`, `3_Preparation.py`, `4_Stress_tests.py`, `tests/test_t4_pages.py`.
- **Réalisé** :
  - **Benchmark** : KPI clés, boxplots Plotly de dispersion du volume et de l'attente sensibles sur 100 crises, histogramme des gains par crise.
  - **Préparation** : carte Folium de l'aléa (KDE), p-médiane MILP (+1,62 % de gain, 14/20 victoires), distances de déploiement et détail des 63 équipes.
  - **Stress tests** : scénarios S1 à S5 (routes coupées, −30 % éq., 2e vague, crises cumulées 48h, 20 équipes), barres comparatives, garantie 100 % de sécurité (0 dépassement d'amplitude).

### Fiche H — Copilote LLM dans la démo (T5.4) 🟡

- **Fichiers** : `app/pages/1_Salle_de_crise_express.py` (section « Décisions expliquées » seulement), éventuellement `src/crise/copilote/llm.py`.
- **À lire** : `src/crise/copilote/llm.py`, `src/crise/copilote/templates.py`, la section « Décisions expliquées » de la page.
- **À faire** : sous l'encadré bleu (texte modèle), un bouton « 🤖 Reformuler avec le copilote IA » qui envoie le JSON `e` à la fonction de `llm.py` (Ollama, `qwen2.5:3b`), affiche le résultat, et **retombe sur le texte modèle** si Ollama ne répond pas ou si le garde-fou anti-chiffres rejette le texte. Pré-générer et mettre en cache les textes de CRISE_024 (T5.4).
- **Fin quand** : le bouton marche avec Ollama lancé ET sans Ollama (pas d'erreur, texte modèle affiché).

### Fiche I — Anticipation + réserve dans WSPT (T2.6) 🟡

- **Fichiers** : `src/crise/policies/wspt_hongrois.py` (propriétaire : P2 — c'est sa fiche en priorité), tests associés.
- **À lire** : ce fichier, `src/crise/simulateur.py` (`amplitude_restante`, `est_faisable`), plan §5.3.
- **À faire** : options activables par `params["anticipation_min"]` et `params["reserve_active"]` (déjà dans la config) : 1) ne pas envoyer une équipe lointaine si une équipe plus proche se libère dans < 30 min (`Equipe.t_libre`, `toutes_equipes`) ; 2) garder 1 équipe en réserve dans un rayon de 40 km si l'incident proposé dure 8h, n'est pas sensible, et qu'il reste des postes sensibles en attente dans la zone. Mesurer avec `lancer(range(1, 21), …)` avec et sans.
- **Fin quand** : gain mesuré (ou absence de gain documentée) ; options désactivées par défaut si pas de gain.

### Fiche J — Page d'accueil + finitions (T4.1, T4.9) 🟢 Terminé

- **Fichiers** : `app/Accueil.py`.
- **Réalisé** : Chargement dynamique instantané (< 1s) des métriques clés depuis `benchmark_resume.csv` via `@st.cache_data`, cartes de navigation interactive vers les 4 espaces, simulation factice instantanée.

---

## 7. À 11h30 (gel)

1. Toutes les PR vertes sont fusionnées ; les autres attendent (on ne fusionne plus rien après 11h45).
2. `git switch main; git pull; pytest -q; python -m crise.benchmark --jobs 2; streamlit run app/Accueil.py`.
3. Mettre à jour les chiffres du pitch (fiche A) si E ou D les ont changés.
