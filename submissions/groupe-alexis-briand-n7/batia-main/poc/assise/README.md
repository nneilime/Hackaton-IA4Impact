# Assise — meilleure version à ce jour (10 octobre 2026, 03h40)

Application interne pour l'équipe technique d'In'li Sud-Ouest : voir venir les
pannes bloquantes et décider quoi réparer d'abord. C'est la version 11 de la nuit
(« Assise », inspirée d'un mur de briques toulousain), jugée la meilleure par
Alexis, dans laquelle la carte Leaflet a été remplacée par la carte vectorielle de
[`../carte/`](../carte/). Sur le serveur de l'équipe, elle tourne sur le port 9011.

Prototype non officiel, données fictives du kit BâtIA.

## Lancer

Il faut Node 18 ou plus. Aucune dépendance à installer, aucun compte, aucune clé.

1. La première fois seulement, fabriquer le fond de carte (environ 140 Mo
   téléchargés, quelques minutes ; il n'est pas dans git) :

   ```bash
   poc/carte/outils/extraire-fond.sh
   ```

   Le script télécharge l'outil `pmtiles` pour Linux x86_64. Sur Mac, prendre
   l'archive `Darwin` de la même version sur
   https://github.com/protomaps/go-pmtiles/releases/tag/v1.31.2 et adapter la
   ligne `curl` du script.

2. Lancer l'application :

   ```bash
   cd poc/assise && node serveur.mjs
   ```

   Puis ouvrir http://localhost:4321. Depuis un téléphone du même réseau :
   `node serveur.mjs --reseau`, puis `http://<adresse-de-la-machine>:4321`.

Une fois le fond fabriqué, la carte ne demande plus rien à Internet.

Deux liens symboliques relient les dossiers : `donnees` vers le dossier
`donnees/` du dépôt (le kit), et `app/vendor/carte` vers `poc/carte/`. Sous
Windows, activer les liens symboliques de git ou les remplacer par des copies.

## Documents

- [`RESULTAT.md`](RESULTAT.md) : ce qui marche, ce qui manque, méthode de risque.
- [`UX.md`](UX.md) : la doctrine d'usage qui fonde chaque écran.
- [`PROMPT.md`](PROMPT.md) : la consigne qui a produit cette version ; elle est
  aussi, avec son image de référence, dans [`consignes/assise/`](../../consignes/assise/).
- [`../carte/README.md`](../carte/README.md) : la carte, son intégration, et des
  captures avant/après dans `../carte/captures/`.

## Ce qui reste à corriger

Demandé par Alexis, en cours de reprise par un agent (fin prévue à 04h49) :

- ouvrir sur le parc, avec « À décider » en second onglet ;
- retirer les phrases qui expliquent l'écran, par exemple « 41 équipements
  risquent une panne bloquante dans les neuf mois suivant le dernier relevé… » ;
- une interface moins fade, à la hauteur de la carte.

Le calcul du risque est isolé dans un module remplaçable. Le barème de Sami
(`poc/preavis/moteur/bareme.py`, 43 pannes trouvées sur 76 en 2025 en visitant
10 % du parc) pourra le remplacer.

La page Méthode dit encore que « seul le fond de carte public est chargé depuis
Internet » : ce n'est plus vrai depuis la carte vectorielle.
