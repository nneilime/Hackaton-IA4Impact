# Schéma réel de la base PostgreSQL partagée

Relevé le 2026-10-10 par lecture seule (`information_schema` / `pg_catalog`, transaction `READ ONLY`).
Référence : `db/schema.sql` (non exécuté). Connexion : `DATABASE_URL` dans `.env` (base `lpc`).

Le schéma réel correspond à `db/schema.sql` (11 tables + 1 vue), **sans** les tables métier du CLAUDE.md
(ACTIVE_ENTITY, REGISTRATION_VERSION, EVIDENCE…) : la base reprend les CSV du starter kit.

## Tables

| Table | Clé primaire | Rôle |
|---|---|---|
| `source_registry` | `source_id` | Sources officielles (FR-EPHY, DE-BVL, CA-PPID…) |
| `products` | `product_id` | Produits (`*_original` / `*_normalized`) |
| `product_aliases` | `alias_id` | Noms alternatifs, historiques, produits sœurs |
| `registrations` | `registration_id` | Homologation produit × pays, avec `source_id`, `source_record_url`, `collected_at` |
| `uses` | `use_id` | Usages (culture, cible, dose…) d'une homologation |
| `product_name_mapping` | `mapping_id` | Mapping LPC des noms de produits |
| `active_entity_mapping` | `mapping_id` | Mapping LPC des substances actives (espèce, souche) |
| `eppo_crop_mapping` / `eppo_pest_mapping` | `concept_id` (+ `eppo_code` UNIQUE) | Cultures / cibles ↔ codes EPPO |
| `collection_runs` | `run_id` (serial) | Une ligne par passage d'un ingestor / chargement |
| `field_evidence` | `evidence_id` (serial) | Preuve au niveau du champ ; **aucune clé d'unicité** |
| `v_comparison` (vue) | – | produit × pays × usage |

## Colonnes (NOT NULL en gras)

- **source_registry** : **source_id**, **official_name**, **country_or_region**, base_url, **access_method**, data_format, license_name, access_and_reuse_limits, **manual_validation_required** (bool), notes
- **products** : **product_id**, **commercial_name**, active_entity_original, active_entity_normalized, formulation_code, **is_synthetic** (bool), **validation_status**
- **product_aliases** : **alias_id**, **product_id**, **alias_name**, country_code (char 2), **relationship_type**, confidence (num), evidence, **review_status**, **is_synthetic**
- **registrations** : **registration_id**, **product_id**, **country_code** (char 2), **authority_name**, registration_number, status_original, **status_normalized**, approval_date (date), expiration_date (date), **source_id**, **source_record_url**, **collected_at** (timestamptz), **validation_status**, **is_synthetic**
- **uses** : **use_id**, **registration_id**, crop_name_original, crop_name_normalized, eppo_crop_code, target_name_original, target_name_normalized, eppo_target_code, application_method, dose_value (num), dose_unit_original, dose_unit_normalized, max_applications (int), application_interval_days (num), phi_days (num), rei_hours (num), restrictions_original, **validation_status**, **is_synthetic**
- **product_name_mapping** : **mapping_id**, **product_id**, **name_variant**, **relationship_type**, market_or_country, confidence_score, confidence_status, evidence_summary, evidence_type, **review_status**
- **active_entity_mapping** : **mapping_id**, **product_id**, **entity_type**, **name_variant**, **canonical_species**, strain, eppo_code, relationship_type, confidence_score, confidence_status, evidence_summary, **review_status**
- **eppo_crop_mapping / eppo_pest_mapping** : **concept_id**, language, name_original, name_normalized, scientific_name, eppo_code, **mapping_status**, source_url, notes, multilingual_aliases
- **collection_runs** : **run_id**, **source_id**, **started_at** (défaut now()), finished_at, input_file, rows_read, rows_written, **status** (défaut `running`), notes
- **field_evidence** : **evidence_id**, **entity_type**, **entity_id**, **field_name**, value_original, excerpt, document_url, page_number, **extraction_method**, model_name, confidence, **validation_status** (défaut `automatically_extracted`), **collected_at** (défaut now())

## Contraintes

- **Valeurs de `validation_status`** (products, registrations, uses, field_evidence) : `automatically_extracted`, `to_verify`, `validated`, `rejected`, `obsolete`, `source_unavailable`.
- `registrations.status_normalized` ∈ `active`, `expired`, `withdrawn`, `pending`, `unknown`.
- `registrations.source_record_url` doit commencer par `http://` ou `https://` ; `source_registry.base_url` aussi (ou NULL).
- `country_code` (registrations, product_aliases) : deux majuscules (`^[A-Z]{2}$`).
- `product_aliases.relationship_type` ∈ `alternate_name`, `historical_name`, `sister_product_candidate`, `confirmed_sister_product` ; `confidence` entre 0 et 1 (idem `confidence_score`, `field_evidence.confidence`).
- `uses` : `max_applications`, `application_interval_days`, `phi_days`, `rei_hours` ≥ 0.
- `collection_runs.status` ∈ `running`, `success`, `failed`, `source_unavailable`.
- `field_evidence.entity_type` ∈ `product`, `registration`, `use`.

## Clés étrangères

- `product_aliases`, `registrations`, `product_name_mapping`, `active_entity_mapping` → `products(product_id)` **ON DELETE CASCADE**
- `uses.registration_id` → `registrations(registration_id)` ON DELETE CASCADE
- `registrations.source_id` → `source_registry(source_id)`
- `collection_runs.source_id` → `source_registry(source_id)`
- `field_evidence` : pas de clé étrangère (`entity_type` + `entity_id` désignent l'entité).

Ordre de chargement imposé : `source_registry` → `products` → `registrations` → `uses` (les mappings après `products`).

## Index

`idx_products_name` (lower(commercial_name)), `idx_products_entity`, `idx_aliases_name`, `idx_aliases_product`, `idx_reg_product`, `idx_reg_country`, `idx_reg_expiration`, `idx_uses_registration`, `idx_uses_crop`, `idx_uses_target`, `idx_entity_variant`, `idx_evidence_entity (entity_type, entity_id)` + les index des clés primaires et `eppo_code`.

## Vue `v_comparison`

```sql
SELECT p.product_id, p.commercial_name, p.active_entity_normalized,
       r.country_code, r.registration_number, r.status_original, r.status_normalized, r.expiration_date,
       u.use_id, u.crop_name_original, u.crop_name_normalized, u.eppo_crop_code,
       u.target_name_original, u.target_name_normalized, u.eppo_target_code,
       u.dose_value, u.dose_unit_original, u.restrictions_original,
       r.source_id, r.source_record_url, r.collected_at,
       r.validation_status AS registration_validation_status,
       u.validation_status AS use_validation_status,
       p.is_synthetic OR r.is_synthetic OR COALESCE(u.is_synthetic, false) AS is_synthetic
FROM products p
JOIN registrations r ON r.product_id = p.product_id
LEFT JOIN uses u ON u.registration_id = r.registration_id;
```

Une homologation sans usage apparaît (LEFT JOIN) avec les colonnes d'usage à NULL.

## État des données au relevé (avant le premier chargement ETL)

| Table | Lignes |
|---|---|
| products / registrations | 13 569 (toutes FR-EPHY, `automatically_extracted`) |
| uses | 18 023 (aucun `eppo_*` ni `*_normalized` renseigné) |
| product_aliases | 3 012 (`alternate_name`) |
| field_evidence | 718 946 (`open_data_csv`) |
| source_registry | 1 (FR-EPHY) · collection_runs : 1 |
| tables de mapping (eppo ×2, active_entity, product_name) | 0 |

D'autres coéquipiers écrivent dans la même base en parallèle (ex. données Canada) : ne jamais supposer les compteurs figés.

## Points d'attention

- **Colonnes manquantes** pour l'ETL : aucune.
- `eppo_crop_mapping.eppo_code` et `eppo_pest_mapping.eppo_code` sont UNIQUE : deux concepts ne peuvent pas partager un code.
- `field_evidence` n'a pas de clé d'unicité : l'ETL évite les doublons par un `INSERT … WHERE NOT EXISTS` sur (entity_type, entity_id, field_name, extraction_method).
- Les suppressions de `products` se propagent en cascade (aliases, registrations, uses, mappings).
