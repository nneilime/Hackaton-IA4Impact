"""Review workflow: user accounts, web sessions and the ticket each pair gets.

A ticket goes open -> assigned -> resolved:
  - any reviewer can request an open ticket (or the next one by risk); it is granted at once if they hold fewer than
    MAX_ACTIVE tickets
  - the assignee (or an admin) can release it back to open
  - the assignee can escalate it: it goes back to the queue, reserved to managers (admins), with their comment
  - the assignee resolves it with the final word: CORRECT (category none / ocr_error) or ISSUES (billing_error /
    suspected_fraud); a comment is required when that disagrees with the algorithmic verdict
  - admins can assign a ticket to anyone and reopen a resolved one
While assigned, the assignee can confirm or dismiss individual checks. Every change is logged in ticket_events.
Messages are in French: the web app shows them as they are.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from typing import Any

from .store import log_event

MAX_ACTIVE = int(os.environ.get("REVIEW_MAX_ACTIVE", "5"))
CATEGORIES = {"CORRECT": ("none", "ocr_error"), "ISSUES": ("billing_error", "suspected_fraud")}


class ReviewError(Exception):
    status_code = 400


class NotFound(ReviewError):
    status_code = 404


class Forbidden(ReviewError):
    status_code = 403


class Conflict(ReviewError):
    status_code = 409


class Unauthorized(ReviewError):
    status_code = 401


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else dict(row)


def _now() -> str:
    return "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"


# ---- users and sessions --------------------------------------------------------------------------------

USER_COLUMNS = "id, username, display_name, role, active, created_at"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_user(conn: sqlite3.Connection, username: str, display_name: str | None = None,
                role: str = "reviewer", password: str | None = None) -> tuple[dict, str]:
    """Returns the user and their API token; only hashes of the token and password are stored."""
    token = secrets.token_urlsafe(32)
    try:
        with conn:
            user_id = conn.execute(
                "INSERT INTO users (username, display_name, role, token_hash, password_hash) VALUES (?, ?, ?, ?, ?)",
                (username, display_name, role, hash_token(token), hash_token(password) if password else None)).lastrowid
    except sqlite3.IntegrityError:
        raise Conflict(f"l'utilisateur {username!r} existe déjà") from None
    return get_user(conn, user_id), token


# Placeholder accounts for the local demo (create_db.py --demo, users.py demo): username, password, name, role.
DEMO_ACCOUNTS = [("agent", "agent", "Agent de contrôle", "reviewer"), ("admin", "admin", "Manager", "admin")]


def ensure_demo_accounts(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """Create the demo accounts, or reset their password and role if they exist. Returns (username, password, role)."""
    for username, password, name, role in DEMO_ACCOUNTS:
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            with conn:
                conn.execute("UPDATE users SET password_hash = ?, role = ?, active = 1, "
                             "display_name = COALESCE(display_name, ?) WHERE username = ?",
                             (hash_token(password), role, name, username))
        else:
            create_user(conn, username, name, role, password)
    return [(u, p, r) for u, p, _, r in DEMO_ACCOUNTS]


def set_password(conn: sqlite3.Connection, username: str, password: str) -> None:
    with conn:
        if conn.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                        (hash_token(password), username)).rowcount == 0:
            raise NotFound(f"utilisateur {username!r} inconnu")


def rotate_token(conn: sqlite3.Connection, username: str) -> str:
    token = secrets.token_urlsafe(32)
    with conn:
        if conn.execute("UPDATE users SET token_hash = ? WHERE username = ?", (hash_token(token), username)).rowcount == 0:
            raise NotFound(f"utilisateur {username!r} inconnu")
    return token


def login(conn: sqlite3.Connection, username: str, password: str) -> tuple[dict, str]:
    """A new session token for the web app."""
    row = conn.execute("SELECT id FROM users WHERE username = ? AND active = 1 AND password_hash = ?",
                       (username, hash_token(password))).fetchone()
    if row is None:
        raise Unauthorized("identifiant ou mot de passe incorrect")
    token = secrets.token_urlsafe(32)
    with conn:
        conn.execute("INSERT INTO sessions (token_hash, user_id) VALUES (?, ?)", (hash_token(token), row["id"]))
    return get_user(conn, row["id"]), token


def logout(conn: sqlite3.Connection, token: str) -> None:
    with conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))


def get_user(conn: sqlite3.Connection, user_id: int) -> dict:
    user = _row(conn.execute(f"SELECT {USER_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone())
    if user is None:
        raise NotFound(f"utilisateur {user_id} inconnu")
    user["active"] = bool(user["active"])
    return user


def user_by_token(conn: sqlite3.Connection, token: str) -> dict | None:
    """The user of a web session token or of an API token (users.py / create_db.py)."""
    h = hash_token(token)
    row = conn.execute(
        f"SELECT {', '.join('u.' + c.strip() for c in USER_COLUMNS.split(','))} FROM users u "
        "LEFT JOIN sessions s ON s.user_id = u.id AND s.token_hash = ? "
        "WHERE u.active = 1 AND (u.token_hash = ? OR s.token_hash IS NOT NULL) LIMIT 1", (h, h)).fetchone()
    return None if row is None else {**dict(row), "active": True}


def list_users(conn: sqlite3.Connection) -> list[dict]:
    users = [dict(r) for r in conn.execute(
        f"SELECT {USER_COLUMNS}, (SELECT COUNT(*) FROM tickets t WHERE t.assignee_id = u.id AND t.status = 'assigned') "
        "AS active_tickets, (SELECT COUNT(*) FROM tickets t WHERE t.resolved_by = u.id) AS resolved_tickets "
        "FROM users u ORDER BY username")]
    for u in users:
        u["active"] = bool(u["active"])
    return users


def update_user(conn: sqlite3.Connection, user_id: int, *, role: str | None = None, active: bool | None = None,
                display_name: str | None = None) -> dict:
    get_user(conn, user_id)
    with conn:
        for column, value in (("role", role), ("active", None if active is None else int(active)),
                              ("display_name", display_name)):
            if value is not None:
                conn.execute(f"UPDATE users SET {column} = ? WHERE id = ?", (value, user_id))
        if active is False:  # a deactivated reviewer's tickets go back to the queue, their sessions end
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            for t in conn.execute("SELECT id FROM tickets WHERE assignee_id = ? AND status = 'assigned'", (user_id,)):
                conn.execute(f"UPDATE tickets SET status = 'open', assignee_id = NULL, updated_at = {_now()} "
                             "WHERE id = ?", (t["id"],))
                log_event(conn, t["id"], None, "released", "compte désactivé")
    return get_user(conn, user_id)


# ---- tickets -------------------------------------------------------------------------------------------

TICKET_SELECT = (
    "SELECT t.*, p.name AS pair_name, p.algo_verdict, p.risk_score, p.clinic_id, c.name AS clinic_name, "
    "f.numero_facture, f.date_fichier, "
    # a file whose layout is broken (check X1) has meaningless amounts: show the form's total instead
    "CASE WHEN EXISTS (SELECT 1 FROM checks x WHERE x.pair_id = p.id AND x.code = 'X1' AND x.status = 'FAIL') "
    " THEN (SELECT montant_total FROM bordereaux b WHERE b.pair_id = p.id) "
    " ELSE COALESCE(f.total_prestations, 0) + COALESCE(f.total_honoraires, 0) END AS amount, "
    "u.username AS assignee, u.display_name AS assignee_name, r.display_name AS resolved_by_name, "
    "(SELECT COUNT(*) FROM checks k WHERE k.pair_id = p.id AND k.status = 'FAIL') AS failed_checks, "
    "(SELECT group_concat(k.code, ',') FROM checks k WHERE k.pair_id = p.id AND k.status = 'FAIL' "
    " AND k.risk = 'fraud' AND k.ocr_suspect = 0) AS fraud_signals "
    "FROM tickets t JOIN pairs p ON p.id = t.pair_id LEFT JOIN factures f ON f.pair_id = p.id "
    "LEFT JOIN clinics c ON c.id = p.clinic_id LEFT JOIN users u ON u.id = t.assignee_id "
    "LEFT JOIN users r ON r.id = t.resolved_by")


# Queue order: questions to managers first, then pairs with anomalies by risk, and the pairs the algorithm found
# CORRECT last (low priority) whatever their score.
QUEUE_ORDER = "t.escalated DESC, p.algo_verdict = 'CORRECT', p.risk_score DESC, p.name"


def list_tickets(conn: sqlite3.Connection, *, status: str | None = None, algo_verdict: str | None = None,
                 assignee_id: int | None = None, escalated: bool | None = None, clinic_id: int | None = None,
                 limit: int = 50, offset: int = 0) -> list[dict]:
    """The review queue, in QUEUE_ORDER."""
    where, params = [], []
    for column, value in (("t.status", status), ("p.algo_verdict", algo_verdict), ("t.assignee_id", assignee_id),
                          ("t.escalated", None if escalated is None else int(escalated)), ("p.clinic_id", clinic_id)):
        if value is not None:
            where.append(f"{column} = ?")
            params.append(value)
    sql = (TICKET_SELECT + (" WHERE " + " AND ".join(where) if where else "")
           + f" ORDER BY {QUEUE_ORDER} LIMIT ? OFFSET ?")
    return [dict(r) for r in conn.execute(sql, (*params, limit, offset))]


def queue_counts(conn: sqlite3.Connection, user: dict) -> dict:
    row = conn.execute(
        "SELECT SUM(status = 'open' AND escalated = 0) AS open, SUM(status = 'open' AND escalated = 1) AS escalated, "
        "SUM(status = 'assigned' AND assignee_id = ?) AS mine, SUM(status = 'resolved') AS resolved, "
        "SUM(status = 'resolved' AND resolved_by = ?) AS resolved_by_me FROM tickets", (user["id"], user["id"])).fetchone()
    return {k: row[k] or 0 for k in row.keys()}


def get_ticket(conn: sqlite3.Connection, ticket_id: int) -> dict:
    ticket = _row(conn.execute(TICKET_SELECT + " WHERE t.id = ?", (ticket_id,)).fetchone())
    if ticket is None:
        raise NotFound(f"dossier {ticket_id} introuvable")
    ticket["events"] = [dict(r) for r in conn.execute(
        "SELECT e.action, e.detail, e.at, u.username AS user, u.display_name AS user_name FROM ticket_events e "
        "LEFT JOIN users u ON u.id = e.user_id "
        "WHERE e.ticket_id = ? ORDER BY e.id", (ticket_id,))]
    ticket["check_reviews"] = [dict(r) for r in conn.execute(
        "SELECT r.check_code, r.outcome, r.comment, r.at, u.username AS user FROM check_reviews r "
        "JOIN users u ON u.id = r.user_id WHERE r.ticket_id = ? ORDER BY r.check_code", (ticket_id,))]
    return ticket


def _ticket_row(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise NotFound(f"dossier {ticket_id} introuvable")
    return row


STATUS_FR = {"open": "en attente", "assigned": "attribué", "resolved": "clôturé"}


def _require_holder(ticket: sqlite3.Row, user: dict) -> None:
    if ticket["status"] != "assigned":
        raise Conflict(f"le dossier {ticket['id']} est {STATUS_FR[ticket['status']]}, il n'est attribué à personne")
    if ticket["assignee_id"] != user["id"] and user["role"] != "admin":
        raise Forbidden(f"le dossier {ticket['id']} est attribué à un autre agent")


def request_assignment(conn: sqlite3.Connection, ticket_id: int, user: dict) -> dict:
    with conn:
        ticket = _ticket_row(conn, ticket_id)
        if ticket["status"] == "resolved":
            raise Conflict(f"le dossier {ticket_id} est déjà clôturé")
        if ticket["status"] == "assigned":
            who = "vous" if ticket["assignee_id"] == user["id"] else "un autre agent"
            raise Conflict(f"le dossier {ticket_id} est déjà attribué à {who}")
        if ticket["escalated"] and user["role"] != "admin":
            raise Forbidden(f"le dossier {ticket_id} attend l'avis d'un manager")
        held = conn.execute("SELECT COUNT(*) FROM tickets WHERE assignee_id = ? AND status = 'assigned'",
                            (user["id"],)).fetchone()[0]
        if held >= MAX_ACTIVE:
            raise Conflict(f"vous avez déjà {held} dossiers en cours (max {MAX_ACTIVE}) : clôturez-en ou "
                           "libérez-en un d'abord")
        # the status guard makes two simultaneous requests for the same ticket safe: only one update matches
        if conn.execute(f"UPDATE tickets SET status = 'assigned', assignee_id = ?, updated_at = {_now()} "
                        "WHERE id = ? AND status = 'open'", (user["id"], ticket_id)).rowcount == 0:
            raise Conflict(f"le dossier {ticket_id} vient d'être pris par quelqu'un d'autre")
        log_event(conn, ticket_id, user["id"], "assigned", "demandé par l'agent")
    return get_ticket(conn, ticket_id)


def claim_next(conn: sqlite3.Connection, user: dict) -> dict:
    """Request the open ticket that matters most (QUEUE_ORDER; escalated ones only for managers)."""
    for _ in range(5):  # another agent may take the same ticket in between: try the next one
        escalated = "" if user["role"] == "admin" else "AND t.escalated = 0"
        row = conn.execute(
            f"SELECT t.id FROM tickets t JOIN pairs p ON p.id = t.pair_id WHERE t.status = 'open' {escalated} "
            f"ORDER BY {QUEUE_ORDER} LIMIT 1").fetchone()
        if row is None:
            raise NotFound("aucun dossier en attente")
        try:
            return request_assignment(conn, row["id"], user)
        except Conflict as e:
            if "vient d'être pris" not in str(e):
                raise
    raise Conflict("la file change trop vite, réessayez")


def escalate(conn: sqlite3.Connection, ticket_id: int, user: dict, comment: str) -> dict:
    """Ask a manager: the ticket returns to the queue, reserved to admins, with the agent's question."""
    if not comment or not comment.strip():
        raise ReviewError("expliquez votre demande au manager")
    with conn:
        ticket = _ticket_row(conn, ticket_id)
        _require_holder(ticket, user)
        conn.execute(f"UPDATE tickets SET status = 'open', assignee_id = NULL, escalated = 1, escalation_comment = ?, "
                     f"updated_at = {_now()} WHERE id = ?", (comment.strip(), ticket_id))
        log_event(conn, ticket_id, user["id"], "escalated", comment.strip())
    return get_ticket(conn, ticket_id)


def release(conn: sqlite3.Connection, ticket_id: int, user: dict, reason: str | None = None) -> dict:
    with conn:
        ticket = _ticket_row(conn, ticket_id)
        _require_holder(ticket, user)
        conn.execute(f"UPDATE tickets SET status = 'open', assignee_id = NULL, updated_at = {_now()} WHERE id = ?",
                     (ticket_id,))
        log_event(conn, ticket_id, user["id"], "released", reason)
    return get_ticket(conn, ticket_id)


def assign(conn: sqlite3.Connection, ticket_id: int, admin: dict, assignee_id: int) -> dict:
    target = get_user(conn, assignee_id)
    if not target["active"]:
        raise Conflict(f"le compte {target['username']} est désactivé")
    with conn:
        ticket = _ticket_row(conn, ticket_id)
        if ticket["status"] == "resolved":
            raise Conflict(f"le dossier {ticket_id} est clôturé : rouvrez-le d'abord")
        conn.execute(f"UPDATE tickets SET status = 'assigned', assignee_id = ?, updated_at = {_now()} WHERE id = ?",
                     (assignee_id, ticket_id))
        log_event(conn, ticket_id, admin["id"], "assigned", f"à {target['username']} par un manager")
    return get_ticket(conn, ticket_id)


def resolve(conn: sqlite3.Connection, ticket_id: int, user: dict, final_verdict: str, category: str,
            comment: str | None = None) -> dict:
    if final_verdict not in CATEGORIES:
        raise ReviewError(f"verdict inconnu : {final_verdict}")
    if category not in CATEGORIES[final_verdict]:
        raise ReviewError(f"avec {final_verdict}, le motif doit être {' ou '.join(CATEGORIES[final_verdict])}")
    with conn:
        ticket = _ticket_row(conn, ticket_id)
        _require_holder(ticket, user)
        algo = conn.execute("SELECT algo_verdict FROM pairs WHERE id = ?", (ticket["pair_id"],)).fetchone()[0]
        if final_verdict != algo and not (comment and comment.strip()):
            raise ReviewError("votre décision contredit l'analyse automatique : justifiez-la dans un commentaire")
        conn.execute(
            f"UPDATE tickets SET status = 'resolved', final_verdict = ?, final_category = ?, final_comment = ?, "
            f"resolved_by = ?, resolved_at = {_now()}, updated_at = {_now()} WHERE id = ?",
            (final_verdict, category, comment, user["id"], ticket_id))
        log_event(conn, ticket_id, user["id"], "resolved", f"{final_verdict} ({category})")
    return get_ticket(conn, ticket_id)


def reopen(conn: sqlite3.Connection, ticket_id: int, admin: dict, reason: str | None = None) -> dict:
    with conn:
        ticket = _ticket_row(conn, ticket_id)
        if ticket["status"] != "resolved":
            raise Conflict(f"le dossier {ticket_id} n'est pas clôturé")
        conn.execute(
            "UPDATE tickets SET status = 'open', assignee_id = NULL, final_verdict = NULL, final_category = NULL, "
            f"final_comment = NULL, resolved_by = NULL, resolved_at = NULL, updated_at = {_now()} WHERE id = ?",
            (ticket_id,))
        log_event(conn, ticket_id, admin["id"], "reopened", reason)
    return get_ticket(conn, ticket_id)


def review_check(conn: sqlite3.Connection, ticket_id: int, user: dict, code: str, outcome: str,
                 comment: str | None = None) -> dict:
    if outcome not in ("confirmed", "dismissed"):
        raise ReviewError("l'avis doit être 'confirmed' ou 'dismissed'")
    with conn:
        ticket = _ticket_row(conn, ticket_id)
        _require_holder(ticket, user)
        if conn.execute("SELECT 1 FROM checks WHERE pair_id = ? AND code = ?", (ticket["pair_id"], code)).fetchone() is None:
            raise NotFound(f"contrôle {code} inconnu pour ce dossier")
        conn.execute(
            "INSERT INTO check_reviews (ticket_id, check_code, user_id, outcome, comment) VALUES (?, ?, ?, ?, ?) "
            f"ON CONFLICT (ticket_id, check_code) DO UPDATE SET user_id = excluded.user_id, outcome = excluded.outcome, "
            f"comment = excluded.comment, at = {_now()}", (ticket_id, code, user["id"], outcome, comment))
        log_event(conn, ticket_id, user["id"], "check_reviewed", f"{code} {outcome}")
    return get_ticket(conn, ticket_id)
