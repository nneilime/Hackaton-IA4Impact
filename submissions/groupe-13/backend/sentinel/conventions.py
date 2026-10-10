"""Centre de validation des conventions métier (version 2.0).

Pour chacune des huit ambiguïtés du cahier des charges (AMB-01 à AMB-08) : texte d'origine de la règle,
ambiguïté constatée, convention appliquée et sa version, dossiers concernés, et — lorsque c'est calculable —
EFFET d'un changement de convention, obtenu en rejouant la règle concernée sur le corpus avec la convention
alternative (rien n'est modifié dans les résultats officiels).

Les conventions sont des propositions de l'équipe, à valider par la MSA : elles ne sont jamais présentées
comme une validation officielle.
"""
from __future__ import annotations

from collections import Counter

from . import RULESET_VERSION
from .normalize import strip_leading_zeros
from .rules import (ANOMALIE, CONFORME, NON_APPLICABLE, RULES, Ctx, _img_presta, _match_codes, _presence_rule,
                    _txt3_items, _txt4_groups, _z10_acts, result)

RULE = {r.id: r for r in RULES}

CONVENTIONS = [
    {"id": "AMB-01", "regles": ["R01"], "version": "v1", "sujet": "Identifiant du formulaire",
     "constat": "Le cahier des charges indique « 12278*0 » ; les bordereaux impriment « 12278*01 ».",
     "convention": "Préfixe « 12278*0 » exigé ; le chiffre final (numéro de version du formulaire) est accepté.",
     "alternative": "Égalité stricte avec « 12278*0 »."},
    {"id": "AMB-02", "regles": ["R03", "R04"], "version": "v1", "sujet": "Zéros de cadrage des numéros",
     "constat": "Le fichier cadre les numéros avec des zéros à gauche (000491901) ; le bordereau non (491901).",
     "convention": "Comparaison numérique : zéros de cadrage ignorés.",
     "alternative": "Comparaison caractère par caractère (zéros compris)."},
    {"id": "AMB-03", "regles": ["R19"], "version": "v1", "sujet": "Rapprochement des actes CCAM",
     "constat": "Un acte de type 4 suivi d'un 4-M est imprimé sur le bordereau sous son code CCAM.",
     "convention": "Acte retrouvé par son code CCAM s'il existe, sinon par son code Acte.",
     "alternative": "Acte toujours recherché par son code Acte (positions 76-80)."},
    {"id": "AMB-04", "regles": ["R14"], "version": "v1", "sujet": "Lignes de détail de biologie",
     "constat": "Sous un acte B, le bordereau imprime des codes de 4 chiffres sans exécutant ni montant.",
     "convention": "Lignes considérées comme détail de l'acte B, non comme actes distincts.",
     "alternative": None,
     "non_simule": "Les codes de détail sont imprimés à la suite sur une même ligne et ne sont pas lus individuellement : "
                   "l'effet d'une autre convention ne peut pas être calculé de façon fiable."},
    {"id": "AMB-05", "regles": ["R18"], "version": "v1", "sujet": "Mention « par mandat » et cachets en zone 11",
     "constat": "Les cases contiennent parfois une mention « par mandat » ou un cachet plutôt qu'une signature manuscrite.",
     "convention": "Présence d'un élément = signature présente ; authenticité jamais certifiée.",
     "alternative": None,
     "non_simule": "Effet non simulable sans décision métier sur la valeur d'une mention « par mandat » ou d'un cachet."},
    {"id": "AMB-06", "regles": ["R09", "R10"], "version": "v1", "sujet": "Règles de cohérence GH",
     "constat": "Deux formulations proches : référence GHS du fichier (R09) ou GHS lu en zone 6 (R10).",
     "convention": "R09 : contrôle interne au fichier ; R10 : actes LPP (zone 7) comparés au GHS lu en zone 6.",
     "alternative": "R10 appliquée à tous les actes de type 3 autres que GHS (pas seulement ceux de la zone 7)."},
    {"id": "AMB-07", "regles": ["R08", "R11", "R13", "R14", "R15", "R19"], "version": "v1",
     "sujet": "Occurrences répétées d'un même code",
     "constat": "Le cahier des charges parle de « présence » ; un même code peut figurer plusieurs fois.",
     "convention": "Rapprochement occurrence par occurrence (deux actes identiques doivent figurer deux fois).",
     "alternative": "Simple présence du code (une occurrence suffit, quel que soit le nombre de lignes)."},
    {"id": "AMB-08", "regles": [], "version": "v1", "sujet": "Absence d'enregistrement de type 0",
     "constat": "Aucun fichier ne contient d'en-tête de type 0.", "convention": "Absence non considérée comme une erreur.",
     "alternative": "Absence d'en-tête de type 0 signalée comme une anomalie de structure du fichier."},
]


def _set_presence(rd, ctx, img, txt, direction, zl, tl):
    """Variante AMB-07 : simple présence des codes (ensembles), sans compter les occurrences."""
    seen_img = {}
    for i in img:
        seen_img.setdefault(i.get("code"), i)
    seen_txt = {}
    for t in txt:
        seen_txt.setdefault(t["code"], t)
    return _presence_rule(rd, ctx, list(seen_img.values()), list(seen_txt.values()), direction, zl, tl)


def _variant(conv_id: str, rid: str, ctx: Ctx):
    rd = RULE[rid]
    if conv_id == "AMB-01":
        v = (ctx.f("Z1") or {}).get("value")
        return CONFORME if v == "12278*0" else (ANOMALIE if v else None)
    if conv_id == "AMB-02":
        fid, fv = ("Z3", ctx.txt.numero_lot) if rid == "R03" else ("Z4", ctx.txt.numero_facture)
        v = (ctx.f(fid) or {}).get("value")
        if v is None or fv is None:
            return None
        return CONFORME if str(v) == str(fv.value).strip() else ANOMALIE
    if conv_id == "AMB-03":
        txt = [{"code": g["acte"], "line_no": g["line_no"], "start": 76, "end": 80, "amount": g["amount"]}
               for g in _txt4_groups(ctx) if g["acte"]]
        return _presence_rule(rd, ctx, _z10_acts(ctx), txt, "txt->img", "zone 10", "Acte de type 4")["status"]
    if conv_id == "AMB-04":
        rows = ctx.rows("Z10")
        img = []
        for r in rows:
            cell = r["cells"].get("code", {})
            if cell.get("value") and len(cell["value"]) <= 4:
                img.append({"codes": [c["value"] for c in cell.get("candidates", [])], "code": cell["value"],
                            "agreement": cell.get("agreement"), "row": r, "amount": None})
        txt = [{"code": g["acte"], "line_no": g["line_no"], "start": 76, "end": 80} for g in _txt4_groups(ctx) if g["acte"]]
        return _presence_rule(rd, ctx, img, txt, "img->txt", "zone 10", "Acte de type 4")["status"]
    if conv_id == "AMB-06":
        g = ctx.ghs_row()
        ref = ((g or {}).get("cells", {}).get("ghs") or {}).get("value")
        acts = [a for a in ctx.txt.acts3 if a["acte"] and a["acte"] != "GHS"]
        if not acts:
            return NON_APPLICABLE
        if not ref:
            return None
        return CONFORME if all(a["gh"] == ref for a in acts) else ANOMALIE
    if conv_id == "AMB-07":
        if rid in ("R08", "R11", "R13"):
            z6, z7 = _img_presta(ctx.rows("Z6"), require_amount=(rid == "R08")), _img_presta(ctx.rows("Z7"))
            if rid == "R08":
                return _set_presence(rd, ctx, z6, _txt3_items(ctx), "img->txt", "zone 6", "Acte")["status"]
            if rid == "R11":
                return _set_presence(rd, ctx, z7, _txt3_items(ctx), "img->txt", "zone 7", "Acte")["status"]
            return _set_presence(rd, ctx, _img_presta(ctx.rows("Z6")) + z7, _txt3_items(ctx), "txt->img", "zones 6 et 7", "Acte")["status"]
        img = _z10_acts(ctx)
        if rid == "R14":
            txt = [{"code": g["acte"], "line_no": g["line_no"]} for g in _txt4_groups(ctx) if g["acte"]]
            return _set_presence(rd, ctx, [i for i in img if i["code"] and len(i["code"]) <= 4], txt, "img->txt", "zone 10", "Acte")["status"]
        if rid == "R15":
            txt = [{"code": c["code7"], "line_no": c["line_no"]} for c in ctx.txt.ccam4m if c["code7"]]
            return _set_presence(rd, ctx, [i for i in img if i["code"] and len(i["code"]) == 7], txt, "img->txt", "zone 10", "CCAM")["status"]
        txt = [{"code": g["ccam"] or g["acte"], "line_no": g["ccam_line"] or g["line_no"]} for g in _txt4_groups(ctx) if g["ccam"] or g["acte"]]
        return _set_presence(rd, ctx, img, txt, "txt->img", "zone 10", "Acte")["status"]
    if conv_id == "AMB-08":
        return ANOMALIE if not any(r.rtype == "0" for r in ctx.txt.records) else CONFORME
    return None


def concerned(conv_id: str, ctx: Ctx, results: dict) -> bool:
    """Le dossier est-il concerné par l'ambiguïté (la convention a-t-elle eu à s'appliquer) ?"""
    if conv_id == "AMB-01":
        v = (ctx.f("Z1") or {}).get("value")
        return bool(v) and v != "12278*0"
    if conv_id == "AMB-02":
        return any(fv is not None and str(fv.value).strip() != strip_leading_zeros(str(fv.value).strip())
                   for fv in (ctx.txt.numero_lot, ctx.txt.numero_facture))
    if conv_id == "AMB-03":
        return bool(ctx.txt.ccam4m)
    if conv_id == "AMB-04":
        return any(r.get("kind") == "detail" for r in ctx.rows("Z10"))
    if conv_id == "AMB-05":
        return any("MANDAT" in (s.get("text") or "").upper() for s in (ctx.ext.get("signatures") or {}).get("Z11", []))
    if conv_id == "AMB-06":
        return bool([a for a in ctx.txt.acts3 if a["acte"] and a["acte"] != "GHS"])
    if conv_id == "AMB-07":
        codes = [a["acte"] for a in ctx.txt.acts3] + [g["ccam"] or g["acte"] for g in _txt4_groups(ctx)]
        return any(n > 1 for n in Counter(c for c in codes if c).values())
    if conv_id == "AMB-08":
        return not any(r.rtype == "0" for r in ctx.txt.records)
    return False


def analyze(cases: list) -> list:
    """cases : liste de (case_id, ParsedB2, extraction, résultats officiels)."""
    out = []
    for conv in CONVENTIONS:
        concerned_ids, changes = [], []
        for cid, txt, ext, results in cases:
            ctx = Ctx(txt, ext)
            by = {r["rule_id"]: r for r in results}
            if concerned(conv["id"], ctx, by):
                concerned_ids.append(cid)
            if not conv["alternative"]:
                continue
            for rid in conv["regles"] or ["—"]:
                cur = by.get(rid, {}).get("status") if rid in by else ("CONFORME" if conv["id"] == "AMB-08" else None)
                try:
                    alt = _variant(conv["id"], rid if rid != "—" else "R01", ctx)
                except Exception:  # noqa
                    alt = None
                if alt and cur and alt != cur:
                    changes.append({"case_id": cid, "rule_id": rid if rid != "—" else "(structure)", "actuel": cur, "alternatif": alt})
        out.append({**conv, "texte_regles": {rid: RULE[rid].spec for rid in conv["regles"]},
                    "version_complete": f"{conv['id']} {conv['version']} ({RULESET_VERSION})",
                    "dossiers_concernes": concerned_ids,
                    "effet_changement": None if not conv["alternative"] else {
                        "resultats_modifies": len(changes), "dossiers_modifies": len({c["case_id"] for c in changes}),
                        "detail": changes[:200],
                        "par_transition": dict(Counter(f"{c['actuel']} → {c['alternatif']}" for c in changes))},
                    "effet_non_simule": None if conv["alternative"] else conv.get("non_simule"),
                    "statut": "Convention proposée par l'équipe — à valider par la MSA (non officielle)."})
    return out
