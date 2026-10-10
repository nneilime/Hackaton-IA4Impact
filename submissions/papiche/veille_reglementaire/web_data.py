# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fabrique web/data.js : tout ce que la page didactique affiche vient de VRAIES exécutions (traces, Qdrant, réponses)."""
from __future__ import annotations
import json
from collections import Counter
from datetime import date
from . import narration, review, source_viewer, question_answering, comparison_table, config, llm, pipeline, qdrant_store

QUESTIONS = [
    "Quelle est la dose de LALSTOP G46 WG sur vigne en France ?",
    "LALGUARD M52 OD est-il homologué au Canada, et pour quels ravageurs ?",
    "Quelles cultures sont couvertes par BOTANIGARD 22 WP en France ?",
    "Quelle est la dose de LALGUARD M52 OD contre le thrips au Canada ?",
]


def _question_for(tr: dict) -> str:
    r, p = tr["record"] or {}, tr["passage"]
    bits = [p["product"]]
    if r.get("crop_original"):
        bits.append(f"sur {r['crop_original']}")
    if r.get("target_original"):
        bits.append(f"contre {r['target_original']}")
    country = {"FR": "en France", "CA": "au Canada", "US": "aux États-Unis"}[p["country"]]
    return f"Quelle est la dose de {' '.join(bits)} {country} ?"


def _pick(traces: list[dict]) -> list[dict]:
    def first(pred):
        return next((t for t in traces if pred(t)), None)
    cases = [
        ("Source structurée (France, e-Phy)", first(lambda t: t["passage"]["source_id"] == "ephy" and t["outcome"] == "accepted"
                                                  and len(t["attempts"]) == 1 and "G46" in t["passage"]["product"])
         or first(lambda t: t["passage"]["source_id"] == "ephy" and t["outcome"] == "accepted")),
        ("Information absente : l'IA doit répondre null (Canada, PMRA)",
         first(lambda t: t["passage"]["source_id"] == "pmra" and t["outcome"] == "accepted" and "M52 OD" in t["passage"]["product"])
         or first(lambda t: t["passage"]["source_id"] == "pmra" and t["outcome"] == "accepted")),
        ("Étiquette PDF américaine (EPA) : texte désordonné, unités US",
         first(lambda t: t["passage"]["source_id"] == "epa" and t["outcome"] == "accepted" and (t["record"] or {}).get("dose_norm_value")
               and t["record"]["validation_status"] == "verifie_auto")
         or first(lambda t: t["passage"]["source_id"] == "epa" and t["outcome"] == "accepted" and (t["record"] or {}).get("dose_value"))),
        ("La boucle corrige le modèle (retry)",
         first(lambda t: t["outcome"] == "accepted" and len(t["attempts"]) > 1 and t["record"]["validation_status"] == "verifie_auto"
               and t["record"].get("dose_value"))
         or first(lambda t: t["outcome"] == "accepted" and len(t["attempts"]) > 1)),
        ("Le modèle échoue 3 fois : arbitrage humain, rien n'est publié",
         first(lambda t: t["outcome"] == "hitl")),
    ]
    out = []
    for title, tr in cases:
        if not tr:
            continue
        q = _question_for(tr) if tr["record"] else f"Quelle est la dose de {tr['passage']['product']} ?"
        retrieval = qdrant_store.search_passages(q, k=5)
        out.append({"title": title, "question": q, "trace": tr,
                    "retrieval": [{"score": h["score"], "passage_id": h["passage_id"], "product": h["product"],
                                   "country": h["country"], "source_id": h["source_id"], "text": h["text"][:260]} for h in retrieval]})
    return out


def measure_performance(traces: list[dict]) -> dict:
    """Chiffres qui expliquent la performance : ce que chaque garde-fou a rattrapé, calculé sur les vraies traces."""
    published = [t for t in traces if t["outcome"] == "accepted"]
    all_attempts = [a for t in traces for a in t["attempts"]]
    return {
        "passages": len(traces),
        "published": len(published),
        "published_rate": round(len(published) / len(traces), 3) if traces else 0,
        "first_try": sum(len(t["attempts"]) == 1 for t in published),
        "rescued_by_retry": sum(len(t["attempts"]) > 1 for t in published),
        "sent_to_expert": len(traces) - len(published),
        "flagged_to_confirm": sum(t["record"]["validation_status"] == "a_confirmer" for t in published),
        "refused_by_pydantic": sum(bool(a.get("pydantic_error")) for a in all_attempts),
        "refused_unreadable_json": sum(bool(a.get("parse_error")) for a in all_attempts),
        "refused_by_proof_check": sum(str(a.get("error", "")).startswith("preuve non retrouvée") for a in all_attempts),
    }


def read_network_runs() -> dict | None:
    """Preuve de sobriété : la collecte à froid, puis son rejeu (requêtes conditionnelles)."""
    path = config.PROCESSED / "collect_runs.jsonl"
    runs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    if len(runs) >= 2:
        return {"cold": runs[-2]["network"], "warm": runs[-1]["network"]}
    return {"cold": runs[-1]["network"], "warm": None} if runs else None


def count_lines(path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


def read_prompt_history() -> list[dict]:
    """Les trois versions du prompt d'extraction, relues dans data/processed/history (preuve de la démarche)."""
    history = config.PROCESSED / "history"
    versions = [("v1", "Prompt de départ", history / "prompt_v1"),
                ("v2", "Contrôle de preuve plus strict, ancien prompt", history / "prompt_v2_strict"),
                ("v3", "Règle de citation précisée (version actuelle)", config.PROCESSED)]
    rows = []
    for name, description, folder in versions:
        if not (folder / "eval.json").exists():
            continue
        evaluation = json.loads((folder / "eval.json").read_text())
        rows.append({"version": name, "description": description, "published": count_lines(folder / "records.jsonl"),
                     "sent_to_expert": count_lines(folder / "hitl.jsonl"),
                     "first_try": evaluation["essais_par_passage"].get("1", 0)})
    return rows


def build():
    traces = pipeline.load("traces.jsonl")
    records = pipeline.load("records.jsonl")
    passages = qdrant_store.all_passages()
    qa = []
    for q in QUESTIONS:
        r = question_answering.ask(q)
        qa.append({k: r[k] for k in ("question", "plan", "method", "answer", "answer_grounded_by_code", "citations")}
                  | {"rows": r["rows"][:6]})
    data = {
        "built": date.today().isoformat(), "model": config.MODEL, "embed_model": config.EMBED_MODEL,
        "llm_backend": llm.backend(), "qdrant": qdrant_store.mode(),
        "counts": {"passages": len(passages), "passages_by_source": dict(Counter(p.source_id for p in passages)),
                   "records": len(records), "hitl": len(pipeline.load("hitl.jsonl")),
                   "retries": sum(1 for t in traces if len(t["attempts"]) > 1),
                   "status": dict(Counter(r["validation_status"] for r in records))},
        "eval": json.loads((config.PROCESSED / "eval.json").read_text()) if (config.PROCESSED / "eval.json").exists() else None,
        "prompts": {n: (config.PROMPTS / n).read_text(encoding="utf-8")
                    for n in ("extractor.system.md", "retry.user.md", "critic.system.md", "eppo.system.md", "query.system.md")},
        "bench": json.loads((config.PROCESSED / "bench" / "report.json").read_text()) if (config.PROCESSED / "bench" / "report.json").exists() else None,
        "cost": json.loads((config.PROCESSED / "cost" / "report.json").read_text()) if (config.PROCESSED / "cost" / "report.json").exists() else None,
        "code": source_viewer.build(), "review": review.queue_for_page(),
        "sources": [dict(module.INFO) for module in pipeline.SOURCES.values()],
        "holdout": json.loads((config.PROCESSED / "holdout.json").read_text()) if (config.PROCESSED / "holdout.json").exists() else None,
        "narration": narration.render_script(), "audio_available": (narration.AUDIO_FOLDER / "pk-01.mp3").exists(), "network": read_network_runs(), "performance": measure_performance(traces), "prompt_history": read_prompt_history(),
        "models_py": (config.ROOT / "veille_reglementaire" / "models.py").read_text(encoding="utf-8"),
        "cases": _pick(traces), "qa": qa,
        "table": comparison_table.table(records), "footprint": comparison_table.footprint(records),
        "sisters": pipeline.load("sisters.jsonl"),
        "scope": pipeline.scope(),
    }
    (config.WEB / "data.js").write_text("window.VEILLE = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"web/data.js écrit ({len(json.dumps(data)) // 1024} Ko)")
