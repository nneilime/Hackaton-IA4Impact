"""Copilot chat answers for the front-end. Every figure comes from the engine (snapshot, what-if, reinforcement).
Known intents get a deterministic answer; other questions go to the LLM with a compact factual context, and the
answer is accepted only if every number it contains is in that context."""
from __future__ import annotations

import json
import re

from dispatch.copilot.client import chat, llm_available

SYSTEM = (
    "Tu es le copilote d'un responsable de crise Enedis pendant une tempête. Fonctionnement du système : un moteur "
    "d'optimisation décide quelles équipes envoyer sur quelles pannes ; son objectif est de réduire le total « clients × "
    "heures sans électricité » en commençant par les pannes qui rallument le plus de clients par heure de travail, en "
    "respectant les horaires des équipes (12 h de travail, 12 h de repos). L'objectif de service (90 % des incidents "
    "réparés en 48 h) est vérifié à part ; s'il n'est pas tenu, le système chiffre les renforts nécessaires. Le "
    "responsable valide ou refuse chaque plan ; un refus motivé devient une règle et est enregistré pour le retour "
    "d'expérience. Réponds en français simple, en 4 phrases maximum, uniquement à partir des faits JSON fournis "
    "(situation à l'instant affiché, plan proposé inclus). N'invente aucun chiffre : recopie ceux des faits. Si la "
    "réponse n'est pas dans les faits, dis-le et propose une des questions : « Pourquoi ce plan ? », « Et si je perds "
    "50 % des équipes ? », « Quels clients sensibles attendent ? », « Où est la saturation ? », « Faut-il des renforts ? »."
)


def fmt(n: float) -> str:
    return f"{round(n):,}".replace(",", " ")


def _numbers(s: str) -> set[str]:
    return {x.replace(",", ".").replace(" ", "") for x in re.findall(r"\d[\d\s]*(?:[.,]\d+)?", s)}


def context(snap: dict) -> dict:
    k = snap["kpis"]
    waiting = [i for i in snap["incidents"] if i["status"] == "waiting"]
    by_commune: dict[str, int] = {}
    for i in waiting:
        by_commune[i["commune"]] = by_commune.get(i["commune"], 0) + i["clients"]
    top = sorted(by_commune.items(), key=lambda x: -x[1])[:5]
    return {"heure": snap["time"][11:16], "clients_coupes": k["clientsCut"], "clients_realimentes": k["clientsRestored"],
            "incidents_en_attente": k["incidentsWaiting"], "equipes_disponibles": k["teamsAvailable"],
            "equipes_occupees": k["teamsBusy"], "equipes_au_repos": k["teamsResting"],
            "estimation_90_pourcent_h": k["restore90Hours"], "objectif_h": 48,
            "communes_les_plus_touchees": [{"commune": c, "clients_en_attente": n} for c, n in top],
            "recommandations": [r.get("headline") for r in snap["recommendations"][:5]]}


def sensitive(snap: dict) -> str:
    lst = [i for i in snap["incidents"] if i["sensitive"] and i["status"] != "restored"]
    if not lst:
        return "Aucun poste avec client sensible n'est coupé en ce moment."
    status = {"waiting": "en attente", "enroute": "équipe en route", "repairing": "dépannage en cours"}
    lines = [f"• {i['commune']} ({i['posteId']}) · {fmt(i['clients'])} clients · {status.get(i['status'], i['status'])}"
             for i in lst[:6]]
    return f"{len(lst)} poste(s) avec client sensible encore coupé(s) :\n\n" + "\n".join(lines) + ("\n…" if len(lst) > 6 else "")


def saturation(snap: dict) -> str:
    c = context(snap)
    top = "\n".join(f"• {x['commune']} : {fmt(x['clients_en_attente'])} clients" for x in c["communes_les_plus_touchees"])
    return (f"{c['incidents_en_attente']} incidents attendent une équipe ; {c['equipes_disponibles']} équipe(s) disponible(s), "
            f"{c['equipes_au_repos']} au repos.\n\n" + (f"Plus gros volumes de clients en attente :\n{top}" if top else ""))


def reinforcement_text(r: dict) -> str:
    unit = "des clients coupés rétablis" if r.get("basis") == "customers" else "des incidents signalés réparés"
    if r.get("target_met"):
        return (f"Pas besoin de renfort : selon le plan actuel, {round(100 * r['projected_share'])} % {unit} avant "
                f"48 h (objectif 90 %).")
    rf = r.get("reinforcement") or {}
    sites = ", ".join(f"{n} à {c}" for c, n in rf.get("by_site", {}).items())
    return (f"Objectif 90 % à 48 h hors d'atteinte : {round(100 * r['projected_share'])} % {unit} à 48 h. Demander "
            f"{rf.get('extra_teams', '?')} équipe(s) en renfort ({sites}) permettrait d'atteindre "
            f"{round(100 * (rf.get('projected_share_after') or 0))} %.")


def free_answer(question: str, snap: dict, cfg) -> str | None:
    if not llm_available():
        return None
    ctx = context(snap)
    try:
        text = chat(SYSTEM, json.dumps({"question": question, "faits": ctx}, ensure_ascii=False), cfg, max_tokens=400)
    except Exception:
        return None
    allowed = _numbers(json.dumps(ctx, ensure_ascii=False)) | {"48", "50", "90"}
    allowed |= {str(int(float(n))) for n in allowed if n.replace(".", "", 1).isdigit()}
    return text if text and _numbers(text) <= allowed else None


HELP = ("Je réponds à partir des données du moteur. Essayez : « Pourquoi ce plan ? », « Pourquoi cette équipe ? », "
        "« Quels clients sensibles attendent ? », « Où est la saturation ? », « Faut-il des renforts ? ».")


def answer(question: str, snap: dict, cfg, *, plan_explanation, rec_explanation, reinforcement, what_if=None,
           final_score: float | None = None, rec_id: str | None = None) -> dict:
    """Route a manager's question to the engine's data. Known intents get a deterministic answer; anything else goes
    to the LLM with a factual context (numbers checked). The callables give the mode-specific engine answers:
    plan_explanation() -> {resume, points, source}, rec_explanation(rec) -> {headline, paragraphs, limits, source},
    reinforcement() -> service check, what_if(share) -> {score, baseline} (None when not available)."""
    q = question.lower()
    words = set(re.findall(r"\w+", q))
    if "plan" in words and words & {"pourquoi", "justifie", "justifier", "explique", "expliquer"}:
        e = plan_explanation()
        return {"answer": "\n\n".join([e["resume"]] + [f"• {p}" for p in e["points"]]), "source": e["source"]}
    if "pourquoi" in words:
        recs = snap["recommendations"]
        rec = next((r for r in recs if r["id"] == rec_id), recs[0] if recs else None)
        if not rec:
            return {"answer": "Aucune recommandation n'est en attente en ce moment.", "source": "engine"}
        e = rec_explanation(rec)
        return {"answer": "\n\n".join([e["headline"] + "."] + e["paragraphs"] + [e["limits"]]), "source": e["source"]}
    if re.search(r"\b(50 ?%|moitié|perd\w*)", q):
        if what_if is None or final_score is None:
            return {"answer": "La simulation « et si » sur toute la crise n'est disponible qu'en revue d'une crise passée. "
                              "En direct, demandez plutôt « Faut-il des renforts ? ».", "source": "engine"}
        r = what_if(0.5)
        delta = 100 * (r["score"] - final_score) / final_score if final_score else 0.0
        return {"answer": (f"Simulation avec la moitié des équipes de chaque site :\n\n"
                           f"• Coupure cumulée en fin de crise : {fmt(r['score'])} clients·h, soit {delta:+.0f} % par "
                           f"rapport au plan actuel ({fmt(final_score)}).\n• La stratégie de référence monterait à "
                           f"{fmt(r['baseline'])} clients·h dans les mêmes conditions.\n\nLevier : demander des renforts "
                           f"sur les sites les plus chargés (« Faut-il des renforts ? »)."), "source": "engine"}
    if "sensible" in q or "sensibles" in words:
        return {"answer": sensitive(snap), "source": "engine"}
    if words & {"renfort", "renforts", "fire", "objectif"} or re.search(r"\b48 ?h\b", q):
        return {"answer": reinforcement_text(reinforcement()), "source": "engine"}
    if "saturation" in q or "où" in words:
        return {"answer": saturation(snap), "source": "engine"}
    text = free_answer(question, snap, cfg)
    return {"answer": text or HELP, "source": "llm" if text else "engine"}
