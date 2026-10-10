"""Persistance locale (SQLite, bibliothèque standard).

Les MÉTADONNÉES de l'application (utilisateurs, statuts, décisions, corrections, journal) sont
stockées ici, séparément des documents originaux (lecture seule) et des résultats d'extraction.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('agent','superviseur','admin','auditeur')),
    pwd_salt TEXT NOT NULL, pwd_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_files (
    path TEXT PRIMARY KEY, kind TEXT, size INTEGER, sha256 TEXT, read_only INTEGER, registered_at TEXT);
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY, family TEXT, jpg_path TEXT, txt_path TEXT, jpg_sha256 TEXT, txt_sha256 TEXT,
    pairing_status TEXT, finess TEXT, establishment TEXT, invoice_no TEXT, billed_cents INTEGER,
    n_anomalies INTEGER, n_nv INTEGER, n_errors INTEGER, n_observations INTEGER, state TEXT,
    net_gap_cents INTEGER, act_gap_cents INTEGER, priority_score REAL, priority_reasons TEXT,
    status TEXT NOT NULL DEFAULT 'À contrôler', assigned_to INTEGER, priority_override TEXT,
    analyzed_at TEXT, run_id INTEGER);
CREATE TABLE IF NOT EXISTS analyses (
    case_id TEXT PRIMARY KEY, payload TEXT NOT NULL, analyzed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS check_results (
    case_id TEXT, rule_id TEXT, status TEXT, gap_cents INTEGER, uncertainty TEXT, run_id INTEGER,
    PRIMARY KEY (case_id, rule_id));
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT, engine_version TEXT, ruleset_version TEXT,
    n_cases INTEGER, triggered_by TEXT);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY, case_id TEXT NOT NULL, rule_id TEXT, kind TEXT NOT NULL, value TEXT,
    comment TEXT, user_id INTEGER, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY, case_id TEXT NOT NULL, target TEXT NOT NULL, original TEXT, corrected TEXT NOT NULL,
    comment TEXT, user_id INTEGER, created_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY, ts TEXT NOT NULL, user_id INTEGER, username TEXT, action TEXT NOT NULL,
    target TEXT, details TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, target TEXT, status TEXT NOT NULL, progress INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0, message TEXT, error TEXT, created_by TEXT, created_at TEXT NOT NULL,
    started_at TEXT, finished_at TEXT, duration_s REAL);
CREATE TABLE IF NOT EXISTS activity (
    case_id TEXT NOT NULL, user_id INTEGER NOT NULL, day TEXT NOT NULL, active_s INTEGER NOT NULL DEFAULT 0,
    first_seen TEXT, last_seen TEXT, PRIMARY KEY (case_id, user_id, day));
CREATE TABLE IF NOT EXISTS validations (
    id INTEGER PRIMARY KEY, case_id TEXT NOT NULL, rule_id TEXT NOT NULL, verdict TEXT NOT NULL, cause TEXT,
    printed_value TEXT, b2_value TEXT, comment TEXT, validator_id INTEGER, validator_name TEXT,
    validator_kind TEXT NOT NULL DEFAULT 'humain', engine_status TEXT, engine_version TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_validations_case ON validations(case_id, rule_id);
CREATE INDEX IF NOT EXISTS idx_decisions_case ON decisions(case_id);
CREATE INDEX IF NOT EXISTS idx_corrections_case ON corrections(case_id);
"""

# Colonnes ajoutées par la version 2.0 (migration non destructive d'une base 1.x)
MIGRATIONS = [
    ("cases", "analysis_key", "TEXT"),
    ("cases", "source", "TEXT DEFAULT 'corpus'"),
    ("cases", "source_status", "TEXT DEFAULT 'ok'"),
    ("cases", "label", "TEXT"),
    ("cases", "created_by", "TEXT"),
    ("cases", "opened_at", "TEXT"),
    ("cases", "closed_at", "TEXT"),
    ("cases", "analysis_s", "REAL"),
    ("corrections", "effect", "TEXT"),
    ("corrections", "kind", "TEXT DEFAULT 'correction'"),
    ("users", "is_demo", "INTEGER DEFAULT 0"),
]

CASE_STATUSES = ["À contrôler", "En analyse", "Anomalie à vérifier", "Revue complémentaire nécessaire",
                 "Écart confirmé", "Faux positif reconnu", "Contrôle terminé", "Clôturé"]
ROLES = ["agent", "superviseur", "admin", "auditeur"]

_lock = threading.RLock()


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


class DB:
    def __init__(self, path: Path = DB_PATH):
        self.path = Path(path)
        self.conn = connect(self.path)
        with self.tx() as c:
            c.executescript(SCHEMA)
            for table, col, ddl in MIGRATIONS:
                cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
                if col not in cols:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            # reprise sûre : un traitement interrompu (arrêt de l'application) n'est jamais laissé « en cours »
            c.execute("UPDATE jobs SET status='interrompu', finished_at=? WHERE status IN ('en_attente','en_cours')",
                      (now(),))

    @contextmanager
    def tx(self):
        with _lock:
            try:
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def q(self, sql, args=()):
        with _lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        r = self.q(sql, args)
        return r[0] if r else None

    # ------------------------------------------------------------ utilisateurs
    @staticmethod
    def _hash(pwd: str, salt: str) -> str:
        return hashlib.scrypt(pwd.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1).hex()

    def create_user(self, username, display_name, role, password, is_demo=False) -> int:
        if role not in ROLES:
            raise ValueError("rôle inconnu")
        if len(password) < 8:
            raise ValueError("Le mot de passe doit contenir au moins 8 caractères.")
        salt = secrets.token_hex(16)
        with self.tx() as c:
            cur = c.execute("INSERT INTO users (username, display_name, role, pwd_salt, pwd_hash, created_at, is_demo) "
                            "VALUES (?,?,?,?,?,?,?)", (username.strip().lower(), display_name.strip(), role, salt,
                                                       self._hash(password, salt), now(), int(is_demo)))
            return cur.lastrowid

    def set_password(self, username, password) -> bool:
        """Réinitialisation locale d'un mot de passe (commande d'administration, jamais journalisé en clair)."""
        if len(password) < 8:
            raise ValueError("Le mot de passe doit contenir au moins 8 caractères.")
        salt = secrets.token_hex(16)
        with self.tx() as c:
            cur = c.execute("UPDATE users SET pwd_salt=?, pwd_hash=?, active=1 WHERE username=?",
                            (salt, self._hash(password, salt), username.strip().lower()))
            u = c.execute("SELECT id FROM users WHERE username=?", (username.strip().lower(),)).fetchone()
            if u:
                c.execute("DELETE FROM sessions WHERE user_id=?", (u[0],))
            return cur.rowcount > 0

    def check_password(self, username, password):
        u = self.one("SELECT * FROM users WHERE username=? AND active=1", (username.strip().lower(),))
        if not u:
            self._hash(password, "00" * 16)   # temps constant approximatif
            return None
        if hmac.compare_digest(self._hash(password, u["pwd_salt"]), u["pwd_hash"]):
            return u
        return None

    def new_session(self, user_id, hours=12) -> str:
        token = secrets.token_urlsafe(32)
        exp = (dt.datetime.now() + dt.timedelta(hours=hours)).isoformat(timespec="seconds")
        with self.tx() as c:
            c.execute("INSERT INTO sessions VALUES (?,?,?,?)",
                      (hashlib.sha256(token.encode()).hexdigest(), user_id, now(), exp))
        return token

    def session_user(self, token):
        if not token:
            return None
        s = self.one("SELECT * FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
        if not s or s["expires_at"] < now():
            return None
        return self.one("SELECT id, username, display_name, role FROM users WHERE id=? AND active=1", (s["user_id"],))

    def drop_session(self, token):
        with self.tx() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))

    def users(self):
        return self.q("SELECT id, username, display_name, role, active, created_at, is_demo FROM users ORDER BY role, username")

    # ------------------------------------------------------------ journal
    def audit(self, user, action, target=None, details=None):
        # le journal ne recopie jamais un numéro d'assuré complet (masquage à l'écriture)
        from .privacy import mask_text
        target, details = mask_text(target), mask_text(details)
        with self.tx() as c:
            c.execute("INSERT INTO audit (ts, user_id, username, action, target, details) VALUES (?,?,?,?,?,?)",
                      (now(), user["id"] if user else None, user["username"] if user else "système", action, target,
                       json.dumps(details, ensure_ascii=False) if details is not None else None))

    def meta_get(self, key, default=None):
        r = self.one("SELECT value FROM meta WHERE key=?", (key,))
        return json.loads(r["value"]) if r else default

    def meta_set(self, key, value):
        with self.tx() as c:
            c.execute("INSERT INTO meta (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (key, json.dumps(value, ensure_ascii=False)))

    # ------------------------------------------------------------ purge des métadonnées de session
    def purge_metadata(self, keep_users=True):
        with self.tx() as c:
            c.execute("DELETE FROM decisions")
            c.execute("DELETE FROM corrections")
            c.execute("UPDATE cases SET status='À contrôler', assigned_to=NULL, priority_override=NULL")
            c.execute("DELETE FROM audit")
            if not keep_users:
                c.execute("DELETE FROM sessions")
                c.execute("DELETE FROM users")
