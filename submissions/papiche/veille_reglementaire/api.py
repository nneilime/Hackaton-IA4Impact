# SPDX-License-Identifier: AGPL-3.0-or-later
"""API REST (contrat OpenAPI auto-généré sur /openapi.json) — base d'un connecteur personnalisé Power Platform."""
from __future__ import annotations
from typing import Optional
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from . import admin_api, comparison_table, config, pipeline, question_answering, review

app = FastAPI(title="Veille réglementaire PPP", version="0.1.0",
              description="Veille réglementaire PPP : enregistrements cités, vérifiés, avec retour à la source.")


app.include_router(admin_api.router)
app.include_router(admin_api.protected)


class Ask(BaseModel):
    question: str


@app.get("/health", operation_id="health")
def health():
    return {"status": "ok", "records": len(pipeline.load("records.jsonl"))}


@app.get("/records", operation_id="listRecords")
def records(product: Optional[str] = None, country: Optional[str] = None, crop: Optional[str] = None,
            target: Optional[str] = None):
    return comparison_table.table(pipeline.load("records.jsonl"), product, [country] if country else None, crop, target)


@app.get("/footprint", operation_id="getFootprint")
def footprint():
    return comparison_table.footprint(pipeline.load("records.jsonl"))


@app.get("/sisters", operation_id="listSisterHypotheses")
def sisters():
    return pipeline.load("sisters.jsonl")


@app.post("/ask", operation_id="askRegulatory")
def ask(body: Ask):
    return question_answering.ask(body.question)


# ── Relecture humaine : les sources que l'IA ne tranche pas ─────────────────

class Decision(BaseModel):
    author: str
    reason: str = ""
    fields: dict = {}


def apply_or_refuse(passage_id: str, action: str, body: Decision):
    """Une valeur refusée par le contrat ou le contrôle de preuve revient à l'expert avec son motif exact."""
    try:
        return review.decide(passage_id, action, body.author, fields=body.fields, reason=body.reason)
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.get("/review", operation_id="listReview")
def review_list(all: bool = False):
    return review.review_queue(include_decided=all)


@app.post("/review/{passage_id}/correct", dependencies=[Depends(admin_api.require_token)], operation_id="correctPassage")
def review_correct(passage_id: str, body: Decision):
    return apply_or_refuse(passage_id, "corrected", body)


@app.post("/review/{passage_id}/confirm", dependencies=[Depends(admin_api.require_token)], operation_id="confirmPassage")
def review_confirm(passage_id: str, body: Decision):
    return apply_or_refuse(passage_id, "confirmed", body)


@app.post("/review/{passage_id}/dismiss", dependencies=[Depends(admin_api.require_token)], operation_id="dismissPassage")
def review_dismiss(passage_id: str, body: Decision):
    return apply_or_refuse(passage_id, "dismissed", body)


@app.get("/admin", include_in_schema=False)
@app.get("/review-ui", include_in_schema=False)
def admin_screen():
    return FileResponse(config.WEB / "admin.html")
