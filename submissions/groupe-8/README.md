# EnedisPO — copilote de dispatch en crise climatique

Défi Enedis, La Mêlée 2026. Pendant une tempête, le système dit au responsable de crise **quelle équipe envoyer sur
quelle panne, et dans quel ordre**, pour rétablir le plus de clients le plus vite possible.
**Le moteur d'optimisation décide, l'IA explique et traduit, le responsable valide.**

## La solution

| Brique | Rôle |
|---|---|
| **Moteur d'optimisation (RSLS)** | Minimise Σ clients × heures sans électricité (l'indicateur du défi). Règle de Smith (clients rétablis par heure de travail) + recherche locale, re-planifié à chaque événement (< 3 s). Respecte les horaires (12 h de travail / 12 h de repos), aucune interruption de dépannage, aucune anticipation. |
| **Horaires des équipes** | Fixés une fois au début : groupes A, B (+2 h) et C, la relève (+12 h), optimisés sur 50 crises passées ; au moins 20 % des équipes en service à tout instant. |
| **Objectif 90 % en 48 h** | Contrôlé, pas optimisé. S'il est manqué, alerte et calcul des renforts nécessaires (combien d'équipes, sur quels sites). |
| **IA (Mistral, repli OpenRouter)** | Explique le plan en français (chiffres vérifiés contre ceux du moteur) et traduit un refus du responsable en règle (zone inaccessible, équipe indisponible…), chiffrée avant application. Ne décide jamais. |
| **Boucle d'apprentissage** | Chaque refus est enregistré ; quand des remarques se répètent, l'IA propose d'ajuster une variable du calcul (ex. temps de trajet vers une zone), mesurée sur 10 crises passées, adoptée ou non par une personne. |
| **Tableau de bord** | Carte des pannes et des équipes, plan proposé (tracés routiers réels), validation du plan entier, refus motivé, journal, copilote, alerte 48 h. |

Résultats sur les 100 crises fournies : −16 % à −28 % de clients × heures par rapport aux règles classiques
(premier arrivé, équipe la plus proche, plus de clients d'abord), meilleur sur 100 crises sur 100 ; plan de 3 s à 2,3 %
d'OR-Tools (60 s). Modèle mathématique : [docs/modele_mathematique.pdf](docs/modele_mathematique.pdf).

## Structure

```
backend/    moteur, API, IA, apprentissage (Python)
  src/dispatch/   engine/ (optimisation)  api/ (FastAPI)  copilot/ (IA)  learning/  live/  data/  sim/
  config/         default.yaml (objectif, horaires, trajets, IA), registre des ajustements
  data/           raw/ (données Enedis)  scenarios/ (scénario de démonstration CRISE_DEMO)
  bench/          benchmarks, optimisation des horaires, génération du scénario de démo
  simulator/      simulateur de terrain (envoie alertes et retours d'intervention au backend)
  tests/
frontend/   tableau de bord (React, TypeScript, Vite, MapLibre, deck.gl)
docs/       modèle mathématique, architecture, contexte du pitch, journal de développement
```

## Lancer la démo

```bash
# 1. backend (Python 3.12) : clés dans backend/.env (MISTRAL_API_KEY, OPENROUTER_API_KEY), voir backend/.env.example
cd backend
pip install -e .
python -m uvicorn dispatch.api.app:app --app-dir src --port 8000

# 2. tableau de bord
cd frontend
npm install
VITE_DATA_SOURCE=api VITE_API_URL=http://localhost:8000 npm run dev -- --port 5173
```

Ouvrir http://localhost:5173 : le scénario de démonstration (une tempête qui s'intensifie, CRISE_DEMO) se charge par
défaut ; `?crise=CRISE_027` rejoue une crise historique. Au premier lancement, le backend précalcule la crise (~15 s) et
met en cache les tracés routiers (~2 min, une seule fois).

Tests : `cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`.
