"""Référentiel de validation humaine (version 3.0).

But : mesurer l'exactitude du moteur sur le corpus autorisé à partir d'une VÉRITÉ TERRAIN construite par des
validateurs humains, et non à partir de la sortie de l'OCR ou du TXT.

Une validation porte sur un couple (dossier, règle) :
  - la valeur imprimée vérifiée à l'œil sur le bordereau, la valeur B2 vérifiée ;
  - le verdict : écart réel, faux positif (avec sa cause), conforme confirmé, écart manqué, indéterminé ;
  - l'identité du validateur, la date, le statut du moteur au moment de la validation.
Plusieurs validateurs peuvent se prononcer (double revue) : un désaccord est signalé, jamais tranché
automatiquement.

Une « revue assistée » (pré-examen réalisé avec l'assistant IA, sans validateur humain) est conservée à part :
elle n'entre JAMAIS dans les métriques officielles, qui n'utilisent que les validations humaines.

L'annotation est une métadonnée de validation créée à partir du corpus autorisé ; elle ne constitue pas une
nouvelle facture et ne modifie aucun résultat.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

VERDICTS = {
    "ecart_reel": "Écart réel entre les deux documents",
    "faux_positif": "Faux positif : les documents concordent",
    "conforme_confirme": "Conforme confirmé",
    "ecart_manque": "Écart manqué par le moteur",
    "indetermine": "Indéterminé (document illisible ou règle ambiguë)",
}
CAUSES = {
    "FP-GEO": "Mauvaise localisation du champ",
    "FP-OCR": "Caractère mal reconnu",
    "FP-TABLE": "Mauvaise association dans un tableau",
    "FP-B2": "Lecture du fichier B2 incorrecte",
    "FP-PAIR": "Appariement incorrect entre prestations",
    "FP-NORM": "Normalisation inadéquate",
    "FP-RULE": "Logique métier incorrecte",
    "FP-CONVENTION": "Interprétation métier non validée",
    "FP-CACHE": "Donnée obsolète",
    "FP-UI": "Résultat juste mais mal affiché",
}
SEED = Path(__file__).parent / "data" / "revue_assistee_v3.json"


def seed_assisted_review(db) -> int:
    """Charge le pré-examen assisté (une seule fois). Il reste marqué « revue assistée, à confirmer »."""
    if not SEED.exists() or db.one("SELECT id FROM validations WHERE validator_kind='revue_assistee' LIMIT 1"):
        return 0
    items = json.loads(SEED.read_text(encoding="utf-8"))["validations"]
    with db.tx() as c:
        for it in items:
            c.execute("INSERT INTO validations (case_id, rule_id, verdict, cause, comment, validator_kind, validator_name, "
                      "engine_status, engine_version, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (it["dossier"], it["regle"], it["verdict"], it.get("cause"), it.get("commentaire"),
                       "revue_assistee", "Revue assistée par IA (à confirmer par un validateur humain)",
                       it.get("statut_moteur"), it.get("version"), it.get("date")))
    return len(items)


def consensus(rows: list) -> dict:
    """Verdict par (dossier, règle) à partir de la DERNIÈRE validation de chaque validateur humain."""
    last = {}
    for r in sorted(rows, key=lambda r: r["id"]):
        if r["validator_kind"] != "humain":
            continue
        last[(r["case_id"], r["rule_id"], r["validator_id"])] = r
    by = defaultdict(list)
    for (cid, rid, _), r in last.items():
        by[(cid, rid)].append(r)
    out = {}
    for k, rs in by.items():
        verdicts = {r["verdict"] for r in rs}
        out[k] = {"verdict": verdicts.pop() if len(verdicts) == 1 else "desaccord", "validateurs": len(rs),
                  "details": [{"validateur": r.get("validator_name"), "verdict": r["verdict"], "cause": r.get("cause"),
                               "date": r["created_at"]} for r in rs]}
    return out


def metrics(engine: dict, rows: list) -> dict:
    """engine : {(dossier, règle): statut actuel du moteur}. Matrice de confusion sur les cas validés."""
    cons = consensus(rows)
    m = Counter()
    per_rule = defaultdict(Counter)
    causes = Counter()
    stale = 0
    for k, c in cons.items():
        st = engine.get(k)
        if st is None:
            continue
        v = c["verdict"]
        if v == "desaccord":
            m["desaccords"] += 1; continue
        if v == "indetermine":
            m["indetermines"] += 1; continue
        cell = None
        if st == "ANOMALIE":
            cell = "VP" if v == "ecart_reel" else ("FP" if v == "faux_positif" else None)
        elif st in ("CONFORME", "NON_APPLICABLE"):
            cell = "VN" if v in ("conforme_confirme", "faux_positif") else ("FN" if v in ("ecart_manque", "ecart_reel") else None)
        elif st == "NON_VERIFIABLE":
            cell = "NV_ecart" if v in ("ecart_reel", "ecart_manque") else "NV_conforme"
        if cell is None:
            stale += 1; continue
        m[cell] += 1
        per_rule[k[1]][cell] += 1
    for r in rows:
        if r["validator_kind"] == "humain" and r["verdict"] == "faux_positif" and r.get("cause"):
            causes[r["cause"]] += 1
    vp, fp, vn, fn = m["VP"], m["FP"], m["VN"], m["FN"]
    return {
        "taille_referentiel": len(cons), "validations_humaines": sum(1 for r in rows if r["validator_kind"] == "humain"),
        "validateurs": len({r["validator_id"] for r in rows if r["validator_kind"] == "humain"}),
        "double_revue": sum(1 for c in cons.values() if c["validateurs"] >= 2),
        "matrice": {"VP": vp, "FP": fp, "VN": vn, "FN": fn, "NV_sur_ecart_reel": m["NV_ecart"],
                    "NV_sur_conforme": m["NV_conforme"]},
        "desaccords": m["desaccords"], "indetermines": m["indetermines"], "validation_sur_statut_different": stale,
        "precision": round(vp / (vp + fp), 3) if vp + fp else None,
        "rappel": round(vp / (vp + fn), 3) if vp + fn else None,
        "par_regle": {k: dict(v) for k, v in sorted(per_rule.items())},
        "causes_faux_positifs": {k: {"libelle": CAUSES.get(k, k), "n": n} for k, n in causes.most_common()},
        "note": "Calculé uniquement sur les validations HUMAINES (la revue assistée par IA est exclue). "
                "Précision = VP / (VP + FP) ; rappel = VP / (VP + FN). Une métrique sans effectif est « indisponible ».",
    }
