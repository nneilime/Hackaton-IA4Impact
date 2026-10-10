"""Lecture multiple (« double lecture ») d'un champ ou d'une cellule.

Plusieurs lectures indépendantes sont produites (deux moteurs OCR, plusieurs prétraitements),
puis normalisées et validées par le format attendu du champ. Les valeurs valides sont
regroupées par vote. Le résultat garde TOUTES les lectures (traçabilité) et indique le niveau
d'accord, utilisé ensuite par le moteur de règles pour distinguer ANOMALIE et NON_VERIFIABLE.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Optional

import cv2
import numpy as np

from .. import normalize as N
from .engine import get_engine, text_band

# ---------------------------------------------------------------- formats attendus
VALIDATORS = {
    "digits": lambda v: bool(v) and v.isdigit(),
    "finess": lambda v: bool(v) and v.isdigit() and len(v) == 9,
    "lot": lambda v: bool(v) and v.isdigit() and 1 <= len(v) <= 3,
    "facture": lambda v: bool(v) and v.isdigit() and 4 <= len(v) <= 9,
    "nir": lambda v: bool(v) and v.isdigit() and len(v) >= 13,
    "amount": lambda v: v is not None,
    "cerfa_id": lambda v: bool(v) and re.fullmatch(r"\d{5}\*\d{2}", v) is not None,
    "cerfa_code": lambda v: bool(v) and re.fullmatch(r"[A-Z]\d{4}", v) is not None,
    # cahier des charges : code acte sur 4+1 caractères, code CCAM sur 7 caractères (4 lettres + 3 chiffres)
    "code": lambda v: bool(v) and (re.fullmatch(r"[A-Z0-9]{1,5}", v) is not None
                                  or re.fullmatch(r"[A-Z]{4}\d{3}", v) is not None),
    "ghs": lambda v: bool(v) and re.fullmatch(r"\d{4}", v) is not None,
    "executant": lambda v: bool(v) and re.fullmatch(r"\d{9}", v) is not None,
    "date": lambda v: bool(v) and re.fullmatch(r"\d{2}/\d{2}/\d{2,4}", v) is not None,
    "text": lambda v: bool(v),
}


def normalize_reading(kind: str, text: str):
    """Normalisation par type. Retourne (valeur, note) ; note décrit toute interprétation."""
    t = (text or "").strip()
    note = ""
    if kind in ("digits", "finess", "lot", "facture", "executant", "ghs"):
        v = N.digits(t)
        if kind == "facture":
            v = N.strip_leading_zeros(v) if v else v
        return v or None, note
    if kind == "nir":
        # n° d'immatriculation : 13 chiffres + clé de 2 chiffres ; le texte voisin (« clé », « à défaut ») est ignoré
        m = re.search(r"(?<!\d)(\d{13})\s?(\d{2})(?!\d)", t)
        if m:
            return m.group(1) + m.group(2), note
        return N.digits(t) or None, note
    if kind == "amount":
        # validation stricte : la cellule doit contenir UN montant (bruit de bordure toléré aux extrémités)
        u = re.sub(r"^[\s|\[\]Il!:;'`\"_\-]+|[\s|\[\]Il!:;'`\"_\-]+$", "", t.replace("€", ""))
        if re.fullmatch(r"\d{1,3}(?:[ \u202f\u00a0]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?", u):
            return N.parse_amount(u), note
        return None, note
    if kind == "cerfa_id":
        s = t.replace(" ", "")
        m = re.search(r"(\d{5})\*(\d{2})", s)
        if m:
            return f"{m.group(1)}*{m.group(2)}", note
        # séparateur lu comme un autre symbole non alphanumérique (", ™, ■, -, x) entre 5 et 2 chiffres
        m = re.search(r"(\d{5})[^\w\s]{1,2}(\d{2})(?!\d)", s)
        if m:
            return f"{m.group(1)}*{m.group(2)}", "séparateur lu comme un symbole et interprété comme « * »"
        return None, note
    if kind == "cerfa_code":
        s = re.sub(r"\s+", "", t.upper())
        m = re.search(r"([A-Z$58])(\d{4})(?!\d)", s)
        if m:
            p = m.group(1)
            if p in "$58":
                return "S" + m.group(2), f"préfixe lu « {p} » interprété comme « S » (confusion typographique)"
            return p + m.group(2), note
        return None, note
    if kind == "code":
        v = re.sub(r"[^A-Z0-9]", "", t.upper())
        # « GHS » dont le G est traversé par un trait de colonne : confusions G/S/C/6/$/( documentées
        if re.fullmatch(r"(?:[\$\(\[][GSC6\$]{0,2}|[GSC6\$]{1,2})HS[I1|\)\]]?", t.strip().upper()) and v != "GHS" and v.endswith("HS") or \
                (re.fullmatch(r"[GSC6]{1,2}HS[I1]?", v) and v != "GHS"):
            return "GHS", f"« {v} » interprété comme « GHS » (G traversé par un trait de colonne)"
        # Codes CCAM : 4 lettres + 3 chiffres ; corrige O→0 / I→1 uniquement dans la partie numérique
        if len(v) == 7 and re.fullmatch(r"[A-Z]{4}[A-Z0-9]{3}", v):
            tail = v[4:].replace("O", "0").replace("I", "1").replace("L", "1")
            if tail != v[4:]:
                note = "partie numérique d'un code CCAM : O→0 / I→1"
            v = v[:4] + tail
        return v or None, note
    if kind == "date":
        m = re.search(r"\d{2}/\d{2}/\d{2,4}", t.replace(" ", ""))
        return (m.group(0) if m else None), note
    return t or None, note


def _crop(gray, box):
    H, W = gray.shape
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    return gray[y0:y1, x0:x1]


def _pad(img, p=10):
    return cv2.copyMakeBorder(img, p, p, p, p, cv2.BORDER_CONSTANT, value=255)


_TES = "?"


def _optional_tesseract():
    """Tesseract est facultatif : sans lui, seules les lectures RapidOCR sont utilisées."""
    global _TES
    if _TES == "?":
        try:
            _TES = get_engine("tesseract")
        except Exception:
            _TES = None
    return _TES


def multi_read(gray: np.ndarray, clean: np.ndarray, box, kind: str, unit: float,
               mode: str = "center", fast: bool = False) -> dict:
    """Lit un champ (mode « center » : ligne la plus proche du centre de la boîte) ou une cellule
    de tableau (mode « all » : ligne la plus encrée). unit = largeur_image / 1190."""
    raw = _crop(gray, box)
    cl = _crop(clean, box)
    if raw.size == 0:
        return _result([], kind)
    ink = float((cl < 160).mean()) if cl.size else 0.0
    band = text_band(cl, pick="center" if mode == "center" else "max") if ink >= 0.002 else None
    if band is None:
        return _result([], kind, empty=True, ink=ink)
    y0, y1, x0, x1 = band
    raw_b = raw[y0:y1, x0:x1]
    cl_b = cl[y0:y1, x0:x1]
    if raw_b.size == 0:
        return _result([], kind, empty=True, ink=ink)
    readings = []
    rap = get_engine("rapidocr")
    tes = _optional_tesseract()
    # étirement horizontal : évite la fusion de caractères répétés (« 00 » lu « 0 ») par le décodeur CTC
    stretch = lambda im: cv2.resize(im, None, fx=1.4, fy=1, interpolation=cv2.INTER_CUBIC)
    for label, img in (("brut", raw_b), ("traits effacés", cl_b),
                       ("brut étiré ×1,4", stretch(raw_b)), ("traits effacés étiré ×1,4", stretch(cl_b))):
        im = _pad(img, 6)
        t, c = rap.recognize(im)
        readings.append({"engine": "rapidocr", "prep": label, "raw": t, "conf": c})
    f = 3.0 / unit
    for label, img in (() if tes is None else (("traits effacés", cl_b),) if fast else (("traits effacés", cl_b), ("brut", raw_b))):
        im = _pad(cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC), 12)
        r = tes.read(im, "text", psm=7)
        readings.append({"engine": "tesseract", "prep": f"{label} x3", "raw": r.text.replace("\n", " "),
                         "conf": r.conf})
    res = _result(readings, kind, ink=ink)
    res["text_box"] = [box[0] + x0, box[1] + y0, box[0] + x1, box[1] + y1]
    return res


def _result(readings, kind, empty=False, ink=0.0):
    valid = VALIDATORS.get(kind, VALIDATORS["text"])
    groups: "OrderedDict" = OrderedDict()
    for r in readings:
        v, note = normalize_reading(kind, r["raw"])
        r["value"] = v
        r["note"] = note
        r["valid"] = bool(valid(v)) if v is not None else False
    if kind == "amount":
        # Lecture tronquée : « 936.6 » (une décimale) alors qu'une autre lecture donne « 936.68 » →
        # le dernier chiffre a été coupé (bord de case) ; la lecture soutient la valeur complète.
        full = [r for r in readings if r["valid"] and re.search(r"[.,]\d{2}\b", r["raw"] or "")]
        for r in readings:
            if r["valid"] and re.search(r"[.,]\d(?!\d)", r["raw"] or "") and not re.search(r"[.,]\d{2}", r["raw"] or ""):
                match = [f["value"] for f in full if f["value"] // 10 == r["value"] // 10]
                if match:
                    r["note"] = (r.get("note") or "") + "lecture tronquée d'un chiffre, rattachée à la valeur complète"
                    r["value"] = match[0]
    for r in readings:
        if r["valid"]:
            groups.setdefault(r["value"], []).append(r)
    # Vote : le soutien de moteurs DIFFÉRENTS prime sur le nombre de lectures (les prétraitements d'un même
    # moteur ne sont pas des lectures indépendantes) ; deux moteurs en désaccord = lectures divergentes.
    cands = sorted(groups.items(), key=lambda kv: (-len({x["engine"] for x in kv[1]}), -len(kv[1]),
                                                   -max((x["conf"] or 0) for x in kv[1])))
    candidates = [{"value": v, "votes": len(rs), "engines": sorted({x["engine"] for x in rs})} for v, rs in cands]
    top = candidates[0] if candidates else None
    n_valid = sum(1 for r in readings if r["valid"])
    if empty:
        status = "vide"
    elif not top:
        status = "illisible"
    elif len(candidates) == 1 and (top["votes"] >= 2):
        status = "concordant"
    elif len(candidates) == 1:
        status = "lecture_unique"
    else:
        second = candidates[1]
        engines_present = {e for c in candidates for e in c["engines"]}
        if len(top["engines"]) > len(second["engines"]) and top["votes"] >= second["votes"]:
            status = "majoritaire"          # soutenue par plus de moteurs différents
        elif second["votes"] >= 2 and set(second["engines"]) - set(top["engines"]):
            status = "divergent"            # un autre moteur soutient de façon répétée une autre valeur
        elif top["votes"] > second["votes"]:
            status = "majoritaire"
        else:
            status = "divergent"            # désaccord réel : lecture humaine
    best_raw = None
    if top:
        best_raw = next(r["raw"] for r in readings if r["valid"] and r["value"] == top["value"])
    confs = [r["conf"] for r in readings if r.get("valid") and top and r["value"] == top["value"] and r["conf"] is not None]
    notes = sorted({r["note"] for r in readings if r.get("note") and top and r["value"] == top["value"]})
    return {
        "value": top["value"] if top else None,
        "raw": best_raw if best_raw is not None else (readings[0]["raw"] if readings else ""),
        "conf": round(sum(confs) / len(confs), 3) if confs else None,
        "agreement": status,
        "votes": top["votes"] if top else 0,
        "n_readings": len(readings),
        "n_valid": n_valid,
        "candidates": candidates,
        "readings": readings,
        "notes": notes,
        "ink_ratio": round(ink, 4),
    }
