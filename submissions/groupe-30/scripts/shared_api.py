"""Routes authentifiées de l'app : sources, imports, classement et dossiers."""

from __future__ import annotations
import json, logging, os, time
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

import httpx
import psycopg
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from scripts.database import connection, revision, source_rows, safe
from scripts.catalog import catalog, history
from scripts.import_csv import parse_files, preview
from scripts.schema import ROOT
from scripts.schema import IMPORT_SOURCES
from scripts.scoring import schedule, run_job, latest_result
from scripts.workspace import (
    load_workspace,
    save_action,
    save_feedback,
    validate_action,
    validate_feedback,
)
from scripts import economics

router = APIRouter(prefix="/api")
bearer = HTTPBearer(auto_error=False)
DEFAULT_DATE = date(2026, 1, 1)


def public_config():
    return {
        "url": os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL", ""),
        "publishableKey": os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", ""),
    }


@router.get("/config")
def config():
    return public_config()


def member(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
    if credentials is None:
        raise HTTPException(401, "Connectez-vous pour accéder à l’équipe.")
    conf = public_config()
    if not conf["url"] or not conf["publishableKey"]:
        raise HTTPException(503, "Supabase Auth est indisponible.")
    try:
        response = httpx.get(
            conf["url"] + "/auth/v1/user",
            headers={
                "apikey": conf["publishableKey"],
                "Authorization": "Bearer " + credentials.credentials,
            },
            timeout=15,
        )
        if response.status_code in (401, 403):
            raise HTTPException(401, "Session expirée. Reconnectez-vous.")
        response.raise_for_status()
        user = response.json()
        user_id = str(UUID(user["id"]))
        with connection(user_id) as conn:
            profile = conn.execute(
                "select * from public.membres where user_id=%s", [user_id]
            ).fetchone()
        if not profile:
            raise HTTPException(
                403, "Votre compte n’a pas encore été ajouté à cette équipe."
            )
        return {
            "id": user_id,
            "email": user.get("email", ""),
            "role": profile["role"],
            "name": profile["nom"],
        }
    except HTTPException:
        raise
    except (httpx.HTTPError, psycopg.OperationalError, RuntimeError):
        logging.exception("Connexion Supabase indisponible")
        raise HTTPException(
            503, "Connexion Supabase indisponible. Vérifiez la configuration serveur."
        )


def admin(user=Depends(member)):
    if user["role"] != "admin":
        raise HTTPException(403, "L’import est réservé aux administrateurs.")
    return user


def moment(as_of_date):
    return datetime.combine(as_of_date, datetime.min.time())


class BudgetPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    version: int = Field(ge=0)
    sourceRevision: int = Field(ge=0)
    renovationBudget: Decimal = Field(ge=0, le=999999999999, decimal_places=2)
    maintenanceBudget: Decimal | None = Field(
        default=None, ge=0, le=999999999999, decimal_places=2
    )
    operationIds: list[str] = Field(max_length=500)


def economic_data(conn, horizon, as_of_date):
    result = latest_result(conn, horizon, as_of_date)
    symptoms = (
        conn.execute(
            "select equipement_id,types_pannes from public.predictions where calcul_id=%s and horizon_jours=%s",
            [result.get("runId"), horizon],
        ).fetchall()
        if result.get("runId")
        else []
    )
    return economics.overview(
        source_rows(conn, economics.TABLES),
        moment(as_of_date),
        revision(conn),
        result,
        symptoms,
    )


@router.get("/economies")
def get_economies(
    horizon: int = 90,
    as_of_date: date = DEFAULT_DATE,
    year: int = 2026,
    user=Depends(member),
):
    if horizon not in (90, 180, 365, 730) or not 2000 <= year <= 2100:
        raise HTTPException(422, "Horizon ou année invalide.")
    with connection(user["id"], snapshot=True) as conn:
        return {
            **economic_data(conn, horizon, as_of_date),
            "plan": economics.load_plan(conn, year),
        }


@router.get("/equipements/{equipment_id}/economie")
def get_equipment_economy(
    equipment_id: str,
    horizon: int = 90,
    as_of_date: date = DEFAULT_DATE,
    user=Depends(member),
):
    if horizon not in (90, 180, 365, 730):
        raise HTTPException(422, "Horizon invalide.")
    with connection(user["id"], snapshot=True) as conn:
        data = economic_data(conn, horizon, as_of_date)
        item = next(
            (e for e in data["equipment"] if e["equipmentId"] == equipment_id), None
        )
        if item is None:
            raise HTTPException(404, "Équipement introuvable.")
        return {
            "equipment": item,
            "referenceDate": data["referenceDate"],
            "revision": data["revision"],
            "periodStart": data["periodStart"],
            "stale": data["result"]["stale"],
            "operations": [
                o for o in data["operations"] if o["id"] in item["operationIds"]
            ],
            "groups": [g for g in data["groups"] if equipment_id in g["equipmentIds"]],
        }


@router.put("/budgets/{year}")
def put_budget(year: int, plan: BudgetPlan, user=Depends(member)):
    if not 2000 <= year <= 2100:
        raise HTTPException(422, "Année attendue entre 2000 et 2100.")
    with connection(user["id"]) as conn:
        return economics.save_plan(conn, year, plan, user["id"])


@router.get("/workspace")
def workspace(
    horizon: int = 90,
    as_of_date: date = DEFAULT_DATE,
    user=Depends(member),
):
    if horizon not in (90, 180, 365, 730):
        raise HTTPException(422, "Horizon attendu : 90, 180, 365 ou 730 jours.")
    with connection(user["id"], snapshot=True) as conn:
        rows = source_rows(
            conn,
            [
                "residences",
                "batiments",
                "logements",
                "equipements",
                "prestataires",
                "interventions",
            ],
        )
        return {
            "user": user,
            "catalog": catalog(rows, moment(as_of_date), revision(conn)),
            "result": latest_result(conn, horizon, as_of_date),
            **load_workspace(conn),
            "jobs": safe(
                conn.execute(
                    "select * from public.calculs order by cree_le desc limit 10"
                ).fetchall()
            ),
        }


@router.get("/catalog")
def get_catalog(as_of_date: date = DEFAULT_DATE, user=Depends(member)):
    with connection(user["id"], snapshot=True) as conn:
        return catalog(
            source_rows(
                conn,
                [
                    "residences",
                    "batiments",
                    "logements",
                    "equipements",
                    "prestataires",
                    "interventions",
                ],
            ),
            moment(as_of_date),
            revision(conn),
        )


@router.get("/equipements/{equipment_id}/historique")
def get_history(
    equipment_id: str, as_of_date: date = DEFAULT_DATE, user=Depends(member)
):
    try:
        with connection(user["id"], snapshot=True) as conn:
            return history(conn, equipment_id, moment(as_of_date))
    except KeyError:
        raise HTTPException(404, "Équipement introuvable.")


@router.post("/imports/preview")
async def preview_import(
    files: Annotated[list[UploadFile], File()], user=Depends(admin)
):
    payloads = []
    size = 0
    for file in files:
        payload = await file.read(20 * 1024 * 1024 + 1)
        size += len(payload)
        if size > 20 * 1024 * 1024:
            raise HTTPException(413, "Le lot doit faire au maximum 20 Mo.")
        payloads.append((file.filename or "import.csv", payload))
    parsed = parse_files(payloads)
    with connection(user["id"], snapshot=True) as conn:
        rev = revision(conn)
        result = preview(parsed, source_rows(conn))
    parsed["files"] = result["files"]
    token = str(uuid4())
    folder = ROOT / ".cache" / "previews"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.json"):
        if time.time() - old.stat().st_mtime > 1800:
            old.unlink(missing_ok=True)
    (folder / (token + ".json")).write_text(
        json.dumps(
            {
                "user": user["id"],
                "time": time.time(),
                "revision": rev,
                "parsed": parsed,
                "errors": result["errors"],
            }
        ),
        encoding="utf-8",
    )
    return {**result, "token": token, "revision": rev}


@router.get("/imports/formats")
def import_formats(user=Depends(admin)):
    return [
        {"table": table, "columns": columns.split()}
        for table, (_, _, columns) in IMPORT_SOURCES.items()
    ]


@router.post("/imports/{token}/confirm")
def confirm_import(
    token: str,
    background: BackgroundTasks,
    as_of_date: date = DEFAULT_DATE,
    user=Depends(admin),
):
    try:
        path = ROOT / ".cache" / "previews" / (str(UUID(token)) + ".json")
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Aperçu introuvable. Vérifiez à nouveau les fichiers.")
    if stored["user"] != user["id"]:
        raise HTTPException(403, "Cet aperçu appartient à un autre utilisateur.")
    if time.time() - stored["time"] > 1800:
        raise HTTPException(409, "Aperçu expiré. Vérifiez à nouveau les fichiers.")
    if stored["errors"]:
        raise HTTPException(422, "Corrigez les erreurs avant l’import.")
    try:
        with connection(user["id"]) as conn:
            result = conn.execute(
                "select public.importer_lot(%s,%s,%s) as result",
                [
                    Jsonb(stored["parsed"]["lot"]),
                    stored["revision"],
                    Jsonb(stored["parsed"]["files"]),
                ],
            ).fetchone()["result"]
    except psycopg.errors.SerializationFailure:
        raise HTTPException(409, "La base a changé. Vérifiez à nouveau les fichiers.")
    except psycopg.IntegrityError as error:
        raise HTTPException(
            422, "Import annulé : référence, rattachement ou valeur incompatible."
        ) from error
    path.unlink(missing_ok=True)
    if result["modelChanged"]:
        try:
            run_id, created = schedule(user["id"], as_of_date)
            result["calculationId"] = run_id
            if created:
                background.add_task(run_job, run_id, user["id"])
        except FileNotFoundError:
            result["calculationError"] = (
                "Import enregistré. Installez les quatre modèles puis relancez le calcul."
            )
    return result


@router.post("/calculs")
def calculate(
    background: BackgroundTasks, as_of_date: date = DEFAULT_DATE, user=Depends(member)
):
    try:
        run_id, created = schedule(user["id"], as_of_date)
        if created:
            background.add_task(run_job, run_id, user["id"])
        return {"id": run_id}
    except FileNotFoundError:
        raise HTTPException(
            503, "Les quatre modèles entraînés et leurs métriques sont requis."
        )


@router.get("/calculs/{run_id}")
def get_calculation(run_id: UUID, user=Depends(member)):
    with connection(user["id"]) as conn:
        run = conn.execute(
            "select * from public.calculs where id=%s", [run_id]
        ).fetchone()
    if not run:
        raise HTTPException(404, "Calcul introuvable.")
    return safe(run)


@router.put("/inspections/{inspection_id}")
def put_inspection(inspection_id: str, action: dict, user=Depends(member)):
    if action.get("id") != inspection_id:
        raise HTTPException(422, "Identifiant incompatible.")
    try:
        with connection(user["id"]) as conn:
            save_action(conn, action, user["id"])
            result = load_workspace(conn)
        return result
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Un dossier est déjà ouvert pour cet équipement.")
    except psycopg.IntegrityError:
        raise HTTPException(
            422, "Équipement ou prestataire inconnu, ou dossier incomplet."
        )


@router.delete("/inspections/{inspection_id}")
def delete_inspection(inspection_id: str, version: int, user=Depends(member)):
    with connection(user["id"]) as conn:
        removed = conn.execute(
            "delete from public.inspections where id=%s and version=%s returning id",
            [inspection_id, version],
        ).fetchone()
        if not removed:
            raise HTTPException(
                409,
                "Ce dossier a changé ou a déjà été supprimé. Rechargez les données.",
            )
        result = load_workspace(conn)
    return result


@router.post("/signalements")
def post_feedback(item: dict, user=Depends(member)):
    try:
        with connection(user["id"]) as conn:
            save_feedback(conn, item, user["id"])
            result = load_workspace(conn)
        return result
    except psycopg.IntegrityError:
        raise HTTPException(422, "Équipement inconnu.")


@router.post("/workspace/recovery/preview")
def preview_recovery(backup: dict, user=Depends(member)):
    if backup.get("version") != 1 or not isinstance(backup.get("actions"), list):
        raise HTTPException(422, "Sauvegarde invalide.")
    if not isinstance(backup.get("feedback", []), list):
        raise HTTPException(422, "Signalements invalides.")
    for action in backup["actions"]:
        validate_action(action)
    for item in backup.get("feedback", []):
        validate_feedback(item)
    with connection(user["id"]) as conn:
        existing = load_workspace(conn)
        ids = {a["id"] for a in existing["actions"]}
        fids = {f["id"] for f in existing["feedback"]}
        known = {
            r["equipement_id"]
            for r in conn.execute("select equipement_id from public.equipements")
        }
        opened = {
            a["equipmentId"] for a in existing["actions"] if a["status"] != "closed"
        }
        seen = set()
        for action in backup["actions"]:
            if action["id"] in seen:
                raise HTTPException(
                    422, "Identifiant de dossier répété dans la sauvegarde."
                )
            seen.add(action["id"])
            if action["id"] in ids:
                continue
            if action["equipmentId"] not in known:
                raise HTTPException(422, "Équipement inconnu dans la sauvegarde.")
            if action["status"] != "closed":
                if action["equipmentId"] in opened:
                    raise HTTPException(
                        409,
                        "Un dossier est déjà ouvert pour cet équipement. La copie locale est conservée.",
                    )
                opened.add(action["equipmentId"])
        for item in backup.get("feedback", []):
            if item["equipmentId"] not in known:
                raise HTTPException(422, "Équipement inconnu dans les signalements.")
    return {
        "actions": sum(a["id"] not in ids for a in backup["actions"]),
        "feedback": sum(f["id"] not in fids for f in backup.get("feedback", [])),
        "skipped": sum(a["id"] in ids for a in backup["actions"]),
    }


@router.post("/workspace/recovery")
def recover(backup: dict, user=Depends(member)):
    preview_recovery(backup, user)
    try:
        with connection(user["id"]) as conn:
            for action in backup["actions"]:
                save_action(conn, action, user["id"], recover=True)
            for item in backup.get("feedback", []):
                save_feedback(conn, item, user["id"], recover=True)
            result = load_workspace(conn)
        return result
    except psycopg.IntegrityError:
        raise HTTPException(
            409,
            "Récupération annulée : un dossier est déjà ouvert ou une référence est inconnue. La copie locale est conservée.",
        )
