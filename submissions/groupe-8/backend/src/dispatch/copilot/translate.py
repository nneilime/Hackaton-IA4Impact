"""Manager's refusal reason (quick chip and/or free text) -> modifiers from the fixed catalogue.

With an API key, Claude proposes the JSON modifiers; without one (or if its answer is unusable) a deterministic
parser handles the standard reasons. Either way the output goes through the validator before the engine sees it.
Returns {"modifiers": [dict, ...], "restatement": str} or {"question": str} when information is missing.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from dispatch.copilot.client import chat, llm_available

REASONS = {
    "acces": "Route coupée / zone inaccessible",
    "equipe": "Équipe indisponible (fatigue, véhicule, matériel)",
    "duree": "Durée de dépannage sous-estimée",
    "priorite": "Un autre incident est plus prioritaire",
    "competence": "Compétence / habilitation manquante",
    "securite": "Sécurité",
    "terrain": "Connaissance du terrain",
    "autre": "Autre",
}
KEYWORDS = [
    ("acces", r"inond|route|coup[ée]|accès|acces|impraticable|neige|arbre|bloqu|pont"),
    ("equipe", r"fatigu|malad|indispon|véhicule|vehicule|camion|panne|matériel|materiel|repos"),
    ("duree", r"durée|duree|plus long|sous-estim|pylône|pylone|poteau"),
    ("securite", r"sécurit|securit|danger|risque"),
    ("competence", r"compéten|competen|habilit|qualif"),
    ("priorite", r"priorit|urgent|hôpital|hopital|sensible|dialyse|ehpad"),
]


def _until_h(text: str, ctx: dict) -> float | None:
    """'jusqu'à 18h' / '18h30' -> hours since H0; 'pendant 3 h' / 'dans 2h' -> now + duration."""
    t = (text or "").lower()
    m = re.search(r"(?:pendant|durant|dans)\s+(\d+(?:[.,]\d+)?)\s*h", t)
    if m:
        return ctx["now_h"] + float(m.group(1).replace(",", "."))
    m = re.search(r"(\d{1,2})\s*h\s*(\d{2})?", t)
    if m and ctx.get("t0"):
        t0: datetime = ctx["t0"]
        cur = t0 + timedelta(hours=ctx["now_h"])
        target = cur.replace(hour=int(m.group(1)) % 24, minute=int(m.group(2) or 0), second=0, microsecond=0)
        if target <= cur:
            target += timedelta(days=1)
        return (target - t0).total_seconds() / 3600
    return None


def _duration(text: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*h(?!\s*\d)", (text or "").lower())
    if m and not re.search(r"jusqu|à\s*\d", (text or "").lower()):
        return float(m.group(1).replace(",", "."))
    return None


def _classify(text: str | None) -> str:
    t = (text or "").lower()
    for code, pat in KEYWORDS:
        if re.search(pat, t):
            return code
    return "autre"


def fallback(reason_code: str | None, text: str | None, ctx: dict) -> dict:
    code = reason_code or _classify(text)
    team, inc, commune = ctx["team"], ctx["incident"], ctx["commune"]
    pair = {"type": "forbid", "team_or_site": team, "incident_or_zone": inc, "reason": text or REASONS.get(code, ""),
            "scope": "incident"}
    if code == "acces":
        until = _until_h(text, ctx) or ctx["now_h"] + 6.0
        return {"modifiers": [{"type": "zone_inaccessible", "zone": commune, "until_h": until, "reason": text or "",
                               "scope": "crisis"}],
                "restatement": f"Compris : {commune} inaccessible jusqu'à H0 + {until:.1f} h. Aucune équipe n'y sera "
                               f"envoyée avant."}
    if code == "equipe":
        until = _until_h(text, ctx)
        if until is None and not re.search(r"toute la crise|définitiv|definitiv", (text or "").lower()):
            return {"question": f"Jusqu'à quelle heure l'équipe {team} est-elle indisponible ? "
                                f"(ex. « jusqu'à 18h », « pendant 3 h », « toute la crise »)"}
        return {"modifiers": [{"type": "team_unavailable", "team": team, "from_h": ctx["now_h"], "until_h": until,
                               "reason": text or "", "scope": "crisis"}],
                "restatement": f"Compris : l'équipe {team} est indisponible"
                               + (f" jusqu'à H0 + {until:.1f} h." if until else " pour le reste de la crise.")}
    if code == "duree":
        h = _duration(text)
        if h is None:
            return {"question": "Quelle durée de dépannage estimez-vous pour cet incident ? (ex. « plutôt 8 h »)"}
        return {"modifiers": [{"type": "duration_update", "incident": inc, "hours": h, "reason": text or "",
                               "scope": "incident"}],
                "restatement": f"Compris : le dépannage de {inc} prendra plutôt {h:g} h. Le plan est recalculé."}
    label = REASONS.get(code, "Autre")
    return {"modifiers": [pair],
            "restatement": f"Compris ({label}) : ne pas envoyer {team} sur {inc}. Le plan est recalculé autour."}


SYSTEM = (
    "Tu traduis le motif de refus d'un responsable de crise Enedis en règles pour un moteur d'optimisation. "
    "Réponds UNIQUEMENT par un objet JSON, soit {\"modifiers\": [...], \"restatement\": \"phrase courte en français\"}, "
    "soit {\"question\": \"une seule question\"} si une information indispensable manque. Chaque règle a un champ "
    "\"type\" parmi : zone_inaccessible {zone, until_h}, team_unavailable {team, from_h, until_h ou null}, "
    "duration_update {incident, hours}, forbid {team_or_site, incident_or_zone}, priority {incident, factor}, "
    "travel_factor {zone, factor}. Une zone est le NOM D'UNE COMMUNE ou d'un département (par défaut la commune de "
    "l'incident, contexte.commune), jamais un identifiant de site. Les heures sont en heures depuis H0 : le contexte "
    "donne now_h (heure actuelle depuis H0) et t0 (date et heure de H0). Exemple : "
    "{\"modifiers\": [{\"type\": \"zone_inaccessible\", \"zone\": \"Muret\", \"until_h\": 9.0}], "
    "\"restatement\": \"Compris : Muret inaccessible jusqu'à 20h.\"}. N'invente aucun identifiant."
)


def _normalise(mods: list) -> list[dict]:
    """Accept {"zone_inaccessible": {...}} as well as {"type": "zone_inaccessible", ...}."""
    out = []
    for m in mods if isinstance(mods, list) else []:
        if isinstance(m, dict) and "type" not in m and len(m) == 1:
            (k, v), = m.items()
            m = {"type": k, **(v if isinstance(v, dict) else {})}
        if isinstance(m, dict):
            out.append(m)
    return out


def reason_to_modifiers(reason_code: str | None, reason_text: str | None, ctx: dict, cfg) -> dict:
    """LLM first when a key is set and the reason is free text; deterministic parser otherwise.
    The output carries "source": "llm" or "rules" so the caller can fall back if validation fails."""
    if llm_available() and reason_text:
        try:
            ctx_json = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in ctx.items()}
            msg = json.dumps({"motif_code": reason_code, "motif": reason_text, "contexte": ctx_json}, ensure_ascii=False)
            raw = chat(SYSTEM, msg, cfg, max_tokens=600, json_mode=True)
            out = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            if out.get("question"):
                return {"question": out["question"], "source": "llm"}
            mods = _normalise(out.get("modifiers"))
            if mods and out.get("restatement"):
                return {"modifiers": mods, "restatement": out["restatement"], "source": "llm"}
        except Exception:
            pass
    return {**fallback(reason_code, reason_text, ctx), "source": "rules"}
