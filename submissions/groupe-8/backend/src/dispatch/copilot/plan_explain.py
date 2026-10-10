"""Justification of the WHOLE plan of a step, for the crisis manager: a one-sentence summary + up to 4 short points.

The engine's score (customers x hours without power) is translated into insight before anything is written:
  - what the plan does now (teams sent, customers restored, by when, sensitive customers first);
  - why this order (customers restored per hour of team work) and what a different choice would cost, also as
    "these N customers stay X longer without power";
  - the effect over the whole crisis: average time without power per customer vs the reference strategy;
  - the 48 h target check and what is still waiting.
The template is built from the facts and is always available. The LLM rewrites it in plainer French; its text is kept
only if every number, time and duration in it appears in the facts (same rule as the recommendation cards).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from dispatch.copilot.client import chat, llm_available

DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

SYSTEM = (
    "Tu es le copilote d'un responsable de crise Enedis pendant une tempête. Le moteur d'optimisation a calculé un "
    "PLAN : quelles équipes partent maintenant, vers quelles pannes. Son objectif est de réduire le total « clients × "
    "heures sans électricité » : il commence par les pannes qui rétablissent le plus de clients par heure de travail "
    "(trajet + réparation), en respectant les horaires des équipes (12 h de travail, 12 h de repos). L'objectif de "
    "service est de réparer 90 % des incidents en moins de 48 h ; c'est un contrôle, pas l'objectif optimisé.\n"
    "On te donne les FAITS du plan et un BROUILLON. Réécris le brouillon pour qu'un responsable non technicien "
    "comprenne en 15 secondes pourquoi valider ce plan. Réponds UNIQUEMENT par un objet JSON "
    "{\"resume\": \"une phrase\", \"points\": [\"phrase\", ...]} avec au plus 4 points d'une phrase chacun, en "
    "français simple. Mots interdits : score, algorithme, indice, optimisation, heuristique. Dis « clients privés "
    "d'électricité » plutôt que « clients·h » quand c'est possible. Recopie chiffres, heures et durées EXACTEMENT "
    "comme dans les faits ou le brouillon ; n'en calcule et n'en invente aucun."
)


def _clock(iso: str | datetime) -> str:
    d = datetime.fromisoformat(iso) if isinstance(iso, str) else iso
    return f"{d.hour:02d}h{d.minute:02d}"


def _dur(h: float) -> str:
    m = round(h * 60)
    return f"{m // 60} h {m % 60:02d}" if m >= 60 else f"{m} min"


def _int(n: float) -> str:
    return f"{round(n):,}".replace(",", " ")            # no-break space: "1 912" never wraps (every font has it)


def plan_facts(ours: list[dict], reference: list[dict] | None, k: int, start_iso: str) -> dict:
    """Facts of the plan proposed at step k, in business units (from the front-end snapshots).
    `reference` = the reference strategy's timeline (replay only): adds the whole-crisis comparison."""
    snap = ours[k]
    teams = {t["id"]: t for t in snap["teams"]}
    incs = {i["id"]: i for i in snap["incidents"]}
    label = lambda tid: teams.get(tid, {}).get("label", tid)                       # noqa: E731
    lines = []
    for n, r in enumerate(snap["recommendations"], 1):
        f = r["factors"]
        inc = incs.get(r["incidentId"], {})
        eta = datetime.fromisoformat(r["eta"])
        line = {"n": n, "equipe": label(r["teamId"]), "commune": inc.get("commune", r["incidentId"]),
                "clients": f["clients"], "client_sensible": bool(f["sensitive"]), "trajet": f"{f['travelMinutes']} min",
                "reparation": _dur(f["repairHours"]), "arrivee": _clock(eta),
                "retabli_vers": _clock(eta + timedelta(hours=f["repairHours"]))}
        alt = next((a for a in r.get("alternatives", []) if a.get("feasible") and a.get("deltaScore", 0) > 0), None)
        if alt:
            line["autre_equipe"] = label(alt["teamId"])
            line["surcout_clients_h"] = _int(alt["deltaScore"])
            if f["clients"]:
                line["retard_equivalent"] = _dur(alt["deltaScore"] / f["clients"])
        lines.append(line)

    k_ = snap["kpis"]
    planned = {r["incidentId"] for r in snap["recommendations"]}
    waiting = [i for i in snap["incidents"] if i["status"] == "waiting" and i["id"] not in planned]
    restored = [datetime.fromisoformat(r["eta"]) + timedelta(hours=r["factors"]["repairHours"])
                for r in snap["recommendations"]]
    facts = {
        "heure": _clock(snap["time"]), "equipes_envoyees": len(lines),
        "clients_retablis_par_le_plan": _int(sum(x["clients"] for x in lines)),
        "dernier_retablissement": _clock(max(restored)) if restored else None,
        "pannes_avec_client_sensible": sum(x["client_sensible"] for x in lines),
        "pannes_encore_en_attente": len(waiting), "clients_encore_en_attente": _int(sum(i["clients"] for i in waiting)),
        "equipes_disponibles": k_["teamsAvailable"], "lignes": lines,
    }

    # the whole crisis: average time without power per affected customer, ours vs reference strategy
    final_o, final_r = ours[-1], (reference or [{"kpis": {"score": 0}}])[-1]
    customers = sum(i["clients"] for i in final_o["incidents"]) or 1
    so, sr = final_o["kpis"]["score"], final_r["kpis"]["score"]
    if reference and sr > 0:
        facts["crise_entiere"] = {
            "coupure_moyenne_par_client": _dur(so / customers), "coupure_moyenne_reference": _dur(sr / customers),
            "clients_h_evites": _int(sr - so), "gain_pourcent": f"{round(100 * (sr - so) / sr)} %",
            "equivalent_clients_24h": _int((sr - so) / 24)}

    h90 = k_.get("restore90Hours")
    if h90 is not None:
        when = datetime.fromisoformat(start_iso) + timedelta(hours=h90)
        facts["objectif_48h"] = {"tenu": h90 <= 48, "reparation_90_pourcent": f"{DAYS[when.weekday()]} vers {when.hour} h",
                                 "marge": f"{round(abs(48 - h90))} h"}
    return facts


def plan_template(f: dict) -> dict:
    lines = f["lignes"]
    if not lines:
        return {"resume": "Aucune équipe à envoyer à ce moment : pas de panne en attente ou pas d'équipe libre.", "points": []}
    n = f["equipes_envoyees"]
    resume = (f"Ce plan envoie {n} équipe{'s' if n > 1 else ''} maintenant et rétablit "
              f"{f['clients_retablis_par_le_plan']} clients d'ici {f['dernier_retablissement']}.")
    pts = []
    top = max(lines, key=lambda x: x["clients"])
    sens = [x for x in lines if x["client_sensible"]]
    first = (f"Priorité aux pannes qui rallument le plus de clients par heure de travail : {top['equipe']} part à "
             f"{top['commune']} ({top['clients']} clients, arrivée {top['arrivee']})")
    if sens:
        first += f", et les clients sensibles de {sens[0]['commune']} sont servis dans ce plan"
    pts.append(first + ".")
    costly = [x for x in lines if "surcout_clients_h" in x]
    if costly:
        c = max(costly, key=lambda x: int(re.sub(r"\D", "", x["surcout_clients_h"])))     # "1 506" (narrow space) -> 1506
        pts.append(f"Changer d'équipe coûterait cher : envoyer {c['autre_equipe']} au lieu de {c['equipe']} à "
                   f"{c['commune']} laisserait ces {c['clients']} clients {c['retard_equivalent']} de plus sans "
                   f"électricité.")
    ce = f.get("crise_entiere")
    if ce:
        pts.append(f"Sur toute la crise, un client coupé attend en moyenne {ce['coupure_moyenne_par_client']} avec ce "
                   f"pilotage, contre {ce['coupure_moyenne_reference']} avec la stratégie de référence "
                   f"({ce['gain_pourcent']} de coupure en moins).")
    o = f.get("objectif_48h")
    tail = (f"{f['pannes_encore_en_attente']} pannes restent en attente faute d'équipe libre, elles seront prises dès "
            f"qu'une équipe se libère" if f["pannes_encore_en_attente"] else "Aucune autre panne n'attend")
    if o:
        pts.append(f"90 % des incidents seront réparés {o['reparation_90_pourcent']}, "
                   f"{o['marge']} {'avant' if o['tenu'] else 'après'} l'objectif de 48 h ; {tail}.")
    else:
        pts.append(tail + ".")
    return {"resume": resume, "points": pts[:4]}


def _tokens(s: str) -> set[str]:
    s = s.replace(" ", " ").replace(" ", " ")
    s = re.sub(r"(\d) (\d{3})", r"\1\2", s)
    return set(re.findall(r"\d+(?:[.,]\d+)?", s))


def grounded(text: str, facts: dict, template: dict) -> bool:
    allowed = _tokens(json.dumps(facts, ensure_ascii=False) + " " + json.dumps(template, ensure_ascii=False))
    return _tokens(text) <= allowed | {"48", "90", "12", "15"}


def explain_plan(facts: dict, cfg, use_llm: bool = True) -> dict:
    tpl = plan_template(facts)
    if not use_llm or not facts["lignes"] or not llm_available():
        return {**tpl, "source": "template"}
    try:
        raw = chat(SYSTEM, json.dumps({"faits": facts, "brouillon": tpl}, ensure_ascii=False), cfg, max_tokens=700,
                   json_mode=True)
        out = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        resume, points = str(out.get("resume", "")).strip(), [str(p).strip() for p in out.get("points", []) if str(p).strip()]
    except Exception:
        return {**tpl, "source": "template"}
    text = resume + " " + " ".join(points)
    if resume and 1 <= len(points) <= 4 and grounded(text, facts, tpl):
        return {"resume": resume, "points": points, "source": "llm"}
    return {**tpl, "source": "template"}
