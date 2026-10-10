# Comparatif de modèles et dimensionnement GPU / stockage

**Service d'IA mesuré** : GPU RTX 3090 (24 Go) (essaim Astroport.ONE, joint via `http://localhost:11434`). Le poste client (12th Gen Intel(R) Core(TM) i5-1235U) n'exécute pas le modèle.
Échantillon identique pour tous les modèles : 40 passages ({'ephy': 20, 'pmra': 10, 'epa': 10}).

> **Mesuré** : qualité, essais, latence, tokens/s, disque, mémoire GPU du modèle chargé.
> **Estimé** : VRAM d'autres réglages et débit d'autres cartes. Efficacité de bande passante calibrée sur la mesure : 0.71.

## 1. Qualité et vitesse (mesurées)

| Modèle | Taille | Disque | Acceptés | Vers l'expert | Dose exacte (e-Phy) | Valeurs inventées | s / passage | tokens/s |
|---|---|---|---|---|---|---|---|---|
| llama3.2:latest | 3.2B | 2.02 Go | 23/40 | 17 | 100 % | 0 | 1.43 | 246.1 |
| qwen2.5:latest | 7.6B | 4.68 Go | 37/40 | 3 | 100 % | 0 | 1.9 | 145.9 |
| gemma3:12b | 12.2B | 8.15 Go | 36/40 | 4 | 100 % | 0 | 4.18 | 82.0 |

## 2. Mémoire GPU : mesurée et estimée

| Modèle | Poids | VRAM mesurée (chargé, 1 requête) | VRAM estimée, 1 requête | VRAM estimée, 4 requêtes // |
|---|---|---|---|---|
| llama3.2:latest | 2.02 Go | 3.1 Go | 3.29 Go | 4.7 Go |
| qwen2.5:latest | 4.68 Go | 5.13 Go | 5.71 Go | 6.42 Go |
| gemma3:12b | 8.15 Go | 9.01 Go | 10.56 Go | 15.39 Go |

Cache KV = 2 × couches × têtes KV × dimension × 2 octets × 4096 jetons × requêtes parallèles (borne haute).

**Recommandation** : `qwen2.5:latest` (plus petit modèle à moins de 2 passages du meilleur (37 acceptés)). VRAM : 5.71 Go pour 1 requête, 6.42 Go pour 4 en parallèle. Plus petite carte du catalogue qui convient : RTX 4060 (8 Go).

## 3. Quelle carte ? (estimation)

| GPU | Modèle | Tient en VRAM | Débit estimé (tok/s) | Passages / heure |
|---|---|---|---|---|
| RTX 4060 (8 Go) | llama3.2:latest | oui (3.29 Go) | 96 | 1212 |
| RTX 4060 (8 Go) | qwen2.5:latest | oui (5.71 Go) | 41 | 718 |
| RTX 4060 (8 Go) | gemma3:12b | non (10.56 Go) | 24 | – |
| RTX 4060 Ti (16 Go) | llama3.2:latest | oui (3.29 Go) | 101 | 1283 |
| RTX 4060 Ti (16 Go) | qwen2.5:latest | oui (5.71 Go) | 44 | 760 |
| RTX 4060 Ti (16 Go) | gemma3:12b | oui (10.56 Go) | 25 | 461 |
| RTX 3090 (24 Go) | llama3.2:latest | oui (3.29 Go) | 329 | 4170 |
| RTX 3090 (24 Go) | qwen2.5:latest | oui (5.71 Go) | 142 | 2470 |
| RTX 3090 (24 Go) | gemma3:12b | oui (10.56 Go) | 82 | 1498 |
| RTX 4090 (24 Go) | llama3.2:latest | oui (3.29 Go) | 354 | 4491 |
| RTX 4090 (24 Go) | qwen2.5:latest | oui (5.71 Go) | 153 | 2660 |
| RTX 4090 (24 Go) | gemma3:12b | oui (10.56 Go) | 88 | 1613 |
| L40S (48 Go) | llama3.2:latest | oui (3.29 Go) | 304 | 3850 |
| L40S (48 Go) | qwen2.5:latest | oui (5.71 Go) | 131 | 2280 |
| L40S (48 Go) | gemma3:12b | oui (10.56 Go) | 75 | 1382 |

## 4. Stockage

Mesuré : données brutes 129.3 Mo ({'ephy': 14.0, 'pmra': 11.1, 'epa': 104.2}), sorties 4.1 Mo, cache IA 7.5 Mo, 197 passages indexés.

| Scénario | Passages | Qdrant (estimé) |
|---|---|---|
| MVP actuel (3 sources, produits LPC) | 197 | 0.0 Go |
| Catalogues complets FR + CA + US | 400 000 | 3.29 Go |
| Monde (≈ 10 pays) | 1 000 000 | 8.24 Go |

Extrapolation linéaire (×1,6 pour l'index et la réplication), à recalibrer sur le volume réel.

Modèles à héberger : llama3.2:latest (2.02 Go), qwen2.5:latest (4.68 Go), gemma3:12b (8.15 Go) ; embedding nomic-embed-text:latest (0.27 Go).
