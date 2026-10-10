# Relecture humaine : voir, corriger, décider

L'IA ne publie que ce qu'elle prouve. Ce qu'elle ne tranche pas arrive dans une **file de relecture** pour l'expert.

## Ce qui entre dans la file
| Cas | Signification | Ce que l'expert peut faire |
|---|---|---|
| **à corriger** | trois essais ratés, rien n'a été publié | corriger les valeurs, ou écarter la source |
| **à confirmer** | publié, mais le second avis de l'IA doute | confirmer, corriger, ou écarter |

## Trois façons de travailler
1. **Interface d'administration** : `./veille serve` puis <http://localhost:8088/admin>. Onglets : tableau de bord (état, lancement des traitements avec journal),
   à relire, sources et périmètre, historique des décisions.
2. **Ligne de commande** : `./veille review`, `./veille review --show 3`, `./veille correct 3 --author Camille --dose-value 0.35 …`,
   `./veille confirm 3 --author Camille`, `./veille dismiss 3 --author Camille --reason "étiquette sans dose"`.
3. **API REST** : `GET /review`, `POST /review/{id}/correct|confirm|dismiss` (voir `/docs`).

## Les garde-fous s'appliquent aussi à l'humain
Une valeur saisie par l'expert passe par le **même contrat Pydantic** et le **même contrôle de preuve** que celle de l'IA : la citation, la dose, l'unité, la
culture et la cible doivent figurer **mot à mot** dans le texte source. Une valeur sans preuve est refusée avec son motif exact (`veille_reglementaire/review.py`,
`build_human_record`). Seul l'expert peut poser le statut `valide_humain`.

## Rien n'est perdu
Chaque décision est gardée dans `data/processed/corrections.jsonl` (qui, quand, quoi, pourquoi) et **rejouée après chaque nouvelle extraction** : relancer l'IA
ne défait pas le travail de l'expert. La dernière décision sur un passage l'emporte ; l'historique complet reste lisible dans l'onglet « Historique ».

## Sécurité de l'interface
Le serveur écoute sur `127.0.0.1` par défaut (`--host 0.0.0.0` pour ouvrir au réseau). Si `VEILLE_ADMIN_TOKEN` est défini, toute action qui modifie des données
exige l'en-tête `X-Admin-Token` (champ « Jeton » de l'interface). Pas de comptes ni de rôles : le nom du relecteur est conservé à titre de traçabilité, pas
comme preuve d'identité.
