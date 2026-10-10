"""Moteur des 22 contrôles officiels (« Les contrôles à implémenter »).

Chaque règle est une fonction indépendante, déterministe et testable, qui reçoit le contexte
(fichier TXT analysé + extraction du bordereau) et renvoie un résultat traçable.

Statuts : CONFORME | ANOMALIE | NON_VERIFIABLE | NON_APPLICABLE | ERREUR_TECHNIQUE.
Une anomalie est un écart documentaire constaté, jamais une preuve de fraude.
"""
from __future__ import annotations

import datetime as dt
import traceback
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import ENGINE_VERSION, RULESET_VERSION
from .b2parser import ParsedB2, shifted_reading
from .normalize import amount_str, strip_leading_zeros

CONFORME, ANOMALIE, NON_VERIFIABLE, NON_APPLICABLE, ERREUR = (
    "CONFORME", "ANOMALIE", "NON_VERIFIABLE", "NON_APPLICABLE", "ERREUR_TECHNIQUE")

READ_OK = ("concordant", "majoritaire", "corrigé")


# =====================================================================================
@dataclass
class RuleDef:
    id: str
    category: str
    title: str
    spec: str              # formulation du cahier des charges
    zones: list
    txt_fields: list
    func: Callable = None
    convention: str = ""   # convention d'interprétation retenue (documentée)


RULES: list[RuleDef] = []


def rule(id, category, title, spec, zones, txt_fields, convention=""):
    def deco(fn):
        RULES.append(RuleDef(id, category, title, spec, zones, txt_fields, fn, convention))
        return fn
    return deco


CATEGORIES = {
    "A": "Identification du document",
    "B": "Frais de structure et de soins",
    "C": "Produits LPP, pharmacie et médicaments",
    "D": "Récapitulatif des prestations",
    "E": "Honoraires médicaux, paramédicaux et laboratoire",
    "F": "Conclusion du document",
}


# =====================================================================================
@dataclass
class Ctx:
    txt: ParsedB2
    ext: dict
    conventions: dict = field(default_factory=dict)   # décisions métier enregistrées : {"AMB-01": "validée"|"rejetée"}
    now: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))

    # ---- accès extraction
    def f(self, fid):
        return (self.ext.get("fields") or {}).get(fid)

    def rows(self, zone, kind=None):
        rs = (self.ext.get("tables") or {}).get(zone, [])
        return [r for r in rs if kind is None or r.get("kind") == kind]

    def ghs_row(self):
        """Ligne GHS de la zone 6 : d'abord par la valeur retenue ; à défaut par une autre lecture candidate
        (la ligne est alors marquée « ghs_incertain » et les règles qui en dépendent ne concluent pas)."""
        rows = self.rows("Z6", "prestation")
        for r in rows:
            if _cell_value(r["cells"].get("prestation")) == "GHS" and not contradictory_tie(r["cells"].get("prestation")):
                return r
        for r in rows:
            if _cell_matches(r["cells"].get("prestation"), "GHS"):
                return dict(r, ghs_incertain=True)
        return None


def _cell_matches(cell, value) -> bool:
    if not cell:
        return False
    return any(c["value"] == value for c in cell.get("candidates", []))


def _cell_value(cell):
    return cell.get("value") if cell else None


def _img_ref(label, item, zone=None):
    if not item:
        return None
    return {"label": label, "box": item.get("box"), "box_norm": item.get("box_norm"),
            "zone": zone or item.get("zone")}


def _txt_ref(fv, label=None):
    if fv is None:
        return None
    if isinstance(fv, dict):
        return {"label": label or fv.get("name"), "line_no": fv.get("line_no"), "start": fv.get("start"),
                "end": fv.get("end")}
    return {"label": label or fv.name, "line_no": fv.line_no, "start": fv.start, "end": fv.end}


def result(rd: RuleDef, ctx: Ctx, status, *, jpg=None, txt=None, explanation="", gap=None,
           img_refs=None, txt_refs=None, uncertainty=None, details=None, action=None):
    if action is None:
        action = {
            CONFORME: "Aucune action requise.",
            ANOMALIE: "Comparer visuellement les deux sources (cliquer pour localiser), puis confirmer l'écart "
                      "ou le déclarer faux positif.",
            NON_VERIFIABLE: "Lecture humaine nécessaire : vérifier la valeur sur le bordereau et la corriger si besoin.",
            NON_APPLICABLE: "Aucune action requise.",
            ERREUR: "Signaler l'erreur technique ; contrôler manuellement.",
        }[status]
    return {
        "rule_id": rd.id, "category": rd.category, "category_label": CATEGORIES[rd.category],
        "title": rd.title, "spec": rd.spec, "convention": rd.convention,
        "status": status, "jpg_value": jpg, "txt_value": txt, "gap": gap,
        "zones": rd.zones, "txt_fields": rd.txt_fields,
        "img_refs": [r for r in (img_refs or []) if r], "txt_refs": [r for r in (txt_refs or []) if r],
        "explanation": explanation, "uncertainty": uncertainty, "details": details or {},
        "next_action": action, "processed_at": ctx.now, "engine_version": ENGINE_VERSION,
        "ruleset_version": RULESET_VERSION,
        "provenance": {"jpg": ctx.ext.get("file"), "jpg_sha256": ctx.ext.get("sha256"),
                       "txt": ctx.txt.path, "txt_sha256": ctx.txt.sha256,
                       "extractor": ctx.ext.get("extractor_version")},
    }


def _evidence(c) -> tuple:
    """Niveau de preuve d'une valeur candidate : nombre de moteurs OCR distincts, puis nombre de lectures."""
    return (len(c.get("engines") or []), c.get("votes", 0))


def contradictory_tie(field_res: Optional[dict]) -> list:
    """Valeurs concurrentes ayant exactement le même niveau de preuve que la valeur retenue."""
    cands = (field_res or {}).get("candidates") or []
    if len(cands) < 2 or (field_res or {}).get("agreement") == "corrigé":
        return []
    top = cands[0]
    return [c for c in cands[1:] if _evidence(c) == _evidence(top) and c["value"] != top["value"]]


def compare_read(field_res: Optional[dict], expected, match: Callable = None):
    """Compare une lecture multiple du bordereau à une valeur attendue.

    Retourne (statut, valeur_retenue, incertitude, motif).

    Politique d'incertitude (version 2.0) — la valeur du fichier ne sert JAMAIS à choisir une lecture
    du bordereau :
    - lectures contradictoires ex æquo (même nombre de moteurs et de lectures) → NON_VERIFIABLE,
      même si l'une d'elles est identique à la valeur du fichier ;
    - moteurs OCR en désaccord (« divergent ») → NON_VERIFIABLE ;
    - valeur retenue fiable (concordante, majoritaire ou corrigée par un agent) → CONFORME si elle égale
      la valeur attendue, ANOMALIE sinon (si elle est soutenue par au moins 2 lectures) ;
    - lecture unique : CONFORME à incertitude faible si elle concorde ; ANOMALIE à incertitude moyenne
      seulement si la confiance du moteur est élevée ; NON_VERIFIABLE sinon ;
    - zone vide, illisible ou non localisée → NON_VERIFIABLE.
    Une correction humaine (« corrigé ») lève l'incertitude.
    """
    match = match or (lambda a, b: a == b)
    if not field_res:
        return NON_VERIFIABLE, None, "forte", "zone non localisée"
    ag = field_res.get("agreement")
    cands = field_res.get("candidates") or []
    geo = field_res.get("geometrie") or {}
    if geo.get("fiable") is False and ag != "corrigé":
        return NON_VERIFIABLE, (cands[0]["value"] if cands else None), "forte", \
            (f"localisation du champ incertaine sur le bordereau (écart de recalage {geo.get('residu_px')} px, "
             f"seuil {geo.get('seuil_px')} px) : la valeur lue peut provenir d'une case voisine")
    if ag == "vide":
        return NON_VERIFIABLE, None, "forte", "zone vide sur le bordereau (aucune encre détectée)"
    if not cands:
        return NON_VERIFIABLE, None, "forte", "aucune lecture conforme au format attendu"
    top = cands[0]
    tie = contradictory_tie(field_res)
    if tie:
        vals = " / ".join(str(c["value"]) for c in [top] + tie)
        return NON_VERIFIABLE, None, "forte", \
            f"lectures OCR contradictoires ex æquo ({vals}) : aucune ne peut être retenue sans vérification humaine"
    if ag == "divergent":
        others = ", ".join(str(c["value"]) for c in cands[1:3])
        return NON_VERIFIABLE, top["value"], "forte", \
            f"moteurs OCR en désaccord (valeur la plus lue : {top['value']} ; autre(s) lecture(s) : {others})"
    top_ok = expected is not None and match(top["value"], expected)
    if top_ok:
        if ag in READ_OK:
            return CONFORME, top["value"], None, ""
        return CONFORME, top["value"], "faible", "lecture par un seul passage OCR valide"
    minority = [c for c in cands[1:] if expected is not None and match(c["value"], expected)]
    if minority:
        # une seule lecture isolée concorde alors que la valeur retenue est soutenue par ≥ 2 lectures
        if ag in READ_OK and top["votes"] >= 2 and max(c["votes"] for c in minority) == 1:
            return ANOMALIE, top["value"], "moyenne", \
                f"valeur lue par {top['votes']} lectures ; une lecture isolée correspond à la valeur du fichier"
        return NON_VERIFIABLE, top["value"], "forte", \
            "lectures OCR divergentes (une lecture minoritaire concorde) : vérification visuelle requise"
    if ag in READ_OK and top["votes"] >= 2:
        return ANOMALIE, top["value"], None, f"valeur lue par {top['votes']} lectures concordantes"
    if len(cands) == 1 and (field_res.get("conf") or 0) >= 0.8:
        return ANOMALIE, top["value"], "moyenne", "valeur lue par une seule lecture OCR (confiance élevée)"
    return NON_VERIFIABLE, top["value"], "forte", "lectures OCR insuffisamment concordantes"


def _unc(level, motif):
    return {"level": level, "reason": motif} if level else None


def _simple_field_rule(rd, ctx, fid, expected, txt_display, txt_ref, match=None, what=""):
    fr = ctx.f(fid)
    st, val, lvl, motif = compare_read(fr, expected, match)
    expl = {
        CONFORME: f"{what} : valeur du bordereau ({val}) identique à celle du fichier ({txt_display}).",
        ANOMALIE: f"{what} différent. Valeur du bordereau : {val}. Valeur du fichier : {txt_display}. "
                  f"Une vérification est nécessaire.",
        NON_VERIFIABLE: f"{what} : comparaison impossible de manière fiable ({motif}).",
    }[st]
    return result(rd, ctx, st, jpg=val, txt=txt_display, explanation=expl,
                  img_refs=[_img_ref(f"Bordereau — {(fr or {}).get('zone_label') or fid}", fr)],
                  txt_refs=[txt_ref], uncertainty=_unc(lvl, motif),
                  details={"lectures": _readings_summary(fr)})


def _readings_summary(fr):
    if not fr:
        return []
    return [{"moteur": r.get("engine"), "pretraitement": r.get("prep"), "texte": r.get("raw"),
             "valeur": r.get("value"), "valide": r.get("valid"), "confiance": r.get("conf"),
             "note": r.get("note")} for r in fr.get("readings", [])]


def _shift_hint(ctx: Ctx, key):
    if ctx.txt.alignment_shift:
        alt = shifted_reading(ctx.txt, ctx.txt.alignment_shift).get(key)
        return (f" Le fichier présente un décalage probable d'un caractère (voir observation) : en lecture "
                f"décalée, la valeur serait « {alt} » (hypothèse, non utilisée pour le contrôle).") if alt else ""
    return ""


STATUS_LABEL = {"CONFORME": "conforme", "ANOMALIE": "anomalie", "NON_VERIFIABLE": "à vérifier",
                "NON_APPLICABLE": "non applicable", "ERREUR_TECHNIQUE": "erreur technique"}


def conv_decision(ctx: Ctx, amb: str) -> str:
    """Décision métier enregistrée pour une ambiguïté du cahier des charges : « proposée » tant que la MSA
    ne s'est pas prononcée (la convention de l'équipe s'applique, signalée comme non validée)."""
    return (ctx.conventions or {}).get(amb) or "proposée"


def decision_label(d: str) -> str:
    return {"proposée": "proposée par l'équipe, non validée par la MSA", "validée": "validée par la MSA",
            "rejetée": "rejetée par la MSA"}.get(d, d)


# =====================================================================================
# A — Identification
@rule("R01", "A", "Identifiant du formulaire (CERFA 12278*0)",
      "S'assurer que le code identifiant récupéré dans la zone 1 du pdf vaut bien 12278*0",
      ["Z1"], [],
      convention="Le cahier des charges écrit « 12278*0 » ; le modèle annoté montre « 12278*0(.) » et les "
                 "bordereaux impriment « 12278*01 ». Convention retenue : l'identifiant doit commencer par "
                 "« 12278*0 » (le dernier chiffre est le numéro de version du formulaire). À confirmer par le métier.")
def r01(rd, ctx):
    fr = ctx.f("Z1")
    decision = conv_decision(ctx, "AMB-01")
    literal = decision == "rejetée"
    prefix = lambda v, e: str(v).startswith(e)
    exact = lambda v, e: str(v) == e
    st, val, lvl, motif = compare_read(fr, "12278*0", match=exact if literal else prefix)
    st_lit = compare_read(fr, "12278*0", match=exact)[0]
    st_conv = compare_read(fr, "12278*0", match=prefix)[0]
    rule_used = "égalité stricte (convention AMB-01 rejetée)" if literal else "préfixe « 12278*0 »"
    expl = {
        CONFORME: f"Identifiant lu « {val} » : commence bien par « 12278*0 »." if not literal else
                  f"Identifiant lu « {val} » : identique à « 12278*0 ».",
        ANOMALIE: f"Identifiant du formulaire lu « {val} » : ne correspond pas à « 12278*0 » ({rule_used}). "
                  f"Une vérification est nécessaire.",
        NON_VERIFIABLE: f"Identifiant du formulaire non vérifiable ({motif}).",
    }[st]
    if st_lit != st_conv and st != NON_VERIFIABLE:
        expl += (f" Selon la lettre du cahier des charges (« 12278*0 » exactement), le résultat serait "
                 f"« {STATUS_LABEL[st_lit]} » ; selon la convention AMB-01 (version du formulaire acceptée), "
                 f"« {STATUS_LABEL[st_conv]} ». Convention {decision_label(decision)}.")
    return result(rd, ctx, st, jpg=val, txt="12278*0 (référence du cahier des charges)", explanation=expl,
                  img_refs=[_img_ref("Bordereau — zone 1", fr)], uncertainty=_unc(lvl, motif),
                  details={"lectures": _readings_summary(fr), "ambiguite": "AMB-01",
                           "interpretations": {"litterale": st_lit, "convention": st_conv,
                                               "appliquee": "littérale" if literal else "convention",
                                               "decision": decision}})


@rule("R02", "A", "N° d'établissement (FINESS) = NumeroTiers",
      "Le numéro d'établissement récupéré dans la zone 2 est égal à la donnée « NumeroTiers »",
      ["Z2"], ["NumeroTiers (type 1, pos. 2-10)"])
def r02(rd, ctx):
    t = ctx.txt.numero_tiers
    if t is None or t.status != "ok":
        return result(rd, ctx, NON_VERIFIABLE, explanation="NumeroTiers absent ou illisible dans le fichier.",
                      txt_refs=[_txt_ref(t)])
    r = _simple_field_rule(rd, ctx, "Z2", t.value, t.value, _txt_ref(t, "NumeroTiers"), what="N° d'établissement")
    r["explanation"] += _shift_hint(ctx, "NumeroTiers") if r["status"] == ANOMALIE else ""
    return r


@rule("R03", "A", "N° de lot = NumeroLot",
      "Le numéro de lot récupéré dans la zone 3 est égal à la donnée « NumeroLot »",
      ["Z3"], ["NumeroLot (type 1, pos. 20-22)"],
      convention="Comparaison numérique : les zéros de cadrage à gauche sont ignorés.")
def r03(rd, ctx):
    t = ctx.txt.numero_lot
    if t is None or t.status != "ok":
        return result(rd, ctx, NON_VERIFIABLE, explanation="NumeroLot absent ou illisible dans le fichier.",
                      txt_refs=[_txt_ref(t)])
    m = _id_match(ctx)
    r = _simple_field_rule(rd, ctx, "Z3", t.value, t.value, _txt_ref(t, "NumeroLot"), match=m, what="N° de lot")
    if r["status"] == ANOMALIE:
        r["explanation"] += _shift_hint(ctx, "NumeroLot")
    return r


def _id_match(ctx):
    """AMB-02 : zéros de cadrage ignorés (convention), ou comparaison caractère par caractère si la MSA rejette
    la convention."""
    if conv_decision(ctx, "AMB-02") == "rejetée":
        return lambda v, e: str(v) == str(e).strip()
    return lambda v, e: strip_leading_zeros(str(v)) == strip_leading_zeros(str(e).strip())


@rule("R04", "A", "N° de facture = NumeroFacture",
      "Le numéro de facture récupéré dans la zone 4 est égal à la donnée « NumeroFacture »",
      ["Z4"], ["NumeroFacture (type 2, pos. 30-38)"],
      convention="Comparaison numérique : le fichier cadre le numéro sur 9 chiffres avec des zéros à gauche "
                 "(ex. 000491901), le bordereau l'imprime sans (491901).")
def r04(rd, ctx):
    t = ctx.txt.numero_facture
    if t is None or t.status != "ok":
        return result(rd, ctx, NON_VERIFIABLE, explanation="NumeroFacture absent ou illisible dans le fichier.",
                      txt_refs=[_txt_ref(t)])
    m = _id_match(ctx)
    strict = conv_decision(ctx, "AMB-02") == "rejetée"
    r = _simple_field_rule(rd, ctx, "Z4", t.value.strip() if strict else strip_leading_zeros(t.value.strip()), t.value,
                           _txt_ref(t, "NumeroFacture"), match=m, what="N° de facture")
    if len(ctx.txt.invoice_headers) > 1:
        r["explanation"] += (f" Remarque : le fichier contient {len(ctx.txt.invoice_headers)} enregistrements "
                             f"« début de facture » (voir observations).")
    if r["status"] == ANOMALIE:
        r["explanation"] += _shift_hint(ctx, "NumeroFacture")
    return r


@rule("R05", "A", "N° d'assuré (13 premiers caractères) = NumeroAssure",
      "Le numéro d'assuré récupéré dans la zone 5 (13 premiers caractères) est égal à « NumeroAssure »",
      ["Z5"], ["NumeroAssure (type 2, pos. 12-24)"],
      convention="Les espaces de présentation du bordereau sont ignorés avant de prendre les 13 premiers caractères.")
def r05(rd, ctx):
    t = ctx.txt.numero_assure
    if t is None or t.status != "ok":
        return result(rd, ctx, NON_VERIFIABLE, explanation="NumeroAssure absent ou illisible dans le fichier.",
                      txt_refs=[_txt_ref(t)])
    m = lambda v, e: str(v)[:13] == e
    fr = ctx.f("Z5")
    st, val, lvl, motif = compare_read(fr, t.value, match=m)
    v13 = str(val)[:13] if val else None
    expl = {
        CONFORME: f"N° d'assuré : les 13 premiers caractères du bordereau ({v13}) sont identiques au fichier ({t.value}).",
        ANOMALIE: f"N° d'assuré différent. Bordereau (13 premiers caractères) : {v13}. Fichier : {t.value}. "
                  f"Une vérification est nécessaire.",
        NON_VERIFIABLE: f"N° d'assuré non vérifiable ({motif}).",
    }[st]
    if st == ANOMALIE:
        expl += _shift_hint(ctx, "NumeroAssure")
    return result(rd, ctx, st, jpg=v13, txt=t.value, explanation=expl,
                  img_refs=[_img_ref("Bordereau — zone 5", fr)], txt_refs=[_txt_ref(t, "NumeroAssure")],
                  uncertainty=_unc(lvl, motif), details={"lu_complet": val, "lectures": _readings_summary(fr)})


# =====================================================================================
# B — Frais de structure et de soins
@rule("R06", "B", "Présence d'une prestation GHS avec son numéro",
      "Une prestation GHS doit être récupérée dans la colonne prestation de la zone 6 avec son numéro de GHS",
      ["Z6"], [])
def r06(rd, ctx):
    rows = ctx.rows("Z6")
    g = ctx.ghs_row()
    if g and g.get("ghs_incertain"):
        return result(rd, ctx, NON_VERIFIABLE, jpg="GHS ?",
                      explanation="Une ligne de la zone 6 pourrait être la prestation GHS, mais ce code n'est lu qu'en "
                                  "lecture minoritaire : vérification visuelle nécessaire.",
                      img_refs=[_img_ref("Ligne GHS probable — zone 6", g, "Z6")],
                      uncertainty=_unc("forte", "code de prestation lu de façon incertaine"))
    if g:
        num = g["cells"].get("ghs", {})
        nv = _cell_value(num)
        if nv and num.get("agreement") in READ_OK + ("lecture_unique",) and not contradictory_tie(num):
            return result(rd, ctx, CONFORME, jpg=f"GHS {nv}", explanation=f"Prestation GHS trouvée en zone 6 avec le numéro {nv}.",
                          img_refs=[_img_ref("Ligne GHS — zone 6", g, "Z6")])
        return result(rd, ctx, NON_VERIFIABLE, jpg="GHS (numéro illisible)",
                      explanation="Prestation GHS trouvée mais numéro de GHS illisible.",
                      img_refs=[_img_ref("Ligne GHS — zone 6", g, "Z6")], uncertainty=_unc("forte", "numéro illisible"))
    if not rows:
        return result(rd, ctx, ANOMALIE, jpg="aucune prestation lue en zone 6",
                      explanation="Aucune ligne de prestation n'a été détectée en zone 6 : la prestation GHS attendue est absente.",
                      uncertainty=_unc("moyenne", "absence constatée par détection de lignes"))
    codes = [_cell_value(r["cells"].get("prestation")) for r in rows]
    return result(rd, ctx, NON_VERIFIABLE, jpg=", ".join(str(c) for c in codes),
                  explanation=f"Aucune prestation lue comme « GHS » en zone 6 (lectures : {codes}).",
                  img_refs=[_img_ref("Zone 6", r, "Z6") for r in rows], uncertainty=_unc("forte", "lecture des codes incertaine"))


def _txt_ghs(ctx):
    return [a for a in ctx.txt.acts3 if a["acte"] == "GHS"]


@rule("R07", "B", "N° GHS du bordereau = NumeroGH (type 3, prestation GHS)",
      "Le numéro de GHS récupéré dans la zone 6 pour l'acte GHS est égal à « NumeroGH » de type 3 de la prestation GHS",
      ["Z6"], ["NumeroGH (type 3, pos. 110-113)"])
def r07(rd, ctx):
    g = ctx.ghs_row()
    tg = _txt_ghs(ctx)
    if not tg:
        return result(rd, ctx, ANOMALIE if g else NON_VERIFIABLE, jpg=_cell_value(g["cells"].get("ghs")) if g else None,
                      txt="aucune prestation GHS de type 3",
                      explanation="Le fichier ne contient aucune prestation « GHS » de type 3 : impossible de rapprocher le numéro.",
                      img_refs=[_img_ref("Ligne GHS — zone 6", g, "Z6")] if g else [])
    t = tg[0]
    if not g:
        return result(rd, ctx, NON_VERIFIABLE, txt=t["gh"], explanation="Prestation GHS non localisée en zone 6.",
                      txt_refs=[{"label": "NumeroGH", "line_no": t["line_no"], "start": 110, "end": 113}])
    cell = g["cells"].get("ghs")
    st, val, lvl, motif = compare_read(cell, t["gh"])
    if g.get("ghs_incertain") and st != NON_VERIFIABLE:
        st, lvl, motif = NON_VERIFIABLE, "forte", "ligne GHS identifiée sur une lecture minoritaire du code de prestation"
    expl = {
        CONFORME: f"N° GHS identique : bordereau {val}, fichier {t['gh']}.",
        ANOMALIE: f"N° GHS différent. Valeur du bordereau : {val}. Valeur du fichier : {t['gh']}. Une vérification est nécessaire.",
        NON_VERIFIABLE: f"N° GHS non vérifiable ({motif}).",
    }[st]
    return result(rd, ctx, st, jpg=val, txt=t["gh"], explanation=expl,
                  img_refs=[_img_ref("N° GHS — zone 6", cell, "Z6")],
                  txt_refs=[{"label": "NumeroGH (GHS)", "line_no": t["line_no"], "start": 110, "end": 113}],
                  uncertainty=_unc(lvl, motif))


def _match_codes(img_items, txt_items):
    """Rapprochement occurrence par occurrence (multiensemble) de codes.

    img_items / txt_items : listes de dicts {code, codes (lectures candidates), ...}.
    1re passe : appariement sur la valeur RETENUE de la lecture du bordereau.
    2e passe : un élément du bordereau non apparié peut l'être par une autre lecture candidate ; l'appariement
    est alors marqué « incertain » (la valeur du fichier ne départage jamais des lectures OCR).
    Un appariement sur une lecture « divergente » ou ex æquo est également marqué incertain.
    Retourne (non_appariés_bordereau, non_appariés_fichier, paires)."""
    t_left = list(txt_items)
    pending, pairs = [], []
    for it in img_items:
        idx = next((i for i, t in enumerate(t_left) if t["code"] == it.get("code")), None)
        if idx is None:
            pending.append(it)
        else:
            weak = it.get("agreement") == "divergent" or bool(it.get("tie"))
            pairs.append((dict(it, uncertain_match=weak) if weak else it, t_left.pop(idx)))
    unmatched_img = []
    for it in pending:
        idx = next((i for i, t in enumerate(t_left) if t["code"] in (it.get("codes") or [])), None)
        if idx is None:
            unmatched_img.append(it)
        else:
            pairs.append((dict(it, uncertain_match=True), t_left.pop(idx)))
    return unmatched_img, t_left, pairs


def _img_presta(rows, require_amount=False):
    out = []
    for r in rows:
        if r.get("kind") != "prestation":
            continue
        if require_amount and not r.get("has_amount"):
            continue
        cell = r["cells"].get("prestation", {})
        codes = [c["value"] for c in cell.get("candidates", [])]
        out.append({"codes": codes, "code": _cell_value(cell), "agreement": cell.get("agreement"), "row": r,
                    "tie": bool(contradictory_tie(cell)), "amount": _cell_value(r["cells"].get("montant"))})
    return out


def _pairs_detail(pairs, unmatched_img, missing_txt):
    """Détail ligne à ligne du rapprochement (utilisé par la fiche des zones 6, 7 et 10)."""
    out = []
    for it, t in pairs:
        r = it.get("row") or {}
        out.append({"zone": r.get("zone"), "row": r.get("row"), "code": it.get("code"), "txt_code": t["code"],
                    "line_no": t.get("line_no"), "start": t.get("start"), "end": t.get("end"),
                    "incertain": bool(it.get("uncertain_match"))})
    for it in unmatched_img:
        r = it.get("row") or {}
        out.append({"zone": r.get("zone"), "row": r.get("row"), "code": it.get("code"), "txt_code": None,
                    "line_no": None, "incertain": it.get("agreement") not in READ_OK})
    for t in missing_txt:
        out.append({"zone": None, "row": None, "code": None, "txt_code": t["code"], "line_no": t.get("line_no"),
                    "start": t.get("start"), "end": t.get("end"), "incertain": False})
    return out


def _presence_rule(rd, ctx, img_items, txt_items, direction, zone_label, txt_label):
    """direction = 'img->txt' : chaque élément du bordereau doit exister dans le fichier ;
    'txt->img' : chaque élément du fichier doit exister sur le bordereau.
    Un appariement qui ne repose que sur une lecture OCR minoritaire, divergente ou ex æquo ne permet pas de
    conclure à la conformité : le contrôle est alors NON_VERIFIABLE."""
    unmatched_img, missing_txt, pairs = _match_codes(img_items, txt_items)
    weak = [it for it, _ in pairs if it.get("uncertain_match")]
    weak_txt = ", ".join(f"{it.get('code')} (lu) ↔ {t['code']} (fichier)" for it, t in pairs if it.get("uncertain_match"))
    detail = {"appariements": _pairs_detail(pairs, unmatched_img, missing_txt)}
    if direction == "img->txt":
        missing = unmatched_img
        uncertain = [m for m in missing if m.get("agreement") not in READ_OK or m.get("tie")]
        certain = [m for m in missing if m.get("agreement") in READ_OK and not m.get("tie")]
        if not img_items:
            return result(rd, ctx, NON_APPLICABLE, jpg="aucune", txt=", ".join(t["code"] for t in txt_items) or "—",
                          explanation=f"Aucune prestation concernée lue en {zone_label}.", details=detail)
        if not missing and not weak:
            return result(rd, ctx, CONFORME, jpg=", ".join(i["code"] for i in img_items),
                          txt=", ".join(t["code"] for t in txt_items),
                          explanation=f"Toutes les prestations de {zone_label} ({len(img_items)}) sont présentes dans le fichier ({txt_label}).",
                          img_refs=[_img_ref(f"{i['code']}", i["row"]) for i in img_items], details=detail)
        gap_cents = sum((m.get("amount") or 0) for m in certain)
        if certain:
            codes = ", ".join(m["code"] for m in certain)
            return result(rd, ctx, ANOMALIE, jpg=codes, txt=", ".join(t["code"] for t in txt_items) or "aucun",
                          gap={"type": "prestation absente du fichier", "amount_cents": gap_cents or None,
                               "label": "montant affiché sur le bordereau pour ces lignes",
                               "lines": [{"zone": m["row"].get("zone"), "row": m["row"].get("row"), "code": m["code"],
                                          "amount_cents": m.get("amount")} for m in certain]},
                          explanation=f"Prestation(s) {codes} présente(s) sur le bordereau ({zone_label}) mais absente(s) "
                                      f"du fichier ({txt_label}). Une vérification est nécessaire.",
                          img_refs=[_img_ref(f"{m['code']} — absent du fichier", m["row"]) for m in certain],
                          details=dict(detail, non_retrouves=[m["code"] for m in certain],
                                       lecture_incertaine=[m["code"] for m in uncertain]))
        if uncertain:
            return result(rd, ctx, NON_VERIFIABLE, jpg=", ".join(str(m["code"]) for m in uncertain),
                          txt=", ".join(t["code"] for t in txt_items),
                          explanation="Code(s) lu(s) sur le bordereau non retrouvé(s) dans le fichier, mais la lecture OCR "
                                      "de ces codes est incertaine.",
                          img_refs=[_img_ref(f"{m['code']} (lecture incertaine)", m["row"]) for m in uncertain],
                          uncertainty=_unc("forte", "lecture des codes incertaine"), details=detail)
        return result(rd, ctx, NON_VERIFIABLE, jpg=", ".join(str(i["code"]) for i in img_items),
                      txt=", ".join(t["code"] for t in txt_items),
                      explanation=f"Les prestations semblent présentes dans le fichier, mais au moins un rapprochement "
                                  f"repose sur une lecture OCR incertaine ({weak_txt}) : vérification visuelle nécessaire.",
                      img_refs=[_img_ref(f"{i.get('code')} (lecture incertaine)", i["row"]) for i in weak],
                      uncertainty=_unc("forte", "rapprochement fondé sur une lecture minoritaire ou divergente"),
                      details=detail)
    # ---------------- 'txt->img'
    missing = missing_txt
    if not txt_items:
        return result(rd, ctx, NON_APPLICABLE, txt="aucun", explanation=f"Aucun élément concerné dans le fichier ({txt_label}).",
                      details=detail)
    if not missing and not weak:
        return result(rd, ctx, CONFORME, jpg=", ".join(i["code"] for i in img_items),
                      txt=", ".join(t["code"] for t in txt_items),
                      explanation=f"Tous les éléments du fichier ({len(txt_items)}) sont présents sur le bordereau ({zone_label}).",
                      txt_refs=[{"label": t["code"], "line_no": t["line_no"], "start": t.get("start"), "end": t.get("end")} for t in txt_items],
                      details=detail)
    if not missing:
        return result(rd, ctx, NON_VERIFIABLE, jpg=", ".join(str(i["code"]) for i in img_items),
                      txt=", ".join(t["code"] for t in txt_items),
                      explanation=f"Les éléments du fichier semblent présents sur le bordereau, mais au moins un rapprochement "
                                  f"repose sur une lecture OCR incertaine ({weak_txt}) : vérification visuelle nécessaire.",
                      img_refs=[_img_ref(f"{i.get('code')} (lecture incertaine)", i["row"]) for i in weak],
                      uncertainty=_unc("forte", "rapprochement fondé sur une lecture minoritaire ou divergente"),
                      details=detail)
    # si des codes du bordereau sont illisibles, un « manquant » peut être un défaut de lecture
    unreadable = [i for i in unmatched_img if i.get("agreement") not in READ_OK or i.get("tie")]
    codes = ", ".join(t["code"] for t in missing)
    gap_cents = None if ctx.txt.alignment_shift else sum((t.get("amount") or 0) for t in missing)
    st = ANOMALIE if not unreadable else NON_VERIFIABLE
    expl = (f"Élément(s) {codes} facturé(s) dans le fichier ({txt_label}) mais absent(s) du bordereau ({zone_label}). "
            f"Une vérification est nécessaire." if st == ANOMALIE else
            f"Élément(s) {codes} du fichier non retrouvé(s) sur le bordereau, mais certains codes du bordereau sont "
            f"illisibles ({', '.join(str(u['code']) for u in unreadable)}).")
    return result(rd, ctx, st, jpg=", ".join(str(i["code"]) for i in img_items) or "aucun", txt=codes,
                  gap={"type": "élément facturé absent du justificatif", "amount_cents": gap_cents or None,
                       "label": "montant porté par ces lignes dans le fichier",
                       "lines": None if ctx.txt.alignment_shift else
                       [{"line_no": t["line_no"], "code": t["code"], "amount_cents": t.get("amount")} for t in missing]},
                  explanation=expl,
                  txt_refs=[{"label": f"{t['code']} — absent du bordereau", "line_no": t["line_no"],
                             "start": t.get("start"), "end": t.get("end")} for t in missing],
                  uncertainty=_unc("forte", "codes du bordereau illisibles") if unreadable else None,
                  details=dict(detail, non_retrouves=[t["code"] for t in missing]))


def _txt3_items(ctx, exclude=()):
    return [{"code": a["acte"], "line_no": a["line_no"], "start": 56, "end": 60, "amount": a.get("base_cents"),
             "gh": a["gh"]} for a in ctx.txt.acts3 if a["acte"] and a["acte"] not in exclude]


@rule("R08", "B", "Prestations de la zone 6 (avec montant) présentes dans le fichier",
      "Toutes les prestations de la zone 6 ayant un montant facturé renseigné sont présentes dans le fichier (« Acte » de type 3)",
      ["Z6"], ["Acte (type 3, pos. 56-60)"],
      convention="Rapprochement occurrence par occurrence : deux lignes identiques sur le bordereau doivent "
                 "correspondre à deux enregistrements dans le fichier.")
def r08(rd, ctx):
    return _presence_rule(rd, ctx, _img_presta(ctx.rows("Z6"), require_amount=True), _txt3_items(ctx),
                          "img->txt", "zone 6", "Acte de type 3")


@rule("R09", "B", "NumeroGH des actes de type 3 = NumeroGH de l'acte GHS",
      "La valeur « NumeroGH » des actes de type 3 autres que GHS est égale à celle de l'acte GHS",
      ["Z6"], ["NumeroGH (type 3, pos. 110-113)"],
      convention="Contrôle interne au fichier : la référence est le NumeroGH de l'enregistrement 3 « GHS ».")
def r09(rd, ctx):
    tg = _txt_ghs(ctx)
    others = [a for a in ctx.txt.acts3 if a["acte"] and a["acte"] != "GHS"]
    if not tg:
        return result(rd, ctx, NON_VERIFIABLE, explanation="Aucun acte GHS de type 3 dans le fichier : référence absente.")
    ref = tg[0]["gh"]
    if not others:
        return result(rd, ctx, NON_APPLICABLE, txt=f"GHS {ref}", explanation="Aucun autre acte de type 3 dans le fichier.")
    bad = [a for a in others if a["gh"] != ref]
    refs = [{"label": f"NumeroGH {a['acte']} = {a['gh']}", "line_no": a["line_no"], "start": 110, "end": 113} for a in others]
    refs.insert(0, {"label": f"NumeroGH GHS = {ref}", "line_no": tg[0]["line_no"], "start": 110, "end": 113})
    if not bad:
        return result(rd, ctx, CONFORME, txt=f"GHS {ref}", explanation=f"Les {len(others)} autres actes de type 3 portent le NumeroGH {ref}.",
                      txt_refs=refs)
    return result(rd, ctx, ANOMALIE, txt=", ".join(f"{a['acte']}={a['gh']}" for a in bad), jpg=None,
                  explanation=f"NumeroGH incohérent : {', '.join(a['acte'] + ' porte ' + str(a['gh']) for a in bad)} "
                              f"alors que l'acte GHS porte {ref}. Une vérification est nécessaire.",
                  txt_refs=refs, details={"reference": ref})


# =====================================================================================
# C — LPP
@rule("R10", "C", "NumeroGH des actes de type 3 (LPP) = n° GHS de la zone 6",
      "La valeur « NumeroGH » des actes de type 3 est égale au NumeroGH de l'acte GHS (récupéré dans la zone 6)",
      ["Z6", "Z7"], ["NumeroGH (type 3, pos. 110-113)"],
      convention="Actes concernés : enregistrements 3 correspondant aux prestations de la zone 7. "
                 "Référence : numéro GHS LU sur le bordereau en zone 6.")
def r10(rd, ctx):
    g = ctx.ghs_row()
    lpp_codes = set()
    for i in _img_presta(ctx.rows("Z7")):
        lpp_codes.update(i["codes"])
    acts = [a for a in ctx.txt.acts3 if a["acte"] in lpp_codes and a["acte"] != "GHS"]
    if not acts:
        return result(rd, ctx, NON_APPLICABLE, explanation="Aucun acte de type 3 correspondant à une prestation de la zone 7.")
    if not g:
        return result(rd, ctx, NON_VERIFIABLE, explanation="N° GHS de la zone 6 non lu : référence indisponible.")
    cell = g["cells"].get("ghs")
    ref = _cell_value(cell)
    if not ref or cell.get("agreement") not in READ_OK + ("lecture_unique",) or contradictory_tie(cell) \
            or g.get("ghs_incertain"):
        return result(rd, ctx, NON_VERIFIABLE, explanation="N° GHS de la zone 6 illisible ou incertain : référence indisponible.",
                      img_refs=[_img_ref("N° GHS — zone 6", cell, "Z6")])
    bad = [a for a in acts if a["gh"] != ref]
    refs = [{"label": f"NumeroGH {a['acte']} = {a['gh']}", "line_no": a["line_no"], "start": 110, "end": 113} for a in acts]
    if not bad:
        return result(rd, ctx, CONFORME, jpg=f"GHS {ref}", txt=", ".join(f"{a['acte']}={a['gh']}" for a in acts),
                      explanation=f"Les actes LPP du fichier ({', '.join(a['acte'] for a in acts)}) portent le n° GHS {ref} lu en zone 6.",
                      img_refs=[_img_ref("N° GHS — zone 6", cell, "Z6")], txt_refs=refs)
    return result(rd, ctx, ANOMALIE, jpg=f"GHS {ref}", txt=", ".join(f"{a['acte']}={a['gh']}" for a in bad),
                  explanation=f"NumeroGH différent du n° GHS lu en zone 6 ({ref}) : "
                              f"{', '.join(a['acte'] + ' porte ' + str(a['gh']) for a in bad)}. Une vérification est nécessaire.",
                  img_refs=[_img_ref("N° GHS — zone 6", cell, "Z6")], txt_refs=refs)


@rule("R11", "C", "Prestations de la zone 7 présentes dans le fichier",
      "Toutes les prestations récupérées dans la zone 7 sont présentes dans le fichier (« Acte » de type 3)",
      ["Z7"], ["Acte (type 3, pos. 56-60)"],
      convention="Rapprochement occurrence par occurrence. Les enregistrements 3 déjà rapprochés de la zone 6 "
                 "ne sont pas réutilisés.")
def r11(rd, ctx):
    z6 = _img_presta(ctx.rows("Z6"))
    txt = _txt3_items(ctx)
    _, txt_left, _ = _match_codes(z6, txt)
    return _presence_rule(rd, ctx, _img_presta(ctx.rows("Z7")), txt_left, "img->txt", "zone 7", "Acte de type 3")


# =====================================================================================
# D — Récapitulatif
def _amount_rule(rd, ctx, fid, txt_fv, label, txt_name):
    fr = ctx.f(fid)
    if txt_fv is None or txt_fv.cents is None:
        return result(rd, ctx, NON_VERIFIABLE, explanation=f"{txt_name} absent ou non numérique dans le fichier.",
                      txt_refs=[_txt_ref(txt_fv)])
    st, val, lvl, motif = compare_read(fr, txt_fv.cents)
    gap = None
    if st == ANOMALIE and val is not None and not ctx.txt.alignment_shift:
        gap = {"type": "écart de montant", "amount_cents": txt_fv.cents - val,
               "label": "fichier − bordereau"}
    if st == CONFORME:
        expl = f"{label} identique : {amount_str(val)} sur le bordereau, {amount_str(txt_fv.cents)} dans le fichier."
    elif st == ANOMALIE:
        expl = (f"{label} différent. Bordereau : {amount_str(val)}. Fichier ({txt_name}) : {amount_str(txt_fv.cents)}. "
                f"Écart : {amount_str(txt_fv.cents - val)}. Une vérification est nécessaire.")
    else:
        expl = f"{label} non vérifiable ({motif})."
    if st == ANOMALIE and ctx.txt.alignment_shift:
        expl = (f"{label} différent. Bordereau : {amount_str(val)}. Valeur lue aux positions officielles du fichier : "
                f"{amount_str(txt_fv.cents)}. Le fichier présentant un décalage de positions, cet écart n'est pas "
                f"chiffrable de manière fiable. Une vérification est nécessaire.")
    return result(rd, ctx, st, jpg=amount_str(val) if val is not None else None, txt=amount_str(txt_fv.cents),
                  gap=gap, explanation=expl, img_refs=[_img_ref(f"Bordereau — {(fr or {}).get('zone_label') or fid}", fr)],
                  txt_refs=[_txt_ref(txt_fv, txt_name)], uncertainty=_unc(lvl, motif),
                  details={"jpg_cents": val, "txt_cents": txt_fv.cents, "lectures": _readings_summary(fr)})


@rule("R12", "D", "Sous-total 1+2+3 (zone 8) = TotalPrestations",
      "Le montant récupéré dans la zone 8 est égal à la donnée « TotalPrestations »",
      ["Z8"], ["TotalPrestations (type 5, pos. 42-49)"],
      convention="Montants comparés au centime (deux décimales implicites dans le fichier).")
def r12(rd, ctx):
    return _amount_rule(rd, ctx, "Z8", ctx.txt.total_prestations, "Total des prestations", "TotalPrestations")


@rule("R13", "D", "Prestations du fichier présentes en zone 6 ou 7",
      "Toutes les prestations du fichier (« Acte » de type 3) sont présentes dans la zone 6 ou la zone 7",
      ["Z6", "Z7"], ["Acte (type 3, pos. 56-60)"],
      convention="Rapprochement occurrence par occurrence ; toutes les lignes de prestation des zones 6 et 7 "
                 "sont prises en compte (avec ou sans montant).")
def r13(rd, ctx):
    items = _img_presta(ctx.rows("Z6")) + _img_presta(ctx.rows("Z7"))
    return _presence_rule(rd, ctx, items, _txt3_items(ctx), "txt->img", "zones 6 et 7", "Acte de type 3")


# =====================================================================================
# E — Honoraires
def _z10_acts(ctx):
    out = []
    for r in ctx.rows("Z10", "acte"):
        cell = r["cells"].get("code", {})
        codes = [c["value"] for c in cell.get("candidates", [])]
        out.append({"codes": codes, "code": _cell_value(cell), "agreement": cell.get("agreement"), "row": r,
                    "tie": bool(contradictory_tie(cell)), "amount": _cell_value(r["cells"].get("honoraires"))})
    return out


def _txt4_groups(ctx):
    """Actes de type 4 avec leur éventuel code CCAM (enregistrement 4-M qui suit)."""
    groups = []
    ccam_by_parent = {}
    for c in ctx.txt.ccam4m:
        ccam_by_parent.setdefault(c["parent_line"], []).append(c)
    for a in ctx.txt.acts4:
        cc = ccam_by_parent.get(a["line_no"], [])
        groups.append({"acte": a["acte"], "line_no": a["line_no"], "amount": a.get("honoraires_cents"),
                       "ccam": cc[0]["code7"] if cc else None, "ccam_line": cc[0]["line_no"] if cc else None})
    return groups


@rule("R14", "E", "Actes de la zone 10 codés sur ≤ 4 caractères présents dans le fichier",
      "Tous les actes de la zone 10 codifiés sur 4 caractères ou moins sont présents dans le fichier (« Acte » de type 4)",
      ["Z10"], ["Acte (type 4, pos. 76-80)"],
      convention="Seules les lignes d'acte (avec exécutant, date ou honoraires) sont prises en compte ; les lignes de "
                 "détail (codes de biologie imprimés sous un acte B) sont exclues. Rapprochement occurrence par occurrence.")
def r14(rd, ctx):
    img = [i for i in _z10_acts(ctx) if i["code"] and len(i["code"]) <= 4]
    txt = [{"code": g["acte"], "line_no": g["line_no"], "start": 76, "end": 80, "amount": g["amount"]}
           for g in _txt4_groups(ctx) if g["acte"]]
    return _presence_rule(rd, ctx, img, txt, "img->txt", "zone 10", "Acte de type 4")


@rule("R15", "E", "Actes CCAM (7 caractères) de la zone 10 présents dans le fichier",
      "Tous les actes de la zone 10 codifiés sur 7 caractères sont présents dans le fichier (« CodeCCAM » de type 4M)",
      ["Z10"], ["CodeCCAM (type 4-M, pos. 43-55, 7 caractères utiles)"])
def r15(rd, ctx):
    img = [i for i in _z10_acts(ctx) if i["code"] and len(i["code"]) == 7]
    txt = [{"code": c["code7"], "line_no": c["line_no"], "start": 43, "end": 55} for c in ctx.txt.ccam4m if c["code7"]]
    return _presence_rule(rd, ctx, img, txt, "img->txt", "zone 10", "CodeCCAM de type 4-M")


@rule("R16", "E", "NumeroGH des enregistrements 4-S = n° GHS de la zone 6",
      "La valeur « NumeroGH » des actes de type 4S est égale au NumeroGH de l'acte GHS (récupéré dans zone 6)",
      ["Z6"], ["NumeroGH (type 4-S, pos. 120-123)"])
def r16(rd, ctx):
    recs = ctx.txt.gh4s
    if not recs:
        return result(rd, ctx, NON_APPLICABLE, explanation="Aucun enregistrement 4-S dans le fichier.")
    g = ctx.ghs_row()
    cell = g["cells"].get("ghs") if g else None
    ref = _cell_value(cell)
    if not ref or (cell or {}).get("agreement") not in READ_OK + ("lecture_unique",) or contradictory_tie(cell) \
            or (g or {}).get("ghs_incertain"):
        return result(rd, ctx, NON_VERIFIABLE, explanation="N° GHS de la zone 6 non lu de façon fiable : référence indisponible.")
    bad = [r for r in recs if r["gh"] != ref]
    refs = [{"label": f"NumeroGH 4-S = {r['gh']}", "line_no": r["line_no"], "start": 120, "end": 123} for r in (bad or recs)]
    if not bad:
        return result(rd, ctx, CONFORME, jpg=f"GHS {ref}", txt=f"{len(recs)} × {ref}",
                      explanation=f"Les {len(recs)} enregistrements 4-S portent le NumeroGH {ref} lu en zone 6.",
                      img_refs=[_img_ref("N° GHS — zone 6", cell, "Z6")], txt_refs=refs[:20])
    vals = Counter(r["gh"] for r in bad)
    return result(rd, ctx, ANOMALIE, jpg=f"GHS {ref}", txt=", ".join(f"{k} (×{v})" for k, v in vals.items()),
                  explanation=f"{len(bad)} enregistrement(s) 4-S porte(nt) un NumeroGH différent du n° GHS lu en zone 6 ({ref}) : "
                              f"{', '.join(vals)}. Une vérification est nécessaire.",
                  img_refs=[_img_ref("N° GHS — zone 6", cell, "Z6")], txt_refs=refs[:20])


@rule("R17", "E", "Sous-total 4 (zone 12) = TotalHonoraires",
      "Le montant récupéré dans la zone 12 est égal à la donnée « TotalHonoraires »",
      ["Z12"], ["TotalHonoraires (type 5, pos. 58-65)"])
def r17(rd, ctx):
    return _amount_rule(rd, ctx, "Z12", ctx.txt.total_honoraires, "Total des honoraires", "TotalHonoraires")


@rule("R18", "E", "Signatures des exécutants (zone 11)",
      "Pour les numéros d'exécutants de la zone 9 qui ne sont pas des établissements (3e caractère ≠ 0), une signature "
      "doit figurer dans une des cases de la zone 11",
      ["Z9", "Z11"], [],
      convention="Présence d'un élément (signature manuscrite, cachet ou mention « par mandat ») et non authenticité. "
                 "Association exécutant ↔ case : par le numéro imprimé dans la case lorsqu'il est lisible.")
def r18(rd, ctx):
    execs = ctx.ext.get("executants") or []
    if not execs:
        if ctx.rows("Z10", "acte"):
            return result(rd, ctx, NON_VERIFIABLE, explanation="Numéros d'exécutants illisibles en zone 9.")
        return result(rd, ctx, NON_APPLICABLE, explanation="Aucun acte en zone 10 : aucun exécutant.")
    need = [e for e in execs if len(e["value"]) >= 3 and e["value"][2] != "0"]
    if not need:
        return result(rd, ctx, NON_APPLICABLE, jpg=", ".join(e["value"] for e in execs),
                      explanation=f"Exécutant(s) {', '.join(e['value'] for e in execs)} : établissement(s) (3e caractère = 0), "
                                  f"pas de signature de praticien exigée.")
    boxes = ctx.ext.get("signatures", {}).get("Z11", [])
    present = [b for b in boxes if b.get("status") == "PRESENT"]
    unsure = [b for b in boxes if b.get("status") == "INDETERMINE"]
    per, worst = [], CONFORME
    used = set()
    for e in need:
        box = next((b for b in boxes if e["value"] in (b.get("numbers") or [])), None)
        if box and box.get("status") == "PRESENT":
            used.add(box["case"])
            per.append({"executant": e["value"], "statut": "signature présente", "case": box["case"]})
        else:
            per.append({"executant": e["value"], "statut": None, "case": box["case"] if box else None})
    unassigned_present = [b for b in present if b["case"] not in used]
    for p in per:
        if p["statut"]:
            continue
        if unassigned_present:
            b = unassigned_present.pop(0)
            p["statut"] = f"élément présent en case {b['case']} (association non prouvée)"
            p["case"] = b["case"]
            worst = NON_VERIFIABLE if worst == CONFORME else worst
        elif unsure:
            p["statut"] = "présence indéterminée"
            worst = NON_VERIFIABLE if worst == CONFORME else worst
        elif not next((e.get("reliable", True) for e in need if e["value"] == p["executant"]), True):
            p["statut"] = "numéro d'exécutant lu de façon incertaine"
            worst = NON_VERIFIABLE if worst == CONFORME else worst
        else:
            p["statut"] = "aucune signature trouvée"
            worst = ANOMALIE
    img_refs = []
    if boxes:
        xs = [b["box"] for b in boxes]
        union = [min(x[0] for x in xs), min(x[1] for x in xs), max(x[2] for x in xs), max(x[3] for x in xs)]
        img_refs.append({"label": "Zone 11 — cases de signature", "box": union, "zone": "Z11"})
    img_refs += [_img_ref(f"Case {b['case']} — {b['status']}", b, "Z11") for b in boxes if b["status"] != "VIDE"]
    img_refs += [_img_ref(f"Exécutant {e['value']} — zone 9", e, "Z9") for e in need]
    missing = [p["executant"] for p in per if p["statut"] == "aucune signature trouvée"]
    expl = {
        CONFORME: f"Une signature/cachet est présent pour chaque exécutant concerné ({', '.join(e['value'] for e in need)}). "
                  f"L'authenticité n'est pas certifiée.",
        NON_VERIFIABLE: "Des éléments sont présents en zone 11 mais l'association avec chaque exécutant ne peut pas être "
                        "prouvée automatiquement : vérification visuelle nécessaire.",
        ANOMALIE: f"Aucune signature trouvée en zone 11 pour l'exécutant {', '.join(missing)}. Une vérification est nécessaire.",
    }[worst]
    action = "Vérifier visuellement les cases de signature de la zone 11." if worst != CONFORME else None
    return result(rd, ctx, worst, jpg="; ".join(f"{p['executant']} : {p['statut']}" for p in per),
                  txt="(contrôle propre au bordereau)", explanation=expl, img_refs=img_refs,
                  uncertainty=_unc("moyenne", "détection de présence par analyse d'image") if worst != CONFORME else None,
                  details={"executants": per}, action=action)


@rule("R19", "E", "Actes du fichier (type 4 / 4-M) présents en zone 10",
      "Toutes les prestations du fichier (« Acte » de type 4 ou « CodeCCAM » de type 4M) sont présentes dans la zone 10",
      ["Z10"], ["Acte (type 4, pos. 76-80)", "CodeCCAM (type 4-M, pos. 43-55)"],
      convention="Un acte de type 4 suivi d'un enregistrement 4-M est retrouvé par son code CCAM (c'est le code "
                 "imprimé sur le bordereau) ; sinon par son code Acte. Rapprochement occurrence par occurrence.")
def r19(rd, ctx):
    img = _z10_acts(ctx)
    txt = []
    for g in _txt4_groups(ctx):
        if g["ccam"]:
            txt.append({"code": g["ccam"], "line_no": g["ccam_line"], "start": 43, "end": 55, "amount": g["amount"],
                        "acte": g["acte"]})
        elif g["acte"]:
            txt.append({"code": g["acte"], "line_no": g["line_no"], "start": 76, "end": 80, "amount": g["amount"]})
    return _presence_rule(rd, ctx, img, txt, "txt->img", "zone 10", "Acte de type 4 / CodeCCAM 4-M")


# =====================================================================================
# F — Conclusion
@rule("R20", "F", "Montant total (zone 13) = zone 8 + zone 12",
      "Le montant total de la facture (zone 13) est égal à la somme des montants des zones 8 et 12",
      ["Z13", "Z8", "Z12"], [],
      convention="Contrôle arithmétique propre au bordereau, au centime. Il ne repose que sur des montants lus de "
                 "façon fiable (lectures concordantes ou majoritaires, ou correction d'un agent) : aucune combinaison "
                 "de lectures contradictoires n'est recherchée pour faire apparaître une égalité.")
def r20(rd, ctx):
    names = {"Z8": "zone 8", "Z12": "zone 12", "Z13": "zone 13"}
    frs = {k: ctx.f(k) for k in ("Z8", "Z12", "Z13")}
    refs = [_img_ref(names[k], fr) for k, fr in frs.items()]
    cands = {k: [x["value"] for x in (fr or {}).get("candidates") or []] for k, fr in frs.items()}
    for k, fr in frs.items():
        if not fr or not fr.get("candidates") or fr.get("agreement") in ("vide", "illisible"):
            return result(rd, ctx, NON_VERIFIABLE, explanation=f"Montant de la {names[k]} illisible : contrôle arithmétique impossible.",
                          img_refs=refs, uncertainty=_unc("forte", "montant illisible"), details={"candidats": cands})
    unreliable = {k: fr for k, fr in frs.items()
                  if fr.get("agreement") not in READ_OK or contradictory_tie(fr)}
    if unreliable:
        desc = " ; ".join(f"{names[k]} : " + " / ".join(amount_str(v) for v in cands[k]) for k in unreliable)
        return result(rd, ctx, NON_VERIFIABLE,
                      jpg="lecture incertaine",
                      explanation=f"Contrôle arithmétique non concluant : lecture incertaine ({desc}). Les valeurs candidates "
                                  f"sont conservées ; un agent doit lire ou corriger le montant avant toute conclusion.",
                      img_refs=refs, uncertainty=_unc("forte", "au moins un montant lu de façon incertaine"),
                      details={"candidats": cands, "incertains": list(unreliable)})
    v8, v12, v13 = (frs[k]["value"] for k in ("Z8", "Z12", "Z13"))
    if v8 + v12 == v13:
        return result(rd, ctx, CONFORME, jpg=f"{amount_str(v13)}", txt=None,
                      explanation=f"Zone 13 ({amount_str(v13)}) = zone 8 ({amount_str(v8)}) + zone 12 ({amount_str(v12)}).",
                      img_refs=refs, details={"candidats": cands})
    return result(rd, ctx, ANOMALIE, jpg=f"Z13 = {amount_str(v13)} ; Z8 + Z12 = {amount_str(v8 + v12)}",
                  gap={"type": "incohérence arithmétique", "amount_cents": v13 - (v8 + v12),
                       "label": "zone 13 − (zone 8 + zone 12)"},
                  explanation=f"Montant total incohérent : zone 13 = {amount_str(v13)}, alors que zone 8 ({amount_str(v8)}) + "
                              f"zone 12 ({amount_str(v12)}) = {amount_str(v8 + v12)}. Les trois montants sont lus de façon fiable.",
                  img_refs=refs, details={"candidats": cands})


@rule("R21", "F", "Signature du directeur de l'établissement (zone 14)",
      "S'assurer qu'il y a bien une signature dans la zone 14",
      ["Z14"], [],
      convention="Détection de présence d'un élément (tracé, cachet, signature électronique) ; l'authenticité "
                 "n'est jamais certifiée.")
def r21(rd, ctx):
    sigs = ctx.ext.get("signatures", {}).get("Z14", [])
    if not sigs:
        return result(rd, ctx, NON_VERIFIABLE, explanation="Zone 14 non localisée.")
    s = sigs[0]
    ref = [_img_ref("Zone 14 — signature du directeur", s, "Z14")]
    det = {"taux_encre": s.get("ink_ratio"), "composantes": s.get("components"), "traces_larges": s.get("large_strokes"),
           "texte_lu": s.get("text")}
    if s["status"] == "PRESENT":
        return result(rd, ctx, CONFORME, jpg=f"élément présent ({s.get('nature')})",
                      explanation="Un élément de signature est présent en zone 14 (présence constatée, authenticité non certifiée).",
                      img_refs=ref, details=det)
    if s["status"] == "VIDE":
        return result(rd, ctx, ANOMALIE, jpg="zone apparemment vide",
                      explanation="La zone 14 (signature du directeur de l'établissement) apparaît vide. Une vérification est nécessaire.",
                      img_refs=ref, details=det, uncertainty=_unc("faible", "détection par analyse d'image"))
    return result(rd, ctx, NON_VERIFIABLE, jpg="présence indéterminée",
                  explanation="Présence d'une signature en zone 14 impossible à déterminer automatiquement.",
                  img_refs=ref, details=det, uncertainty=_unc("forte", "faible quantité d'encre"),
                  action="Vérifier visuellement la zone 14.")


@rule("R22", "F", "Code CERFA (zone 15) = S3404",
      "S'assurer que le code cerfa récupéré dans la zone 15 vaut bien S3404",
      ["Z15"], [],
      convention="Les espaces de présentation sont ignorés (« S 3404 » = « S3404 »).")
def r22(rd, ctx):
    fr = ctx.f("Z15")
    st, val, lvl, motif = compare_read(fr, "S3404")
    expl = {
        CONFORME: f"Code CERFA lu « {val} » conforme à S3404.",
        ANOMALIE: f"Code CERFA lu « {val} » au lieu de S3404. Une vérification est nécessaire.",
        NON_VERIFIABLE: f"Code CERFA non vérifiable ({motif}).",
    }[st]
    return result(rd, ctx, st, jpg=val, txt="S3404 (référence du cahier des charges)", explanation=expl,
                  img_refs=[_img_ref("Bordereau — zone 15", fr)], uncertainty=_unc(lvl, motif),
                  details={"lectures": _readings_summary(fr), "notes": fr.get("notes") if fr else None})


# =====================================================================================
def run_rules(txt: ParsedB2, ext: dict, conventions: Optional[dict] = None) -> list:
    ctx = Ctx(txt, ext, conventions or {})
    out = []
    for rd in RULES:
        try:
            out.append(rd.func(rd, ctx))
        except Exception as e:  # une erreur n'interrompt jamais les autres contrôles
            out.append(result(rd, ctx, ERREUR, explanation=f"Erreur technique : {type(e).__name__}: {e}",
                              details={"trace": traceback.format_exc(limit=3)}))
    _table_gate(out, ext)
    _confusable_hint(out)
    _internal_total_note(out, txt)
    return out


def _internal_total_note(results: list, txt: ParsedB2) -> None:
    """R12 / R17 : si la somme des lignes du FICHIER égale la valeur du bordereau, c'est le total du fichier qui
    est incohérent avec ses propres lignes. L'anomalie est maintenue (la règle compare zone et total) ; la cause
    probable est signalée à l'agent."""
    sums = {"R12": [a["base_cents"] for a in txt.acts3 if a.get("base_cents") is not None],
            "R17": [a["honoraires_cents"] for a in txt.acts4 if a.get("honoraires_cents") is not None]}
    for r in results:
        if r["rule_id"] in sums and r["status"] == ANOMALIE and sums[r["rule_id"]]:
            jpg = (r.get("details") or {}).get("jpg_cents")
            tot = sum(sums[r["rule_id"]])
            if jpg is not None and tot == jpg:
                r["details"]["somme_lignes_fichier_cents"] = tot
                r["explanation"] += (f" Remarque : la somme des lignes du fichier ({amount_str(tot)}) est égale à la valeur "
                                     f"du bordereau ; c'est le total du fichier qui diffère de ses propres lignes.")


# Règles fondées sur la lecture des tableaux (zone → tableaux du gabarit)
TABLE_RULES = {"R06": ("Z6",), "R07": ("Z6",), "R08": ("Z6",), "R10": ("Z6", "Z7"), "R11": ("Z7",),
               "R13": ("Z6", "Z7"), "R14": ("Z10",), "R15": ("Z10",), "R16": ("Z6",), "R19": ("Z10",)}


def table_reliability(ext: dict, zone: str) -> tuple:
    """(fiable, motif) d'un tableau : recalage local et structure des lignes détectées (extraction 3.0).
    Une extraction antérieure sans ces contrôles est considérée fiable (comportement inchangé)."""
    checks = {k: v for k, v in (ext.get("table_checks") or {}).items() if k.startswith(zone + ":")}
    for k, c in checks.items():
        g = c.get("geometrie") or {}
        if g.get("fiable") is False:
            return False, (f"localisation du tableau {zone} incertaine (écart de recalage {g.get('residu_px')} px, "
                           f"seuil {g.get('seuil_px')} px)")
        if c.get("fiable") is False:
            parts = []
            if c.get("lignes_hautes"):
                parts.append(f"{len(c['lignes_hautes'])} ligne(s) anormalement haute(s), deux prestations possiblement fusionnées")
            if c.get("encre_hors_lignes_px"):
                parts.append("du texte hors des lignes détectées, une ligne a pu être ignorée")
            return False, f"découpage des lignes du tableau {zone} incertain ({' ; '.join(parts)})"
    return True, ""


def _table_gate(results: list, ext: dict) -> None:
    """Un tableau mal localisé ou mal découpé ne permet ni de conclure à une anomalie ni à la conformité :
    le contrôle devient « à vérifier », avec la région concernée."""
    for r in results:
        zones = TABLE_RULES.get(r["rule_id"])
        if not zones or r["status"] not in (ANOMALIE, CONFORME):
            continue
        for z in zones:
            # une ligne corrigée ou validée par un agent dans ce tableau lève le doute de lecture
            if any(cell.get("agreement") == "corrigé" for row in (ext.get("tables") or {}).get(z, [])
                   for cell in (row.get("cells") or {}).values()):
                continue
            ok, why = table_reliability(ext, z)
            if not ok:
                r["details"]["statut_avant_controle_geometrique"] = r["status"]
                r["status"] = NON_VERIFIABLE
                r["uncertainty"] = _unc("forte", why)
                r["explanation"] = f"Lecture du bordereau insuffisamment fiable pour conclure : {why}. " + r["explanation"]
                r["next_action"] = "Vérifier visuellement le tableau sur le bordereau, puis corriger les lectures si besoin."
                break


CONFUSABLE = [set("08"), set("38"), set("56"), set("17"), set("49"), set("13"), set("69")]


def _confusable_hint(results: list) -> None:
    """Deux valeurs qui ne diffèrent que d'un caractère couramment confondu à la lecture (0/8, 1/7…) :
    l'anomalie est maintenue (lecture concordante des deux moteurs) mais l'agent est invité à regarder le chiffre."""
    for r in results:
        if r["status"] != ANOMALIE:
            continue
        a, b = str(r.get("jpg_value") or ""), str(r.get("txt_value") or "")
        a, b = a.replace(" ", "").replace("€", ""), b.replace(" ", "").replace("€", "")
        if len(a) == len(b) and a:
            d = [(x, y) for x, y in zip(a, b) if x != y]
            if len(d) == 1 and {d[0][0], d[0][1]} in CONFUSABLE:
                r["details"]["caractere_confusable"] = f"{d[0][0]} / {d[0][1]}"


def complementary_observations(txt: ParsedB2, ext: dict) -> list:
    """Observations complémentaires : incohérences techniques hors cahier des charges.
    Elles ne sont JAMAIS présentées comme des non-conformités."""
    obs = [dict(o.to_dict(), source="fichier TXT") for o in txt.observations]
    f = ext.get("fields", {})

    def v(k):
        x = f.get(k)
        return x.get("value") if x and x.get("agreement") in READ_OK else None
    st1, st2, st3, z8 = v("ST1"), v("ST2") or 0, v("ST3") or 0, v("Z8")
    if st1 is not None and z8 is not None and st1 + st2 + st3 != z8:
        obs.append({"code": "SOUS_TOTAUX_BORDEREAU", "severity": "info", "source": "bordereau",
                    "message": f"Sous-totaux 1+2+3 lus ({amount_str(st1)} + {amount_str(st2)} + {amount_str(st3)}) ≠ "
                               f"zone 8 ({amount_str(z8)}).", "line_nos": [], "details": {}})
    hon = [r["cells"]["honoraires"]["value"] for r in ext.get("tables", {}).get("Z10", [])
           if r.get("kind") == "acte" and r["cells"].get("honoraires", {}).get("agreement") in READ_OK]
    z12 = v("Z12")
    n_act = len([r for r in ext.get("tables", {}).get("Z10", []) if r.get("kind") == "acte"])
    if hon and z12 is not None and len(hon) == n_act and sum(hon) != z12:
        obs.append({"code": "SOMME_HONORAIRES_BORDEREAU", "severity": "info", "source": "bordereau",
                    "message": f"Somme des honoraires lus en zone 10 ({amount_str(sum(hon))}) ≠ zone 12 ({amount_str(z12)}).",
                    "line_nos": [], "details": {}})
    q = ext.get("quality", {})
    if q.get("issues"):
        obs.append({"code": "QUALITE_IMAGE", "severity": "info", "source": "bordereau",
                    "message": "Qualité d'image : " + ", ".join(q["issues"]), "line_nos": [], "details": q})
    for w in ext.get("warnings", []):
        obs.append({"code": "EXTRACTION", "severity": "warning", "source": "bordereau", "message": w,
                    "line_nos": [], "details": {}})
    return obs


def pairing_check(txt: ParsedB2, ext: dict) -> dict:
    """Vérifie que le bordereau et le fichier concernent le même dossier (au-delà du nom de fichier)."""
    f = ext.get("fields", {})
    checks = {}
    for k, t, m in (("Z2", txt.numero_tiers, lambda a, b: a == b),
                    ("Z4", txt.numero_facture, lambda a, b: strip_leading_zeros(a) == strip_leading_zeros(b.strip())),
                    ("Z5", txt.numero_assure, lambda a, b: str(a)[:13] == b)):
        fr = f.get(k)
        if not fr or not t or not fr.get("candidates"):
            checks[k] = None
        else:
            checks[k] = any(m(c["value"], t.value) for c in fr["candidates"])
    ok = sum(1 for x in checks.values() if x)
    known = sum(1 for x in checks.values() if x is not None)
    status = "confirmé" if ok >= 2 else ("ambigu" if known else "non vérifiable")
    return {"status": status, "identifiants_concordants": ok, "identifiants_compares": known, "details": checks,
            "methode": "Appariement par nom de fichier, confirmé si au moins 2 identifiants sur 3 (FINESS, facture, "
                       "assuré) concordent entre le bordereau et le fichier."}


def summarize(results: list, txt: ParsedB2, ext: dict) -> dict:
    c = Counter(r["status"] for r in results)
    anomalies = [r for r in results if r["status"] == ANOMALIE]
    # Écart de facturation mesurable sans double comptage : différences nettes sur les deux totaux
    net = 0
    measurable = False
    for rid in ("R12", "R17"):
        r = next((x for x in results if x["rule_id"] == rid), None)
        if r and r["status"] == ANOMALIE and r.get("gap") and r["gap"].get("amount_cents") is not None:
            net += abs(r["gap"]["amount_cents"]); measurable = True
    act_level = 0 if txt.alignment_shift else sum(abs(r["gap"]["amount_cents"]) for r in anomalies
                    if r.get("gap") and r["gap"].get("amount_cents") and r["rule_id"] in ("R08", "R11", "R13", "R14", "R15", "R19"))
    tp = txt.total_prestations.cents if txt.total_prestations and txt.total_prestations.cents is not None else None
    th = txt.total_honoraires.cents if txt.total_honoraires and txt.total_honoraires.cents is not None else None
    return {
        "counts": dict(c),
        "n_anomalies": c.get(ANOMALIE, 0),
        "n_non_verifiable": c.get(NON_VERIFIABLE, 0),
        "n_errors": c.get(ERREUR, 0),
        "anomaly_rules": [r["rule_id"] for r in anomalies],
        "nv_rules": [r["rule_id"] for r in results if r["status"] == NON_VERIFIABLE],
        # fichier décalé : les montants lus aux positions officielles ne sont pas fiables
        "billed_cents": None if txt.alignment_shift else ((tp or 0) + (th or 0) if tp is not None or th is not None else None),
        "net_total_gap_cents": net if measurable else 0,
        "act_level_gap_cents": act_level,
        "state": ("anomalie" if c.get(ANOMALIE) else "lecture_humaine" if c.get(NON_VERIFIABLE) or c.get(ERREUR)
                  else "conforme"),
    }
