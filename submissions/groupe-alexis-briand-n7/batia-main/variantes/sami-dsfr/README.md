# BâtIA, variante présentée au jury

Application de pilotage des pannes et des rénovations pour In'li Sud-Ouest, sur les données fictives du kit du hackathon. Un serveur Node sans dépendance, une carte MapLibre avec un fond Protomaps local, un moteur de score en Python déjà calculé dans `livrables/`.

## Lancer

Il faut Node 20 ou plus. Le fond de carte, 134 Mo, se télécharge une fois au premier lancement.

    ./lancer.sh

Le site s'ouvre sur http://localhost:4860. `PORT=4871 ./lancer.sh` pour un autre port, `./lancer.sh --reseau` pour l'ouvrir au téléphone.

Pour se mettre à jour et relancer en une commande, `./derniere-version.sh`. Sur Mac, double-cliquer `voir-batia.command`, détails dans `LANCER-MAC.md`. Pour mettre le site en ligne, `DEPLOIEMENT.md`.

## Ce que montre l'application

- **Connexion.** Une page d'entrée avec identifiant, mot de passe et rôle, gestionnaire de proximité ou direction. En local rien n'est vérifié. En ligne, un mot de passe serveur protège les données du kit.
- **Carte d'abord.** Les résidences sont des points colorés par la pire catégorie présente. La barre blanche porte la recherche et le menu à trois points. Les lentilles Pannes, Énergie et Rénovations ouvrent la file.
- **Pannes.** Chaque équipement à visiter est une carte : catégorie, score du moteur, type et lieu, une phrase tirée des faits, dernier dépannage. Un sélecteur de résidence en tête dit ce qui est affiché. La fiche détaille les points de chaque raison, le taux de pannes observé l'an dernier dans la bande, et propose Visite, Remplacer ou Plus tard, puis le retour terrain après la visite.
- **Compte.** Le rond en haut à droite donne le rôle, les dix actions de la semaine avec raison et coût, la page Direction, les animations réduites et la déconnexion.
- **Direction.** `direction.html` compare, pour la résidence A, le remplacement groupé des 160 chaudières et le cas par cas, trouve le seuil de bascule et recommande une année dans l'enveloppe de 1,5 M€. Calculé par `outils/direction.py` sur le kit seul.
- **Données.** Import d'un classeur Excel ou d'un CSV par dépôt. Chaque feuille est reconnue à ses colonnes, fusionnée par identifiant dans l'une des 13 tables du kit, puis les faits et les scores sont recalculés. Les exports CSV sont dans le menu.
- **Données réelles et Sous le capot.** La bascule en haut à droite passe au parc réel sur données publiques, et la page Sous le capot décrit un immeuble à partir d'une adresse avec les sources de l'État.

## Organisation des fichiers

| Dossier | Contenu |
|---|---|
| `app/` | la page, le script, les feuilles de style, la connexion, la page Direction |
| `carte/` | la carte, son style gris, les polices et le fond de carte téléchargé dans `carte/fond/` |
| `risque/` | lecture des tables du kit, fusion des imports, faits par équipement |
| `moteur/` et `livrables/` | le barème Python du défi 1 et ses sorties, lues par le serveur, jamais recalculées sans import |
| `outils/` | scripts Python : conversion d'un classeur, rescore après import, analyse de la résidence A |
| `reel/`, `rejeu/`, `capot/` | données réelles, rejeu de 2025, Sous le capot |
| `donnees/` | le kit du hackathon, treize tables CSV |
| `imports/`, `etat/` | ce que l'application écrit, hors git |

`LOOK.md` retrace chaque passe de design et liste les fichiers à reporter dans une autre version. `UX.md` et `RESULTAT.md` viennent de la version d'origine.

## Règles tenues

Le kit ne sort pas du hackathon. Aucun composant, police ni bloc de marque de l'État n'est utilisé. L'en-tête garde la mention « prototype non officiel ».
