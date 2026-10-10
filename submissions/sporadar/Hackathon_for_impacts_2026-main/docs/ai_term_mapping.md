# Dictionnaire de traduction cultures / cibles suggéré par l'IA

Fichier : [data/ai_term_mapping.csv](../data/ai_term_mapping.csv) (402 lignes : 200 cultures + 200 cibles + 2 formes génériques).

## Pourquoi

Chaque pays publie ses cultures et ses cibles dans sa langue (« Echter Mehltau » en Allemagne, « Oïdium(s) » en France :
la même maladie). Les mappings LPC (`eppo_crop_mapping.csv`, `eppo_pest_mapping.csv`, 25 entrées chacun) ne reconnaissaient
que 3 % des lignes de cibles et 25 % des lignes de cultures. Sans nom commun, impossible de comparer les pays.

## Comment c'est produit

- Les valeurs non reconnues les plus fréquentes viennent de `data/merged/unrecognized_crop.csv` et `unrecognized_target.csv`
  (écrits par `load_db.py --normalize-db`). Les 200 premières de chaque liste couvrent environ 92 % des lignes non reconnues.
- Les traductions ont été proposées **une seule fois, hors ligne**, par le modèle qui a exécuté Claude Code
  (colonne `model_name`). Aucune clé d'IA n'est utilisée par le prototype : le fichier est versionné et relisible.
- Colonnes : `kind` (crop/target), `value_original`, `language`, `normalized_en` (nom anglais commun),
  `group_en` (catégorie large, ex. « Powdery mildews », « Cereals »), `eppo_code_candidate`, `confidence` (0..1),
  `method` (= `ai_suggested`), `model_name`, `review_status` (= `to_verify`), `note`.
- Règles : le code EPPO n'est rempli que pour une espèce précise dont le modèle est très sûr (63 lignes). Les catégories
  larges (« Insectes piqueurs », « Fruits à pépins ») n'ont que `normalized_en` + `group_en`. Une valeur composite
  (« Tomate - Aubergine ») donne « Tomato; Eggplant ». En cas de doute : `confidence` < 0.6 et une `note`.
  Un même `normalized_en` porte toujours le même code EPPO (sinon `/compare` n'alignerait pas les pays).

## Comment c'est utilisé

1. `backend/etl/normalize.py` : le mapping LPC reste **toujours prioritaire** ; si la valeur n'y est pas, le dictionnaire IA
   est le second recours (`method` = `ai_suggested`, `mapping_status` = `ai_suggested`, ou `validated` si l'expert a validé la ligne).
   Les colonnes `*_original` ne sont jamais modifiées ; le résultat va dans `crop_name_normalized` / `target_name_normalized`
   (et `eppo_*_code` seulement si `eppo_code_candidate` est rempli). Valeur inconnue : rien n'est écrit.
2. `python backend/etl/load_db.py --normalize-db` écrit la normalisation en base (colonnes vides uniquement, aucun DELETE)
   et, dans `field_evidence`, une ligne par valeur : `extraction_method` = `ai_suggested`, `model_name`, `confidence`,
   `validation_status` = `to_verify`.
3. Le regroupement n'a pas de colonne dédiée (le schéma n'est pas modifié) : il est stocké dans `field_evidence`
   (`field_name` = `crop_group` / `target_group`, `excerpt` = `group_en=...`).
4. L'API : `/compare` aligne les lignes par code EPPO, sinon par `normalized_en` (donc FR et DE se rejoignent) et expose
   `cropGroup` / `targetGroup` sur chaque ligne (ajout optionnel au contrat, à reporter dans `openapi.proposed.yaml`).
   Dans les usages, `cropMappingStatus` / `targetMappingStatus` vaut `to_verify` pour une valeur suggérée par l'IA.

## Comment un expert Regulatory valide une ligne

1. Ouvrir `data/ai_term_mapping.csv` (Excel : enregistrer en CSV UTF-8) et filtrer `review_status` = `to_verify`,
   en commençant par les `confidence` faibles et les lignes avec une `note`.
2. Corriger si besoin `normalized_en`, `group_en`, `eppo_code_candidate` (vérifier le code sur https://data.eppo.int/).
3. Passer `review_status` à `validated` (ou supprimer la ligne si elle est fausse).
4. Relancer la normalisation. Attention : `--normalize-db` ne remplit que les colonnes encore vides ; pour appliquer une
   correction à des lignes déjà normalisées, demander à l'équipe backend de mettre à jour ces colonnes (pas d'écrasement automatique).

## Limites

- Seules les valeurs écrites **exactement** comme dans le fichier (casse, accents et tirets ignorés) sont reconnues ;
  il reste ~370 cultures et ~680 cibles rares (8 % des lignes) à traiter, en relançant la même démarche sur les nouveaux
  `unrecognized_*.csv`.
- Ces traductions sont des hypothèses : une absence de correspondance n'est jamais une preuve d'absence d'homologation.
