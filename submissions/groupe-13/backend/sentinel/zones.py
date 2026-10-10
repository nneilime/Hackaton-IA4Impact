"""Couche « 15 zones CERFA » (version 2.0) : géométrie, correspondance zone ↔ règles, statut de zone.

Cette couche est une VUE DÉRIVÉE : elle ne relit pas l'image et ne duplique pas les résultats en base.
Elle combine :
- la géométrie des zones, calculée à partir des gabarits F1/F2/F3 (`ocr/templates.py`) et du recalage
  effectif de chaque bordereau (`ext["layout"]`) — indépendante des lectures OCR : une zone vide,
  illisible ou non applicable reste localisée et sélectionnable ;
- la table de correspondance zone ↔ règles du cahier des charges (sans applicabilité inventée) ;
- les résultats des 22 règles déjà calculés, pour en déduire un statut de zone explicable.

Statut d'une zone (même code couleur partout : visionneuse, grille, fiche, supervision, rapport) :
    ANOMALIE         au moins une règle associée en anomalie (indicateur si d'autres contrôles sont incertains)
    ERREUR_TECHNIQUE aucune anomalie mais un contrôle n'a pas pu s'exécuter
    NON_VERIFIABLE   aucune anomalie, au moins un contrôle nécessaire non vérifiable — ou une conformité qui
                     ne repose que sur une lecture OCR isolée (la conformité de zone exige des données fiables)
    NON_APPLICABLE   toutes les règles associées sont non applicables à ce dossier
    CONFORME         toutes les règles applicables sont conformes, sans incertitude
Le statut de zone ne remplace jamais le détail des règles : chaque résultat reste présenté individuellement.
"""
from __future__ import annotations

from typing import Optional

from . import ENGINE_VERSION, RULESET_VERSION
from .ocr.layout import map_box, norm_box
from .ocr.templates import TEMPLATES

CONFORME, ANOMALIE, NON_VERIFIABLE, NON_APPLICABLE, ERREUR = (
    "CONFORME", "ANOMALIE", "NON_VERIFIABLE", "NON_APPLICABLE", "ERREUR_TECHNIQUE")

# -------------------------------------------------------------------------------- catalogue
# (zone, titre métier, description, règles associées, rôle de chaque règle)
ZONES = [
    ("Z1", "Identifiant du formulaire", "Numéro d'identification du formulaire CERFA imprimé en haut à gauche.",
     {"R01": "principale"}),
    ("Z2", "N° FINESS de l'établissement", "Numéro d'identification de l'établissement (9 chiffres).",
     {"R02": "principale"}),
    ("Z3", "N° de lot", "Numéro de lot de facturation.", {"R03": "principale"}),
    ("Z4", "N° de facture", "Numéro de la facture.", {"R04": "principale"}),
    ("Z5", "N° d'immatriculation de l'assuré", "Numéro de sécurité sociale de l'assuré (13 caractères + clé).",
     {"R05": "principale"}),
    ("Z6", "Prestations — frais de structure et de soins",
     "Tableaux des prestations hospitalières (forfait GHS, suppléments) avec leur n° GHS et leur montant.",
     {"R06": "principale", "R07": "principale", "R08": "principale",
      "R09": "transversale — cohérence des NumeroGH du fichier avec l'acte GHS de référence",
      "R10": "transversale — référence GHS lue en zone 6", "R13": "transversale — exhaustivité zones 6 et 7",
      "R16": "transversale — référence GHS lue en zone 6"}),
    ("Z7", "Produits LPP, pharmacie et médicaments", "Tableau des prestations LPP / pharmacie / médicaments.",
     {"R10": "principale", "R11": "principale", "R13": "transversale — exhaustivité zones 6 et 7"}),
    ("Z8", "Sous-total des prestations (1+2+3)", "Montant récapitulatif des prestations.",
     {"R12": "principale", "R20": "transversale — zone 13 = zone 8 + zone 12"}),
    ("Z9", "Identification des exécutants",
     "Numéros d'identification des praticiens exécutants (colonne du tableau des actes, zone 10).",
     {"R18": "principale — associée aux signatures de la zone 11"}),
    ("Z10", "Actes médicaux et honoraires", "Tableau des actes : exécutant, date, code acte ou CCAM, honoraires.",
     {"R14": "principale", "R15": "principale", "R19": "principale"}),
    ("Z11", "Signatures des praticiens", "Cases de signature des praticiens et auxiliaires médicaux.",
     {"R18": "principale — associée aux exécutants de la zone 9"}),
    ("Z12", "Sous-total des honoraires (4)", "Montant récapitulatif des honoraires.",
     {"R17": "principale", "R20": "transversale — zone 13 = zone 8 + zone 12"}),
    ("Z13", "Montant total de la facture", "Montant total : somme des zones 8 et 12.",
     {"R20": "principale"}),
    ("Z14", "Signature du directeur de l'établissement", "Signature ou cachet du directeur.",
     {"R21": "principale"}),
    ("Z15", "Code CERFA du document", "Code du formulaire imprimé en bas à droite (S 3404).",
     {"R22": "principale"}),
]
ZONE_IDS = [z[0] for z in ZONES]
ZONE_INFO = {z[0]: {"id": z[0], "label": z[1], "description": z[2], "rules": z[3]} for z in ZONES}


def rules_by_zone() -> dict:
    return {z: list(ZONE_INFO[z]["rules"]) for z in ZONE_IDS}


def zones_of_rule(rule_id: str) -> list:
    return [z for z in ZONE_IDS if rule_id in ZONE_INFO[z]["rules"]]


# Données du fichier TXT rattachées à une zone
TXT_LINKS = {
    "Z2": [("numero_tiers", "NumeroTiers (type 1, pos. 2-10)")],
    "Z3": [("numero_lot", "NumeroLot (type 1, pos. 20-22)")],
    "Z4": [("numero_facture", "NumeroFacture (type 2, pos. 30-38)")],
    "Z5": [("numero_assure", "NumeroAssure (type 2, pos. 12-24)")],
    "Z8": [("total_prestations", "TotalPrestations (type 5, pos. 42-49)")],
    "Z12": [("total_honoraires", "TotalHonoraires (type 5, pos. 58-65)")],
}
NO_TXT = {
    "Z1": "Contrôle propre au bordereau : la valeur est comparée à la référence du cahier des charges (12278*0).",
    "Z9": "Contrôle propre au bordereau : les exécutants sont rapprochés des cases de signature (zone 11).",
    "Z11": "Contrôle propre au bordereau : présence d'une signature pour chaque exécutant (zone 9).",
    "Z13": "Contrôle arithmétique propre au bordereau (zone 13 = zone 8 + zone 12) : aucune donnée du fichier.",
    "Z14": "Contrôle propre au bordereau : présence d'une signature du directeur.",
    "Z15": "Contrôle propre au bordereau : la valeur est comparée à la référence du cahier des charges (S3404).",
}
FIELD_OF_ZONE = {"Z1": "Z1", "Z2": "Z2", "Z3": "Z3", "Z4": "Z4", "Z5": "Z5", "Z8": "Z8", "Z12": "Z12",
                 "Z13": "Z13", "Z15": "Z15"}


# -------------------------------------------------------------------------------- géométrie
def zone_geometry(family: Optional[str], layout: Optional[dict], size) -> dict:
    """Régions de chaque zone (pixels de l'image recalée + coordonnées normalisées), calculées à partir du
    gabarit et du recalage — jamais à partir des lectures OCR. Une zone composée de régions disjointes
    (tableaux 6a/6b, cases de signature) reçoit plusieurs régions plutôt qu'un rectangle approximatif."""
    if not family or family not in TEMPLATES or not layout or not size:
        return {z: [] for z in ZONE_IDS}
    tpl = TEMPLATES[family]
    W, H = size
    reg = {k: layout.get(k) for k in ("sx", "sy", "dx", "dy")}
    pad = int(round(4 * W / 1190.0))      # même marge verticale que l'extraction des champs

    def R(box, label, role="zone", vpad=0):
        b = map_box(box, reg)
        b = (max(0, b[0]), max(0, b[1] - vpad), min(W, b[2]), min(H, b[3] + vpad))
        return {"box": list(b), "box_norm": norm_box(b, W, H), "label": label, "role": role}

    out = {z: [] for z in ZONE_IDS}
    f = tpl["fields"]
    for z in ("Z1", "Z2", "Z3", "Z4", "Z5", "Z8", "Z12", "Z13", "Z15"):
        out[z].append(R(f[z]["box"], ZONE_INFO[z]["label"], "valeur", pad))
    t = tpl["tables"]
    out["Z6"].append(R(t["Z6a"]["body"], "Tableau des prestations (gauche)", "tableau"))
    out["Z6"].append(R(t["Z6b"]["body"], "Tableau des prestations (droite)", "tableau"))
    out["Z6"].append(R(f["ST1"]["box"], "Sous-total 1", "sous-total", pad))
    out["Z6"].append(R(f["ST2"]["box"], "Sous-total 2", "sous-total", pad))
    out["Z7"].append(R(t["Z7"]["body"], "Tableau LPP / pharmacie", "tableau"))
    out["Z7"].append(R(f["ST3"]["box"], "Sous-total 3", "sous-total", pad))
    b10 = t["Z10"]["body"]
    ex = t["Z10"]["cols"]["executant"]
    out["Z9"].append(R((ex[0], b10[1], ex[1], b10[3]), "Colonne des exécutants (dans le tableau des actes)", "colonne"))
    out["Z10"].append(R(b10, "Tableau des actes", "tableau"))
    for i, b in enumerate(tpl["signature_boxes"]["Z11"], start=1):
        out["Z11"].append(R(b, f"Case de signature {i}", "case"))
    for b in tpl["signature_boxes"]["Z14"]:
        out["Z14"].append(R(b, "Signature du directeur", "case"))
    _separate(out, W, H)
    return out


def _separate(geo: dict, W: int, H: int):
    """Deux zones « valeur » voisines (ex. N° de lot et N° de facture, sous-total 3 et zone 8) ne doivent pas se
    recouvrir : chacune doit rester cliquable. La frontière est placée au milieu du recouvrement vertical."""
    vals = [(z, r) for z, rs in geo.items() for r in rs if r["role"] in ("valeur", "sous-total")]
    for i, (za, a) in enumerate(vals):
        for zb, b in vals[i + 1:]:
            if za == zb:
                continue
            A, B = a["box"], b["box"]
            if min(A[2], B[2]) <= max(A[0], B[0]):
                continue                                       # pas de recouvrement horizontal
            top, bot = (a, b) if A[1] <= B[1] else (b, a)
            T, Bo = top["box"], bot["box"]
            if T[3] > Bo[1] and T[1] < Bo[1]:
                mid = (T[3] + Bo[1]) // 2
                T[3], Bo[1] = mid, mid
                for r in (top, bot):
                    r["box_norm"] = norm_box(r["box"], W, H)


def _bbox(regions) -> Optional[list]:
    if not regions:
        return None
    bs = [r["box"] for r in regions]
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


# -------------------------------------------------------------------------------- statut
def zone_status(rule_results: list) -> dict:
    """Statut d'une zone à partir des résultats de ses règles. Retourne statut, indicateurs et motif."""
    sts = [r["status"] for r in rule_results]
    weak_conf = [r for r in rule_results if r["status"] == CONFORME and r.get("uncertainty")]
    flags = []
    if not rule_results:
        return {"status": NON_APPLICABLE, "flags": [], "reason": "Aucune règle associée."}
    if ANOMALIE in sts:
        st = ANOMALIE
        if NON_VERIFIABLE in sts or ERREUR in sts or weak_conf:
            flags.append("controles_egalement_incertains")
        reason = "Au moins une incohérence a été constatée : " + ", ".join(r["rule_id"] for r in rule_results if r["status"] == ANOMALIE) + "."
    elif ERREUR in sts:
        st = ERREUR
        reason = "Un contrôle n'a pas pu être exécuté : " + ", ".join(r["rule_id"] for r in rule_results if r["status"] == ERREUR) + "."
    elif NON_VERIFIABLE in sts:
        st = NON_VERIFIABLE
        reason = "Données insuffisantes pour conclure : " + ", ".join(r["rule_id"] for r in rule_results if r["status"] == NON_VERIFIABLE) + "."
    elif all(s == NON_APPLICABLE for s in sts):
        st = NON_APPLICABLE
        reason = "Les contrôles associés ne concernent pas ce dossier."
    elif weak_conf:
        st = NON_VERIFIABLE
        flags.append("conformite_sur_lecture_isolee")
        reason = ("Conformité fondée sur une lecture OCR isolée (" + ", ".join(r["rule_id"] for r in weak_conf) +
                  ") : une vérification humaine est nécessaire avant de conclure.")
    else:
        st = CONFORME
        reason = "Toutes les vérifications applicables sont satisfaites avec des données fiables."
    distinct = {s for s in sts if s != NON_APPLICABLE}
    if len(distinct) > 1:
        flags.append("mixte")
    return {"status": st, "flags": flags, "reason": reason}


EXPLAIN = {
    CONFORME: "Les contrôles applicables à cette zone concordent avec des lectures fiables.",
    ANOMALIE: "Une incohérence documentaire a été constatée. Ce n'est pas une fraude démontrée : comparez les deux sources.",
    NON_VERIFIABLE: "Les données ne permettent pas une conclusion fiable : une vérification humaine est nécessaire.",
    NON_APPLICABLE: "Aucun contrôle de cette zone ne concerne ce dossier.",
    ERREUR: "Un traitement n'a pas pu être exécuté : contrôlez manuellement et signalez l'erreur.",
}


# -------------------------------------------------------------------------------- contenu des zones
def _field_summary(fr: Optional[dict]) -> Optional[dict]:
    if not fr:
        return None
    return {"field": fr.get("field"), "business": fr.get("business"), "raw": fr.get("raw"), "value": fr.get("value"),
            "agreement": fr.get("agreement"), "conf": fr.get("conf"), "method": fr.get("method"),
            "candidates": fr.get("candidates"), "notes": fr.get("notes"), "box": fr.get("text_box") or fr.get("box"),
            "readings": [{"engine": r.get("engine"), "prep": r.get("prep"), "raw": r.get("raw"), "value": r.get("value"),
                          "valid": r.get("valid"), "conf": r.get("conf"), "note": r.get("note")} for r in fr.get("readings", [])],
            "corrected_by": fr.get("corrected_by"), "corrected_at": fr.get("corrected_at"),
            "original": (fr.get("original") or {}).get("value") if fr.get("original") else None,
            "target": f"fields.{fr.get('field')}"}


def _txt_value(txt, attr) -> Optional[dict]:
    fv = getattr(txt, attr, None) if txt else None
    if fv is None:
        return None
    return {"name": fv.name, "raw": fv.raw, "value": fv.value, "cents": fv.cents, "line_no": fv.line_no,
            "start": fv.start, "end": fv.end, "status": fv.status}


def _cell(c):
    if not c:
        return None
    return {"value": c.get("value"), "raw": c.get("raw"), "agreement": c.get("agreement"), "box": c.get("box"),
            "candidates": c.get("candidates")}


def _rows(ext, zone, by_rule):
    """Lignes d'un tableau avec leur rapprochement (repris du détail des règles de présence)."""
    rows = (ext.get("tables") or {}).get(zone, [])
    links = {}
    for rid in ("R08", "R11", "R13", "R14", "R15", "R19"):
        r = by_rule.get(rid)
        if not r:
            continue
        for a in (r.get("details") or {}).get("appariements", []) or []:
            if a.get("zone") == zone and a.get("row") is not None:
                links.setdefault(a["row"], []).append(dict(a, rule_id=rid))
    out = []
    for r in rows:
        c = r.get("cells", {})
        code_key = "prestation" if zone in ("Z6", "Z7") else "code"
        amount_key = "montant" if zone in ("Z6", "Z7") else "honoraires"
        lk = links.get(r.get("row"), [])
        matched = [l for l in lk if l.get("line_no") and l.get("txt_code")]
        res = ("rapprochée" if matched and not any(l["incertain"] for l in matched) else
               "rapprochement incertain" if matched else
               ("non retrouvée dans le fichier" if lk else ("ligne de détail" if r.get("kind") == "detail" else
                                                              "non contrôlée par une règle de présence")))
        out.append({"row": r.get("row"), "table": r.get("table"), "kind": r.get("kind"), "box": r.get("box"),
                    "code": _cell(c.get(code_key)), "ghs": _cell(c.get("ghs")), "montant": _cell(c.get(amount_key)),
                    "executant": _cell(c.get("executant")), "date": _cell(c.get("date")),
                    "txt": [{"rule_id": l["rule_id"], "line_no": l["line_no"], "code": l["txt_code"], "start": l.get("start"),
                             "end": l.get("end"), "incertain": l["incertain"]} for l in matched],
                    "resultat": res})
    return out


def _txt_only(zone, by_rule, txt):
    """Éléments du fichier non retrouvés sur le bordereau, à rechercher dans cette zone (sans coordonnées
    inventées : on indique la zone où ils auraient dû figurer)."""
    rids = {"Z6": ("R13",), "Z7": ("R13",), "Z10": ("R19",)}.get(zone, ())
    out = []
    for rid in rids:
        r = by_rule.get(rid)
        if not r or r["status"] != ANOMALIE:
            continue
        for t in r.get("txt_refs") or []:
            out.append({"rule_id": rid, "line_no": t.get("line_no"), "start": t.get("start"), "end": t.get("end"),
                        "label": t.get("label"),
                        "attendu_en": "zones 6 ou 7" if rid == "R13" else "zone 10"})
    return out


def build_zones(ext: dict, txt, results: list) -> list:
    """Synthèse des 15 zones d'un dossier (vue dérivée des résultats existants)."""
    lay = ext.get("layout") or {}
    family = lay.get("family")
    geo = zone_geometry(family, lay, ext.get("size"))
    by_rule = {r["rule_id"]: r for r in results}
    fields = ext.get("fields") or {}
    sigs = ext.get("signatures") or {}
    out = []
    for z in ZONE_IDS:
        info = ZONE_INFO[z]
        rr = [by_rule[r] for r in info["rules"] if r in by_rule]
        st = zone_status(rr)
        regions = geo.get(z, [])
        item = {
            "zone_id": z, "label": info["label"], "description": info["description"],
            "regions": regions, "bbox": _bbox(regions),
            "localisation": "gabarit " + family + " + recalage" if regions else
            "localisation impossible : mise en page du bordereau non reconnue",
            "related_rules": [{"rule_id": rid, "role": role} for rid, role in info["rules"].items()],
            "status": st["status"], "flags": st["flags"], "reason": st["reason"],
            "explanation": EXPLAIN[st["status"]],
            "counts": {s: sum(1 for r in rr if r["status"] == s) for s in (CONFORME, ANOMALIE, NON_VERIFIABLE, NON_APPLICABLE, ERREUR)},
            "needs_human_review": st["status"] in (ANOMALIE, NON_VERIFIABLE, ERREUR),
            "rule_results": [{"rule_id": r["rule_id"], "title": r["title"], "status": r["status"], "jpg_value": r.get("jpg_value"),
                              "txt_value": r.get("txt_value"), "explanation": r.get("explanation"), "gap": r.get("gap"),
                              "uncertainty": r.get("uncertainty"), "next_action": r.get("next_action"),
                              "txt_refs": r.get("txt_refs"), "role": info["rules"][r["rule_id"]]} for r in rr],
            "extracted": {}, "txt": {"links": [], "absence": NO_TXT.get(z)},
            "traceability": {"jpg": ext.get("file"), "jpg_sha256": ext.get("sha256"), "txt": getattr(txt, "path", None),
                             "txt_sha256": getattr(txt, "sha256", None), "extractor_version": ext.get("extractor_version"),
                             "engine_version": ENGINE_VERSION, "ruleset_version": RULESET_VERSION,
                             "cache": (ext.get("cache") or {}).get("statut")},
        }
        if z in FIELD_OF_ZONE:
            item["extracted"]["field"] = _field_summary(fields.get(FIELD_OF_ZONE[z]))
        for attr, label in TXT_LINKS.get(z, []):
            v = _txt_value(txt, attr)
            item["txt"]["links"].append({"label": label, **(v or {"absent": True})})
        if z in ("Z6", "Z7", "Z10"):
            item["extracted"]["rows"] = _rows(ext, z, by_rule)
            item["extracted"]["txt_only"] = _txt_only(z, by_rule, txt)
            if z in ("Z6", "Z7"):
                item["extracted"]["subtotals"] = [_field_summary(fields.get(k)) for k in (("ST1", "ST2") if z == "Z6" else ("ST3",)) if fields.get(k)]
                for a in (txt.acts3 if txt else []):
                    item["txt"]["links"].append({"label": f"Acte {a['acte']} (type 3)", "line_no": a["line_no"], "start": 56,
                                                 "end": 60, "value": a["acte"], "gh": a.get("gh")})
            else:
                for a in (txt.acts4 if txt else []):
                    item["txt"]["links"].append({"label": f"Acte {a['acte']} (type 4)", "line_no": a["line_no"], "start": 76,
                                                 "end": 80, "value": a["acte"]})
                for c in (txt.ccam4m if txt else []):
                    item["txt"]["links"].append({"label": f"CCAM {c['code7']} (type 4-M)", "line_no": c["line_no"],
                                                 "start": 43, "end": 55, "value": c["code7"]})
        if z == "Z9":
            item["extracted"]["executants"] = [
                {"value": e.get("value"), "agreement": e.get("agreement"), "reliable": e.get("reliable"), "note": e.get("note"),
                 "box": e.get("box"), "row": e.get("row"),
                 "etablissement": len(e.get("value") or "") >= 3 and e["value"][2] == "0"}
                for e in ext.get("executants") or []]
        if z in ("Z11", "Z14"):
            r18 = {p["executant"]: p for p in ((by_rule.get("R18") or {}).get("details") or {}).get("executants", [])} if z == "Z11" else {}
            cases = []
            for i, s in enumerate(sigs.get(z, [])):
                linked = [e for e, p in r18.items() if p.get("case") == s.get("case")]
                cases.append({"case": s.get("case"), "status": s.get("status"), "original_status": s.get("original_status"),
                              "corrected_by": s.get("corrected_by"), "box": s.get("box"), "ink_ratio": s.get("ink_ratio"),
                              "components": s.get("components"), "nature": s.get("nature"), "numbers": s.get("numbers"),
                              "text": s.get("text"), "executants_associes": linked,
                              "incertitude": "forte (présence indéterminée)" if s.get("status") == "INDETERMINE" else "analyse d'image",
                              "target": f"signatures.{z}.{i}"})
            item["extracted"]["signatures"] = cases
            item["extracted"]["avertissement"] = ("La détection porte sur la PRÉSENCE d'un tracé, d'un cachet ou d'une mention ; "
                                                  "elle ne certifie jamais l'authenticité d'une signature.")
        out.append(item)
    return out


def summarize_zones(zones: list) -> dict:
    from collections import Counter
    return dict(Counter(z["status"] for z in zones))
