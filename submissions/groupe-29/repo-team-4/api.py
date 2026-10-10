"""HTTP API over the SQLite database of compared (facture, bordereau) pairs, their review tickets and clinics.

Run: uvicorn api:app --reload --port 8000   (database: $INVOICES_DB, default invoices.db; create it with create_db.py)
The web app (web/) talks to it through Vite's /api proxy.

Authentication: "Authorization: Bearer <token>", with a token from POST /auth/login (web sessions) or from
create_db.py --admin / users.py (API tokens). /documents/image also takes ?token=..., since an <img> cannot send
headers. Everything but /health and /auth/login needs a token.

Agents (role "reviewer") take tickets from the queue, read the documents (scan, OCR transcription, B2 file), confirm or
dismiss checks, then resolve the ticket or ask a manager. Managers (role "admin") also see the statistics, handle
escalated tickets, edit clinics, ingest pairs and manage users.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterator, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from pipeline import DEFAULT_FLOW, get_flow, load_bordereau, load_facture, registered_flows, review, stats, store

app = FastAPI(title="Invoice review",
              description="Factures (B2) compared with their bordereaux (OCR), and the human review of each pair.")
# local-only project: any origin may call the API (the web app normally goes through Vite's proxy anyway)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)

Verdict = Literal["CORRECT", "ISSUES"]


@app.exception_handler(review.ReviewError)
def review_error(_: Request, e: review.ReviewError) -> JSONResponse:
    return JSONResponse({"detail": str(e)}, status_code=e.status_code)


_schema_checked = False


def db() -> Iterator[sqlite3.Connection]:
    global _schema_checked
    if not store.DEFAULT_DB.exists():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"la base {store.DEFAULT_DB} n'existe pas : lancez create_db.py")
    conn = store.connect(store.DEFAULT_DB)
    if not _schema_checked:  # bring an older database up to date once per process
        store.create_schema(conn)
        _schema_checked = True
    try:
        yield conn
    finally:
        conn.close()


def _token(credentials: HTTPAuthorizationCredentials | None, query_token: str | None) -> str | None:
    return credentials.credentials if credentials else query_token


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                 token: str | None = Query(None, include_in_schema=False),
                 conn: sqlite3.Connection = Depends(db)) -> dict:
    value = _token(credentials, token)
    user = review.user_by_token(conn, value) if value else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session absente ou expirée",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "réservé aux managers")
    return user


def _pair_or_404(conn: sqlite3.Connection, pair_id: int) -> dict:
    pair = store.get_pair(conn, pair_id)
    if pair is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"dossier {pair_id} introuvable")
    return pair


# ---- general and authentication ------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "database": str(store.DEFAULT_DB), "exists": store.DEFAULT_DB.exists()}


class Credentials(BaseModel):
    username: str
    password: str


@app.post("/auth/login")
def login(body: Credentials, conn: sqlite3.Connection = Depends(db)) -> dict:
    """Opens a web session; send the returned token as "Authorization: Bearer <token>"."""
    user, token = review.login(conn, body.username.strip(), body.password)
    return {"token": token, "user": user}


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
           conn: sqlite3.Connection = Depends(db)) -> None:
    if credentials:
        review.logout(conn, credentials.credentials)


@app.get("/me")
def me(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(db)) -> dict:
    return {**user, "queue": review.queue_counts(conn, user), "max_active": review.MAX_ACTIVE}


@app.get("/flows", dependencies=[Depends(current_user)])
def flows() -> list[dict]:
    return [cls.describe() for cls in registered_flows().values()]


# ---- statistics and clinics ----------------------------------------------------------------------------


@app.get("/stats/overview", dependencies=[Depends(admin_user)])
def overview(conn: sqlite3.Connection = Depends(db)) -> dict:
    return stats.overview(conn)


@app.get("/clinics", dependencies=[Depends(current_user)])
def list_clinics(conn: sqlite3.Connection = Depends(db)) -> list[dict]:
    return stats.clinics(conn)


def _clinic_or_404(conn: sqlite3.Connection, clinic_id: int) -> dict:
    clinic = stats.clinic(conn, clinic_id)
    if clinic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"clinique {clinic_id} introuvable")
    return clinic


@app.get("/clinics/{clinic_id}", dependencies=[Depends(current_user)])
def get_clinic(clinic_id: int, conn: sqlite3.Connection = Depends(db)) -> dict:
    clinic = _clinic_or_404(conn, clinic_id)
    clinic["reports_list"] = [dict(r) for r in conn.execute(
        "SELECT r.id, r.reason, r.comment, r.at, u.username AS user, u.display_name AS user_name "
        "FROM clinic_reports r JOIN users u ON u.id = r.user_id WHERE r.clinic_id = ? ORDER BY r.id DESC",
        (clinic_id,))]
    return clinic


class ClinicPatch(BaseModel):
    name: str | None = None
    city: str | None = None
    postal_code: str | None = None
    region: str | None = None
    caisse: str | None = None
    lat: float | None = None
    lon: float | None = None


@app.patch("/clinics/{clinic_id}", dependencies=[Depends(admin_user)])
def update_clinic(clinic_id: int, body: ClinicPatch, conn: sqlite3.Connection = Depends(db)) -> dict:
    _clinic_or_404(conn, clinic_id)
    changes = body.model_dump(exclude_unset=True)
    if changes:
        with conn:
            conn.execute(f"UPDATE clinics SET {', '.join(f'{k} = ?' for k in changes)} WHERE id = ?",
                         (*changes.values(), clinic_id))
    return _clinic_or_404(conn, clinic_id)


@app.get("/clinics/{clinic_id}/invoices", dependencies=[Depends(current_user)])
def clinic_invoices(clinic_id: int, conn: sqlite3.Connection = Depends(db)) -> list[dict]:
    _clinic_or_404(conn, clinic_id)
    return stats.clinic_invoices(conn, clinic_id)


class ReportIn(BaseModel):
    reason: str = Field(min_length=1)
    comment: str | None = None


@app.post("/clinics/{clinic_id}/reports", status_code=status.HTTP_201_CREATED)
def report_clinic(clinic_id: int, body: ReportIn, user: dict = Depends(current_user),
                  conn: sqlite3.Connection = Depends(db)) -> dict:
    """"Signaler": sends the clinic to the fraud-control service."""
    _clinic_or_404(conn, clinic_id)
    with conn:
        report_id = conn.execute("INSERT INTO clinic_reports (clinic_id, user_id, reason, comment) VALUES (?, ?, ?, ?)",
                                 (clinic_id, user["id"], body.reason, body.comment)).lastrowid
    return dict(conn.execute("SELECT * FROM clinic_reports WHERE id = ?", (report_id,)).fetchone())


@app.get("/reports", dependencies=[Depends(admin_user)])
def list_reports(conn: sqlite3.Connection = Depends(db)) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT r.*, c.name AS clinic_name, c.finess, u.username AS user, u.display_name AS user_name "
        "FROM clinic_reports r JOIN clinics c ON c.id = r.clinic_id JOIN users u ON u.id = r.user_id "
        "ORDER BY r.id DESC")]


# ---- pairs ---------------------------------------------------------------------------------------------


class PairIn(BaseModel):
    name: str = Field(min_length=1, description="unique name; posting an existing name refreshes that pair")
    flow: str = DEFAULT_FLOW
    facture: str | list[str] | dict[str, Any] = Field(
        description="B2 file text, a list of its lines, {'lines': [...]}, or parse_factures_txt.py JSON")
    bordereau: dict[str, Any] = Field(description="the OCR result.json object (needs a 'blocks' list)")


@app.get("/pairs", dependencies=[Depends(current_user)])
def list_pairs(finess: str | None = None, numero_lot: str | None = None, numero_facture: str | None = None,
               status_: Literal["ok", "warning", "error"] | None = Query(None, alias="status"),
               algo_verdict: Verdict | None = None,
               limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
               conn: sqlite3.Connection = Depends(db)) -> list[dict]:
    return store.list_pairs(conn, finess=finess, numero_lot=numero_lot, numero_facture=numero_facture,
                            status=status_, algo_verdict=algo_verdict, limit=limit, offset=offset)


@app.get("/pairs/by-name/{name}", dependencies=[Depends(current_user)])
def get_pair_by_name(name: str, conn: sqlite3.Connection = Depends(db)) -> dict:
    pair_id = store.pair_id_by_name(conn, name)
    if pair_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"aucun dossier nommé {name!r}")
    return store.get_pair(conn, pair_id)


@app.get("/pairs/{pair_id}", dependencies=[Depends(current_user)])
def get_pair(pair_id: int, conn: sqlite3.Connection = Depends(db)) -> dict:
    return _pair_or_404(conn, pair_id)


@app.get("/pairs/{pair_id}/documents/facture", response_class=PlainTextResponse,
         dependencies=[Depends(current_user)])
def facture_document(pair_id: int, conn: sqlite3.Connection = Depends(db)) -> str:
    """The B2 records as received (fixed-width: read it in a monospace font)."""
    docs = store.get_documents(conn, pair_id)
    if docs is None or not docs["facture_raw"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "fichier B2 non disponible pour ce dossier")
    return docs["facture_raw"]


@app.get("/pairs/{pair_id}/documents/ocr", response_class=PlainTextResponse, dependencies=[Depends(current_user)])
def ocr_document(pair_id: int, conn: sqlite3.Connection = Depends(db)) -> str:
    """The OCR transcription, with the ![label](x1,y1,x2,y2) block markers (0-1000 page coordinates)."""
    docs = store.get_documents(conn, pair_id)
    if docs is None or not docs["ocr_raw"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "texte OCR non disponible pour ce dossier")
    return docs["ocr_raw"]


@app.get("/pairs/{pair_id}/documents/image", dependencies=[Depends(current_user)])
def image_document(pair_id: int, conn: sqlite3.Connection = Depends(db)) -> FileResponse:
    """The scanned bordereau."""
    docs = store.get_documents(conn, pair_id)
    if docs is None or not docs["image_path"] or not Path(docs["image_path"]).is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "scan non disponible pour ce dossier")
    return FileResponse(docs["image_path"], headers={"Cache-Control": "private, max-age=3600"})


@app.post("/pairs", status_code=status.HTTP_201_CREATED)
def create_pair(body: PairIn, conn: sqlite3.Connection = Depends(db), _: dict = Depends(admin_user)) -> dict:
    """Run the flow on the two documents and store the result; the pair gets (or keeps) its review ticket."""
    try:
        flow = get_flow(body.flow)
        facture, bordereau = load_facture(body.facture), load_bordereau(body.bordereau)
    except (KeyError, ValueError) as e:
        raise HTTPException(422, str(e.args[0])) from None
    raw = body.facture if isinstance(body.facture, str) else "\n".join(facture["lines"]) if "lines" in facture else None
    ctx = flow.run(facture, bordereau)
    pair_id = store.save(conn, body.name, flow.name, ctx, store.Documents(facture_raw=raw, ocr_raw=bordereau.get("raw")))
    return store.get_pair(conn, pair_id)


@app.delete("/pairs/{pair_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pair(pair_id: int, conn: sqlite3.Connection = Depends(db), _: dict = Depends(admin_user)) -> None:
    """Deletes the pair with its ticket and review history."""
    if not store.delete_pair(conn, pair_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"dossier {pair_id} introuvable")


# ---- tickets -------------------------------------------------------------------------------------------


class Resolution(BaseModel):
    final_verdict: Verdict
    category: Literal["none", "ocr_error", "billing_error", "suspected_fraud"] = Field(
        description="CORRECT: none | ocr_error (the algorithm was misled by the OCR); "
                    "ISSUES: billing_error | suspected_fraud")
    comment: str | None = Field(None, description="required when the verdict differs from the algorithm's")


class CheckReview(BaseModel):
    outcome: Literal["confirmed", "dismissed"] = Field(description="confirmed: the check's result is right")
    comment: str | None = None


class Reason(BaseModel):
    reason: str | None = None


class Escalation(BaseModel):
    comment: str = Field(min_length=1)


class Assignment(BaseModel):
    user_id: int


@app.get("/tickets")
def list_tickets(status_: Literal["open", "assigned", "resolved"] | None = Query(None, alias="status"),
                 algo_verdict: Verdict | None = None, mine: bool = False, escalated: bool | None = None,
                 clinic_id: int | None = None,
                 limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                 user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(db)) -> list[dict]:
    """The review queue, escalated first then highest risk. mine=true: only the tickets assigned to you."""
    return review.list_tickets(conn, status=status_, algo_verdict=algo_verdict,
                               assignee_id=user["id"] if mine else None, escalated=escalated, clinic_id=clinic_id,
                               limit=limit, offset=offset)


@app.post("/tickets/claim-next")
def claim_next(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(db)) -> dict:
    """Request the open ticket that matters most (managers get escalated tickets first)."""
    return review.claim_next(conn, user)


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, _: dict = Depends(current_user), conn: sqlite3.Connection = Depends(db)) -> dict:
    """The ticket, its history and check reviews, and the full pair (checks, extracted data, issues, clinic)."""
    ticket = review.get_ticket(conn, ticket_id)
    pair = _pair_or_404(conn, ticket["pair_id"])
    base = f"/pairs/{pair['id']}/documents"
    return {**ticket, "pair": pair,
            "documents": {"facture": f"{base}/facture", "ocr": f"{base}/ocr", "image": f"{base}/image"}}


@app.post("/tickets/{ticket_id}/request")
def request_ticket(ticket_id: int, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(db)) -> dict:
    """Ask to be assigned an open ticket; granted unless someone holds it or you hold too many already."""
    return review.request_assignment(conn, ticket_id, user)


@app.post("/tickets/{ticket_id}/release")
def release_ticket(ticket_id: int, body: Reason | None = None, user: dict = Depends(current_user),
                   conn: sqlite3.Connection = Depends(db)) -> dict:
    return review.release(conn, ticket_id, user, body.reason if body else None)


@app.post("/tickets/{ticket_id}/escalate")
def escalate_ticket(ticket_id: int, body: Escalation, user: dict = Depends(current_user),
                    conn: sqlite3.Connection = Depends(db)) -> dict:
    """Ask a manager's opinion: the ticket goes back to the queue, reserved to managers."""
    return review.escalate(conn, ticket_id, user, body.comment)


@app.put("/tickets/{ticket_id}/checks/{code}")
def review_check(ticket_id: int, code: str, body: CheckReview, user: dict = Depends(current_user),
                 conn: sqlite3.Connection = Depends(db)) -> dict:
    return review.review_check(conn, ticket_id, user, code, body.outcome, body.comment)


@app.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id: int, body: Resolution, user: dict = Depends(current_user),
                   conn: sqlite3.Connection = Depends(db)) -> dict:
    """Give the final word on the pair."""
    return review.resolve(conn, ticket_id, user, body.final_verdict, body.category, body.comment)


@app.post("/tickets/{ticket_id}/assign")
def assign_ticket(ticket_id: int, body: Assignment, admin: dict = Depends(admin_user),
                  conn: sqlite3.Connection = Depends(db)) -> dict:
    return review.assign(conn, ticket_id, admin, body.user_id)


@app.post("/tickets/{ticket_id}/reopen")
def reopen_ticket(ticket_id: int, body: Reason | None = None, admin: dict = Depends(admin_user),
                  conn: sqlite3.Connection = Depends(db)) -> dict:
    return review.reopen(conn, ticket_id, admin, body.reason if body else None)


# ---- users ---------------------------------------------------------------------------------------------


class UserIn(BaseModel):
    username: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str | None = None
    role: Literal["reviewer", "admin"] = "reviewer"
    password: str | None = None


class UserPatch(BaseModel):
    display_name: str | None = None
    role: Literal["reviewer", "admin"] | None = None
    active: bool | None = None


@app.get("/users", dependencies=[Depends(admin_user)])
def list_users(conn: sqlite3.Connection = Depends(db)) -> list[dict]:
    return review.list_users(conn)


@app.post("/users", status_code=status.HTTP_201_CREATED, dependencies=[Depends(admin_user)])
def create_user(body: UserIn, conn: sqlite3.Connection = Depends(db)) -> dict:
    """Creates the account; the returned API token is shown only once."""
    user, token = review.create_user(conn, body.username, body.display_name, body.role, body.password)
    return {**user, "token": token}


@app.patch("/users/{user_id}", dependencies=[Depends(admin_user)])
def update_user(user_id: int, body: UserPatch, conn: sqlite3.Connection = Depends(db)) -> dict:
    """Deactivating a user ends their sessions and returns their assigned tickets to the queue."""
    return review.update_user(conn, user_id, role=body.role, active=body.active, display_name=body.display_name)
