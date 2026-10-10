# Coût : service d'IA local, API au token, forfaits

Tarifs relevés le 2026-10-10 (sources dans `config/pricing.json`). Montants en dollars US, hors taxes.
Volume mesuré sur `qwen2.5:latest` : **1789 tokens lus + 207 tokens écrits par passage** (essais et contrôles inclus), 1.9 s par passage sur la RTX 3090.

## Coût total par scénario

| Option | Démonstration (corpus actuel) (197 passages) | Mise à jour quotidienne pendant 1 an (hypothèse : 500 passages par jour) (182 500 passages) | Chargement initial FR + CA + US (400 000 passages) | Monde (≈ 10 pays) (1 000 000 passages) |
|---|---|---|---|---|
| Service local : RTX 3090, qwen2.5:latest (électricité seule) | 0,01 $ | 7,42 $ | 16,26 $ | 40,64 $ |
| Service local : RTX 3090, qwen2.5:latest (électricité + amortissement) | 0,03 $ | 23,91 $ | 52,40 $ | 131,01 $ |
| Anthropic Claude Haiku 5.5 | 0,06 $ | 51,54 $ | 112,96 $ | 282,40 $ |
| Anthropic Claude Haiku 5.5 (Batch, −50 %) | 0,03 $ | 25,77 $ | 56,48 $ | 141,20 $ |
| Anthropic Claude Sonnet 5.5 | 1,11 $ | 1 030,76 $ | 2 259,20 $ | 5 648,00 $ |
| Anthropic Claude Sonnet 5.5 (Batch, −50 %) | 0,56 $ | 515,38 $ | 1 129,60 $ | 2 824,00 $ |
| Anthropic Claude Opus 5.5 | 2,23 $ | 2 061,52 $ | 4 518,40 $ | 11 296,00 $ |
| Anthropic Claude Opus 5.5 (Batch, −50 %) | 1,11 $ | 1 030,76 $ | 2 259,20 $ | 5 648,00 $ |
| OpenAI gpt-5-nano | 0,03 $ | 31,44 $ | 68,90 $ | 172,25 $ |
| OpenAI gpt-5-nano (Batch, −50 %) | 0,02 $ | 15,72 $ | 34,45 $ | 86,12 $ |
| OpenAI gpt-5-mini | 0,17 $ | 157,18 $ | 344,50 $ | 861,25 $ |
| OpenAI gpt-5-mini (Batch, −50 %) | 0,08 $ | 78,59 $ | 172,25 $ | 430,62 $ |
| OpenAI gpt-5.5 | 2,99 $ | 2 765,79 $ | 6 062,00 $ | 15 155,00 $ |
| OpenAI gpt-5.5 (Batch, −50 %) | 1,49 $ | 1 382,89 $ | 3 031,00 $ | 7 577,50 $ |
| Google gemini-2.5-flash-lite | 0,05 $ | 47,76 $ | 104,68 $ | 261,70 $ |
| Google gemini-2.5-flash-lite (Batch, −50 %) | 0,03 $ | 23,88 $ | 52,34 $ | 130,85 $ |
| Google gemini-2.5-flash | 0,21 $ | 192,39 $ | 421,68 $ | 1 054,20 $ |
| Google gemini-2.5-flash (Batch, −50 %) | 0,10 $ | 96,20 $ | 210,84 $ | 527,10 $ |
| Google gemini-3.1-pro-preview | 1,19 $ | 1 106,32 $ | 2 424,80 $ | 6 062,00 $ |
| Google gemini-3.1-pro-preview (Batch, −50 %) | 0,60 $ | 553,16 $ | 1 212,40 $ | 3 031,00 $ |
| Mistral Large | 0,24 $ | 219,91 $ | 482,00 $ | 1 205,00 $ |
| Mistral Large (Batch, −50 %) | 0,12 $ | 109,96 $ | 241,00 $ | 602,50 $ |

## Hypothèses du coût local

Carte 900 $ amortie sur 3 ans à 20 % d'utilisation ; 350 W ; électricité 0.22 $/kWh. Énergie par passage : 0.18 Wh.

## Forfaits (abonnements par personne)

| Fournisseur | Forfait | Prix mensuel | Remarque |
|---|---|---|---|
| Anthropic | Claude Pro | 20 $ | 17 $/mois en facturation annuelle |
| Anthropic | Claude Max | 100 $ | « à partir de 100 $ » |
| Anthropic | Claude Team (siège standard) | 25 $ | 20 $ en annuel |
| OpenAI | ChatGPT Business (siège standard) | 25 $ | 20 $ en annuel ; 2 sièges minimum |
| OpenAI | ChatGPT Pro | 100 $ | paliers 100 / 200 / 500 $ |
| Mistral | Le Chat Pro | 14.99 $ |  |
| Mistral | Le Chat Team | 24.99 $ | par utilisateur |

- Les forfaits sont des abonnements par personne pour un usage interactif, avec des limites d'usage (fenêtre glissante de 5 heures et plafonds hebdomadaires chez Anthropic).
- Au-delà des limites, Anthropic renvoie vers des crédits facturés « aux tarifs API standard » ; l'offre Enterprise est « siège + usage aux tarifs API ». Un forfait ne fournit donc pas un accès API de traitement en masse.
- Un pipeline automatisé se facture donc au token (colonne API), pas au forfait.

## Réserves

- Les tokens par passage sont ceux du modèle local mesuré (tokenizer différent chez chaque fournisseur : écart possible de quelques dizaines de %).
- Seuls les modèles locaux ont été mesurés en qualité : le coût d'une API ne dit rien de sa qualité sur cette tâche.
- Les coûts locaux supposent le service déjà en place ; hors maintenance, réseau et temps d'exploitation.
- Le prix d'achat de la carte, l'électricité et le taux d'utilisation sont des hypothèses (config/local_cost_assumptions.json).
