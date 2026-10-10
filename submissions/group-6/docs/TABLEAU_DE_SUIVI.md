# Tableau de Suivi — Défi Enedis (Hackathon IA for Impact 2026)

Tableau de suivi des lots et des tâches établi pour la coordination de l'équipe (5 personnes × 5h).

## Tableau d'avancement des Lots

| Lot | Responsable | Statut | Prochaine échéance |
|---|---|---|---|
| **Lot 1 — Données & simulateur** | P1 | En cours | H+2:00 (simulateur minimal & nettoyage) |
| **Lot 2 — Optimisation & explicabilité** | P2 | En cours | H+2:00 (WSPT sur jeu factice) |
| **Lot 3 — Évaluation, robustesse, prépositionnement** | P3 | En attente | H+3:30 (banc d'essai 100 crises) |
| **Lot 4 — Interface Streamlit** | P4 | **T4.1–T4.3 complétées** | H+2:00 (carte animée & KPI sur factice) |
| **Lot 5 — Copilote IA & Coordination** | P5 | **T5.1 complétée** | H+1:30 (T5.2 LLM & T5.3 templates) |

---

## Détail des Tâches par Lot

### LOT 1 — Données & simulateur (P1) · *Chemin critique*
- [x] **T1.1** : Squelette du dépôt, arborescence, config, requirements, CI
- [ ] **T1.2** : `nettoyage.py` : lecture des 3 fichiers, corrections P1 à P7, jointure coupures ↔ postes, export parquet
- [ ] **T1.3** : `models.py` : contrats d'interface §4 + `charger_scenario`
- [x] **T1.4** : `trajet.py` : calcul haversine, détour 1.3, vitesses plaine/montagne
- [ ] **T1.5** : `simulateur.py` : file d'événements, boucle T1→T5, SimResult
- [ ] **T1.6** : `baselines.py` : R1 (FCFS + plus proche) et R2 (plus de clients d'abord)
- [ ] **T1.7** : Contraintes de travail : amplitude 12h, retour base, repos 11h, indisponibilité
- [ ] **T1.8** : Paramètres dynamiques : forçage, refus humain, prépositionnement, 2e vague
- [ ] **T1.9** : Appui intégration + tests pytest + section Simulateur du README

### LOT 2 — Moteur d'optimisation & explicabilité (P2)
- [x] **T2.1** : Jeu factice 3 équipes / 6 incidents (§4)
- [x] **T2.2** : `wspt_hongrois.py` : score WSPT vectorisé et algorithme hongrois
- [x] **T2.3** : Faisabilité et respect amplitude restante
- [ ] **T2.4** : Branchement réel simulateur sur CRISE_001
- [ ] **T2.5** : `explication.py` : facteurs, contributions %, contrefactuel, confiance, export JSON
- [ ] **T2.6** : v2 : anticipation 30 min + réserve anti-piège 8h
- [ ] **T2.7** : Réglage hyperparamètres α et β sur crises d'apprentissage
- [ ] **T2.8** : Section « Moteur & explicabilité » du README

### LOT 3 — Évaluation, robustesse, prépositionnement (P3)
- [x] **T3.1** : `kpi.py` : Σ N·T, % rétablis à 2h/4h/8h, attente max sensibles, Gini territorial
- [x] **T3.2** : Split apprentissage / test (1-80 / 81-100) + fonction courbe clients coupés
- [x] **T3.3** : Carte de risque : KDE pondérée sur crises apprentissage
- [x] **T3.4** : `prepositionnement.py` : K-Means 200 zones + MILP p-médiane capacitaire
- [x] **T3.5** : `benchmark.py` : banc d'essai parallélisé joblib 100 crises
- [x] **T3.6** : `scenarios.py` (stress tests) : S1 à S5
- [x] **T3.7** : Lancement banc d'essai complet + extraction graphiques et KPI clés

### LOT 4 — Interface Streamlit « Salle de crise » (P4)
- [x] **T4.1** : Squelette multi-pages, mise en page et générateur SimResult factice
- [x] **T4.2** : Carte Folium animée avec curseur temporel (pas de 30 min)
- [x] **T4.3** : Bandeau métriques KPI (`st.metric`)
- [ ] **T4.4** : Courbe des clients coupés dans le temps (R1 vs R2 vs WSPT)
- [ ] **T4.5** : Diagramme de Gantt des équipes
- [ ] **T4.6** : Tableau des décisions à t et panneau explicatif
- [ ] **T4.7** : Contrôles interactifs, stress tests, refus et forçage humain
- [x] **T4.8** : Pages Benchmark, Préparation, Stress tests
- [x] **T4.9** : Branchement données réelles et fluidification démo

### LOT 5 — Copilote IA, documentation, pitch (P5) · *Coordination*
- [x] **T5.1** : Lancement Ollama, connexion dépôt GitHub, initialisation tableau de suivi des tâches
- [x] **T5.2** : `copilote/llm.py` : prompt système strict, reformulateur JSON, garde-fou anti-hallucination regex, cache (Validé)
- [ ] **T5.3** : `copilote/templates.py` : f-strings de secours pour fiche décision & point préfecture
- [ ] **T5.4** : Pré-génération des fiches copilote pour la crise de démo
- [ ] **T5.5** : Rédaction complète du `README.md`
- [ ] **T5.6** : Conception des diapositives du pitch (5 min)
- [ ] **T5.7** : Script de démo scénarisé (2 min) et vidéo de secours
- [ ] **T5.8** : Animation des points de synchronisation (H+0:15, H+2:00, H+3:30, H+4:15, H+4:30)

---

## Jalons et Points de Synchronisation
- **H+0:15** : Tout le monde a l'environnement opérationnel ; contrats §4 lus ; Ollama prêt / modèles tirés.
- **H+2:00** : P1 livre `nettoyage` + simulateur minimal ; P2 valide WSPT sur factice ; P4 anime la carte.
- **H+3:30** : WSPT tourne sur 100 crises ; P4 affiche un vrai `SimResult` ; P3 lance le banc d'essai complet.
- **H+4:15** : **Gel des fonctionnalités**. Répétition générale du pitch et enregistrement vidéo de secours.
- **H+4:30 - H+5:00** : Répétition finale chronométrée.
