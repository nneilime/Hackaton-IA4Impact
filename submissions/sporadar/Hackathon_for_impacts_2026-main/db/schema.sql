-- LPC Global Regulatory AI - PostgreSQL schema
-- Built from data/field_dictionary.csv and the CSV headers in data/.
-- Column names match the CSVs exactly, so each file loads with a plain COPY.
-- Safe to re-run: creates only what is missing, never deletes data.
-- (The destructive reset lives in db/reset_DANGER.sql only.)

-- =====================================================================
-- 1. Canonical data (filled by the ingestors)
-- =====================================================================

CREATE TABLE IF NOT EXISTS source_registry (
    source_id                  TEXT PRIMARY KEY,
    official_name              TEXT NOT NULL,
    country_or_region          TEXT NOT NULL,
    base_url                   TEXT,                 -- empty for sources still to validate (e.g. COFEPRIS)
    access_method              TEXT NOT NULL,        -- data uses combined values such as 'api/web'
    data_format                TEXT,
    license_name               TEXT,
    access_and_reuse_limits    TEXT,
    manual_validation_required BOOLEAN NOT NULL,
    notes                      TEXT,
    CHECK (base_url IS NULL OR base_url ~ '^https?://')
);

CREATE TABLE IF NOT EXISTS products (
    product_id               TEXT PRIMARY KEY,       -- stable ID, never the commercial name
    commercial_name          TEXT NOT NULL,
    active_entity_original   TEXT,                   -- exact source wording, never modified
    active_entity_normalized TEXT,
    formulation_code         TEXT,                   -- WG, OD, SC, WP...
    is_synthetic             BOOLEAN NOT NULL,
    validation_status        TEXT NOT NULL CHECK (validation_status IN
        ('automatically_extracted','to_verify','validated','rejected','obsolete','source_unavailable'))
);

CREATE TABLE IF NOT EXISTS product_aliases (
    alias_id          TEXT PRIMARY KEY,
    product_id        TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,   -- the pilot product
    related_product_id TEXT REFERENCES products(product_id) ON DELETE CASCADE,          -- the exact product this alias describes
    alias_name        TEXT NOT NULL,
    country_code      CHAR(2) CHECK (country_code ~ '^[A-Z]{2}$'),
    relationship_type TEXT NOT NULL CHECK (relationship_type IN
        ('alternate_name','historical_name','sister_product_candidate','confirmed_sister_product')),
    confidence        NUMERIC(3,2) CHECK (confidence BETWEEN 0 AND 1),  -- NOT regulatory validation
    evidence          TEXT,
    review_status     TEXT NOT NULL,                 -- to_verify / validated / confirmed ...
    is_synthetic      BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS registrations (
    registration_id     TEXT PRIMARY KEY,
    product_id          TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    country_code        CHAR(2) NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'),
    authority_name      TEXT NOT NULL,
    registration_number TEXT,
    status_original     TEXT,                        -- exact source wording
    status_normalized   TEXT NOT NULL CHECK (status_normalized IN
        ('active','expired','withdrawn','pending','unknown')),
    approval_date       DATE,
    expiration_date     DATE,
    -- traceability (mandatory on every regulatory assertion)
    source_id           TEXT NOT NULL REFERENCES source_registry(source_id),
    source_record_url   TEXT NOT NULL CHECK (source_record_url ~ '^https?://'),
    collected_at        TIMESTAMPTZ NOT NULL,
    validation_status   TEXT NOT NULL CHECK (validation_status IN
        ('automatically_extracted','to_verify','validated','rejected','obsolete','source_unavailable')),
    is_synthetic        BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS uses (
    use_id                    TEXT PRIMARY KEY,
    registration_id           TEXT NOT NULL REFERENCES registrations(registration_id) ON DELETE CASCADE,
    crop_name_original        TEXT,
    crop_name_normalized      TEXT,
    eppo_crop_code            TEXT,
    target_name_original      TEXT,
    target_name_normalized    TEXT,
    eppo_target_code          TEXT,
    application_method        TEXT,
    dose_value                NUMERIC,
    dose_unit_original        TEXT,
    dose_unit_normalized      TEXT,
    max_applications          INTEGER CHECK (max_applications >= 0),
    application_interval_days NUMERIC CHECK (application_interval_days >= 0),
    phi_days                  NUMERIC CHECK (phi_days >= 0),       -- pre-harvest interval
    rei_hours                 NUMERIC CHECK (rei_hours >= 0),      -- restricted-entry interval
    restrictions_original     TEXT,
    validation_status         TEXT NOT NULL CHECK (validation_status IN
        ('automatically_extracted','to_verify','validated','rejected','obsolete','source_unavailable')),
    is_synthetic              BOOLEAN NOT NULL
);

-- =====================================================================
-- 2. Reference / lookup data (LPC mappings, used for normalization)
-- =====================================================================

CREATE TABLE IF NOT EXISTS product_name_mapping (
    mapping_id        TEXT PRIMARY KEY,
    product_id        TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    name_variant      TEXT NOT NULL,
    relationship_type TEXT NOT NULL,     -- canonical_name, historical_or_market_name, related_formulation, sister_product_candidate
    market_or_country TEXT,
    confidence_score  NUMERIC(3,2) CHECK (confidence_score BETWEEN 0 AND 1),
    confidence_status TEXT,
    evidence_summary  TEXT,
    evidence_type     TEXT,
    review_status     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS active_entity_mapping (
    mapping_id        TEXT PRIMARY KEY,
    product_id        TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    entity_type       TEXT NOT NULL,
    name_variant      TEXT NOT NULL,      -- e.g. 'Gliocladium catenulatum J1446'
    canonical_species TEXT NOT NULL,      -- e.g. 'Clonostachys rosea'
    strain            TEXT,               -- strain identity is more specific than species: keep it
    eppo_code         TEXT,
    relationship_type TEXT,
    confidence_score  NUMERIC(3,2) CHECK (confidence_score BETWEEN 0 AND 1),
    confidence_status TEXT,
    evidence_summary  TEXT,
    review_status     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eppo_crop_mapping (
    concept_id           TEXT PRIMARY KEY,
    language             TEXT,
    name_original        TEXT,
    name_normalized      TEXT,
    scientific_name      TEXT,
    eppo_code            TEXT UNIQUE,
    mapping_status       TEXT NOT NULL,   -- 'to_verify' until checked against EPPO
    source_url           TEXT,
    notes                TEXT,
    multilingual_aliases TEXT             -- 'fr:tomate|es:tomate|...'
);

CREATE TABLE IF NOT EXISTS eppo_pest_mapping (LIKE eppo_crop_mapping INCLUDING ALL);

-- =====================================================================
-- 3. Team extensions (allowed by the README; no traceability field removed)
-- =====================================================================

-- One row per ingestor run: enables change detection between two runs (bonus).
CREATE TABLE IF NOT EXISTS collection_runs (
    run_id       BIGSERIAL PRIMARY KEY,
    source_id    TEXT NOT NULL REFERENCES source_registry(source_id),
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    input_file   TEXT,                    -- raw file kept in data/raw/...
    rows_read    INTEGER,
    rows_written INTEGER,
    status       TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','success','failed','source_unavailable')),
    notes        TEXT
);

-- One row per extracted value (mainly label PDFs): evidence at field level.
CREATE TABLE IF NOT EXISTS field_evidence (
    evidence_id       BIGSERIAL PRIMARY KEY,
    entity_type       TEXT NOT NULL CHECK (entity_type IN ('product','registration','use')),
    entity_id         TEXT NOT NULL,      -- product_id / registration_id / use_id
    field_name        TEXT NOT NULL,      -- e.g. 'dose_value', 'phi_days'
    value_original    TEXT,
    excerpt           TEXT,               -- exact text the value was taken from
    document_url      TEXT,
    page_number       INTEGER,
    extraction_method TEXT NOT NULL,      -- open_data_csv, api_json, llm_label_extraction, manual
    model_name        TEXT,               -- which AI model, if any
    confidence        NUMERIC(3,2) CHECK (confidence BETWEEN 0 AND 1),
    validation_status TEXT NOT NULL DEFAULT 'automatically_extracted' CHECK (validation_status IN
        ('automatically_extracted','to_verify','validated','rejected','obsolete','source_unavailable')),
    collected_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- 4. Indexes for the API queries
-- =====================================================================

CREATE INDEX IF NOT EXISTS idx_products_name        ON products (lower(commercial_name));
CREATE INDEX IF NOT EXISTS idx_products_entity      ON products (lower(active_entity_normalized));
CREATE INDEX IF NOT EXISTS idx_aliases_name         ON product_aliases (lower(alias_name));
CREATE INDEX IF NOT EXISTS idx_aliases_product      ON product_aliases (product_id);
CREATE INDEX IF NOT EXISTS idx_aliases_related      ON product_aliases (related_product_id);
CREATE INDEX IF NOT EXISTS idx_reg_product          ON registrations (product_id);
CREATE INDEX IF NOT EXISTS idx_reg_country          ON registrations (country_code);
CREATE INDEX IF NOT EXISTS idx_reg_expiration       ON registrations (expiration_date);
CREATE INDEX IF NOT EXISTS idx_uses_registration    ON uses (registration_id);
CREATE INDEX IF NOT EXISTS idx_uses_crop            ON uses (eppo_crop_code);
CREATE INDEX IF NOT EXISTS idx_uses_target          ON uses (eppo_target_code);
CREATE INDEX IF NOT EXISTS idx_entity_variant       ON active_entity_mapping (lower(name_variant));
CREATE INDEX IF NOT EXISTS idx_evidence_entity      ON field_evidence (entity_type, entity_id);

-- =====================================================================
-- 5. Product x country x use view (the comparison table the brief asks for)
-- =====================================================================

CREATE OR REPLACE VIEW v_comparison AS
SELECT p.product_id, p.commercial_name, p.active_entity_normalized,
       r.country_code, r.registration_number, r.status_original, r.status_normalized,
       r.expiration_date,
       u.use_id, u.crop_name_original, u.crop_name_normalized, u.eppo_crop_code,
       u.target_name_original, u.target_name_normalized, u.eppo_target_code,
       u.dose_value, u.dose_unit_original, u.restrictions_original,
       r.source_id, r.source_record_url, r.collected_at,
       r.validation_status AS registration_validation_status,
       u.validation_status AS use_validation_status,
       (p.is_synthetic OR r.is_synthetic OR coalesce(u.is_synthetic, false)) AS is_synthetic
FROM products p
JOIN registrations r ON r.product_id = p.product_id
LEFT JOIN uses u     ON u.registration_id = r.registration_id;