# Comment un expert réglementaire LPC valide les données

Le prototype **collecte et classe** ; il ne **valide** pas. Tout ce qui est affiché a un statut qui dit qui a vérifié quoi.
Cette page explique comment Regulatory Affairs passe de « extrait automatiquement » à « validé ». Lecture : 3 minutes.

## 1. Les statuts à connaître

**`validation_status`** : l'état d'une donnée (homologation, usage, valeur extraite).

| Statut | Sens |
|---|---|
| `automatically_extracted` | Copié automatiquement depuis la source officielle. **Personne ne l'a relu.** C'est le cas des 18 771 homologations en base. |
| `to_verify` | Une hypothèse ou une valeur douteuse (traduction IA, rapprochement…) : à relire en priorité. |
| `validated` | Relu et confirmé par un expert. |
| `rejected` | Relu et jugé faux. |
| `obsolete` | Était juste, ne l'est plus (source mise à jour). |
| `source_unavailable` | La source n'a pas pu être consultée : on ne peut rien conclure. |

**`review_status`** : l'état d'un **rapprochement** (nom alternatif d'un produit, produit sœur, traduction culture/cible).
Valeurs : `to_verify` (hypothèse) → `validated` ou `confirmed` (relu et accepté) ou `rejected`.

> Les données fictives sont marquées `is_synthetic = true` et restent toujours visibles.
> Une absence de résultat n'est jamais une preuve d'absence d'homologation.

## 2. Retrouver la preuve d'une donnée

Chaque fait affiché (application ou réponse de l'agent) renvoie à une **preuve** :

- **`evidenceIds`** : la liste des preuves qui appuient un fait. Un identifiant se lit ainsi :
  `registration:…` (une homologation), `use:…` (un usage) ou `field:…` (une valeur précise extraite).
  Un fait sans preuve n'est jamais affiché.
- **`sourceRecordUrl`** : le lien direct vers la **fiche officielle** (E-Phy, BVL, Santé Canada). C'est la référence : en cas
  de doute, la source officielle fait foi, pas le prototype.
- Autour de ce lien : `source_id` (CA-PPID, FR-EPHY, DE-BVL), `collected_at` (date de collecte, UTC) et `validation_status`.
- **`field_evidence`** : le « carnet de preuves » champ par champ. Pour chaque valeur, il garde : le texte exact d'où elle
  vient (`excerpt`), la méthode (`extraction_method` : fichier ouvert, API, suggestion IA, manuel), le modèle d'IA utilisé s'il
  y en a un (`model_name`), la confiance (de 0 à 1) et son statut de validation.

## 3. La marche à suivre, étape par étape

1. **Trouver quoi relire.** La file de travail est `GET /issues` (points manquants, incertains, non validés, non
   rapprochés, en conflit, source indisponible), classée par priorité. Commencer par ce qui touche les produits LPC
   (LALSTOP CONTANS WG, LALSTOP G46 WG, LALGUARD M52 OD) et les valeurs `to_verify` à faible confiance.
2. **Ouvrir la source.** Cliquer `sourceRecordUrl`, ou retrouver la fiche via `evidenceIds`.
3. **Comparer** la valeur affichée avec la fiche officielle : statut, date d'expiration, cultures, cibles, doses.
   Les colonnes `*_original` reproduisent la source telle quelle ; les colonnes `*_normalized` sont nos transformations.
   C'est toujours la colonne `*_original` qu'on compare à la source.
4. **Décider** :
   - conforme → `validated` ;
   - faux → `rejected`, avec un commentaire (la valeur correcte et la date) ;
   - la donnée était juste mais la source a changé depuis → `obsolete` ; fiche officielle inaccessible → `source_unavailable`.
5. **Rapprochements** (produits sœurs, noms alternatifs) : `to_verify` → `validated` / `confirmed` si l'expert confirme
   que c'est le même produit ou la même substance ; sinon `rejected`. Un produit sœur reste une **hypothèse** tant que ce
   passage n'est pas fait.
6. **Traductions culture / cible** : ouvrir `data/ai_term_mapping.csv`, filtrer `review_status = to_verify`, corriger le nom
   anglais, la catégorie large et le code EPPO (à vérifier sur data.eppo.int), puis passer la ligne à `validated`. Détail :
   `docs/ai_term_mapping.md`.
7. **Faire appliquer.** Aujourd'hui l'API est en **lecture seule** : l'enregistrement d'une décision (`POST /reviews`,
   prévu au contrat) n'est **pas encore implémenté**. La décision se transmet à l'équipe technique (fichier CSV corrigé ou
   liste de décisions), qui met à jour la base et les fichiers de référence. Rien n'est écrasé automatiquement.

## 4. Ce que vous pouvez dire d'un résultat après validation

| Situation | Formulation correcte |
|---|---|
| `validated` par Regulatory Affairs, fiche officielle citée | « Validé par RA le [date], source : [lien]. » |
| `automatically_extracted` | « Extrait automatiquement de [source] le [date collecte], non relu. » |
| `to_verify` | « Hypothèse à confirmer. » |
| Aucun résultat | « Aucun résultat dans les sources intégrées » — **jamais** « non homologué ». |

## 5. À garder en tête
- Un pays hors FR / DE / CA répond `not_covered` : cela ne dit rien de son homologation.
- Les limites des données (doses du Canada, statuts allemands…) sont dans `docs/limitations.md`.
- Pour une décision réglementaire, toujours se référer à l'étiquette et à la décision officielles de l'autorité du pays.
