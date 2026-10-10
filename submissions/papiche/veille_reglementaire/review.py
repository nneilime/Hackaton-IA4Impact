# SPDX-License-Identifier: AGPL-3.0-or-later
"""Relecture humaine : les sources que l'IA ne tranche pas, et ce que l'expert peut en faire.

Deux cas arrivent dans la file :
  - « a_corriger » : trois essais ratés, rien n'a été publié ;
  - « a_confirmer » : publié, mais le second avis de l'IA doute.
L'expert peut : corriger (nouvelles valeurs, contrôlées par le MÊME contrat et le MÊME contrôle de preuve que l'IA),
confirmer une proposition, ou écarter la source (avec une raison). Chaque décision est gardée dans
data/processed/corrections.jsonl et rejouée après chaque nouvelle extraction : une relecture n'est jamais perdue.
Seul l'expert peut poser le statut « valide_humain ».
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import ValidationError

from . import config, eppo_codes, extraction_loop, pipeline, qdrant_store
from .models import Extraction

CORRECTIONS_FILE = config.PROCESSED / "corrections.jsonl"
EXTRACTION_FIELDS = list(Extraction.model_fields)


# ── Décisions déjà prises ────────────────────────────────────────────────────

def load_decisions() -> dict[str, dict]:
    """Dernière décision par passage (la plus récente l'emporte)."""
    if not CORRECTIONS_FILE.exists():
        return {}
    decisions = {}
    for line in CORRECTIONS_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            decisions[entry["passage_id"]] = entry
    return decisions


def save_decision(entry: dict) -> None:
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    with CORRECTIONS_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── La file à relire ─────────────────────────────────────────────────────────

def last_proposal(trace: dict) -> dict:
    """La dernière proposition JSON du modèle, si elle est lisible (point de départ de la correction)."""
    for attempt in reversed(trace["attempts"]):
        try:
            data = json.loads(attempt["raw"] or "")
            if isinstance(data, dict):
                return {key: data.get(key) for key in EXTRACTION_FIELDS if key in data}
        except ValueError:
            continue
    return {}


def queue_item(trace: dict, kind: str) -> dict:
    passage, record = trace["passage"], trace["record"]
    if kind == "a_corriger":
        reason = trace["attempts"][-1].get("error", "")
        proposal = last_proposal(trace)
    else:
        reason = "; ".join((trace["critic"] or {}).get("motifs", [])) or "le second avis de l'IA doute"
        proposal = {key: record.get(key) for key in EXTRACTION_FIELDS if key in record} | {"quote": record["citation"]["quote"]}
    return {"passage_id": passage["passage_id"], "kind": kind, "product": passage["product"], "country": passage["country"],
            "source_id": passage["source_id"], "source_url": passage["source_url"], "collected_at": passage["collected_at"],
            "text": passage["text"], "reason": reason, "proposal": proposal, "attempts": len(trace["attempts"])}


def review_queue(include_decided: bool = False) -> list[dict]:
    decisions = load_decisions()
    items = []
    for trace in pipeline.load("traces.jsonl"):
        if trace["outcome"] == "hitl":
            item = queue_item(trace, "a_corriger")
        elif trace["record"] and trace["record"]["validation_status"] == "a_confirmer":
            item = queue_item(trace, "a_confirmer")
        else:
            continue
        item["decision"] = decisions.get(item["passage_id"], {}).get("action")
        if include_decided or item["decision"] is None:
            items.append(item)
    return items


def find_trace(passage_id: str) -> dict:
    trace = next((t for t in pipeline.load("traces.jsonl") if t["passage"]["passage_id"] == passage_id), None)
    if trace is None:
        raise KeyError(f"passage inconnu : {passage_id}")
    return trace


# ── Actions de l'expert ──────────────────────────────────────────────────────

def build_human_record(trace: dict, fields: dict, author: str) -> dict:
    """Valide les valeurs de l'expert comme celles de l'IA (contrat + preuve), puis fabrique l'enregistrement."""
    passage = qdrant_store.get_passage(trace["passage"]["passage_id"])
    if passage is None:
        raise KeyError("texte source introuvable dans Qdrant (relancer `./veille index`)")
    try:
        extraction = Extraction.model_validate({k: v for k, v in fields.items() if v not in (None, "")})
    except ValidationError as error:
        raise ValueError(extraction_loop.format_pydantic_error(error)) from error
    failed = [c["detail"] for c in extraction_loop.check_proof(extraction, passage.text) if not c["ok"]]
    if failed:
        raise ValueError("preuve non retrouvée dans la source : " + " ; ".join(failed))
    attempts = trace["attempts"] + [{"model": f"expert:{author}"}]
    record = extraction_loop.build_record(
        passage, extraction, eppo_codes.normalize(extraction.crop_original, "crop"),
        eppo_codes.normalize(extraction.target_original, "pest"), "valide_humain",
        [f"relu et corrigé par {author}"], attempts)
    return json.loads(record.model_dump_json())


def write_record(record: dict) -> None:
    """Remplace (ou ajoute) l'enregistrement dans records.jsonl et dans Qdrant."""
    records = [r for r in pipeline.load("records.jsonl") if r["record_id"] != record["record_id"]] + [record]
    pipeline._dump("records.jsonl", records)
    qdrant_store.upsert_records([record])


def apply_decision(entry: dict) -> None:
    trace = find_trace(entry["passage_id"])
    if entry["action"] == "corrected":
        write_record(build_human_record(trace, entry["fields"], entry["author"]))
    elif entry["action"] == "confirmed" and trace["record"]:
        record = dict(trace["record"], validation_status="valide_humain",
                      critic_notes=trace["record"]["critic_notes"] + [f"confirmé par {entry['author']}"])
        write_record(record)


def decide(passage_id: str, action: str, author: str, fields: dict | None = None, reason: str = "") -> dict:
    """Enregistre une décision (après l'avoir vérifiée) et l'applique tout de suite."""
    entry = {"passage_id": passage_id, "action": action, "author": author, "reason": reason, "fields": fields or {},
             "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if action not in ("corrected", "confirmed", "dismissed"):
        raise ValueError("action inconnue")
    if action == "corrected" and not fields:
        raise ValueError("aucune valeur fournie")
    if action == "dismissed" and not reason.strip():
        raise ValueError("une raison est obligatoire pour écarter une source")
    apply_decision(entry)                 # lève une erreur claire AVANT d'enregistrer si les valeurs sont refusées
    save_decision(entry)
    return entry


def apply_stored_corrections() -> int:
    """À appeler après chaque extraction : rejoue les décisions de l'expert (rien n'est perdu)."""
    count = 0
    for entry in load_decisions().values():
        try:
            apply_decision(entry)
            count += 1
        except (KeyError, ValueError) as error:
            print(f"[relecture] décision {entry['passage_id']} non rejouée : {error}")
    return count


def queue_for_page() -> dict:
    """Résumé pour la page : file en attente et décisions déjà prises."""
    everything = review_queue(include_decided=True)
    waiting = [i for i in everything if i["decision"] is None]
    shorten = lambda item: {**item, "text": item["text"][:420]}
    return {"waiting": [shorten(i) for i in waiting], "decided": len(everything) - len(waiting),
            "to_correct": sum(i["kind"] == "a_corriger" for i in waiting),
            "to_confirm": sum(i["kind"] == "a_confirmer" for i in waiting)}
