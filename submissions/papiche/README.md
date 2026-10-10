# Veille réglementaire PPP — agent IA « maison »

## Équipe

- Nom de l'équipe : papiche
- Membres (pseudo GitHub) : papiche
- Défi choisi : `lallemand`

## Le projet

Transformer des bases d'homologation nationales hétérogènes (e-Phy FR, PMRA CA, EPA US) en un référentiel structuré, traçable et interrogeable.
Un modèle de langage local **propose**, du code **décide** : aucune valeur n'est publiée sans preuve retrouvée mot à mot dans la source,
et les codes EPPO ne sont publiés que s'ils sont confirmés par la table (chaque code renvoie à sa fiche sur [gd.eppo.int](https://gd.eppo.int/)).
Impact visé : comparer produit × pays × usage sans ressaisie, avec une valeur d'origine toujours conservée.

## Fonctionnalités principales

- Extraction avec sortie structurée validée, boucle de correction, contrôle de preuve, second avis IA, arbitrage humain après 3 échecs
- Normalisation EPPO (liste fermée, appariement tolérant aux accents, pluriels et noms scientifiques)
- Recherche sémantique (Qdrant) et questions-réponses citées
- API REST / OpenAPI et export Microsoft 365 (Dataverse)
- Collecte sobre des sources officielles (requêtes conditionnelles, journal de chaque requête)

## Technologies utilisées

- Python, Pydantic, FastAPI, Qdrant, Ollama (modèle local), IPFS
- Protocoles, principes d'IA et mathématiques appliqués, avec vulgarisation : [docs/REFERENCES_ET_VULGARISATION.md](docs/REFERENCES_ET_VULGARISATION.md)

## Lancer le projet

Voir `index.html` (récit du projet) et `requirements.txt` ; `./run_all.sh` enchaîne la chaîne complète (Ollama local requis).
Les données brutes et la vidéo ne sont pas dans ce dossier (poids) : elles sont dans la version IPFS ci-dessous.

## Démo / Slides

- Démo (IPFS, site complet avec vidéo) : https://ipfs.copylaradio.com/ipfs/QmcTBDcsqudotqgHQADNdqVZNdeVUHEbVV6t5W4PmTeGdE/index.html
- Présentation : page `index.html` ci-dessus (format PechaKucha, vidéo incluse)
