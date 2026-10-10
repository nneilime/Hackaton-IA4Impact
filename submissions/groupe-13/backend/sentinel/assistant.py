"""Assistant de contrôle (optionnel) — réponses DÉTERMINISTES et ancrées.

Il n'utilise aucun modèle génératif ni service externe : chaque réponse est construite à partir
des seules données du dossier (résultats des règles, extractions, fichier TXT) et du cahier des
charges. Il ne formule jamais de conclusion de fraude ni de fait médical.
"""
from __future__ import annotations

import re

from .normalize import amount_str
from .rules import RULES

STATUS_FR = {"CONFORME": "conforme", "ANOMALIE": "anomalie", "NON_VERIFIABLE": "non vérifiable",
             "NON_APPLICABLE": "non applicable", "ERREUR_TECHNIQUE": "erreur technique"}


def summarize_case(p: dict) -> dict:
    res = p.get("results", [])
    an = [r for r in res if r["status"] == "ANOMALIE"]
    nv = [r for r in res if r["status"] == "NON_VERIFIABLE"]
    lines = []
    if not an and not nv:
        lines.append("Les 22 contrôles applicables sont conformes ou non applicables : aucun écart documentaire détecté.")
    if an:
        lines.append(f"{len(an)} anomalie(s) documentaire(s) :")
        lines += [f"• {r['rule_id']} — {r['explanation']}" for r in an]
    if nv:
        lines.append(f"{len(nv)} contrôle(s) nécessitant une lecture humaine :")
        lines += [f"• {r['rule_id']} — {r['explanation']}" for r in nv]
    if p.get("pairing", {}).get("status") != "confirmé":
        lines.append(f"Attention : rapprochement bordereau/fichier « {p.get('pairing', {}).get('status')} » — "
                     f"les deux documents pourraient ne pas concerner le même dossier.")
    order = _order(p)
    return {"text": "\n".join(lines), "order": order,
            "sources": [r["rule_id"] for r in an + nv]}


def _order(p):
    """Ordre de traitement proposé : identification d'abord (elle conditionne tout le reste),
    puis montants, actes, codes GHS, signatures, puis lectures humaines."""
    rank = {"R02": 1, "R03": 1, "R04": 1, "R05": 1, "R01": 2, "R22": 2, "R12": 3, "R17": 3, "R20": 3,
            "R08": 4, "R11": 4, "R13": 4, "R14": 4, "R15": 4, "R19": 4, "R06": 5, "R07": 5, "R09": 5, "R10": 5,
            "R16": 5, "R18": 6, "R21": 6}
    items = [r for r in p.get("results", []) if r["status"] in ("ANOMALIE", "NON_VERIFIABLE")]
    items.sort(key=lambda r: (0 if r["status"] == "ANOMALIE" else 1, rank.get(r["rule_id"], 9)))
    why = {1: "identification (conditionne le rapprochement)", 2: "identification du formulaire",
           3: "écart de montant", 4: "prestation/acte présent d'un seul côté", 5: "cohérence des n° GHS",
           6: "signature"}
    return [{"rule_id": r["rule_id"], "status": r["status"], "why": why.get(rank.get(r["rule_id"], 9), "autre"),
             "action": r.get("next_action")} for r in items]


def answer(p: dict, question: str) -> dict:
    q = (question or "").lower()
    res = {r["rule_id"]: r for r in p.get("results", [])}
    m = re.search(r"\br\s?(\d{1,2})\b", q)
    if "fraud" in q:
        return _a("Une anomalie est un écart documentaire constaté entre le bordereau et le fichier. Le système ne "
                  "conclut jamais à une fraude : l'interprétation appartient aux personnes habilitées après instruction.",
                  ["principe fondamental du cahier des charges"])
    if m:
        rid = f"R{int(m.group(1)):02d}"
        r = res.get(rid)
        rd = next((x for x in RULES if x.id == rid), None)
        if not rd:
            return _a(f"La règle {rid} n'existe pas (règles R01 à R22).", [])
        txt = [f"{rid} — {rd.title}.", f"Cahier des charges : « {rd.spec} »."]
        if rd.convention:
            txt.append(f"Convention retenue : {rd.convention}")
        if r:
            txt.append(f"Résultat pour ce dossier : {STATUS_FR[r['status']]}. {r['explanation']}")
            if r.get("uncertainty"):
                txt.append(f"Incertitude {r['uncertainty']['level']} : {r['uncertainty']['reason']}.")
            txt.append(f"Action proposée : {r.get('next_action')}")
        return _a("\n".join(txt), [rid])
    if any(k in q for k in ("résum", "resum", "synth", "bilan")):
        s = summarize_case(p)
        return _a(s["text"], s["sources"])
    if any(k in q for k in ("ordre", "commencer", "priorit", "faire", "étape", "etape", "suite")):
        o = _order(p)
        if not o:
            return _a("Aucun contrôle en écart ni non vérifiable : le dossier peut être marqué « Contrôle terminé ».", [])
        return _a("Ordre de traitement proposé :\n" + "\n".join(
            f"{i}. {x['rule_id']} ({x['why']}) — {x['action']}" for i, x in enumerate(o, 1)), [x["rule_id"] for x in o])
    if any(k in q for k in ("montant", "écart", "ecart", "euro", "€", "total")):
        s = p.get("summary", {})
        lines = [f"Montant facturé dans le fichier : {amount_str(s.get('billed_cents'))}.",
                 f"Écart net mesuré sur les totaux (R12, R17) : {amount_str(s.get('net_total_gap_cents'))}.",
                 f"Montants portés par les lignes en écart (R08/R11/R13/R14/R15/R19) : {amount_str(s.get('act_level_gap_cents'))}."]
        for rid in ("R12", "R17", "R20"):
            r = res.get(rid)
            if r:
                lines.append(f"{rid} : {STATUS_FR[r['status']]} — {r['explanation']}")
        lines.append("Ces écarts sont des différences documentaires : ce ne sont ni des montants récupérés ni des économies.")
        return _a("\n".join(lines), ["R12", "R17", "R20"])
    if "signature" in q or "sign" in q:
        lines = [f"{rid} : {STATUS_FR[res[rid]['status']]} — {res[rid]['explanation']}" for rid in ("R18", "R21") if rid in res]
        lines.append("Le système détecte la présence d'un élément dans la zone, il ne certifie jamais l'authenticité.")
        return _a("\n".join(lines), ["R18", "R21"])
    if any(k in q for k in ("manqu", "absent", "illisible", "vérifier", "verifier", "humain")):
        nv = [r for r in p.get("results", []) if r["status"] == "NON_VERIFIABLE"]
        if not nv:
            return _a("Aucun contrôle n'est en attente de lecture humaine.", [])
        return _a("Éléments à vérifier visuellement :\n" + "\n".join(f"• {r['rule_id']} : {r['explanation']}" for r in nv),
                  [r["rule_id"] for r in nv])
    if any(k in q for k in ("ghs", "gh ")):
        lines = [f"{rid} : {STATUS_FR[res[rid]['status']]} — {res[rid]['explanation']}" for rid in ("R06", "R07", "R09", "R10", "R16") if rid in res]
        return _a("\n".join(lines), ["R06", "R07", "R09", "R10", "R16"])
    return _a("Je réponds uniquement à partir de ce dossier et du cahier des charges. Exemples de questions : "
              "« résumé », « que dois-je faire ? », « pourquoi R12 ? », « écarts de montant », « signatures », "
              "« éléments à vérifier », « numéros GHS ».", [])


def _a(text, sources):
    return {"answer": text, "sources": sources,
            "grounding": "Réponse générée de façon déterministe à partir des résultats du dossier et du cahier des charges."}
