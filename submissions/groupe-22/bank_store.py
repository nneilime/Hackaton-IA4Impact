"""The demo bank's state, in SQLite (stdlib): sessions, and what each one changed.

A session is a visitor (not logged in) or a demo customer (Connexion démo). The browser
only holds a random token, in an HttpOnly cookie; the database keeps its hash, so a copy
of the database can't be replayed as a cookie.

Every demo login opens its own sandbox: the fictional customer as seeded in
demo_customer.py, plus what this session did (card statuses, démarches). Two people
demoing at once don't see each other's changes, and logging out discards them: that is
the demo's reset, so there is no reset endpoint to protect.

The stars given at the end of a conversation (ratings) are anonymous: they stay after
the session goes.
"""

import hashlib
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent / "data" / "compass.db"))
VISITOR_LIFETIME = 24 * 3600  # seconds
CUSTOMER_LIFETIME = 8 * 3600  # a demo day: a reload doesn't log out

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,          -- sha256 of the cookie's token
    customer_id TEXT,             -- NULL: a visitor
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    revoked_at REAL
);
CREATE TABLE IF NOT EXISTS card_states (
    session_id TEXT NOT NULL,
    card_id TEXT NOT NULL,
    status TEXT NOT NULL,         -- LOCKED or OPPOSED: ACTIVE is the seed's
    updated_at REAL NOT NULL,
    PRIMARY KEY (session_id, card_id)
);
CREATE TABLE IF NOT EXISTS demarches (
    reference TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL,
    status TEXT NOT NULL,
    pdf TEXT,                     -- recap file name in RECAPS_DIR
    mode TEXT NOT NULL,           -- voice, text or app
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS demarches_session ON demarches (session_id, created_at);
CREATE TABLE IF NOT EXISTS ratings (
    stars INTEGER NOT NULL,       -- 1 to 5
    mode TEXT NOT NULL,           -- voice or text
    customer INTEGER NOT NULL,    -- 0: a visitor
    created_at REAL NOT NULL
);
"""

_lock = threading.Lock()  # tools run in threads (server.py), the API in the event loop
_db = None


@dataclass(frozen=True)
class Session:
    id: str
    customer_id: str | None  # None: a visitor

    @property
    def is_customer(self):
        return self.customer_id is not None

    def alive(self):
        """Still valid: not logged out, not expired. Checked again before every private
        tool, so logging out during a call or a chat revokes them at once."""
        with _lock:
            row = (
                _conn()
                .execute(
                    "SELECT 1 FROM sessions WHERE id = ? AND revoked_at IS NULL"
                    " AND expires_at > ?",
                    (self.id, time.time()),
                )
                .fetchone()
            )
        return row is not None


def _conn():
    global _db
    if _db is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _db = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
        _db.executescript(SCHEMA)
    return _db


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _purge(now):
    """Expired or logged-out sessions go, with their sandbox."""
    db = _conn()
    old = "SELECT id FROM sessions WHERE expires_at <= ? OR revoked_at IS NOT NULL"
    db.execute(f"DELETE FROM card_states WHERE session_id IN ({old})", (now,))
    db.execute(f"DELETE FROM demarches WHERE session_id IN ({old})", (now,))
    db.execute(
        "DELETE FROM sessions WHERE expires_at <= ? OR revoked_at IS NOT NULL", (now,)
    )


def new_session(customer_id=None):
    """Returns (token for the cookie, Session)."""
    token = secrets.token_urlsafe(32)
    now = time.time()
    lifetime = CUSTOMER_LIFETIME if customer_id else VISITOR_LIFETIME
    with _lock:
        _purge(now)
        _conn().execute(
            "INSERT INTO sessions (id, customer_id, created_at, expires_at)"
            " VALUES (?, ?, ?, ?)",
            (_hash(token), customer_id, now, now + lifetime),
        )
    return token, Session(_hash(token), customer_id)


def get_session(token):
    """The session of a cookie's token, or None (unknown, expired or logged out)."""
    if not token or len(token) > 100:
        return None
    with _lock:
        row = (
            _conn()
            .execute(
                "SELECT id, customer_id FROM sessions WHERE id = ? AND revoked_at IS NULL"
                " AND expires_at > ?",
                (_hash(token), time.time()),
            )
            .fetchone()
        )
    return Session(*row) if row else None


def revoke(session):
    with _lock:
        _conn().execute(
            "UPDATE sessions SET revoked_at = ? WHERE id = ?", (time.time(), session.id)
        )


def card_statuses(session):
    """{card_id: status} for the cards this session changed."""
    with _lock:
        rows = (
            _conn()
            .execute(
                "SELECT card_id, status FROM card_states WHERE session_id = ?",
                (session.id,),
            )
            .fetchall()
        )
    return dict(rows)


def set_card_status(session, card_id, status):
    with _lock:
        _conn().execute(
            "INSERT INTO card_states (session_id, card_id, status, updated_at)"
            " VALUES (?, ?, ?, ?) ON CONFLICT (session_id, card_id)"
            " DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at",
            (session.id, card_id, status, time.time()),
        )


def add_demarche(session, reference, kind, title, detail, status, mode, pdf=None):
    with _lock:
        _conn().execute(
            "INSERT INTO demarches (reference, session_id, kind, title, detail, status,"
            " pdf, mode, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                reference,
                session.id,
                kind,
                title,
                detail,
                status,
                pdf,
                mode,
                time.time(),
            ),
        )
    return find_demarche(session, reference)


def _demarche(row):
    reference, kind, title, detail, status, pdf, mode, created_at = row
    return {
        "reference": reference,
        "kind": kind,
        "title": title,
        "detail": detail,
        "status": status,
        "pdf": pdf,
        "mode": mode,
        "at": int(created_at * 1000),  # like Date.now() on the page
    }


COLUMNS = "reference, kind, title, detail, status, pdf, mode, created_at"


def list_demarches(session):
    """This session's démarches, newest first."""
    with _lock:
        rows = (
            _conn()
            .execute(
                f"SELECT {COLUMNS} FROM demarches WHERE session_id = ?"
                " ORDER BY created_at DESC",
                (session.id,),
            )
            .fetchall()
        )
    return [_demarche(row) for row in rows]


def find_demarche(session, reference):
    with _lock:
        row = (
            _conn()
            .execute(
                f"SELECT {COLUMNS} FROM demarches WHERE session_id = ? AND reference = ?",
                (session.id, reference),
            )
            .fetchone()
        )
    return _demarche(row) if row else None


def clear_demarches(session):
    with _lock:
        _conn().execute("DELETE FROM demarches WHERE session_id = ?", (session.id,))


def owns_pdf(session, name):
    """Whether this recap PDF is one of this session's démarches."""
    with _lock:
        row = (
            _conn()
            .execute(
                "SELECT 1 FROM demarches WHERE session_id = ? AND pdf = ?",
                (session.id, name),
            )
            .fetchone()
        )
    return row is not None


def reference_taken(reference):
    with _lock:
        row = (
            _conn()
            .execute("SELECT 1 FROM demarches WHERE reference = ?", (reference,))
            .fetchone()
        )
    return row is not None


def add_rating(session, stars, mode):
    with _lock:
        _conn().execute(
            "INSERT INTO ratings (stars, mode, customer, created_at) VALUES (?, ?, ?, ?)",
            (stars, mode, int(session.is_customer), time.time()),
        )


def rating_summary():
    """{count, average}: every rating given, all sessions together (the demo panel)."""
    with _lock:
        count, average = (
            _conn().execute("SELECT COUNT(*), AVG(stars) FROM ratings").fetchone()
        )
    return {"count": count, "average": round(average, 1) if count else None}
