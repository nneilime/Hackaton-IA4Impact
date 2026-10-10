# Collecte des FAQ publiques des banques

Livrable principal : [aides-banques.md](aides-banques.md).

Version compacte : [questions-compactees.md](questions-compactees.md), avec les 921 questions réunies en 458 groupes, dont 445 communs et 13 spécifiques à une banque. Chaque question conserve son lien ; les réponses identiques, adaptées ou différentes sont distinguées.

- Caisse d’Épargne : 505 endpoints HTML, dont 459 questions.
- Banque Populaire : 508 endpoints HTML, dont 462 questions.
- Chaque FAQ : 9 catégories et 36 sous-catégories.
- 69 fiches avec un lien vidéo par banque.
- Aucun échec HTTP, lien interne non visité, réponse vide ou alias canonique observé.

Le périmètre correspond aux deux FAQ nationales particuliers indiquées par l’utilisateur. Le document contient l’inventaire, de courts extraits, des repères factuels détectés automatiquement et les liens des sources. Il ne reproduit pas intégralement les réponses et ne résume pas toutes leurs conditions. Les montants, durées et coordonnées extraits doivent être lus dans leur contexte source.

## Fichiers

- `aides-banques.md` : document organisé par banque, catégorie et sous-catégorie.
- `manifest.json` : métadonnées de collecte, relations entre endpoints, extraits bornés et ressources.
- `rapport-controle.json` : mesures de couverture et anomalies automatiques.
- `controle-agent.md` : compte rendu de l’agent de contrôle indépendant.
- `collecter.py` : collecteur reproductible, utilisant uniquement la bibliothèque standard Python.
- `questions-compactees.md` : index fusionné des questions similaires, avec liens CE/BP.
- `fusion.json` : groupes et provenance de chaque question.
- `rapport-fusion.json` : contrôle de couverture de la fusion.
- `controle-fusion-agent.md` : validation indépendante des rapprochements et du document compact.
- `compacter.py` : regroupement depuis la collecte et les HTML du cache, sans accès réseau.

## Reproduire

```sh
python3 collecter.py
```

Le collecteur effectue uniquement des requêtes GET sur les FAQ publiques. Il utilise au plus deux requêtes simultanées et deux départs par seconde par domaine, avec trois tentatives pour les erreurs temporaires. Les réponses brutes sont conservées dans un cache temporaire local pour reprendre la collecte après interruption. Elles ne figurent pas dans les livrables.

Pour contrôler une nouvelle version des sites, utiliser un nouveau répertoire de cache :

```sh
python3 collecter.py --cache /tmp/aides-banques-nouvelle-collecte
```

Pour recalculer l’extraction à partir du cache actuel, sans accès réseau :

```sh
python3 collecter.py --reparse-cache
```

Pour régénérer uniquement le document à partir du manifeste :

```sh
python3 collecter.py --render-only
```

Le nombre de pages peut changer lors d’une nouvelle collecte. L’exhaustivité mesurée correspond au graphe des liens internes des deux FAQ HTML, sans les contenus non liés, les variantes régionales, les espaces connectés ou la transcription des vidéos.

Pour reconstruire l’index compact depuis la collecte et le cache :

```sh
python3 compacter.py
```

Les neuf regroupements de formulations proches sont définis explicitement dans ce script et ont été contrôlés sur les réponses HTML. Un même texte de réponse ne suffit pas à fusionner deux questions dont les intentions diffèrent.
