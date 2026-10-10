# Foraine — version retenue comme base (10 octobre 2026, 05h40)

Application interne pour l'équipe technique d'In'li Sud-Ouest : voir venir les
pannes bloquantes et décider quoi réparer d'abord. La carte occupe tout l'écran ;
la file des priorités, les fiches et l'énergie se posent par-dessus. C'est la
version servie sur le port 9015 du serveur de l'équipe, choisie par Alexis comme
base de la version finale (à simplifier). Agent d'origine : `k-plein-cadre`,
enregistrement 7b0ba7c.

Prototype non officiel, données fictives du kit BâtIA.

## Lancer

Il faut Node 20 ou plus. Aucune dépendance à installer, aucun compte, aucune clé.

1. La première fois seulement, fabriquer le fond de carte (environ 140 Mo
   téléchargés ; il n'est pas dans git) :

   ```bash
   poc/foraine/carte/outils/extraire-fond.sh
   ```

2. Lancer :

   ```bash
   cd poc/foraine && node serveur.mjs
   ```

   Puis ouvrir http://localhost:4720 (`PORT=4721 node serveur.mjs` pour changer
   de port, `--reseau` pour l'ouvrir depuis un téléphone).

`donnees` est un lien symbolique vers le dossier `donnees/` du dépôt (le kit).
`regles-de-session.md` est l'ancien `CLAUDE.md` de l'agent qui l'a construite,
renommé pour ne pas s'appliquer aux sessions Claude Code de l'équipe.

## Documents

- `PROMPT.md` : la consigne donnée à l'agent.
- `UX.md` : sa théorie de l'usage.
- `RESULTAT.md` : ce qui marche, ce qui manque, méthode de risque.
