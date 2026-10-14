# IA NEED IS

## Équipe
- **Nom de l'équipe :** AI-NEED-IS
- **Membres (pseudo GitHub) : tommyjarnac, Neaxyn, CedricGB, Maxime-Maguet, Ox6d
- **Défi choisi :** enedis

## Le projet
Notre solution est une plateforme interactive d'aide à la décision (Tour de contrôle) développée pour aider à la gestion de crise lors d'incidents majeurs (pannes de courant). Elle permet aux gestionnaires de planifier, suivre en temps réel et rejouer des scénarios de crise pour optimiser le déploiement des équipes sur le terrain. L'impact visé est une réduction significative des temps de coupure pour les clients et une meilleure allocation des ressources, même en situation de dégradation (trafic saturé, perte d'effectifs, crises successives).

## Fonctionnalités principales
- **Mode Préparation** : Anticipation des pannes, placement optimal des points de repli (barycentre) et préparation des équipes.
- **Mode Jour J** : Suivi dynamique de la crise avec affectation intelligente des équipes (tenant compte des temps de trajet, des priorités et des règles de repos).
- **Mode Rejeu** : Analyse a posteriori permettant de comparer l'efficacité de différentes stratégies d'affectation face à des scénarios complexes (scénario normal, perte de 50% des effectifs, crises successives).
- **KPIs et Tableaux de bord** : Suivi du nombre de clients coupés/rétablis, du statut des équipes et des temps de résolution.
- **Cartographie interactive** : Visualisation spatiale de l'état du réseau, des incidents et du positionnement des équipes.

## Technologies utilisées
- **Python** (Cœur de la logique métier et algorithmes d'allocation)
- **Streamlit** (Interface utilisateur web dynamique)
- **Pandas** (Traitement et manipulation des données de crise)

## Lancer le projet
Pour exécuter le prototype en local, suivez ces étapes depuis la racine du projet :

1. Assurez-vous d'avoir Python installé (version 3.9+ recommandée).
2. Installez les dépendances requises (si vous avez un fichier requirements.txt) :
   ```bash
   pip install -r requirements.txt
   ```
3. Lancez l'application :
   ```bash
   streamlit run app/main.py
   ```

## Démo / Slides
- 🔗 **[Accès à la présentation Google Slides](https://docs.google.com/presentation/d/1XJcq699pjpq2lvmqE8lVcfwFqLQ24a7S/edit?usp=sharing&ouid=100439694964271481023&rtpof=true&sd=true)**
