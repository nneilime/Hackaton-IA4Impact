"""Recommendation card text: a short HEADLINE (always shown) + expandable DETAILS (two business sentences).

  headline  deterministic, built from the engine's facts: exact and instant ("qui va où, combien, quand")
  details   two French sentences: why this choice, and what the alternative would cost. The template version is
            instant; on demand (card expanded) the LLM rewrites it, accepted only if it has at most two sentences
            and every number, time and duration it contains is in the facts. Otherwise the template stays.

The engine's score is customer-hours without power (customers x hours). Before the LLM sees anything, the engine's
numbers are translated into business terms: extra customer-hours of the alternative, and the same thing as
"these N customers stay without power X longer" (delta / customers).
"""
from __future__ import annotations

import json
import re

from dispatch.copilot.client import chat, llm_available
from dispatch.engine.types import ExplanationFacts

SYSTEM = (
    "Tu es analyste d'exploitation chez Enedis et tu aides un responsable de crise. On te donne les faits calculés "
    "par le moteur d'optimisation pour UNE recommandation (une équipe envoyée sur une panne). Réponds UNIQUEMENT par "
    "un objet JSON {\"details\": \"...\"}. details = EXACTEMENT deux phrases en français, langage métier, sans jargon "
    "(pas : indice, score, algorithme). Phrase 1 : pourquoi ce choix, en reprenant la raison fournie dans \"reason\" "
    "(n'invente AUCUNE autre raison). Phrase 2 : ce que coûterait l'alternative, en clients-heures sans courant et en "
    "retard pour ces clients. Recopie les chiffres, heures et durées EXACTEMENT comme fournis, n'en calcule aucun."
)


def _dur(h: float) -> str:
    m = round(h * 60)
    return f"{m // 60} h {m % 60:02d}" if m >= 60 else f"{m} min"


def business_numbers(f: ExplanationFacts) -> dict:
    """Facts translated into business units (everything the text may use)."""
    x = f.factors
    out = {"team": f.team, "team_site": x.get("site_commune", ""), "incident_commune": x.get("commune", ""),
           "customers": x["customers"], "sensitive": bool(x.get("sensitive")), "travel": f"{x['travel_min']} min",
           "repair": f"{x['repair_h']:g} h", "restored_at": x.get("restored_clock"),
           "reason": ("c'est l'intervention qui rétablit le plus de clients par heure de travail" if f.rank_in_plan == 1
                      else "c'est l'une des interventions qui rétablissent le plus de clients par heure de travail")}
    alt = f.best_alternative_team
    if alt:
        out["alternative_team"] = alt["team"]
        out["extra_customer_hours"] = round(alt["delta"])
        if alt["delta"] > 0 and x["customers"]:
            out["equivalent_delay"] = _dur(alt["delta"] / x["customers"])
    if f.binding_constraint:
        out["constraint"] = f.binding_constraint
    return out


def headline_text(f: ExplanationFacts) -> str:
    b = business_numbers(f)
    when = f" vers {b['restored_at']}" if b["restored_at"] else ""
    sens = " · clients sensibles" if b["sensitive"] else ""
    return f"{b['team_site'] or b['team']} → {b['incident_commune'] or f.incident} : {b['customers']} clients rétablis{when}{sens}"


def details_template(f: ExplanationFacts) -> str:
    b = business_numbers(f)
    sens = ", dont des clients sensibles," if b["sensitive"] else ""
    s1 = (f"L'équipe {b['team']} ({b['team_site']}) rend le courant à {b['customers']} clients{sens} car {b['reason']} "
          f"({b['travel']} de route, {b['repair']} de réparation).")
    if b.get("extra_customer_hours", 0) > 0:
        s2 = (f"Confier cette panne à l'équipe {b['alternative_team']} coûterait {b['extra_customer_hours']} clients-heures "
              f"sans courant de plus, soit ces {b['customers']} clients privés d'électricité {b['equivalent_delay']} de plus.")
    elif b.get("constraint"):
        s2 = f"Point d'attention : {b['constraint']}."
    else:
        s2 = "Aucune autre équipe disponible ne ferait mieux sur cette panne."
    return f"{s1} {s2}"


TOKEN = re.compile(r"\d{1,2}\s?[h:]\s?\d{2}|\d+(?:[.,]\d+)?\s?(?:min|h)\b|\d+(?:[.,]\d+)?")


def _tokens(s: str) -> set[str]:
    return {re.sub(r"\s+", "", t).replace(",", ".").replace(":", "h").lower() for t in TOKEN.findall(s)}


def check_numbers_grounded(text: str, facts: ExplanationFacts) -> bool:
    """Every number, time ('15:18') and duration ('33 min', '2 h') in `text` must appear in the facts."""
    src = (json.dumps(facts.__dict__, default=str, ensure_ascii=False) + " "
           + json.dumps(business_numbers(facts), ensure_ascii=False) + " " + details_template(facts) + " "
           + headline_text(facts))
    allowed = _tokens(src)
    allowed |= {t[:-2] if t.endswith(".0") else t for t in allowed}
    return _tokens(text) <= allowed


def sentence_count(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s])


def llm_details(f: ExplanationFacts, cfg) -> str | None:
    """LLM-written details, or None if unavailable / not compliant (caller keeps the template)."""
    if not llm_available():
        return None
    try:
        raw = chat(SYSTEM, json.dumps(business_numbers(f), ensure_ascii=False), cfg, max_tokens=400, json_mode=True)
        text = json.loads(raw[raw.find("{"): raw.rfind("}") + 1]).get("details", "").strip()
    except Exception:
        return None
    if text and sentence_count(text) <= 2 and check_numbers_grounded(text, f):
        return text
    return None


def explain_card(f: ExplanationFacts, cfg, use_llm: bool = False) -> dict:
    details = llm_details(f, cfg) if use_llm else None
    return {"headline": headline_text(f), "details": details or details_template(f),
            "source": "llm" if details else "template"}


def explain_text(f: ExplanationFacts, cfg, clock=None) -> str:
    """Backward-compatible: headline + template details."""
    c = explain_card(f, cfg)
    return f"{c['headline']}. {c['details']}"
