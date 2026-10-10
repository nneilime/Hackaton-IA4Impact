-- One row in `pairs` per (facture, bordereau) pair; everything else hangs off it and is deleted with it.
-- Amounts are integer cents. NULL means "not found / unknown", never zero.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS pairs (
    id               INTEGER PRIMARY KEY,
    name             TEXT NOT NULL UNIQUE,
    flow             TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('ok', 'warning', 'error')),
    facture_source   TEXT,
    bordereau_source TEXT,
    image_path       TEXT,              -- the scanned bordereau, for reviewers
    facture_raw      TEXT,              -- the B2 records as received
    ocr_raw          TEXT,              -- the OCR transcription with its ![label](bbox) markers
    clinic_id        INTEGER REFERENCES clinics (id),
    algo_verdict     TEXT CHECK (algo_verdict IN ('CORRECT', 'ISSUES')),
    risk_score       REAL,              -- orders the review queue: failed fraud-risk checks weigh most
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- The establishments, created from the documents on ingestion (pipeline.steps.IdentifyClinic); a manager can
-- correct them, and a later ingestion only fills fields that are still empty.
CREATE TABLE IF NOT EXISTS clinics (
    id          INTEGER PRIMARY KEY,
    finess      TEXT NOT NULL UNIQUE,
    name        TEXT,
    postal_code TEXT,
    city        TEXT,
    department  TEXT,
    region      TEXT,                   -- matches the region names of the web map
    caisse      TEXT,
    lat         REAL,
    lon         REAL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- The B2 file side.
CREATE TABLE IF NOT EXISTS factures (
    pair_id           INTEGER PRIMARY KEY REFERENCES pairs (id) ON DELETE CASCADE,
    numero_tiers      TEXT,
    numero_lot        TEXT,
    numero_facture    TEXT,
    numero_assure     TEXT,
    numero_gh         TEXT,
    total_prestations INTEGER,
    total_honoraires  INTEGER,
    date_fichier      TEXT,             -- YYYY-MM-DD, type 1
    code_organisme    TEXT,             -- type 2: régime + caisse + centre
    nom_etablissement TEXT              -- type 1
);

CREATE TABLE IF NOT EXISTS facture_lines (
    id          INTEGER PRIMARY KEY,
    pair_id     INTEGER NOT NULL REFERENCES pairs (id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    record_type TEXT NOT NULL CHECK (record_type IN ('3', '4')),
    sub_type    TEXT NOT NULL,          -- '' for a main line, else S / H / M / B
    acte        TEXT,
    numero_gh   TEXT,
    code_ccam   TEXT,
    raw         TEXT NOT NULL
);

-- The OCR'd form side.
CREATE TABLE IF NOT EXISTS bordereaux (
    pair_id            INTEGER PRIMARY KEY REFERENCES pairs (id) ON DELETE CASCADE,
    cerfa_id           TEXT,            -- zone 1
    finess             TEXT,            -- zone 2
    numero_lot         TEXT,            -- zone 3
    numero_facture     TEXT,            -- zone 4
    numero_assure      TEXT,            -- zone 5, first 13 digits
    sous_total_1       INTEGER,
    sous_total_2       INTEGER,
    sous_total_3       INTEGER,
    sous_total_123     INTEGER,         -- zone 8
    sous_total_4       INTEGER,         -- zone 12
    montant_total      INTEGER,         -- zone 13
    director_signature INTEGER,         -- zone 14: 1 present, 0 absent, NULL unknown
    cerfa_code         TEXT,            -- zone 15
    ocr_truncated      INTEGER NOT NULL DEFAULT 0,
    provenance         TEXT             -- JSON: per field, the raw text, strategy and bbox it was read from
);

CREATE TABLE IF NOT EXISTS bordereau_lines (
    id        INTEGER PRIMARY KEY,
    pair_id   INTEGER NOT NULL REFERENCES pairs (id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    zone      INTEGER NOT NULL CHECK (zone IN (6, 7, 10)),
    code      TEXT,                     -- prestation (zones 6-7) or act code (zone 10)
    numero_gh TEXT,
    montant   INTEGER,
    executant TEXT,                     -- zone 9, zone-10 lines only
    box       INTEGER,                  -- zone-10 lines: the "n° de case" (signature box) read by the OCR
    raw       TEXT NOT NULL
);

-- Zone 11: the 8 signature boxes, analysed on the scan (pipeline/signatures.py, check_signatures.py).
CREATE TABLE IF NOT EXISTS signature_boxes (
    id                INTEGER PRIMARY KEY,
    pair_id           INTEGER NOT NULL REFERENCES pairs (id) ON DELETE CASCADE,
    box               INTEGER NOT NULL CHECK (box BETWEEN 1 AND 8),
    bbox              TEXT,             -- JSON [x1, y1, x2, y2] in scan pixels; NULL when the scan was not analysed
    ink_ratio         REAL,             -- share of dark pixels inside the box
    signed            INTEGER,          -- 1 filled (signature / stamp), 0 empty, NULL unknown
    text              TEXT,             -- what the box prints
    text_source       TEXT CHECK (text_source IN ('box_ocr', 'page_ocr')),
    printed_executant TEXT,
    printed_name      TEXT,
    printed_amount    INTEGER,          -- cents
    rows              INTEGER NOT NULL DEFAULT 0,   -- zone-10 rows of this box
    rows_by           TEXT CHECK (rows_by IN ('executant', 'case')),
    row_executants    TEXT,             -- comma-separated
    computed_amount   INTEGER,          -- cents: sum of those rows' fees
    executant_ok      INTEGER,          -- the printed executant has acts in zone 10
    amount_ok         INTEGER,          -- printed total = computed total
    problems          TEXT NOT NULL DEFAULT '[]',   -- JSON list of messages
    UNIQUE (pair_id, box)
);

CREATE TABLE IF NOT EXISTS issues (
    id       INTEGER PRIMARY KEY,
    pair_id  INTEGER NOT NULL REFERENCES pairs (id) ON DELETE CASCADE,
    step     TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
    field    TEXT,
    message  TEXT NOT NULL
);

-- The controls between the two documents (pipeline/compare.py).
CREATE TABLE IF NOT EXISTS checks (
    id          INTEGER PRIMARY KEY,
    pair_id     INTEGER NOT NULL REFERENCES pairs (id) ON DELETE CASCADE,
    code        TEXT NOT NULL,          -- C1..C22 (CONTEXT.md), X1.. (extra signals)
    label       TEXT NOT NULL,
    category    TEXT NOT NULL,
    risk        TEXT NOT NULL CHECK (risk IN ('fraud', 'error', 'compliance')),
    status      TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL', 'UNVERIFIABLE')),
    expected    TEXT,                   -- the reference value (see expected_source)
    found       TEXT,                   -- the value checked (see found_source)
    expected_source TEXT NOT NULL DEFAULT 'b2',   -- b2 | form | rule | form_calc | scan (pipeline.compare.SOURCES)
    found_source    TEXT NOT NULL DEFAULT 'form',
    detail      TEXT NOT NULL DEFAULT '',
    ocr_suspect INTEGER NOT NULL DEFAULT 0,   -- the difference looks like an OCR misread
    UNIQUE (pair_id, code)
);

-- ---- review workflow ----------------------------------------------------------------------------------
-- Tickets, events and check reviews survive a re-ingestion of their pair; they go only when the pair is deleted.

CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY,
    username     TEXT NOT NULL UNIQUE,
    display_name TEXT,
    role         TEXT NOT NULL DEFAULT 'reviewer' CHECK (role IN ('reviewer', 'admin')),
    token_hash   TEXT NOT NULL UNIQUE,  -- sha256 of the API token; the token itself is shown once
    password_hash TEXT,                 -- sha256 of the password for the web login (local demo: no salt)
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS tickets (
    id             INTEGER PRIMARY KEY,
    pair_id        INTEGER NOT NULL UNIQUE REFERENCES pairs (id) ON DELETE CASCADE,
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'assigned', 'resolved')),
    assignee_id    INTEGER REFERENCES users (id),
    final_verdict  TEXT CHECK (final_verdict IN ('CORRECT', 'ISSUES')),
    final_category TEXT CHECK (final_category IN ('none', 'ocr_error', 'billing_error', 'suspected_fraud')),
    final_comment  TEXT,
    resolved_by    INTEGER REFERENCES users (id),
    resolved_at    TEXT,
    escalated      INTEGER NOT NULL DEFAULT 0,  -- an agent asked for a manager's opinion
    escalation_comment TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    CHECK ((status = 'open') = (assignee_id IS NULL) OR status = 'resolved'),
    CHECK ((status = 'resolved') = (final_verdict IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS ticket_events (
    id        INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets (id) ON DELETE CASCADE,
    user_id   INTEGER REFERENCES users (id),   -- NULL for the pipeline
    action    TEXT NOT NULL,                   -- created, reprocessed, assigned, released, resolved, reopened, ...
    detail    TEXT,
    at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- A reviewer's opinion on one control of their ticket.
CREATE TABLE IF NOT EXISTS check_reviews (
    id         INTEGER PRIMARY KEY,
    ticket_id  INTEGER NOT NULL REFERENCES tickets (id) ON DELETE CASCADE,
    check_code TEXT NOT NULL,
    user_id    INTEGER NOT NULL REFERENCES users (id),
    outcome    TEXT NOT NULL CHECK (outcome IN ('confirmed', 'dismissed')),  -- the algorithm was right / wrong
    comment    TEXT,
    at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (ticket_id, check_code)
);

-- Web login sessions: one token per sign-in, so several browsers can be signed in at once.
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- "Signaler" on a clinic: a report to the fraud-control service.
CREATE TABLE IF NOT EXISTS clinic_reports (
    id        INTEGER PRIMARY KEY,
    clinic_id INTEGER NOT NULL REFERENCES clinics (id) ON DELETE CASCADE,
    user_id   INTEGER NOT NULL REFERENCES users (id),
    reason    TEXT NOT NULL,
    comment   TEXT,
    at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_factures_keys ON factures (numero_tiers, numero_lot, numero_facture);
CREATE INDEX IF NOT EXISTS idx_bordereaux_keys ON bordereaux (finess, numero_lot, numero_facture);
CREATE INDEX IF NOT EXISTS idx_facture_lines_pair ON facture_lines (pair_id);
CREATE INDEX IF NOT EXISTS idx_bordereau_lines_pair ON bordereau_lines (pair_id);
CREATE INDEX IF NOT EXISTS idx_signature_boxes_pair ON signature_boxes (pair_id);
CREATE INDEX IF NOT EXISTS idx_issues_pair ON issues (pair_id);
CREATE INDEX IF NOT EXISTS idx_checks_pair ON checks (pair_id);
CREATE INDEX IF NOT EXISTS idx_tickets_queue ON tickets (status, assignee_id);
CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket ON ticket_events (ticket_id);
CREATE INDEX IF NOT EXISTS idx_clinic_reports_clinic ON clinic_reports (clinic_id);
