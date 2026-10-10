# SPDX-License-Identifier: AGPL-3.0-or-later
"""Boucle de contrôle : extraire (IA) → valider la forme (Pydantic) → vérifier la preuve (code) → recommencer.

Principe : l'IA propose, le code décide. Un enregistrement n'est publié que si chaque valeur est retrouvée
mot à mot dans le passage source. Après MAX_ATTEMPTS échecs, rien n'est publié : un expert tranche.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date

from pydantic import ValidationError

from . import config, eppo_codes, llm
from .models import Citation, CriticVerdict, Extraction, Record, normalize_dose, numbers_in
from .sources import Passage

FIELDS_COPIED_FROM_PASSAGE = ("crop_original", "target_original", "dose_original", "dose_unit")
COUNTED_FIELDS = ("max_applications", "min_interval_days", "pre_harvest_interval_days")


# ── Petits outils ────────────────────────────────────────────────────────────

def read_prompt(file_name: str) -> str:
    return (config.PROMPTS / file_name).read_text(encoding="utf-8")


def normalize_text(text: str | None) -> str:
    """Compare sans tenir compte des espaces multiples ni de la casse (jamais des mots)."""
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def build_user_prompt(passage: Passage) -> str:
    return (f"Source : {passage.source_id} ({passage.country}) — produit {passage.product}\n"
            f"<passage>\n{passage.text}\n</passage>\n"
            "Extrais l'enregistrement JSON.")


def build_retry_prompt(first_prompt: str, previous_answer: str | None, error: str) -> str:
    """Le modèle revoit sa réponse refusée et le motif exact du refus."""
    return (f"{first_prompt}\n\nTa réponse précédente :\n{previous_answer or '(vide)'}\n\n"
            + read_prompt("retry.user.md").format(error=error))


def format_pydantic_error(error: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, e['loc'])) or 'objet'}: {e['msg']}" for e in error.errors())


# ── Contrôle de la preuve (en code : rien n'est laissé à l'appréciation de l'IA) ─

def check_proof(extraction: Extraction, passage_text: str) -> list[dict]:
    """Chaque valeur extraite doit exister dans le passage. Retourne la liste des contrôles et leur résultat."""
    passage = normalize_text(passage_text)
    checks: list[dict] = []

    def add(name: str, passed: bool, detail: str):
        checks.append({"check": name, "ok": passed, "detail": detail})

    add("citation_retrouvee", normalize_text(extraction.quote) in passage,
        f"« {extraction.quote} » doit figurer mot à mot dans le passage")

    for field in FIELDS_COPIED_FROM_PASSAGE:
        value = getattr(extraction, field)
        if value:
            add(f"{field}_retrouve", normalize_text(value) in passage, f"{field}={value!r} doit figurer dans le passage")

    for restriction in extraction.restrictions:
        add("restriction_retrouvee", normalize_text(restriction) in passage,
            f"restriction {restriction!r} doit figurer dans le passage")

    numbers_in_passage = numbers_in(passage_text)
    for field in COUNTED_FIELDS:
        value = getattr(extraction, field)
        if value is not None:
            add(f"{field}_present", float(value) in numbers_in_passage, f"{field}={value} doit apparaître dans le passage")

    if extraction.dose_value is not None:
        add("dose_portee_par_la_citation", normalize_text(extraction.dose_original) in normalize_text(extraction.quote),
            f"la citation doit contenir la dose « {extraction.dose_original} »")
    return checks


def ask_critic(passage_text: str, extraction: Extraction) -> dict:
    """Second avis de l'IA, indicatif : il peut dégrader le statut, jamais publier à la place du code."""
    answer = llm.chat_json(read_prompt("critic.system.md"),
                           f"<passage>\n{passage_text}\n</passage>\nEnregistrement :\n{extraction.model_dump_json()}",
                           num_predict=200)
    try:
        verdict = CriticVerdict.model_validate(json.loads(answer["text"] or "{}"))
        return {"verdict": verdict.verdict, "motifs": verdict.motifs, "raw": answer["text"], "cached": answer["cached"]}
    except ValueError as e:
        return {"verdict": "indetermine", "motifs": [f"sortie du critique invalide : {e}"],
                "raw": answer["text"], "cached": answer["cached"]}


# ── Une tentative d'extraction ───────────────────────────────────────────────

def run_one_attempt(number: int, system_prompt: str, user_prompt: str, passage: Passage) -> tuple[dict, Extraction | None]:
    """Appelle l'IA, valide la forme, vérifie la preuve. Retourne (compte rendu de l'essai, extraction si acceptée)."""
    answer = llm.chat_json(system_prompt, user_prompt)
    attempt = {"n": number, "user_prompt": user_prompt, "raw": answer["text"], "cached": answer["cached"],
               "model": answer["model"], "backend": answer["backend"], "parse_error": None, "pydantic_error": None,
               "checks": [], "accepted": False}

    extraction, error = None, None
    try:
        data = json.loads(answer["text"] or "")
        if not isinstance(data, dict):
            raise ValueError("la racine doit être un objet JSON")
        extraction = Extraction.model_validate(data)
    except ValidationError as e:               # la forme ne respecte pas le contrat Pydantic
        error = attempt["pydantic_error"] = format_pydantic_error(e)
    except ValueError as e:                    # JSON illisible (JSONDecodeError est un ValueError)
        error = attempt["parse_error"] = f"JSON invalide : {e}"

    if extraction is not None:
        attempt["checks"] = check_proof(extraction, passage.text)
        failed = [c for c in attempt["checks"] if not c["ok"]]
        if failed:
            error = "preuve non retrouvée : " + " ; ".join(c["detail"] for c in failed)

    if error:
        attempt["error"] = error
        return attempt, None
    attempt["accepted"] = True
    return attempt, extraction


# ── Construction du résultat ─────────────────────────────────────────────────

def build_record(passage: Passage, extraction: Extraction, crop_eppo: dict, target_eppo: dict,
                 status: str, notes: list[str], attempts: list[dict]) -> Record:
    dose_norm_value, dose_norm_unit = normalize_dose(extraction.dose_value, extraction.dose_unit)
    citation = Citation(
        source_id=passage.source_id, source_url=passage.source_url, dataset_url=passage.dataset_url,
        collected_at=date.fromisoformat(passage.collected_at), quote=extraction.quote,
        passage_id=passage.passage_id, passage_sha256=hashlib.sha256(passage.text.encode()).hexdigest())
    return Record(
        record_id=hashlib.sha1(passage.passage_id.encode()).hexdigest()[:16],
        product=passage.product, country=passage.country, region=passage.region, reg_number=passage.reg_number,
        holder=passage.holder, authorization_status_original=passage.status_original,
        authorization_status=passage.status,
        crop_original=extraction.crop_original, crop_eppo=crop_eppo["eppo"],
        target_original=extraction.target_original, target_eppo=target_eppo["eppo"],
        dose_original=extraction.dose_original, dose_value=extraction.dose_value, dose_unit=extraction.dose_unit,
        dose_norm_value=dose_norm_value, dose_norm_unit=dose_norm_unit,
        max_applications=extraction.max_applications, min_interval_days=extraction.min_interval_days,
        pre_harvest_interval_days=extraction.pre_harvest_interval_days, restrictions=extraction.restrictions,
        citation=citation, validation_status=status, attempts=len(attempts),
        model=attempts[-1]["model"], critic_notes=notes)


def extract_passage(passage: Passage, max_attempts: int | None = None, use_llm_critic: bool | None = None) -> dict:
    """Traite un passage. Retourne une trace complète (utilisée par la page pédagogique) et le Record si accepté."""
    max_attempts = max_attempts or config.MAX_ATTEMPTS
    use_llm_critic = config.LLM_CRITIC if use_llm_critic is None else use_llm_critic
    system_prompt = read_prompt("extractor.system.md")
    first_prompt = build_user_prompt(passage)

    attempts: list[dict] = []
    extraction = None
    user_prompt = first_prompt
    for number in range(1, max_attempts + 1):
        attempt, extraction = run_one_attempt(number, system_prompt, user_prompt, passage)
        attempts.append(attempt)
        if extraction is not None:
            break
        user_prompt = build_retry_prompt(first_prompt, attempt["raw"], attempt["error"])

    trace = {
        "passage": {key: getattr(passage, key) for key in
                    ("passage_id", "source_id", "country", "product", "reg_number", "text", "source_url", "collected_at")},
        "attempts": attempts, "outcome": "accepted" if extraction else "hitl",
        "record": None, "critic": None, "eppo": {},
    }
    if extraction is None:
        return trace        # trois échecs : rien n'est publié, un expert tranche

    status, notes = "verifie_auto", []
    if use_llm_critic:
        trace["critic"] = ask_critic(passage.text, extraction)
        if trace["critic"]["verdict"] != "ok":
            status = "a_confirmer"
            notes = ["second avis IA : " + ("; ".join(trace["critic"]["motifs"]) or trace["critic"]["verdict"])]

    crop_eppo = eppo_codes.normalize(extraction.crop_original, "crop")
    target_eppo = eppo_codes.normalize(extraction.target_original, "pest")
    trace["eppo"] = {"crop": crop_eppo, "target": target_eppo}
    record = build_record(passage, extraction, crop_eppo, target_eppo, status, notes, attempts)
    trace["record"] = json.loads(record.model_dump_json())
    return trace
