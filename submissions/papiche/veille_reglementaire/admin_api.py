# SPDX-License-Identifier: AGPL-3.0-or-later
"""Interface d'administration pour l'humain : voir l'état, relire, gérer les sources, lancer les traitements.

Tout ce qui modifie des données passe par ici ou par `review` : mêmes contrôles que la ligne de commande.
Sécurité : le serveur écoute sur 127.0.0.1 par défaut ; si VEILLE_ADMIN_TOKEN est défini, chaque action qui modifie
quelque chose exige l'en-tête X-Admin-Token.
"""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from . import config, pipeline, qdrant_store, review, source_scaffold
from .sources import discover_sources

JOBS_FOLDER = config.DATA / "jobs"
RUNNABLE_TASKS = ("collect", "index", "extract", "eval", "web")
ROLES = ("pilote", "sœur", "concurrent")


def require_token(x_admin_token: Optional[str] = Header(default=None)) -> None:
    if config.ADMIN_TOKEN and x_admin_token != config.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="jeton d'administration manquant ou incorrect")


router = APIRouter(prefix="/admin", tags=["administration"])
protected = APIRouter(prefix="/admin", tags=["administration"], dependencies=[Depends(require_token)])


# ── État général ─────────────────────────────────────────────────────────────

def last_collection_by_source() -> dict[str, str]:
    dates = {}
    for source_id in pipeline.SOURCES:
        meta = config.RAW / source_id / "_meta.json"
        if meta.exists():
            dates[source_id] = json.loads(meta.read_text()).get("collected_at", "")
    return dates


@router.get("/overview", operation_id="adminOverview")
def overview() -> dict:
    records = pipeline.load("records.jsonl")
    passages = Counter(p.source_id for p in qdrant_store.all_passages())
    records_by_source = Counter(r["citation"]["source_id"] for r in records)
    last_dates = last_collection_by_source()
    queue = review.queue_for_page()
    return {
        "records": len(records), "by_status": dict(Counter(r["validation_status"] for r in records)),
        "review": {"to_correct": queue["to_correct"], "to_confirm": queue["to_confirm"], "decided": queue["decided"]},
        "sources": [{**module.INFO, "passages": passages.get(source_id, 0), "records": records_by_source.get(source_id, 0),
                     "collected_at": last_dates.get(source_id)} for source_id, module in pipeline.SOURCES.items()],
        "system": {"model": config.MODEL, "embedding": config.EMBED_MODEL, "qdrant": qdrant_store.mode(),
                   "token_required": bool(config.ADMIN_TOKEN)},
    }


@router.get("/history", operation_id="adminHistory")
def history() -> list[dict]:
    """Toutes les décisions de l'expert, de la plus récente à la plus ancienne (piste d'audit)."""
    if not review.CORRECTIONS_FILE.exists():
        return []
    entries = [json.loads(line) for line in review.CORRECTIONS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    products = {i["passage_id"]: i["product"] for i in review.review_queue(include_decided=True)}
    return [{**e, "product": products.get(e["passage_id"], "")} for e in reversed(entries)]


# ── Périmètre surveillé et sources ───────────────────────────────────────────

class NewSource(BaseModel):
    source_id: str
    name: str
    country_code: str
    country: str
    region: str
    format: str = "CSV"
    lang: str = "EN"


@router.get("/scope", operation_id="adminGetScope")
def get_scope() -> dict:
    return {"scope": pipeline.scope(), "sources": [dict(m.INFO) for m in pipeline.SOURCES.values()], "roles": list(ROLES)}


def validate_scope(scope: dict) -> dict:
    products = scope.get("products")
    if not isinstance(products, list) or not products:
        raise ValueError("le périmètre doit contenir au moins un produit")
    for product in products:
        if not str(product.get("name", "")).strip():
            raise ValueError("chaque produit a un nom")
        if product.get("role") not in ROLES:
            raise ValueError(f"rôle de « {product.get('name')} » : {', '.join(ROLES)}")
        for key, value in product.items():
            if key in ("role", "name"):
                continue
            if key not in pipeline.SOURCES or not isinstance(value, list) or not all(isinstance(n, str) for n in value):
                raise ValueError(f"« {product['name']} » : la clé « {key} » doit être une source connue avec une liste de noms")
    return scope


@protected.put("/scope", operation_id="adminPutScope")
def put_scope(body: dict) -> dict:
    try:
        scope = validate_scope(body)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    current = pipeline.scope()
    scope = {"_note": current.get("_note", ""), "products": scope["products"]}
    (config.CONFIG / "scope.json").write_text(json.dumps(scope, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saved": True, "products": len(scope["products"])}


@protected.post("/sources", operation_id="adminNewSource")
def new_source(body: NewSource) -> dict:
    try:
        path = source_scaffold.create_source(body.source_id, body.name, body.country_code, body.country, body.region, body.format, body.lang)
    except (ValueError, FileExistsError) as error:
        raise HTTPException(status_code=400, detail=str(error))
    importlib.invalidate_caches()
    pipeline.SOURCES = discover_sources()
    return {"created": path, "next_steps": source_scaffold.NEXT_STEPS.format(path=path, source_id=body.source_id)}


# ── Lancer un traitement ─────────────────────────────────────────────────────

class RunRequest(BaseModel):
    task: str
    source: Optional[str] = None
    product: Optional[str] = None
    per_product: Optional[int] = None
    limit: Optional[int] = None


def build_command(request: RunRequest) -> list[str]:
    if request.task not in RUNNABLE_TASKS:
        raise ValueError(f"traitement inconnu : {request.task}")
    if request.source and request.source not in pipeline.SOURCES:
        raise ValueError(f"source inconnue : {request.source}")
    command = [sys.executable, "-m", "veille_reglementaire", request.task]
    if request.source and request.task in ("collect", "index"):
        command += ["--only", request.source]
    if request.task == "extract":
        if request.source:
            command += ["--source", request.source]
        if request.product:
            command += ["--product", request.product]
        if request.per_product:
            command += ["--per-product", str(int(request.per_product))]
        if request.limit:
            command += ["--limit", str(int(request.limit))]
    return command


def read_job(job_id: str) -> dict:
    path = JOBS_FOLDER / f"{job_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="traitement inconnu")
    job = json.loads(path.read_text())
    process = RUNNING.get(job_id)
    if job["state"] == "running" and process is not None and process.poll() is not None:
        job.update(state="done" if process.returncode == 0 else "failed", exit_code=process.returncode,
                   finished=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        path.write_text(json.dumps(job, ensure_ascii=False))
        RUNNING.pop(job_id, None)
    log = (JOBS_FOLDER / f"{job_id}.log")
    return {**job, "log": log.read_text(errors="replace")[-8000:] if log.exists() else ""}


RUNNING: dict[str, subprocess.Popen] = {}


@protected.post("/run", operation_id="adminRun")
def run_task(request: RunRequest) -> dict:
    if any(p.poll() is None for p in RUNNING.values()):
        raise HTTPException(status_code=409, detail="un traitement est déjà en cours : attendre sa fin")
    try:
        command = build_command(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    JOBS_FOLDER.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex[:10]
    log = (JOBS_FOLDER / f"{job_id}.log").open("w")
    RUNNING[job_id] = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, cwd=config.ROOT)
    job = {"id": job_id, "task": request.task, "command": " ".join(command[3:]), "state": "running",
           "started": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (JOBS_FOLDER / f"{job_id}.json").write_text(json.dumps(job, ensure_ascii=False))
    return job


@router.get("/jobs", operation_id="adminJobs")
def list_jobs() -> list[dict]:
    if not JOBS_FOLDER.exists():
        return []
    ids = [p.stem for p in sorted(JOBS_FOLDER.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:8]]
    return [{k: v for k, v in read_job(i).items() if k != "log"} for i in ids]


@router.get("/jobs/{job_id}", operation_id="adminJob")
def get_job(job_id: str) -> dict:
    return read_job(job_id)
