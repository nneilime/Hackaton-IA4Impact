"""API métier iMSA Sentinel (FastAPI). Toutes les données servies proviennent du corpus autorisé
ou des actions enregistrées des utilisateurs de l'application."""
from __future__ import annotations

import json
import logging
import threading
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ENGINE_VERSION, RULESET_VERSION
from .assistant import answer as assistant_answer, summarize_case
from .compare import compare_images, diff_overlay
from .config import CORPUS_DIR, DATA_DIR, JPG_SUBDIR, STATIC_DIR, TXT_SUBDIR
from .imports import ImportError_, create_import, delete_import, import_pairs
from .corpus import corpus_root
from .db import CASE_STATUSES, DB, now as now_iso
from .triage import triage_case
from .normalize import amount_str
from .pipeline import all_pairs, analyze_all, analyze_case, init_corpus, reanalyze_case, sync_cases
from .reports import case_report_json, case_report_pdf, results_csv
from .privacy import mask_result_values, mask_text
from .rules import CATEGORIES, RULES
from . import finance, jobs
from .corrections import CorrectionError, check as check_correction
from .zones import ZONE_IDS, ZONE_INFO

log = logging.getLogger("sentinel")
db: Optional[DB] = None


@asynccontextmanager
async def lifespan(_app):
    global db
    db = DB()
    threading.Thread(target=_bootstrap, daemon=True).start()
    yield


import os
PRODUCTION = os.environ.get("SENTINEL_MODE", "").lower() == "production"
app = FastAPI(title="iMSA Sentinel", version=ENGINE_VERSION, docs_url="/api/docs", redoc_url=None, lifespan=lifespan)
STATE = {"phase": "démarrage", "done": 0, "total": 0, "current": None, "error": None, "warning": None}
COOKIE = "sentinel_session"


# =============================================================================== démarrage
def _progress(done, total, cid):
    STATE.update(done=done, total=total, current=cid)


def _bootstrap():
    try:
        STATE["phase"] = "initialisation du corpus"
        try:
            rep = init_corpus(db)
            db.audit(None, "corpus.init", None, rep)
        except FileNotFoundError:
            # Le corpus n'est pas versionné (données de santé) : l'utilisateur dépose l'archive autorisée.
            STATE["warning"] = ("Corpus absent : déposez l'archive autorisée « General-main.zip » dans le dossier "
                                "data/ du projet, puis relancez l'application. Les imports restent possibles.")
            db.audit(None, "corpus.absent", None, None)
        STATE["phase"] = "synchronisation des dossiers"

        def run(progress):
            def p(done, total, cid):
                _progress(done, total, cid)
                progress(done, total, cid)
            return sync_cases(db, "démarrage", progress=p)
        job = jobs.submit(db, "synchronisation", "corpus", run, "système", background=False)
        if job["status"] == "erreur":
            raise RuntimeError(job.get("error"))
        db.meta_set("last_versions", [ENGINE_VERSION, RULESET_VERSION])
        from .validation import seed_assisted_review
        seed_assisted_review(db)
        db.audit(None, "synchronisation", None, {"job": job["id"], "resultat": job.get("message")})
        STATE["phase"] = "prêt"
    except Exception as e:  # noqa
        log.exception("bootstrap")
        STATE.update(phase="erreur", error=f"{type(e).__name__}: {e}")


# =============================================================================== sécurité
def current_user(request: Request):
    u = db.session_user(request.cookies.get(COOKIE))
    if not u:
        raise HTTPException(401, "Authentification requise")
    return u


def require(*roles):
    def dep(u=Depends(current_user)):
        if u["role"] not in roles:
            raise HTTPException(403, "Action non autorisée pour votre rôle")
        return u
    return dep


WRITE_ROLES = ("agent", "superviseur", "admin")


def _can_see(u, case) -> bool:
    """Contrôle d'accès côté serveur. Gestionnaire, administrateur et auditeur voient tous les dossiers ;
    un agent voit les dossiers non affectés et les siens — sauf les dossiers importés (simulations) d'un autre
    agent, qui restent privés tant qu'un gestionnaire ne les a pas affectés."""
    if u["role"] in ("superviseur", "admin", "auditeur"):
        return True
    if case.get("assigned_to") == u["id"]:
        return True
    if case.get("assigned_to") is None:
        if case.get("source") == "import" or case.get("family") == "Import":
            return case.get("created_by") == u["username"]
        return True
    return False


def _active(c) -> bool:
    return (c.get("source_status") or "ok") == "ok"


def _case_or_404(cid, u):
    c = db.one("SELECT * FROM cases WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404, "Dossier introuvable")
    if not _can_see(u, c):
        raise HTTPException(403, "Dossier affecté à un autre agent")
    return c


def _busy(fn):
    """Traduit un refus de concurrence (verrou, maintenance) en réponse 409 explicite."""
    try:
        return fn()
    except jobs.Busy as e:
        raise HTTPException(409, str(e))


def mask_nir(v: Optional[str]) -> Optional[str]:
    if not v:
        return v
    return v[:5] + "•" * max(0, len(v) - 5)


# =============================================================================== modèles
class SetupIn(BaseModel):
    admin_username: str = Field(min_length=2, max_length=40)
    admin_display_name: str = Field(min_length=2, max_length=80)
    admin_password: str = Field(min_length=8, max_length=200)
    create_demo_accounts: bool = False
    demo_password: Optional[str] = Field(default=None, max_length=200)


class LoginIn(BaseModel):
    username: str
    password: str


class DecisionIn(BaseModel):
    kind: str
    rule_id: Optional[str] = None
    value: Optional[str] = None
    comment: Optional[str] = Field(default=None, max_length=4000)


class CorrectionIn(BaseModel):
    target: str
    corrected: str = Field(min_length=1, max_length=200)
    comment: Optional[str] = Field(default=None, max_length=2000)


class AssignIn(BaseModel):
    user_id: Optional[int] = None


class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    display_name: str = Field(min_length=2, max_length=80)
    role: str
    password: str = Field(min_length=8, max_length=200)


class AskIn(BaseModel):
    question: str = Field(max_length=500)


class CompareIn(BaseModel):
    a: str
    b: str


# =============================================================================== état / authentification
_ENGINES = None


@app.get("/api/status")
def status():
    users = db.one("SELECT COUNT(*) AS n FROM users")["n"] if db else 0
    global _ENGINES
    if _ENGINES is None:
        try:
            from .ocr.engine import available_engines
            _ENGINES = available_engines()
        except Exception:  # noqa
            _ENGINES = {}
    return {"state": STATE, "needs_setup": users == 0, "engine_version": ENGINE_VERSION,
            "ruleset_version": RULESET_VERSION, "ocr": _ENGINES, "production": PRODUCTION}


@app.post("/api/setup")
def setup(body: SetupIn, response: Response):
    if db.one("SELECT COUNT(*) AS n FROM users")["n"] > 0:
        raise HTTPException(409, "L'application est déjà initialisée")
    if body.create_demo_accounts and PRODUCTION:
        raise HTTPException(400, "Comptes de démonstration désactivés en mode production (SENTINEL_MODE=production).")
    try:
        uid = db.create_user(body.admin_username, body.admin_display_name, "admin", body.admin_password)
        if body.create_demo_accounts:
            pw = body.demo_password or body.admin_password
            for un, dn, role in (("agent1", "Agent de contrôle 1", "agent"), ("agent2", "Agent de contrôle 2", "agent"),
                                 ("superviseur", "Gestionnaire de caisse", "superviseur"),
                                 ("auditeur", "Auditeur (lecture seule)", "auditeur")):
                db.create_user(un, dn, role, pw, is_demo=True)
    except ValueError as e:
        raise HTTPException(400, str(e))
    u = db.one("SELECT id, username, display_name, role FROM users WHERE id=?", (uid,))
    db.audit(u, "setup", None, {"demo_accounts": body.create_demo_accounts})
    token = db.new_session(uid)
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict")
    return {"user": u}


@app.post("/api/login")
def login(body: LoginIn, response: Response):
    u = db.check_password(body.username, body.password)
    if not u:
        db.audit(None, "login.echec", body.username[:40])
        raise HTTPException(401, "Identifiant ou mot de passe incorrect")
    token = db.new_session(u["id"])
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict")
    user = {k: u[k] for k in ("id", "username", "display_name", "role")}
    db.audit(user, "login")
    return {"user": user}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    t = request.cookies.get(COOKIE)
    if t:
        db.drop_session(t)
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(u=Depends(current_user)):
    return u


@app.get("/api/users")
def users(u=Depends(require("superviseur", "admin", "auditeur"))):
    return db.users()


@app.post("/api/users")
def create_user(body: UserIn, u=Depends(require("admin"))):
    try:
        uid = db.create_user(body.username, body.display_name, body.role, body.password)
    except Exception as e:
        raise HTTPException(400, str(e))
    db.audit(u, "utilisateur.creation", body.username, {"role": body.role})
    return {"id": uid}


# =============================================================================== dossiers
def _case_list_row(c, users_by_id):
    return {**{k: c.get(k) for k in ("id", "family", "finess", "establishment", "invoice_no", "billed_cents", "n_anomalies",
                                     "n_nv", "n_errors", "n_observations", "state", "net_gap_cents", "act_gap_cents",
                                     "priority_score", "status", "pairing_status", "priority_override", "analyzed_at",
                                     "source", "label", "source_status")},
            "priority_reasons": json.loads(c["priority_reasons"] or "[]"),
            "assigned_to": c["assigned_to"],
            "assigned_name": users_by_id.get(c["assigned_to"], {}).get("display_name") if c["assigned_to"] else None,
            "anomaly_rules": [r["rule_id"] for r in db.q("SELECT rule_id FROM check_results WHERE case_id=? AND status='ANOMALIE' ORDER BY rule_id", (c["id"],))]}


@app.get("/api/cases")
def list_cases(u=Depends(current_user)):
    users_by_id = {x["id"]: x for x in db.users()}
    rows = db.q("SELECT * FROM cases ORDER BY id")
    zst = _zone_status_index()
    return [dict(_case_list_row(c, users_by_id), zones=zst.get(c["id"], {})) for c in rows if _active(c) and _can_see(u, c)]


def _payload(cid) -> dict:
    a = db.one("SELECT payload FROM analyses WHERE case_id=?", (cid,))
    return json.loads(a["payload"]) if a else {}


def _decisions(cid) -> list:
    return db.q("SELECT d.*, us.display_name, us.username FROM decisions d LEFT JOIN users us ON us.id=d.user_id "
                "WHERE case_id=? ORDER BY d.id", (cid,))


_ZCACHE: dict = {}


def _zone_status_index() -> dict:
    """Statut des 15 zones de chaque dossier (lu dans l'analyse enregistrée ; mis en cache par empreinte)."""
    out = {}
    for r in db.q("SELECT case_id, analyzed_at FROM analyses"):
        key = (r["case_id"], r["analyzed_at"])
        if key not in _ZCACHE:
            p = _payload(r["case_id"])
            _ZCACHE[key] = {z["zone_id"]: z["status"] for z in p.get("zones", [])}
        out[r["case_id"]] = _ZCACHE[key]
    return out


@app.get("/api/cases/{cid}")
def get_case(cid: str, u=Depends(current_user)):
    c = _case_or_404(cid, u)
    payload = _payload(cid)
    decisions = _decisions(cid)
    users_by_id = {x["id"]: x for x in db.users()}
    db.audit(u, "dossier.consultation", cid)
    if not c.get("opened_at"):
        with db.tx() as con:
            con.execute("UPDATE cases SET opened_at=? WHERE id=? AND opened_at IS NULL", (now_iso(), cid))
    fin = finance.case_finance(payload.get("results", []), decisions, c.get("billed_cents")) if payload.get("results") else None
    job = jobs.active_job(db, target=cid)
    return {"case": _case_list_row(c, users_by_id), "analysis": payload, "decisions": list(reversed(decisions)),
            "statuses": CASE_STATUSES, "finance": fin, "job": job,
            "triage": (triage_case(payload) + _homologue_signal(cid, payload)) if payload.get("results") else []}


def _homologue_signal(cid: str, payload: dict) -> list:
    """Le bordereau porte-t-il le n° de facture du FICHIER d'un autre dossier ? (pièce non homologue ou
    réutilisée). Signal de priorité documentaire, jamais une conclusion."""
    if (payload.get("pairing") or {}).get("status") == "confirmé":
        return []
    z4 = ((payload.get("extraction") or {}).get("fields") or {}).get("Z4") or {}
    val = str(z4.get("value") or "").lstrip("0")
    if not val or z4.get("agreement") not in ("concordant", "majoritaire", "corrigé"):
        return []
    others = [c["id"] for c in db.q("SELECT id, invoice_no FROM cases WHERE id != ?", (cid,))
              if c["invoice_no"] and str(c["invoice_no"]).strip().lstrip("0") == val]
    if not others:
        return []
    return [{"id": "homologue", "type": "identification", "title": "Bordereau d'un autre dossier ?",
             "hypothesis": f"Le n° de facture lu sur ce bordereau est celui du fichier du dossier {', '.join(others)}. "
                           "Le bordereau pourrait appartenir à une autre facture (pièce non homologue ou réutilisée).",
             "rules": [r for r in ("R04", "R05") if any(x["rule_id"] == r and x["status"] == "ANOMALIE"
                                                      for x in payload.get("results", []))],
             "zones": ["Z4", "Z5"], "evidence": [f"Rapprochement des documents : {(payload.get('pairing') or {}).get('status')}"],
             "first_check": f"Comparez avec le dossier {others[0]} (menu Comparaison d'images).",
             "avertissement": "Hypothèse d'aide au tri : chaque règle reste vérifiée et décidée individuellement."}]


def _case_file(c, kind: str) -> Path:
    """Chemin d'un document du dossier (stocké relativement à data/), contrôlé contre toute sortie."""
    rel = c["jpg_path" if kind == "jpg" else "txt_path"]
    p = (DATA_DIR / rel).resolve()
    if not p.exists():   # ancien format (nom seul) : corpus officiel
        p = (corpus_root(CORPUS_DIR) / (JPG_SUBDIR if kind == "jpg" else TXT_SUBDIR) / Path(rel).name).resolve()
    if DATA_DIR.resolve() not in p.parents or not p.is_file():
        raise HTTPException(404, "Document introuvable")
    return p


def _normalized_jpeg(c) -> Optional[bytes]:
    """Image redressée (scan incliné) dans le repère des zones ; None si l'image d'origine convient."""
    layout = ((_payload(c["id"]).get("extraction") or {}).get("layout") or {})
    if not layout.get("deskew_deg"):
        return None
    import cv2
    import numpy as np
    from .ocr.layout import normalized_image
    img = cv2.imdecode(np.fromfile(str(_case_file(c, "jpg")), np.uint8), cv2.IMREAD_COLOR)
    out = normalized_image(img, dict(layout, rotation=0))      # le retournement à 180° reste fait par l'affichage
    return cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes()


@app.get("/api/cases/{cid}/image")
def case_image(cid: str, u=Depends(current_user)):
    c = _case_or_404(cid, u)
    p = _case_file(c, "jpg")
    norm = _normalized_jpeg(c)
    if norm is not None:
        return Response(norm, media_type="image/jpeg", headers={"Cache-Control": "private, no-cache"})
    return FileResponse(p, media_type="image/png" if p.suffix.lower() == ".png" else "image/jpeg",
                        headers={"Cache-Control": "private, max-age=3600"})


@app.get("/api/cases/{cid}/crop")
def case_crop(cid: str, rule: Optional[str] = None, zone: Optional[str] = None, u=Depends(current_user)):
    """Agrandissement de la région du bordereau qui fonde un contrôle (ou d'une zone) : la preuve visuelle."""
    import cv2
    import numpy as np
    from .ocr.layout import normalized_image
    c = _case_or_404(cid, u)
    pl = _payload(cid)
    boxes = []
    if rule:
        r = next((x for x in pl.get("results", []) if x["rule_id"] == rule), None)
        if not r:
            raise HTTPException(404, "Contrôle inconnu")
        boxes = [x["box"] for x in r.get("img_refs") or [] if x.get("box")]
        zones = r.get("zones") or []
    else:
        zones = [zone] if zone else []
    if not boxes:
        zmap = {z["zone_id"]: z for z in pl.get("zones", [])}
        boxes = [reg["box"] for z in zones for reg in (zmap.get(z) or {}).get("regions", [])]
    if not boxes:
        raise HTTPException(404, "Aucune région localisée")
    img = cv2.imdecode(np.fromfile(str(_case_file(c, "jpg")), np.uint8), cv2.IMREAD_COLOR)
    img = normalized_image(img, (pl.get("extraction") or {}).get("layout") or {})
    H, W = img.shape[:2]
    x0, y0 = max(0, min(b[0] for b in boxes) - 20), max(0, min(b[1] for b in boxes) - 20)
    x1, y1 = min(W, max(b[2] for b in boxes) + 20), min(H, max(b[3] for b in boxes) + 20)
    crop = img[y0:y1, x0:x1].copy()
    for b in boxes:
        cv2.rectangle(crop, (b[0] - x0, b[1] - y0), (b[2] - x0, b[3] - y0), (38, 38, 220), 2)
    k = min(3.0, 1100 / max(1, crop.shape[1]))
    if k > 1.05:
        crop = cv2.resize(crop, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    return Response(cv2.imencode(".png", crop)[1].tobytes(), media_type="image/png",
                    headers={"Cache-Control": "private, no-cache"})


@app.get("/api/cases/{cid}/txt")
def case_txt(cid: str, u=Depends(current_user)):
    c = _case_or_404(cid, u)
    p = _case_file(c, "txt")
    return PlainTextResponse(p.read_bytes().decode("latin-1"))


def _check_write(u, c):
    if u["role"] == "agent" and c["assigned_to"] not in (None, u["id"]):
        raise HTTPException(403, "Dossier affecté à un autre agent")


DECISION_KINDS = {"examen", "confirmation", "faux_positif", "revue_complementaire", "commentaire", "statut",
                  "escalade", "priorite", "decision_motivee", "annulation", "omission"}


@app.post("/api/cases/{cid}/decisions")
def add_decision(cid: str, body: DecisionIn, u=Depends(require(*WRITE_ROLES))):
    c = _case_or_404(cid, u)
    _check_write(u, c)
    if body.kind not in DECISION_KINDS:
        raise HTTPException(400, "Type de décision inconnu")
    if body.kind in ("priorite",) and u["role"] not in ("superviseur", "admin"):
        raise HTTPException(403, "Réservé au gestionnaire")
    if body.kind == "statut":
        if body.value not in CASE_STATUSES:
            raise HTTPException(400, "Statut inconnu")
        if body.value == "Clôturé" and u["role"] not in ("superviseur", "admin"):
            raise HTTPException(403, "La clôture est réservée au gestionnaire")
    if body.kind in ("faux_positif", "decision_motivee", "escalade", "annulation", "omission") and not (body.comment or "").strip():
        raise HTTPException(400, "Un commentaire motivé est obligatoire pour cette décision")
    if body.rule_id and body.rule_id not in {r.id for r in RULES}:
        raise HTTPException(400, "Règle inconnue")
    if body.kind in ("confirmation", "faux_positif", "omission") and not body.rule_id:
        raise HTTPException(400, "Cette décision doit porter sur une règle")
    if body.kind in ("confirmation", "faux_positif"):
        res = next((r for r in _payload(cid).get("results", []) if r["rule_id"] == body.rule_id), None)
        if not res or res["status"] != "ANOMALIE":
            raise HTTPException(400, "Seule une règle actuellement en anomalie peut être confirmée ou déclarée faux positif")
    if body.kind == "annulation":
        target = db.one("SELECT * FROM decisions WHERE id=? AND case_id=?", (str(body.value or "0"), cid)) \
            if str(body.value or "").isdigit() else None
        if not target:
            raise HTTPException(400, "Décision à annuler introuvable dans ce dossier")
        if target["user_id"] != u["id"] and u["role"] not in ("superviseur", "admin"):
            raise HTTPException(403, "Seul l'auteur de la décision ou un gestionnaire peut l'annuler")
        body.rule_id = target["rule_id"]
    with db.tx() as con:
        con.execute("INSERT INTO decisions (case_id, rule_id, kind, value, comment, user_id, created_at) VALUES (?,?,?,?,?,?,datetime('now','localtime'))",
                    (cid, body.rule_id, body.kind, body.value, body.comment, u["id"]))
        new_status = None
        if body.kind == "statut":
            new_status = body.value
        elif body.kind == "escalade":
            new_status = "Revue complémentaire nécessaire"
        elif body.kind == "revue_complementaire":
            new_status = "Revue complémentaire nécessaire"
        elif body.kind == "examen" and c["status"] == "À contrôler":
            new_status = "En analyse"
        if new_status:
            con.execute("UPDATE cases SET status=? WHERE id=?", (new_status, cid))
            if new_status == "Clôturé":
                con.execute("UPDATE cases SET closed_at=? WHERE id=?", (now_iso(), cid))
        if body.kind == "priorite":
            con.execute("UPDATE cases SET priority_override=? WHERE id=?", (body.value, cid))
        if c["assigned_to"] is None and u["role"] == "agent":
            con.execute("UPDATE cases SET assigned_to=? WHERE id=?", (u["id"], cid))
    db.audit(u, f"decision.{body.kind}", cid, body.model_dump())
    return {"ok": True}


@app.post("/api/cases/{cid}/assign")
def assign(cid: str, body: AssignIn, u=Depends(require("superviseur", "admin", "agent"))):
    c = _case_or_404(cid, u)
    if u["role"] == "agent" and body.user_id not in (u["id"], None):
        raise HTTPException(403, "Un agent ne peut s'affecter que lui-même")
    if u["role"] == "agent" and c["assigned_to"] not in (None, u["id"]):
        raise HTTPException(403, "Dossier affecté à un autre agent")
    with db.tx() as con:
        con.execute("UPDATE cases SET assigned_to=? WHERE id=?", (body.user_id, cid))
        con.execute("INSERT INTO decisions (case_id, kind, value, user_id, created_at) VALUES (?,?,?,?,datetime('now','localtime'))",
                    (cid, "affectation", str(body.user_id) if body.user_id else "aucun", u["id"]))
    db.audit(u, "dossier.affectation", cid, {"user_id": body.user_id})
    return {"ok": True}


def _statuses(payload) -> dict:
    return {r["rule_id"]: r["status"] for r in payload.get("results", [])}


def _zstatuses(payload) -> dict:
    return {z["zone_id"]: z["status"] for z in payload.get("zones", [])}


@app.post("/api/cases/{cid}/corrections")
def add_correction(cid: str, body: CorrectionIn, u=Depends(require(*WRITE_ROLES))):
    """Correction (ou validation) d'une lecture : validée côté serveur, enregistrée avec son effet (règles et
    zones recalculées), puis le dossier est réanalysé sous verrou."""
    c = _case_or_404(cid, u)
    _check_write(u, c)
    if jobs.active_job(db, target=cid):
        raise HTTPException(409, "Une analyse de ce dossier est en cours : réessayez lorsqu'elle sera terminée.")
    before = _payload(cid)
    if not before.get("extraction"):
        raise HTTPException(409, "Analyse indisponible pour ce dossier")
    try:
        chk = check_correction(before["extraction"], body.target, body.corrected)
    except CorrectionError as e:
        raise HTTPException(400, str(e))

    def do():
        with jobs.operation():
            with db.tx() as con:
                con.execute("UPDATE corrections SET active=0 WHERE case_id=? AND target=?", (cid, body.target))
                cur = con.execute(
                    "INSERT INTO corrections (case_id, target, original, corrected, comment, user_id, created_at, kind) "
                    "VALUES (?,?,?,?,?,?,datetime('now','localtime'),?)",
                    (cid, body.target, json.dumps(chk["original"], ensure_ascii=False) if not isinstance(chk["original"], str)
                     else chk["original"], body.corrected.strip(), body.comment, u["id"], chk["kind"]))
                corr_id = cur.lastrowid
            after = reanalyze_case(db, cid)
            effect = {"regles": {k: [v, _statuses(after).get(k)] for k, v in _statuses(before).items() if _statuses(after).get(k) != v},
                      "zones": {k: [v, _zstatuses(after).get(k)] for k, v in _zstatuses(before).items() if _zstatuses(after).get(k) != v}}
            with db.tx() as con:
                con.execute("UPDATE corrections SET effect=? WHERE id=?", (json.dumps(effect, ensure_ascii=False), corr_id))
            return effect
    effect = _busy(do)
    db.audit(u, f"extraction.{chk['kind']}", cid, {"target": body.target, "original": chk["original"],
                                                     "corrected": body.corrected, "effet": effect})
    return {"ok": True, "kind": chk["kind"], "effect": effect}


@app.delete("/api/cases/{cid}/corrections/{corr_id}")
def cancel_correction(cid: str, corr_id: int, u=Depends(require(*WRITE_ROLES))):
    c = _case_or_404(cid, u)
    _check_write(u, c)
    if not db.one("SELECT id FROM corrections WHERE id=? AND case_id=? AND active=1", (corr_id, cid)):
        raise HTTPException(404, "Correction introuvable ou déjà annulée")

    def do():
        with jobs.operation():
            with db.tx() as con:
                con.execute("UPDATE corrections SET active=0 WHERE id=? AND case_id=?", (corr_id, cid))
            reanalyze_case(db, cid)
    _busy(do)
    db.audit(u, "extraction.correction_annulee", cid, {"id": corr_id})
    return {"ok": True}


@app.post("/api/cases/{cid}/reanalyze")
def reanalyze_endpoint(cid: str, u=Depends(require(*WRITE_ROLES))):
    """Réanalyse d'un dossier en tâche de fond (idempotente : un double-clic renvoie le traitement en cours)."""
    c = _case_or_404(cid, u)
    _check_write(u, c)
    job = jobs.submit(db, "reanalyse", cid, lambda progress: reanalyze_case(db, cid) and {"dossier": cid}, u["username"])
    db.audit(u, "dossier.reanalyse", cid, {"job": job["id"]})
    return job


@app.post("/api/cases/{cid}/activity")
def activity(cid: str, body: dict, u=Depends(current_user)):
    """Temps de travail ACTIF : l'interface n'envoie un signal que si l'onglet est visible et qu'une interaction
    a eu lieu dans la minute ; un dossier laissé ouvert pendant une pause ne compte pas."""
    _case_or_404(cid, u)
    sec = max(0, min(60, int(body.get("active_seconds") or 0)))
    if sec:
        day = now_iso()[:10]
        with db.tx() as con:
            con.execute("INSERT INTO activity (case_id, user_id, day, active_s, first_seen, last_seen) VALUES (?,?,?,?,?,?) "
                        "ON CONFLICT(case_id, user_id, day) DO UPDATE SET active_s=active_s+excluded.active_s, "
                        "last_seen=excluded.last_seen", (cid, u["id"], day, sec, now_iso(), now_iso()))
    return {"ok": True}


@app.post("/api/cases/{cid}/ask")
def ask(cid: str, body: AskIn, u=Depends(current_user)):
    _case_or_404(cid, u)
    a = json.loads(db.one("SELECT payload FROM analyses WHERE case_id=?", (cid,))["payload"])
    return assistant_answer(a, body.question)


@app.get("/api/cases/{cid}/summary")
def case_summary(cid: str, u=Depends(current_user)):
    _case_or_404(cid, u)
    a = json.loads(db.one("SELECT payload FROM analyses WHERE case_id=?", (cid,))["payload"])
    return summarize_case(a)


@app.get("/api/cases/{cid}/report.{fmt}")
def report(cid: str, fmt: str, u=Depends(current_user)):
    c = _case_or_404(cid, u)
    a = json.loads(db.one("SELECT payload FROM analyses WHERE case_id=?", (cid,))["payload"])
    decisions = db.q("SELECT d.*, us.display_name, us.username FROM decisions d LEFT JOIN users us ON us.id=d.user_id "
                     "WHERE case_id=? ORDER BY d.id", (cid,))
    db.audit(u, f"rapport.{fmt}", cid)
    if fmt == "json":
        return Response(case_report_json(a, decisions), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="rapport_{cid}.json"'})
    if fmt == "pdf":
        try:
            jpg = _case_file(c, "jpg")
        except HTTPException:
            jpg = None
        return Response(case_report_pdf(a, decisions, c, jpg), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="rapport_{cid}.pdf"'})
    raise HTTPException(404)


@app.get("/api/export/results.csv")
def export_csv(u=Depends(require("superviseur", "admin", "auditeur", "agent"))):
    rows = []
    for c in db.q("SELECT * FROM cases ORDER BY id"):
        if not _active(c) or not _can_see(u, c):
            continue
        a = _payload(c["id"])
        for r in a.get("results", []):
            rows.append([c["id"], c["family"], c["status"], r["rule_id"], r["title"], r["status"],
                         mask_text(r.get("jpg_value") or ""), mask_text(r.get("txt_value") or ""),
                         (r.get("gap") or {}).get("amount_cents") or "",
                         (r.get("uncertainty") or {}).get("level", "") if r.get("uncertainty") else "",
                         mask_text(r.get("explanation", ""))])
    db.audit(u, "export.csv")
    return Response(results_csv(rows), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="imsa_sentinel_resultats.csv"'})


# =============================================================================== vues globales
@app.get("/api/overview")
def overview(u=Depends(current_user)):
    rows = [c for c in db.q("SELECT * FROM cases") if _active(c) and _can_see(u, c)]
    st = Counter(c["status"] for c in rows)
    mine = [c["id"] for c in rows if c["assigned_to"] == u["id"]]
    recent = db.q("SELECT d.*, us.display_name FROM decisions d LEFT JOIN users us ON us.id=d.user_id "
                  "ORDER BY d.id DESC LIMIT 15")
    recent = [d for d in recent if any(c["id"] == d["case_id"] for c in rows)]
    return {
        "accessible": len(rows),
        "a_controler": st.get("À contrôler", 0),
        "en_cours": st.get("En analyse", 0) + st.get("Anomalie à vérifier", 0) + st.get("Revue complémentaire nécessaire", 0),
        "avec_anomalies": sum(1 for c in rows if (c["n_anomalies"] or 0) > 0),
        "lecture_humaine": sum(1 for c in rows if (c["n_nv"] or 0) > 0),
        "verifies": sum(st.get(s, 0) for s in ("Écart confirmé", "Faux positif reconnu", "Contrôle terminé", "Clôturé")),
        "mes_dossiers": mine, "statuts": dict(st), "decisions_recentes": recent,
        "queue": sorted([{"id": c["id"], "priority_score": c["priority_score"], "n_anomalies": c["n_anomalies"],
                          "n_nv": c["n_nv"], "status": c["status"], "establishment": c["establishment"],
                          "priority_override": c["priority_override"]}
                         for c in rows if c["status"] not in ("Contrôle terminé", "Clôturé", "Faux positif reconnu")],
                        key=lambda x: (-(x["priority_override"] == "haute"), -(x["priority_score"] or 0), x["id"]))[:12],
    }


def _corpus_cases():
    return [c for c in db.q("SELECT * FROM cases ORDER BY id") if _active(c) and c["family"] != "Import"
            and (c.get("source") or "corpus") == "corpus"]


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


@app.get("/api/supervision")
def supervision(u=Depends(require("superviseur", "admin", "auditeur"))):
    all_cases = [c for c in db.q("SELECT * FROM cases ORDER BY id") if _active(c)]
    cases = _corpus_cases()                                            # statistiques : corpus officiel seul
    corpus_ids = {c["id"] for c in cases}
    checks = [r for r in db.q("SELECT * FROM check_results") if r["case_id"] in corpus_ids]
    pairs = [p for p in db.meta_get("pairs", []) if p.get("family") != "Import"]
    manifest = db.meta_get("manifest", {})
    by_rule = defaultdict(Counter)
    for r in checks:
        by_rule[r["rule_id"]][r["status"]] += 1
    est = defaultdict(lambda: {"dossiers": 0, "avec_anomalie": 0, "anomalies": 0, "nv": 0})
    for c in cases:
        k = f"{c['establishment']} ({c['finess']})"
        est[k]["dossiers"] += 1
        est[k]["anomalies"] += c["n_anomalies"] or 0
        est[k]["nv"] += c["n_nv"] or 0
        est[k]["avec_anomalie"] += 1 if (c["n_anomalies"] or 0) > 0 else 0
    for k, v in est.items():
        v["faible_effectif"] = v["dossiers"] < 30
    # Finances : écarts rattachés aux règles et aux décisions effectives (sans double comptage)
    payloads, fin_rows = {}, []
    all_dec = defaultdict(list)
    for d in db.q("SELECT d.*, us.display_name, us.username FROM decisions d LEFT JOIN users us ON us.id=d.user_id ORDER BY d.id"):
        all_dec[d["case_id"]].append(d)
    unreadable = Counter()
    zone_matrix = {z: Counter() for z in ZONE_IDS}
    zone_mixed = Counter()
    for c in cases:
        p = _payload(c["id"])
        payloads[c["id"]] = p
        fin_rows.append((c, finance.case_finance(p.get("results", []), all_dec[c["id"]], c["billed_cents"])))
        for fid, f in (p.get("extraction", {}).get("fields") or {}).items():
            if f.get("agreement") in ("illisible", "divergent"):
                unreadable[fid] += 1
        for z in p.get("zones", []):
            zone_matrix[z["zone_id"]][z["status"]] += 1
            if "mixte" in z.get("flags", []) or "controles_egalement_incertains" in z.get("flags", []):
                zone_mixed[z["zone_id"]] += 1
    port = finance.portfolio(fin_rows)
    users = {x["id"]: x for x in db.users()}
    load = Counter(c["assigned_to"] for c in cases if c["assigned_to"])
    decisions = db.q("SELECT d.*, us.display_name FROM decisions d LEFT JOIN users us ON us.id=d.user_id ORDER BY d.id DESC LIMIT 200")
    corpus_dec = [d for ds in all_dec.values() for d in ds if d["case_id"] in corpus_ids]
    # activité réelle (aucune donnée inventée) : décisions par jour, contrôles confirmés / faux positifs
    per_day = Counter(d["created_at"][:10] for d in corpus_dec if d["kind"] in ("confirmation", "faux_positif", "statut",
                                                                              "revue_complementaire", "decision_motivee"))
    eff_kinds = Counter(d["kind"] for _, f in fin_rows for d in f["decisions_effectives"].values())
    # productivité : temps actif mesuré, délais réels
    act = db.q("SELECT case_id, SUM(active_s) AS s FROM activity GROUP BY case_id")
    act_by = {a["case_id"]: a["s"] for a in act if a["case_id"] in corpus_ids}
    first_dec = {}
    for d in corpus_dec:
        if d["kind"] in ("confirmation", "faux_positif", "statut", "revue_complementaire", "examen") and d["case_id"] not in first_dec:
            first_dec[d["case_id"]] = d["created_at"]

    def secs(a, b):
        try:
            import datetime as _dt
            return (_dt.datetime.fromisoformat(b.replace(" ", "T")) - _dt.datetime.fromisoformat(a.replace(" ", "T"))).total_seconds()
        except Exception:  # noqa
            return None
    to_first = [secs(c["opened_at"], first_dec[c["id"]]) for c in cases if c.get("opened_at") and c["id"] in first_dec]
    to_close = [secs(c["opened_at"], c["closed_at"]) for c in cases if c.get("opened_at") and c.get("closed_at")]
    ocr_times = [((p.get("timings") or {}).get("ocr_s")) for p in payloads.values()]
    ana_times = [((p.get("timings") or {}).get("analyse_s")) for p in payloads.values()]
    rules_info = {r.id: {"title": r.title, "category": r.category} for r in RULES}
    n = len(cases)
    return {
        "denominateurs": {
            "fichiers_analyses": manifest.get("counts", {}),
            "paires": len(pairs),
            "factures_identifiees": n,
            "controles_executes": len(checks),
            "zones_evaluees": n * len(ZONE_IDS),
            "dossiers_importes": sum(1 for c in all_cases if c["id"] not in corpus_ids),
            "note": "Statistiques calculées sur le corpus officiel uniquement (dossiers importés et simulations exclus). "
                    "Un dossier = une paire bordereau JPG + fichier TXT. Un contrôle = l'application d'une règle à un dossier. "
                    "Une anomalie = un contrôle au statut ANOMALIE. Une zone = l'une des 15 zones CERFA d'un bordereau.",
        },
        "dossiers": {
            "total": n,
            "rapproches": sum(1 for c in cases if c["pairing_status"] == "confirmé"),
            "rapprochement_ambigu": [c["id"] for c in cases if c["pairing_status"] != "confirmé"],
            "avec_anomalie": sum(1 for c in cases if (c["n_anomalies"] or 0) > 0),
            "avec_non_verifiable": sum(1 for c in cases if (c["n_nv"] or 0) > 0),
            "conformes": sum(1 for c in cases if c["state"] == "conforme"),
            "revue_humaine_requise": sum(1 for c in cases if (c["n_anomalies"] or 0) + (c["n_nv"] or 0) > 0
                                         and c["status"] not in ("Écart confirmé", "Faux positif reconnu", "Contrôle terminé", "Clôturé")),
            "en_attente_revue": sum(1 for c in cases if c["status"] in ("À contrôler", "En analyse", "Anomalie à vérifier",
                                                                         "Revue complémentaire nécessaire")),
            "valides_agent": sum(1 for c in cases if c["status"] in ("Écart confirmé", "Faux positif reconnu", "Contrôle terminé", "Clôturé")),
            "clotures": sum(1 for c in cases if c["status"] == "Clôturé"),
            "par_statut": dict(Counter(c["status"] for c in cases)),
        },
        "activite": {
            "decisions_par_jour": dict(sorted(per_day.items())),
            "controles_confirmes": eff_kinds.get("confirmation", 0),
            "faux_positifs": eff_kinds.get("faux_positif", 0),
            "revues_demandees": eff_kinds.get("revue_complementaire", 0),
            "note": "Données réellement enregistrées depuis la mise en service ; aucun historique antérieur n'est reconstitué.",
        },
        "productivite": {
            "ocr_s_median": _median(ocr_times), "ocr_mesures": sum(1 for x in ocr_times if x is not None),
            "analyse_s_median": _median(ana_times), "analyse_mesures": sum(1 for x in ana_times if x is not None),
            "temps_actif_s_median": _median(list(act_by.values())), "temps_actif_dossiers": len(act_by),
            "delai_premiere_decision_s_median": _median(to_first), "delai_premiere_decision_mesures": len(to_first),
            "delai_cloture_s_median": _median(to_close), "delai_cloture_mesures": len(to_close),
            "note": "Temps actif = interactions dans un onglet visible (une pause n'est pas comptée). Délais = temps écoulé "
                    "entre la première ouverture du dossier et la décision ou la clôture. Aucun gain de productivité n'est "
                    "extrapolé : une comparaison avec un protocole manuel doit être mesurée sur les mêmes dossiers.",
        },
        "zones": [{"zone_id": z, "label": ZONE_INFO[z]["label"], "counts": dict(zone_matrix[z]), "mixtes": zone_mixed[z],
                   "denominateur": n} for z in ZONE_IDS],
        "regles": [{"rule_id": rid, **rules_info.get(rid, {}), "counts": dict(cnt),
                    "evaluables": sum(v for k, v in cnt.items() if k != "NON_APPLICABLE")}
                   for rid, cnt in sorted(by_rule.items())],
        "etablissements": [{"nom": k, **v} for k, v in sorted(est.items())],
        "finances": {
            **port,
            "notes": {
                "facture_total": "Somme TotalPrestations + TotalHonoraires des fichiers TXT analysés.",
                "en_anomalie": "Montants des écarts constatés (non confirmés), sans double comptage : par dossier et par famille "
                               "(prestations / honoraires), maximum entre l'écart sur le total et la somme des lignes en écart.",
                "ecart_net": "Somme des différences |TXT − bordereau| sur les totaux (R12, R17).",
                "lignes_en_ecart": "Montants portés par les prestations/actes présents d'un seul côté (R08, R11, R13, R14, R15, R19).",
                "dossiers_alerte": "Montant facturé total des dossiers comportant au moins une anomalie (ce n'est PAS un montant indu).",
                "confirme": "Écarts des seules règles dont la dernière décision (non annulée) est une confirmation par un agent, "
                            "règle par règle, sans double comptage. Un faux positif, une revue demandée ou une décision annulée "
                            "n'est pas compté.",
                "indu": "Un indu n'est établi qu'après une procédure de notification hors application : non calculable.",
                "recupere": "Aucune donnée de recouvrement n'est disponible dans le corpus : non calculable.",
                "extrapolation": "Aucune estimation d'économies annuelles n'est produite : le corpus n'est ni représentatif ni annoté.",
            },
        },
        "priorites": sorted([{"id": c["id"], "score": c["priority_score"], "reasons": json.loads(c["priority_reasons"] or "[]"),
                              "status": c["status"], "override": c["priority_override"]} for c in cases],
                            key=lambda x: (-(x["override"] == "haute"), -(x["score"] or 0)))[:20],
        "charge_agents": [{"user_id": k, "nom": users.get(k, {}).get("display_name"), "dossiers": v,
                           "en_cours": sum(1 for c in cases if c["assigned_to"] == k and c["status"] not in ("Contrôle terminé", "Clôturé"))}
                          for k, v in load.items()],
        "decisions": decisions,
        "lectures_difficiles": dict(unreadable),
        "ambiguites": AMBIGUITIES,
        "parametres_priorite": "Score opérationnel proposé par l'équipe (pondérations dans config.py) — pas une norme MSA.",
    }


AMBIGUITIES = [
    {"id": "AMB-01", "sujet": "Identifiant du formulaire (R01)",
     "constat": "Le cahier des charges indique « 12278*0 » ; les bordereaux impriment « 12278*01 ».",
     "convention": "Préfixe « 12278*0 » exigé ; le chiffre final (version) est accepté.", "a_clarifier": True},
    {"id": "AMB-02", "sujet": "Format des numéros (R03, R04)",
     "constat": "Le fichier cadre les numéros avec des zéros à gauche (000491901) ; le bordereau non (491901).",
     "convention": "Comparaison numérique, zéros de cadrage ignorés.", "a_clarifier": False},
    {"id": "AMB-03", "sujet": "Actes CCAM (R19)",
     "constat": "Un acte de type 4 suivi d'un 4-M est imprimé sur le bordereau sous son code CCAM, pas sous son code Acte.",
     "convention": "Acte retrouvé par son code CCAM s'il existe, sinon par son code Acte.", "a_clarifier": True},
    {"id": "AMB-04", "sujet": "Lignes de détail biologie (R14)",
     "constat": "Sous un acte B, le bordereau imprime des codes de 4 chiffres (ex. 9107 9106…) sans exécutant ni montant.",
     "convention": "Lignes considérées comme détail de l'acte B, non comme actes distincts.", "a_clarifier": True},
    {"id": "AMB-05", "sujet": "Signatures zone 11 (R18)",
     "constat": "Les cases contiennent parfois une mention « par mandat » ou un cachet plutôt qu'une signature manuscrite.",
     "convention": "Présence d'un élément = signature présente ; authenticité jamais certifiée.", "a_clarifier": True},
    {"id": "AMB-06", "sujet": "R09 / R10 (NumeroGH des actes de type 3)",
     "constat": "Deux formulations proches : référence GHS du fichier (R09) ou GHS lu en zone 6 (R10).",
     "convention": "R09 : contrôle interne au fichier ; R10 : actes LPP (zone 7) comparés au GHS lu en zone 6.",
     "a_clarifier": True},
    {"id": "AMB-07", "sujet": "Comptage des occurrences (R08, R11, R13, R14, R15, R19)",
     "constat": "Le cahier des charges parle de « présence » ; un même code peut figurer plusieurs fois.",
     "convention": "Rapprochement occurrence par occurrence (deux actes identiques doivent figurer deux fois).",
     "a_clarifier": True},
    {"id": "AMB-08", "sujet": "Enregistrement de type 0",
     "constat": "Aucun fichier ne contient d'en-tête de type 0.", "convention": "Absence non considérée comme une erreur.",
     "a_clarifier": False},
]


@app.get("/api/anomalies")
def anomalies(u=Depends(current_user)):
    out = []
    for c in db.q("SELECT * FROM cases ORDER BY id"):
        if not _active(c) or not _can_see(u, c):
            continue
        p = _payload(c["id"])
        dec = _decisions(c["id"])
        eff = finance.effective_decisions(dec)
        last = {}
        for d in dec:
            if d.get("rule_id"):
                last[d["rule_id"]] = d
        for r in p.get("results", []):
            if r["status"] in ("ANOMALIE", "NON_VERIFIABLE"):
                out.append({"case_id": c["id"], "family": c["family"], "establishment": c["establishment"],
                            "case_status": c["status"], "rule_id": r["rule_id"], "title": r["title"],
                            "category": r["category"], "status": r["status"], "jpg_value": mask_text(r.get("jpg_value")),
                            "txt_value": mask_text(r.get("txt_value")), "gap_cents": (r.get("gap") or {}).get("amount_cents"),
                            "explanation": mask_text(r["explanation"]), "uncertainty": mask_text(r.get("uncertainty")),
                            "last_decision": last.get(r["rule_id"]),
                            "effective_decision": (eff.get(r["rule_id"]) or {}).get("kind"),
                            "zones": [z for z in ZONE_IDS if r["rule_id"] in ZONE_INFO[z]["rules"]],
                            "source": c.get("source") or "corpus", "priority_score": c.get("priority_score")})
    return out


@app.get("/api/review/queue")
def review_queue(include_nv: bool = True, u=Depends(current_user)):
    """Revue rapide : anomalies (et contrôles non vérifiables) sans décision effective, par priorité de dossier."""
    items = [x for x in anomalies(u) if not x["effective_decision"] and (include_nv or x["status"] == "ANOMALIE")]
    items.sort(key=lambda x: (x["source"] != "corpus", -(x["priority_score"] or 0), x["case_id"],
                              x["status"] != "ANOMALIE", x["rule_id"]))
    return items


@app.get("/api/triage")
def triage_all(u=Depends(current_user)):
    from .triage import triage_portfolio
    pl = {c["id"]: _payload(c["id"]) for c in db.q("SELECT * FROM cases ORDER BY id") if _active(c) and _can_see(u, c)}
    return mask_text(triage_portfolio(pl))


_CONV_CACHE: dict = {}


@app.get("/api/conventions")
def conventions(u=Depends(current_user)):
    from .b2parser import parse_b2
    from .conventions import analyze as conv_analyze
    cases = _corpus_cases()
    key = tuple((c["id"], c["analyzed_at"]) for c in cases)
    if _CONV_CACHE.get("key") != key:
        rows = []
        for c in cases:
            p = _payload(c["id"])
            if not p.get("results"):
                continue
            rows.append((c["id"], parse_b2(_case_file(c, "txt")), p["extraction"], p["results"]))
        _CONV_CACHE.update(key=key, value=conv_analyze(rows))
    return {"conventions": _CONV_CACHE["value"], "n_dossiers": len(cases),
            "decisions": db.meta_get("convention_decisions", {}) or {},
            "note": "Les effets sont calculés en rejouant la règle sur le corpus avec la convention alternative ; les "
                    "résultats officiels ne sont pas modifiés. Conventions proposées par l'équipe, à valider par la MSA."}


@app.get("/api/quality")
def quality(u=Depends(require("superviseur", "admin", "auditeur"))):
    """Qualité mesurée de l'OCR et des alertes, à partir des seules validations et corrections des agents
    (référentiel construit progressivement). Une métrique sans effectif est « indisponible », jamais 100 %."""
    from .corrections import parse_target
    corpus = {c["id"] for c in _corpus_cases()}
    corr = [c for c in db.q("SELECT * FROM corrections WHERE active=1") if c["case_id"] in corpus]
    by_kind = defaultdict(lambda: {"verifies": 0, "corrects": 0})
    by_zone = defaultdict(lambda: {"verifies": 0, "corrects": 0})
    for c in corr:
        try:
            t = parse_target(c["target"])
        except Exception:  # noqa
            continue
        k = {"amount": "montants", "code": "codes actes / CCAM", "ghs": "numéros GHS", "signature": "signatures"}.get(
            t["kind"], "identifiants")
        z = t.get("id") if t["type"] == "field" else t.get("zone")
        z = {"ST1": "Z6", "ST2": "Z6", "ST3": "Z7"}.get(z, z)
        ok = (c.get("kind") or "correction") == "validation"
        for d, key in ((by_kind, k), (by_zone, z)):
            d[key]["verifies"] += 1
            d[key]["corrects"] += 1 if ok else 0

    def rate(d):
        return {**d, "exactitude": round(d["corrects"] / d["verifies"], 3) if d["verifies"] else None}
    # désaccords entre moteurs et champs illisibles (mesurables sans vérité terrain)
    from .rules import contradictory_tie
    dis, ill, tot = Counter(), Counter(), Counter()
    for cid in corpus:
        ext = _payload(cid).get("extraction") or {}
        for f in (ext.get("fields") or {}).values():
            tot[f.get("zone")] += 1
            if f.get("agreement") == "divergent" or contradictory_tie(f):
                dis[f.get("zone")] += 1
            elif f.get("agreement") == "illisible":
                ill[f.get("zone")] += 1
    # qualité des alertes sur les cas annotés : dossiers dont l'examen est terminé (un agent y a décidé chaque
    # alerte et pouvait signaler une omission). Sans dossier annoté, précision et rappel sont indisponibles.
    annotated = {c["id"] for c in _corpus_cases() if c["status"] in ("Contrôle terminé", "Clôturé", "Écart confirmé", "Faux positif reconnu")}
    tp = fp = om = 0
    tp_all = fp_all = 0
    nv_total = checks_total = 0
    for cid in corpus:
        dec = _decisions(cid)
        eff = finance.effective_decisions(dec)
        c_tp = sum(1 for d in eff.values() if d["kind"] == "confirmation")
        c_fp = sum(1 for d in eff.values() if d["kind"] == "faux_positif")
        tp_all += c_tp; fp_all += c_fp
        if cid in annotated:
            tp += c_tp; fp += c_fp
            om += sum(1 for d in dec if d["kind"] == "omission")
    for r in db.q("SELECT case_id, status FROM check_results"):
        if r["case_id"] in corpus:
            checks_total += 1
            nv_total += r["status"] == "NON_VERIFIABLE"
    return {
        "ocr": {"par_type": {k: rate(v) for k, v in by_kind.items()}, "par_zone": {k: rate(v) for k, v in by_zone.items()},
                "champs_verifies": sum(v["verifies"] for v in by_kind.values()),
                "corrections_humaines": sum(1 for c in corr if (c.get("kind") or "correction") == "correction"),
                "validations_humaines": sum(1 for c in corr if c.get("kind") == "validation"),
                "desaccords_moteurs_par_zone": {z: {"desaccords": dis[z], "illisibles": ill[z], "champs": tot[z]}
                                                for z in sorted(tot, key=lambda z: int(z[1:]))}},
        "alertes": {"confirmees": tp_all, "faux_positifs": fp_all, "omissions_signalees": om, "dossiers_annotes": len(annotated),
                    "precision": round(tp_all / (tp_all + fp_all), 3) if tp_all + fp_all else None,
                    "rappel": round(tp / (tp + om), 3) if annotated and tp + om else None,
                    "taux_faux_positifs": round(fp_all / (tp_all + fp_all), 3) if tp_all + fp_all else None,
                    "taux_non_verifiables": round(nv_total / checks_total, 4) if checks_total else None,
                    "controles": checks_total},
        "note": "Référentiel construit uniquement à partir des validations et corrections des agents sur le corpus autorisé. "
                "Précision = confirmées / (confirmées + faux positifs) ; rappel = confirmées / (confirmées + omissions signalées), "
                "calculé uniquement sur les dossiers dont l'examen est terminé (cas annotés). "
                "Sans décision enregistrée, la métrique est indisponible.",
    }


# =============================================================================== référentiel de validation
class ValidationIn(BaseModel):
    case_id: str
    rule_id: str
    verdict: str
    cause: Optional[str] = None
    printed_value: Optional[str] = Field(default=None, max_length=200)
    b2_value: Optional[str] = Field(default=None, max_length=200)
    comment: Optional[str] = Field(default=None, max_length=2000)


@app.get("/api/validation")
def validation_list(u=Depends(require("superviseur", "admin", "auditeur", "agent"))):
    """Éléments à valider : toutes les anomalies et contrôles à vérifier du corpus, plus un échantillon fixe de
    contrôles conformes (un sur dix, tiré de façon déterministe) pour mesurer les écarts manqués."""
    import hashlib
    from .validation import CAUSES, VERDICTS, consensus
    rows = db.q("SELECT * FROM validations ORDER BY id")
    cons = consensus(rows)
    assisted = {(r["case_id"], r["rule_id"]): r for r in rows if r["validator_kind"] == "revue_assistee"}
    mine = {(r["case_id"], r["rule_id"]): r for r in rows if r["validator_id"] == u["id"]}
    items = []
    for c in _corpus_cases():
        p = _payload(c["id"])
        for r in p.get("results", []):
            k = (c["id"], r["rule_id"])
            sample = int(hashlib.sha256(f"{k}".encode()).hexdigest(), 16) % 10 == 0
            if r["status"] in ("ANOMALIE", "NON_VERIFIABLE") or (r["status"] == "CONFORME" and sample) or k in cons:
                items.append({"case_id": c["id"], "rule_id": r["rule_id"], "title": r["title"], "status": r["status"],
                              "jpg_value": r.get("jpg_value"), "txt_value": r.get("txt_value"),
                              "explanation": r["explanation"], "zones": r.get("zones"),
                              "echantillon_conformes": r["status"] == "CONFORME",
                              "consensus": cons.get(k), "ma_validation": mine.get(k),
                              "revue_assistee": ({"verdict": assisted[k]["verdict"], "commentaire": assisted[k]["comment"]}
                                                 if k in assisted else None)})
    return {"items": items, "verdicts": VERDICTS, "causes": CAUSES}


@app.post("/api/validation")
def validation_add(body: ValidationIn, u=Depends(require("superviseur", "admin", "agent"))):
    from .validation import CAUSES, VERDICTS
    c = _case_or_404(body.case_id, u)
    if body.verdict not in VERDICTS:
        raise HTTPException(400, "Verdict inconnu")
    if body.verdict == "faux_positif" and body.cause not in CAUSES:
        raise HTTPException(400, "Indiquez la cause du faux positif")
    r = next((x for x in _payload(c["id"]).get("results", []) if x["rule_id"] == body.rule_id), None)
    if not r:
        raise HTTPException(400, "Contrôle inconnu")
    with db.tx() as con:
        con.execute("INSERT INTO validations (case_id, rule_id, verdict, cause, printed_value, b2_value, comment, "
                    "validator_id, validator_name, validator_kind, engine_status, engine_version, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,'humain',?,?,?)",
                    (c["id"], body.rule_id, body.verdict, body.cause if body.verdict == "faux_positif" else None,
                     body.printed_value, body.b2_value, body.comment, u["id"], u["display_name"], r["status"],
                     ENGINE_VERSION, now_iso()))
    db.audit(u, "validation.ajout", c["id"], {"regle": body.rule_id, "verdict": body.verdict, "cause": body.cause})
    return {"ok": True}


@app.get("/api/validation/metrics")
def validation_metrics(u=Depends(require("superviseur", "admin", "auditeur"))):
    from .validation import metrics
    corpus = {c["id"] for c in _corpus_cases()}
    engine = {(r["case_id"], r["rule_id"]): r["status"] for r in db.q("SELECT case_id, rule_id, status FROM check_results")
              if r["case_id"] in corpus}
    rows = [r for r in db.q("SELECT * FROM validations ORDER BY id") if r["case_id"] in corpus]
    out = metrics(engine, rows)
    out["revue_assistee"] = Counter(r["verdict"] for r in rows if r["validator_kind"] == "revue_assistee")
    return out


# =============================================================================== décisions métier (conventions)
class ConventionDecisionIn(BaseModel):
    decision: str
    reference: str = Field(min_length=3, max_length=300)   # référence du courrier, de la note ou de la réunion


@app.post("/api/conventions/{amb}/decision")
def convention_decision(amb: str, body: ConventionDecisionIn, u=Depends(require("superviseur", "admin"))):
    """Enregistre la décision de la MSA sur une ambiguïté du cahier des charges. Seules AMB-01 et AMB-02
    modifient le moteur ; les autres sont tracées. Tous les dossiers sont ensuite réanalysés."""
    from .conventions import CONVENTIONS
    if amb not in {c["id"] for c in CONVENTIONS}:
        raise HTTPException(404, "Convention inconnue")
    if body.decision not in ("validée", "rejetée", "proposée"):
        raise HTTPException(400, "Décision : validée, rejetée ou proposée")
    cur = db.meta_get("convention_decisions", {}) or {}
    if body.decision == "proposée":
        cur.pop(amb, None)
    else:
        cur[amb] = {"decision": body.decision, "reference": body.reference, "par": u["display_name"], "le": now_iso()}
    db.meta_set("convention_decisions", cur)
    db.audit(u, "convention.decision", amb, {"decision": body.decision, "reference": body.reference})
    job = jobs.submit(db, "synchronisation", "conventions",
                      lambda progress: sync_cases(db, u["username"], progress=progress), u["username"])
    return {"ok": True, "applique_au_moteur": amb in ("AMB-01", "AMB-02"), "job": job}


@app.get("/api/rules")
def rules(u=Depends(current_user)):
    cnt = defaultdict(Counter)
    corpus = {c["id"] for c in _corpus_cases()}
    for r in db.q("SELECT case_id, rule_id, status FROM check_results"):
        if r["case_id"] in corpus:
            cnt[r["rule_id"]][r["status"]] += 1
    return {"categories": CATEGORIES,
            "rules": [{"id": r.id, "category": r.category, "title": r.title, "spec": r.spec, "zones": r.zones,
                       "txt_fields": r.txt_fields, "convention": r.convention, "counts": dict(cnt[r.id])} for r in RULES],
            "ambiguities": AMBIGUITIES,
            "zones": [{"zone_id": z, "label": ZONE_INFO[z]["label"], "description": ZONE_INFO[z]["description"],
                       "rules": [{"rule_id": k, "role": v} for k, v in ZONE_INFO[z]["rules"].items()]} for z in ZONE_IDS]}


@app.get("/api/audit")
def audit(limit: int = 300, u=Depends(require("superviseur", "admin", "auditeur"))):
    rows = db.q("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (min(limit, 2000),))
    for r in rows:
        r["details"] = mask_text(json.loads(r["details"])) if r["details"] else None
        r["target"] = mask_text(r["target"])
    return rows


@app.get("/api/corpus")
def corpus(u=Depends(current_user)):
    return {"manifest": db.meta_get("manifest"), "pairs": db.meta_get("pairs"),
            "runs": db.q("SELECT * FROM runs ORDER BY id DESC LIMIT 10")}


# =============================================================================== comparaison d'images
def _ext_for(cid):
    a = db.one("SELECT payload FROM analyses WHERE case_id=?", (cid,))
    return json.loads(a["payload"]).get("extraction") if a else None


@app.post("/api/compare")
def compare(body: CompareIn, u=Depends(current_user)):
    ca, cb = _case_or_404(body.a, u), _case_or_404(body.b, u)
    res = compare_images(_case_file(ca, "jpg"), _case_file(cb, "jpg"), _ext_for(body.a), _ext_for(body.b))
    db.audit(u, "comparaison.images", f"{body.a} ↔ {body.b}", {"mode": res["mode"], "regions": len(res["regions"])})
    return res


@app.get("/api/compare/visual")
def compare_visual(a: str, b: str, mode: str = "diff", u=Depends(current_user)):
    ca, cb = _case_or_404(a, u), _case_or_404(b, u)
    return Response(diff_overlay(_case_file(ca, "jpg"), _case_file(cb, "jpg"), mode), media_type="image/png")


# =============================================================================== import de dossiers / simulations
def _import_visible(u, meta, case) -> bool:
    if case:
        return _can_see(u, case)
    return u["role"] in ("superviseur", "admin", "auditeur") or meta.get("by") == u["username"]


def _start_import_job(iid: str, username: str):
    def run(progress):
        pair = next(p for p in import_pairs() if p["id"] == iid)
        progress(0, 1, "lecture OCR du bordereau")
        run_row = db.one("SELECT MAX(id) AS id FROM runs")
        analyze_case(db, pair, run_row["id"] if run_row else None)
        progress(1, 1, "analyse terminée")
        db.audit({"id": None, "username": username}, "import.analyse", iid)
        return {"dossier": iid}
    return jobs.submit(db, "analyse_import", iid, run, username)


@app.post("/api/imports")
async def new_import(bordereau: UploadFile = File(...), facture: UploadFile = File(...),
                     label: Optional[str] = Form(None), u=Depends(require(*WRITE_ROLES))):
    img = await bordereau.read()
    txt = await facture.read()
    try:
        meta = create_import(img, bordereau.filename, txt, facture.filename, label, u["username"])
    except ImportError_ as e:
        raise HTTPException(400, str(e))
    db.audit(u, "import.depot", meta["id"], {"bordereau": meta["jpg"], "facture": meta["txt"]})
    job = _start_import_job(meta["id"], u["username"])
    return {**meta, "job": job}


class SimulationIn(BaseModel):
    label: Optional[str] = Field(default=None, max_length=120)
    edits: list = Field(min_length=1, max_length=20)


@app.post("/api/cases/{cid}/simulate")
def simulate(cid: str, body: SimulationIn, u=Depends(require(*WRITE_ROLES))):
    """Simulation : copie d'un dossier autorisé dont une ou plusieurs valeurs du TXT sont modifiées (le fichier
    original n'est jamais modifié). La copie est analysée par le moteur réel et exclue des statistiques."""
    c = _case_or_404(cid, u)
    jpg, txtp = _case_file(c, "jpg"), _case_file(c, "txt")
    raw = txtp.read_bytes().decode("latin-1")
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(eol)
    applied = []
    for e in body.edits:
        try:
            ln, start, end, val = int(e["line_no"]), int(e["start"]), int(e["end"]), str(e["value"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, "Modification invalide : ligne, positions et valeur sont requises.")
        if not (1 <= ln <= len(lines)) or not (1 <= start <= end <= len(lines[ln - 1])):
            raise HTTPException(400, f"Positions {start}-{end} hors de la ligne {ln}.")
        if len(val) != end - start + 1:
            raise HTTPException(400, f"La nouvelle valeur doit faire exactement {end - start + 1} caractère(s) "
                                     "(les positions du format B2 sont fixes).")
        if not all(32 <= ord(ch) < 127 for ch in val):
            raise HTTPException(400, "Caractères non autorisés dans la valeur.")
        old = lines[ln - 1][start - 1:end]
        lines[ln - 1] = lines[ln - 1][:start - 1] + val + lines[ln - 1][end:]
        applied.append({"line_no": ln, "start": start, "end": end, "avant": old, "apres": val})
    label = body.label or f"Simulation de {cid} : " + "; ".join(f"l.{a['line_no']} pos.{a['start']}-{a['end']} {a['avant']}→{a['apres']}" for a in applied)
    try:
        meta = create_import(jpg.read_bytes(), jpg.name, eol.join(lines).encode("latin-1"), txtp.stem + "_simulation.txt",
                             label[:120], u["username"], origin=cid, edits=applied)
    except ImportError_ as e:
        raise HTTPException(400, str(e))
    db.audit(u, "simulation.creation", meta["id"], {"origine": cid, "modifications": applied})
    job = _start_import_job(meta["id"], u["username"])
    return {**meta, "job": job}


@app.get("/api/imports")
def list_imports(u=Depends(current_user)):
    out = []
    for p in import_pairs():
        c = db.one("SELECT * FROM cases WHERE id=?", (p["id"],))
        if not _import_visible(u, p["meta"], c):
            continue
        job = db.one("SELECT * FROM jobs WHERE target=? AND kind='analyse_import' ORDER BY id DESC", (p["id"],))
        st = {"status": "prêt" if c else "en attente"}
        if job and job["status"] in ("en_attente", "en_cours"):
            st = {"status": "analyse", "job": job}
        elif job and job["status"] in ("erreur", "interrompu"):
            st = {"status": "erreur", "error": job.get("error") or "Analyse interrompue (redémarrage de l'application)", "job": job}
        summ = {k: c[k] for k in ("id", "n_anomalies", "n_nv", "state", "status")} if c else None
        out.append({**p["meta"], **st, "case": summ})
    return sorted(out, key=lambda x: x["created_at"], reverse=True)


@app.delete("/api/imports/{iid}")
def remove_import(iid: str, u=Depends(require(*WRITE_ROLES))):
    meta = next((p["meta"] for p in import_pairs() if p["id"] == iid), None)
    if not meta:
        raise HTTPException(404, "Import introuvable")
    c = db.one("SELECT * FROM cases WHERE id=?", (iid,))
    if not _import_visible(u, meta, c):
        raise HTTPException(403, "Import d'un autre agent")
    if u["role"] == "agent" and meta.get("by") != u["username"]:
        raise HTTPException(403, "Seul l'agent qui a déposé ce dossier, ou un gestionnaire, peut le supprimer")
    if jobs.active_job(db, target=iid) or jobs.is_locked(iid):
        raise HTTPException(409, "Analyse en cours : suppression impossible tant qu'elle n'est pas terminée.")

    def do():
        with jobs.operation(), jobs.case_lock(iid, timeout=5):
            try:
                delete_import(iid)
            except ImportError_ as e:
                raise HTTPException(400, str(e))
            with db.tx() as con:
                for t in ("cases", "analyses"):
                    con.execute(f"DELETE FROM {t} WHERE {'id' if t == 'cases' else 'case_id'}=?", (iid,))
                con.execute("DELETE FROM check_results WHERE case_id=?", (iid,))
    _busy(do)
    db.audit(u, "import.suppression", iid)
    return {"ok": True}


# =============================================================================== traitements
@app.get("/api/jobs")
def list_jobs(u=Depends(current_user)):
    rows = jobs.recent(db, 40)
    if u["role"] == "agent":
        visible = {c["id"] for c in db.q("SELECT * FROM cases") if _can_see(u, c)}
        rows = [j for j in rows if j["created_by"] == u["username"] or j["target"] in visible]
    return rows


@app.get("/api/jobs/{jid}")
def get_job(jid: int, u=Depends(current_user)):
    j = jobs.get(db, jid)
    if not j:
        raise HTTPException(404, "Traitement introuvable")
    if u["role"] == "agent" and j["created_by"] != u["username"]:
        c = db.one("SELECT * FROM cases WHERE id=?", (j["target"],))
        if not c or not _can_see(u, c):
            raise HTTPException(403, "Traitement d'un autre utilisateur")
    return j


# =============================================================================== administration
@app.post("/api/admin/reanalyze")
def admin_reanalyze(u=Depends(require("admin"))):
    def run(progress):
        STATE.update(phase="prêt")
        return analyze_all(db, u["username"], progress=lambda d, t, c: progress(d, t, c))
    job = jobs.submit(db, "reanalyse_complete", "corpus", run, u["username"])
    db.audit(u, "analyse.relance", None, {"job": job["id"]})
    return job


@app.post("/api/admin/sync")
def admin_sync(u=Depends(require("admin", "superviseur"))):
    job = jobs.submit(db, "synchronisation", "corpus", lambda progress: sync_cases(db, u["username"], progress=progress),
                      u["username"])
    db.audit(u, "synchronisation.demande", None, {"job": job["id"]})
    return job


@app.post("/api/admin/purge")
def admin_purge(u=Depends(require("admin"))):
    from .backup import create_backup
    bk = create_backup(db, "avant-purge")      # protection contre l'effacement accidentel

    def do():
        with jobs.exclusive():
            db.purge_metadata(keep_users=True)
    _busy(do)
    db.audit(u, "metadonnees.purge", None, {"conserve": "comptes utilisateurs, résultats d'analyse", "sauvegarde": bk["file"]})
    for c in db.q("SELECT id FROM cases WHERE source_status='ok'"):
        reanalyze_case(db, c["id"])
    return {"ok": True, "sauvegarde": bk}


@app.post("/api/admin/backup")
def admin_backup(u=Depends(require("admin"))):
    from .backup import create_backup
    bk = create_backup(db, "manuelle")
    db.audit(u, "sauvegarde.creation", None, {"fichier": bk["file"], "sha256": bk["sha256"]})
    return bk


@app.get("/api/admin/backups")
def admin_backups(u=Depends(require("admin"))):
    from .backup import list_backups
    return list_backups()


@app.get("/api/admin/cache")
def admin_cache(u=Depends(require("admin", "superviseur"))):
    from .ocrcache import status_report
    return status_report()


# =============================================================================== interface
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = STATIC_DIR / path
        if path and f.is_file() and STATIC_DIR in f.resolve().parents:
            return FileResponse(f)
        # jamais mis en cache : après une mise à jour, le navigateur charge toujours la nouvelle interface
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
