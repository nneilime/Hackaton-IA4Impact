"""Validation des corrections humaines de lecture (version 2.0).

Liste blanche des cibles réellement corrigibles, contrôle du type et du format de la nouvelle valeur,
cohérence des indices de tableaux et valeurs permises pour les signatures. Une correction invalide est
refusée avant enregistrement (elle n'est jamais enregistrée puis ignorée lors du recalcul).

Si la valeur saisie est identique à la lecture actuelle, l'action est une « validation » de la lecture :
elle lève l'incertitude (lecture confirmée par un agent) et alimente la mesure de la qualité OCR.
"""
from __future__ import annotations

import re
from typing import Optional

from .normalize import parse_amount
from .ocr.reader import VALIDATORS, normalize_reading

FIELD_KINDS = {"Z1": "cerfa_id", "Z2": "finess", "Z3": "lot", "Z4": "facture", "Z5": "nir", "ST1": "amount",
               "ST2": "amount", "ST3": "amount", "Z8": "amount", "Z12": "amount", "Z13": "amount", "Z15": "cerfa_code"}
CELL_KINDS = {"prestation": "code", "ghs": "ghs", "montant": "amount", "code": "code", "executant": "executant",
              "date": "date", "quantite": "amount", "honoraires": "amount"}
TABLE_COLS = {"Z6": {"prestation", "ghs", "montant"}, "Z7": {"prestation", "ghs", "code", "montant"},
              "Z10": {"executant", "date", "ghs", "code", "quantite", "honoraires"}}
SIGNATURE_VALUES = ("PRESENT", "VIDE")
KIND_HELP = {
    "cerfa_id": "5 chiffres, « * », 2 chiffres (ex. 12278*01)", "finess": "9 chiffres", "lot": "1 à 3 chiffres",
    "facture": "4 à 9 chiffres", "nir": "au moins 13 chiffres", "amount": "montant (ex. 818,97)",
    "cerfa_code": "une lettre et 4 chiffres (ex. S3404)", "code": "code acte (≤ 5 caractères) ou CCAM (4 lettres + 3 chiffres)",
    "ghs": "4 chiffres", "executant": "9 chiffres", "date": "JJ/MM/AA ou JJ/MM/AAAA",
}


class CorrectionError(ValueError):
    pass


def parse_target(target: str) -> dict:
    """Analyse une cible : fields.<ID> | tables.<Z>.<ligne>.cells.<colonne> | signatures.<Z11|Z14>.<i>."""
    m = re.fullmatch(r"fields\.(Z1|Z2|Z3|Z4|Z5|ST1|ST2|ST3|Z8|Z12|Z13|Z15)", target)
    if m:
        return {"type": "field", "id": m.group(1), "kind": FIELD_KINDS[m.group(1)]}
    m = re.fullmatch(r"tables\.(Z6|Z7|Z10)\.(\d{1,3})\.cells\.([a-z]+)", target)
    if m:
        z, row, col = m.group(1), int(m.group(2)), m.group(3)
        if col not in TABLE_COLS[z]:
            raise CorrectionError(f"Colonne « {col} » inexistante dans le tableau {z}.")
        return {"type": "cell", "zone": z, "row": row, "col": col, "kind": CELL_KINDS[col]}
    m = re.fullmatch(r"signatures\.(Z11|Z14)\.(\d{1,2})", target)
    if m:
        return {"type": "signature", "zone": m.group(1), "index": int(m.group(2)), "kind": "signature"}
    raise CorrectionError("Cible de correction non autorisée.")


def resolve(ext: dict, t: dict) -> dict:
    """Retourne l'élément ciblé de l'extraction (vérifie l'existence et les indices)."""
    try:
        if t["type"] == "field":
            node = (ext.get("fields") or {})[t["id"]]
        elif t["type"] == "cell":
            rows = (ext.get("tables") or {}).get(t["zone"], [])
            if not (0 <= t["row"] < len(rows)):
                raise CorrectionError(f"La ligne {t['row'] + 1} n'existe pas dans le tableau {t['zone']}.")
            node = rows[t["row"]]["cells"][t["col"]]
        else:
            sigs = (ext.get("signatures") or {}).get(t["zone"], [])
            if not (0 <= t["index"] < len(sigs)):
                raise CorrectionError(f"La case {t['index'] + 1} n'existe pas en {t['zone']}.")
            node = sigs[t["index"]]
    except KeyError:
        raise CorrectionError("Élément introuvable dans l'extraction du bordereau.")
    return node


def validate_value(t: dict, value: str):
    """Contrôle et normalise la valeur saisie selon le type attendu. Retourne la valeur normalisée."""
    v = (value or "").strip()
    if not v:
        raise CorrectionError("Valeur vide.")
    if t["kind"] == "signature":
        if v not in SIGNATURE_VALUES:
            raise CorrectionError("Valeur de signature permise : PRESENT ou VIDE.")
        return v
    if t["kind"] == "amount":
        if not re.fullmatch(r"\d{1,3}(?:[   ]?\d{3})*(?:[.,]\d{1,2})?", v):
            raise CorrectionError(f"Format de montant invalide (attendu : {KIND_HELP['amount']}).")
        cents = parse_amount(v)
        if cents is None or cents > 10_000_000_00:
            raise CorrectionError("Montant invalide ou hors limites.")
        return cents
    norm, _ = normalize_reading(t["kind"], v)
    if norm is None or not VALIDATORS.get(t["kind"], VALIDATORS["text"])(norm):
        raise CorrectionError(f"Format invalide pour ce champ (attendu : {KIND_HELP.get(t['kind'], 'texte')}).")
    return norm


def current_value(node: dict, t: dict):
    if t["type"] == "signature":
        return node.get("status")
    return node.get("value")


def check(ext: dict, target: str, value: str) -> dict:
    """Validation complète. Retourne {target, parsed, normalized, original, kind: correction|validation}."""
    t = parse_target(target)
    node = resolve(ext, t)
    norm = validate_value(t, value)
    orig_node = node.get("original") or {}
    original = node.get("original_status") if t["type"] == "signature" and node.get("original_status") else \
        (orig_node.get("value") if orig_node else current_value(node, t))
    kind = "validation" if norm == current_value(node, t) and node.get("agreement") != "corrigé" else "correction"
    return {"target": target, "parsed": t, "normalized": norm, "original": original, "kind": kind}
