"""SQLite storage of processed pairs (the review workflow on top of them is in pipeline/review.py)."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import Context

SCHEMA = Path(__file__).with_name("schema.sql")
DEFAULT_DB = Path(os.environ.get("INVOICES_DB", "invoices.db"))

FACTURE_COLUMNS = ("numero_tiers", "numero_lot", "numero_facture", "numero_assure", "numero_gh", "total_prestations",
                   "total_honoraires", "date_fichier", "code_organisme", "nom_etablissement")
BORDEREAU_COLUMNS = ("cerfa_id", "finess", "numero_lot", "numero_facture", "numero_assure", "sous_total_1",
                     "sous_total_2", "sous_total_3", "sous_total_123", "sous_total_4", "montant_total",
                     "director_signature", "cerfa_code", "ocr_truncated")


def connect(path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    # check_same_thread off: FastAPI runs a request's dependencies on different worker threads; each request has its
    # own connection and uses it one step at a time
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after the first release: (table, column, definition). create_schema adds them to older databases.
ADDED_COLUMNS = [
    ("bordereau_lines", "box", "INTEGER"),
    ("pairs", "clinic_id", "INTEGER REFERENCES clinics (id)"),
    ("factures", "date_fichier", "TEXT"),
    ("factures", "code_organisme", "TEXT"),
    ("factures", "nom_etablissement", "TEXT"),
    ("users", "password_hash", "TEXT"),
    ("tickets", "escalated", "INTEGER NOT NULL DEFAULT 0"),
    ("tickets", "escalation_comment", "TEXT"),
    ("checks", "expected_source", "TEXT NOT NULL DEFAULT 'b2'"),
    ("checks", "found_source", "TEXT NOT NULL DEFAULT 'form'"),
]


def create_schema(conn: sqlite3.Connection) -> None:
    """Create missing tables and columns; safe to run on an existing database (users and tickets are kept)."""
    # columns first: the script's indexes may use them, and its CREATE TABLEs skip existing tables
    for table, column, definition in ADDED_COLUMNS:
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if existing and column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()


PAIR_DATA_TABLES = ("factures", "facture_lines", "bordereaux", "bordereau_lines", "signature_boxes", "issues",
                    "checks")


@dataclass
class Documents:
    """What reviewers look at besides the extracted data."""
    facture_source: str | None = None
    bordereau_source: str | None = None
    image_path: str | None = None
    facture_raw: str | None = None
    ocr_raw: str | None = None


def save(conn: sqlite3.Connection, name: str, flow: str, ctx: Context, docs: Documents | None = None) -> int:
    """Insert or refresh the pair named `name` and make sure it has a review ticket. Returns the pair id.

    A refresh replaces the extracted data and the checks but keeps the pair id, its ticket and the review history;
    a changed algorithmic verdict is logged on the ticket.
    """
    docs = docs or Documents()
    assessment = ctx.record.get("assessment") or {}
    verdict, score = assessment.get("verdict"), assessment.get("risk_score")
    with conn:
        old = conn.execute("SELECT id, algo_verdict FROM pairs WHERE name = ?", (name,)).fetchone()
        clinic_id = upsert_clinic(conn, ctx.record["clinic"]) if ctx.record.get("clinic") else None
        values = (flow, ctx.status, docs.facture_source, docs.bordereau_source, docs.image_path, docs.facture_raw,
                  docs.ocr_raw, verdict, score, clinic_id)
        if old is None:
            pair_id = conn.execute(
                "INSERT INTO pairs (flow, status, facture_source, bordereau_source, image_path, facture_raw, ocr_raw, "
                "algo_verdict, risk_score, clinic_id, name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*values, name)).lastrowid
        else:
            pair_id = old["id"]
            conn.execute(
                "UPDATE pairs SET flow = ?, status = ?, facture_source = COALESCE(?, facture_source), "  # documents not
                "bordereau_source = COALESCE(?, bordereau_source), image_path = COALESCE(?, image_path), "  # resent are kept
                "facture_raw = COALESCE(?, facture_raw), ocr_raw = COALESCE(?, ocr_raw), algo_verdict = ?, risk_score = ?, "
                "clinic_id = COALESCE(?, clinic_id), updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?", (*values, pair_id))
            for table in PAIR_DATA_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE pair_id = ?", (pair_id,))

        ticket = conn.execute("SELECT id FROM tickets WHERE pair_id = ?", (pair_id,)).fetchone()
        if ticket is None:
            ticket_id = conn.execute("INSERT INTO tickets (pair_id) VALUES (?)", (pair_id,)).lastrowid
            log_event(conn, ticket_id, None, "created", f"algorithmic verdict {verdict}")
        elif old["algo_verdict"] != verdict:
            log_event(conn, ticket["id"], None, "reprocessed", f"algorithmic verdict {old['algo_verdict']} -> {verdict}")

        if fac := ctx.record.get("facture"):
            conn.execute(f"INSERT INTO factures (pair_id, {', '.join(FACTURE_COLUMNS)}) "
                         f"VALUES (?{', ?' * len(FACTURE_COLUMNS)})", (pair_id, *(fac[c] for c in FACTURE_COLUMNS)))
            conn.executemany(
                "INSERT INTO facture_lines (pair_id, position, record_type, sub_type, acte, numero_gh, code_ccam, raw) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(pair_id, i, l["record_type"], l["sub_type"], l["acte"], l["numero_gh"], l["code_ccam"], l["raw"])
                 for i, l in enumerate(fac["lines"])])

        if bor := ctx.record.get("bordereau"):
            values = [bor.get(c) for c in BORDEREAU_COLUMNS]
            conn.execute(f"INSERT INTO bordereaux (pair_id, {', '.join(BORDEREAU_COLUMNS)}, provenance) "
                         f"VALUES (?{', ?' * len(BORDEREAU_COLUMNS)}, ?)",
                         (pair_id, *values, json.dumps(bor.get("provenance"), ensure_ascii=False)))
            conn.executemany(
                "INSERT INTO bordereau_lines (pair_id, position, zone, code, numero_gh, montant, executant, box, raw) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(pair_id, i, l["zone"], l["code"], l["numero_gh"], l["montant"], l["executant"], l.get("case"),
                  l["raw"]) for i, l in enumerate(bor.get("lines", []))])
            conn.executemany(
                f"INSERT INTO signature_boxes (pair_id, {', '.join(BOX_COLUMNS)}) VALUES (?{', ?' * len(BOX_COLUMNS)})",
                [(pair_id, *_box_values(b)) for b in bor.get("signature_boxes", [])])

        conn.executemany("INSERT INTO issues (pair_id, step, severity, field, message) VALUES (?, ?, ?, ?, ?)",
                         [(pair_id, i.step, i.severity, i.field, i.message) for i in ctx.issues])
        conn.executemany(
            "INSERT INTO checks (pair_id, code, label, category, risk, status, expected, found, detail, ocr_suspect, "
            "expected_source, found_source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(pair_id, c["code"], c["label"], c["category"], c["risk"], c["status"], c["expected"], c["found"],
              c["detail"], int(c["ocr_suspect"]), c["expected_source"], c["found_source"])
             for c in ctx.record.get("checks", [])])
    return pair_id


BOX_COLUMNS = ("box", "bbox", "ink_ratio", "signed", "text", "text_source", "printed_executant", "printed_name",
               "printed_amount", "rows", "rows_by", "row_executants", "computed_amount", "executant_ok", "amount_ok",
               "problems")


def _box_values(b: dict) -> tuple:
    def flag(v: bool | None) -> int | None:
        return None if v is None else int(v)
    return (b["box"], json.dumps(b["bbox"]) if b["bbox"] else None, b["ink_ratio"], flag(b["signed"]), b["text"],
            b["text_source"], b["printed_executant"], b["printed_name"], b["printed_amount"], b["rows"], b["rows_by"],
            ",".join(b["row_executants"]), b["computed_amount"], flag(b["executant_ok"]), flag(b["amount_ok"]),
            json.dumps(b["problems"], ensure_ascii=False))


def _box_from_row(b: dict) -> dict:
    b["bbox"] = json.loads(b["bbox"]) if b["bbox"] else None
    b["problems"] = json.loads(b["problems"])
    b["row_executants"] = b["row_executants"].split(",") if b["row_executants"] else []
    for key in ("signed", "executant_ok", "amount_ok"):
        b[key] = None if b[key] is None else bool(b[key])
    return b


CLINIC_FIELDS = ("name", "postal_code", "city", "department", "region", "caisse")


def upsert_clinic(conn: sqlite3.Connection, clinic: dict) -> int | None:
    """The id of the pair's clinic, created if needed. An existing clinic only gets its empty fields filled, so a
    manager's corrections stay. A FINESS both documents agree on wins, then one already known, then the form's."""
    candidates = clinic.get("finess_candidates") or []
    if not candidates:
        return None
    known = [conn.execute("SELECT id FROM clinics WHERE finess = ?", (f,)).fetchone() for f in candidates]
    if len(set(candidates)) > 1 and any(known):
        clinic_id = next(k["id"] for k in known if k)
    else:
        finess = candidates[0]
        row = conn.execute("SELECT id FROM clinics WHERE finess = ?", (finess,)).fetchone()
        clinic_id = row["id"] if row else conn.execute("INSERT INTO clinics (finess) VALUES (?)", (finess,)).lastrowid
    lat, lon = clinic.get("coordinates") or (None, None)
    conn.execute(
        f"UPDATE clinics SET {', '.join(f'{c} = COALESCE({c}, ?)' for c in CLINIC_FIELDS)}, "
        "lat = COALESCE(lat, ?), lon = COALESCE(lon, ?) WHERE id = ?",
        (*(clinic.get(c) for c in CLINIC_FIELDS), lat, lon, clinic_id))
    return clinic_id


def log_event(conn: sqlite3.Connection, ticket_id: int, user_id: int | None, action: str, detail: str | None = None):
    conn.execute("INSERT INTO ticket_events (ticket_id, user_id, action, detail) VALUES (?, ?, ?, ?)",
                 (ticket_id, user_id, action, detail))


def _row(row: sqlite3.Row | None, drop: tuple[str, ...] = ("pair_id",)) -> dict[str, Any] | None:
    return None if row is None else {k: row[k] for k in row.keys() if k not in drop}


def list_pairs(conn: sqlite3.Connection, *, finess: str | None = None, numero_lot: str | None = None,
               numero_facture: str | None = None, status: str | None = None, algo_verdict: str | None = None,
               limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    where, params = [], []
    for column, value in (("f.numero_tiers", finess), ("f.numero_lot", numero_lot),
                          ("f.numero_facture", numero_facture), ("p.status", status), ("p.algo_verdict", algo_verdict)):
        if value is not None:
            where.append(f"{column} = ?")
            params.append(value)
    sql = ("SELECT p.id, p.name, p.flow, p.status, p.algo_verdict, p.risk_score, p.created_at, p.updated_at, "
           "f.numero_tiers, f.numero_lot, f.numero_facture, t.id AS ticket_id, t.status AS ticket_status, "
           "t.final_verdict, (SELECT COUNT(*) FROM checks c WHERE c.pair_id = p.id AND c.status = 'FAIL') AS failed_checks "
           "FROM pairs p LEFT JOIN factures f ON f.pair_id = p.id LEFT JOIN tickets t ON t.pair_id = p.id"
           + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY p.name LIMIT ? OFFSET ?")
    return [_row(r, ()) for r in conn.execute(sql, (*params, limit, offset))]


def get_pair(conn: sqlite3.Connection, pair_id: int) -> dict[str, Any] | None:
    """Everything about a pair except the raw documents (see get_documents)."""
    pair = _row(conn.execute("SELECT * FROM pairs WHERE id = ?", (pair_id,)).fetchone(),
                ("facture_raw", "ocr_raw"))
    if pair is None:
        return None

    def rows(sql: str) -> list[dict]:
        return [_row(r, ("pair_id", "id")) for r in conn.execute(sql, (pair_id,))]

    facture = _row(conn.execute("SELECT * FROM factures WHERE pair_id = ?", (pair_id,)).fetchone())
    if facture is not None:
        facture["lines"] = rows("SELECT * FROM facture_lines WHERE pair_id = ? ORDER BY position")
    bordereau = _row(conn.execute("SELECT * FROM bordereaux WHERE pair_id = ?", (pair_id,)).fetchone())
    if bordereau is not None:
        bordereau["provenance"] = json.loads(bordereau["provenance"] or "null")
        for key in ("director_signature", "ocr_truncated"):
            bordereau[key] = None if bordereau[key] is None else bool(bordereau[key])
        bordereau["lines"] = rows("SELECT * FROM bordereau_lines WHERE pair_id = ? ORDER BY position")
        bordereau["signature_boxes"] = [_box_from_row(b) for b in
                                        rows("SELECT * FROM signature_boxes WHERE pair_id = ? ORDER BY box")]
    checks = rows("SELECT * FROM checks WHERE pair_id = ? ORDER BY id")
    for c in checks:
        c["ocr_suspect"] = bool(c["ocr_suspect"])
    ticket = conn.execute("SELECT id FROM tickets WHERE pair_id = ?", (pair_id,)).fetchone()
    clinic = _row(conn.execute("SELECT * FROM clinics WHERE id = ?", (pair["clinic_id"],)).fetchone(), ())
    return {**pair, "ticket_id": ticket["id"] if ticket else None, "clinic": clinic, "checks": checks, "facture": facture,
            "bordereau": bordereau, "issues": rows("SELECT * FROM issues WHERE pair_id = ? ORDER BY id")}


def get_documents(conn: sqlite3.Connection, pair_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT name, facture_raw, ocr_raw, image_path FROM pairs WHERE id = ?", (pair_id,)).fetchone()
    return _row(row, ())


def pair_id_by_name(conn: sqlite3.Connection, name: str) -> int | None:
    row = conn.execute("SELECT id FROM pairs WHERE name = ?", (name,)).fetchone()
    return row["id"] if row else None


def delete_pair(conn: sqlite3.Connection, pair_id: int) -> bool:
    with conn:
        return conn.execute("DELETE FROM pairs WHERE id = ?", (pair_id,)).rowcount > 0
