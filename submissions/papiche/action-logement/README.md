# BâtIA — hacker le bâtiment avant qu'il ne casse

## Équipe

- Nom de l'équipe : papiche
- Membres (pseudo GitHub) : papiche
- Contact : support@qo-op.com (G1FabLab)
- Défi choisi : `action-logement`

## Le projet

Prédire quels équipements d'un parc de logements (In'li Sud-Ouest) risquent une **panne bloquante** (« arrêt total ») entre le 01/01 et le 30/09/2026, pour intervenir avant la panne.
L'IA recommande, l'humain décide : le score est calculé par un modèle explicable, l'IA générative ne fait qu'expliquer et rédiger, et chaque note est relue avant diffusion.

Résultats sur 1 285 équipements (validation dans le passé, janv.-sept. 2025, données fictives du kit) :

| | Âge seul (référence) | BâtIA |
|---|---|---|
| AUC | 0,777 | **0,850** |
| Précision sur les 10 % les plus à risque | 14,8 % | **28,1 %** (taux de base 5,9 %) |
| Vraies pannes repérées en inspectant 128 équipements | 19 sur 76 (25 %) | **36 sur 76 (47 %)** |

## Fonctionnalités principales

- Score de risque par équipement (`livrables/defi1_soumission.csv`) et trois raisons lisibles par équipement (`defi1_explications.csv`)
- Aucune fuite temporelle : chaque variable n'utilise que l'historique antérieur à la date de référence
- Mesures sur les dépannages (dispersion mensuelle, récidive à 90 jours, exposant de Hurst, présenté comme un indice et non une preuve)
- Présentation Pecha Kucha (20 × 20 s) avec voix off, sous-titres, questions du jury et simulateur de coût

## Technologies utilisées

- Python, numpy, scipy, pandas : régression logistique L2 (contribution = coefficient × variable standardisée, donc explicable)
- Voix off locale (Orpheus-FastAPI) ; page web avec p5.js ; IPFS pour la publication

## Lancer le projet

```bash
python3 tools/defi1_score.py <dossier_donnees>   # le kit de données fourni par l'organisateur n'est pas redistribué ici
python3 tools/analyse_signaux.py <dossier_donnees>
```

Les sorties vont dans `livrables/`. Ouvrir `index.html` pour la présentation.

## Démo / Slides

- Démo (IPFS) : https://ipfs.copylaradio.com/ipfs/QmPucvJo8ehcBN1nGVtTxWQDzWWV37NiZG4SwGBDfzTGKr/index.html
- Présentation : la page ci-dessus (20 diapositives, voix off)
