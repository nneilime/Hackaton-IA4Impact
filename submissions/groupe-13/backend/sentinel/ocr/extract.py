"""Extraction structurée d'un bordereau JPG (pipeline perceptif).

Étapes : chargement → contrôle qualité → orientation et identification de la mise en page →
recalage géométrique → localisation des zones (gabarit normalisé) → lecture multiple de chaque
champ / cellule (2 moteurs OCR locaux) → reconstruction des lignes de tableaux → détection de
présence dans les zones de signature → normalisation → conservation des coordonnées.

Chaque valeur conserve : valeur brute, valeur normalisée, champ métier, zone, coordonnées
(pixels et normalisées), image source, méthode, confiance fournie par le moteur, niveau
d'accord entre lectures, et toutes les lectures individuelles.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from pathlib import Path

import cv2
import numpy as np

from .. import ENGINE_VERSION
from .engine import clean_page, get_engine
from .layout import (SKEW_MIN_DEG, anchor_residuals, box_geometry, deskew, estimate_skew, identify_and_register,
                     map_box, norm_box, quality)
from .reader import _optional_tesseract, multi_read
from .templates import TEMPLATES, ZONE_LABELS

EXTRACTOR_VERSION = "extract-3.0"

FIELD_BUSINESS = {
    "Z1": "Identifiant du formulaire", "Z2": "N° FINESS établissement", "Z3": "N° de lot",
    "Z4": "N° de facture", "Z5": "N° d'immatriculation assuré", "ST1": "Sous-total 1", "ST2": "Sous-total 2",
    "ST3": "Sous-total 3", "Z8": "Sous-total 1+2+3", "Z12": "Sous-total 4 (honoraires)",
    "Z13": "Montant total", "Z15": "Code CERFA",
}
FIELD_KIND = {"Z1": "cerfa_id", "Z2": "finess", "Z3": "lot", "Z4": "facture", "Z5": "nir",
              "ST1": "amount", "ST2": "amount", "ST3": "amount", "Z8": "amount", "Z12": "amount",
              "Z13": "amount", "Z15": "cerfa_code"}
FIELD_ZONE = {"ST1": "Z6", "ST2": "Z6", "ST3": "Z7"}
COL_KIND = {"prestation": "code", "ghs": "ghs", "montant": "amount", "code": "code", "executant": "executant",
            "date": "date", "quantite": "amount", "honoraires": "amount"}
FAST_COLS = {"date", "quantite"}
SIG_THRESHOLD = 210


def _find_rows(clean_body: np.ndarray, col_ranges: list, min_h: int) -> list:
    """Segmente les lignes de texte d'un corps de tableau par projection horizontale."""
    mask = np.zeros_like(clean_body, dtype=np.uint8)
    for a, b in col_ranges:
        mask[:, max(0, a + 2):max(0, b - 2)] = 1
    ink = ((clean_body < 150) & (mask > 0)).sum(1)
    rows, start = [], None
    for y, v in enumerate(ink):
        if v > 0 and start is None:
            start = y
        elif v == 0 and start is not None:
            rows.append([start, y]); start = None
    if start is not None:
        rows.append([start, len(ink)])
    merged = []
    for r in rows:
        if merged and r[0] - merged[-1][1] <= 1 and (r[1] - merged[-1][0]) < min_h * 2.2:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [r for r in merged if r[1] - r[0] >= max(4, min_h // 2)]


def _table_structure(body: np.ndarray, col_ranges: list, rows: list, char_h: int) -> dict:
    """Contrôles structurels d'un tableau : lignes détectées, hauteurs anormales (deux prestations
    possiblement fusionnées) et encre hors des lignes retenues (ligne possiblement ignorée)."""
    hs = [r[1] - r[0] for r in rows]
    med = float(np.median(hs)) if hs else 0.0
    suspicious = [i for i, h in enumerate(hs) if med and h > 1.8 * med]
    mask = np.zeros(body.shape[0], dtype=bool)
    for a, b in rows:
        mask[max(0, a - 2):b + 2] = True
    colmask = np.zeros_like(body, dtype=bool)
    for a, b in col_ranges:
        colmask[:, max(0, a + 2):max(0, b - 2)] = True
    ink_rows = ((body < 150) & colmask).sum(1)
    stray = int(((ink_rows > 3) & ~mask).sum())
    return {"lignes_detectees": len(rows), "hauteur_mediane_px": round(med, 1),
            "lignes_hautes": suspicious, "encre_hors_lignes_px": stray,
            "fiable": not suspicious and stray < max(3, char_h // 2)}


def _method(res) -> str:
    engines = sorted({r["engine"] for r in res.get("readings", [])})
    return f"lecture multiple ({res.get('n_readings', 0)} lectures : {', '.join(engines)})" if engines else \
        "aucune encre détectée"


def extract_bordereau(path: Path | str) -> dict:
    path = Path(path)
    data = path.read_bytes()
    arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        raise ValueError(f"Image illisible : {path.name}")
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    q = quality(gray)
    reg = identify_and_register(gray)
    if reg.get("rotation") == 180:
        gray = cv2.rotate(gray, cv2.ROTATE_180)
    # redressement d'un scan légèrement incliné, puis nouveau recalage sur l'image redressée
    skew = estimate_skew(gray)
    reg["deskew_deg"] = 0.0
    reg["skew_estimated_deg"] = skew
    if abs(skew) >= SKEW_MIN_DEG:
        gray = deskew(gray, skew)
        rot = reg.get("rotation", 0)
        reg = identify_and_register(gray)
        if reg.get("rotation") == 180:            # ne devrait pas arriver après le premier retournement
            gray = cv2.rotate(gray, cv2.ROTATE_180)
        reg["rotation"] = rot
        reg["deskew_deg"] = skew
        reg["skew_estimated_deg"] = skew
    clean = clean_page(gray)
    unit = W / 1190.0
    out = {
        "file": path.name, "sha256": hashlib.sha256(data).hexdigest(), "size": [W, H],
        "quality": q, "layout": dict(reg),
        "extractor_version": EXTRACTOR_VERSION, "engine_version": ENGINE_VERSION,
        "ocr_engines": {"tesseract": getattr(_optional_tesseract(), "version", None), "rapidocr": "rapidocr_onnxruntime (PP-OCRv3)"},
        "processed_at": dt.datetime.now().isoformat(timespec="seconds"),
        "fields": {}, "tables": {"Z6": [], "Z7": [], "Z10": []}, "signatures": {"Z11": [], "Z14": []},
        "executants": [], "warnings": [],
    }
    if not reg.get("family"):
        out["warnings"].append("Mise en page non reconnue : extraction impossible.")
        return out
    if not reg.get("reliable"):
        out["warnings"].append("Mise en page reconnue avec une faible certitude : extraction à vérifier.")
    tpl = TEMPLATES[reg["family"]]
    residuals = anchor_residuals(gray, reg, tpl)
    out["layout"]["anchor_residuals"] = residuals
    found = [abs(r) for k in ("h", "v") for _, r in residuals[k] if r is not None]
    out["layout"]["residual_max_px"] = max(found) if found else None
    out["layout"]["anchors_missing"] = sum(1 for k in ("h", "v") for _, r in residuals[k] if r is None)

    # ---------------- champs simples
    pad = int(round(4 * unit))
    for fid, f in tpl["fields"].items():
        box = map_box(f["box"], reg)
        box = (box[0], box[1] - pad, box[2], box[3] + pad)
        res = multi_read(gray, clean, box, FIELD_KIND[fid], unit, mode="center")
        zone = FIELD_ZONE.get(fid, fid)
        out["fields"][fid] = {
            "field": fid, "business": FIELD_BUSINESS[fid], "zone": zone, "zone_label": ZONE_LABELS.get(zone, ""),
            "box": list(box), "box_norm": norm_box(box, W, H), "source": path.name, "method": _method(res),
            "geometrie": box_geometry(f["box"], residuals, unit),
            **res,
        }

    # ---------------- tableaux
    char_h = int(round(10 * unit))
    for tid, tb in tpl["tables"].items():
        bx0, by0, bx1, by1 = map_box(tb["body"], reg)
        cols = {c: (int(round(a * reg["sx"])) + reg["dx"], int(round(b * reg["sx"])) + reg["dx"])
                for c, (a, b) in tb["cols"].items()}
        rel = [(a - bx0, b - bx0) for (a, b) in cols.values()]
        rows = _find_rows(clean[by0:by1, bx0:bx1], rel, char_h)
        out.setdefault("table_checks", {})[tb["zone"] + ":" + tid] = {
            "geometrie": box_geometry(tb["body"], residuals, unit),
            **_table_structure(clean[by0:by1, bx0:bx1], rel, rows, char_h)}
        for (ry0, ry1) in rows:
            y0, y1 = by0 + ry0 - 2, by0 + ry1 + 2
            cells = {}
            for c, (a, b) in cols.items():
                res = multi_read(gray, clean, (a, y0, b, y1), COL_KIND[c], unit, mode="all",
                                 fast=c in FAST_COLS)
                cells[c] = {"box": [a, y0, b, y1], "box_norm": norm_box((a, y0, b, y1), W, H),
                            "method": _method(res), **res}
            row = {"table": tid, "zone": tb["zone"], "row": len(out["tables"][tb["zone"]]),
                   "box": [bx0, y0, bx1, y1], "box_norm": norm_box((bx0, y0, bx1, y1), W, H), "cells": cells}
            _classify_row(row)
            out["tables"][tb["zone"]].append(row)

    # ---------------- signatures
    margin = int(round(tpl.get("signature_number_margin", 12) * unit))
    for i, b in enumerate(tpl["signature_boxes"]["Z11"], start=1):
        out["signatures"]["Z11"].append(_signature(gray, clean, map_box(b, reg), W, H, unit, margin, case=i))
    for b in tpl["signature_boxes"]["Z14"]:
        out["signatures"]["Z14"].append(_signature(gray, clean, map_box(b, reg), W, H, unit, 0, case=None))

    # ---------------- zone 9 : exécutants (colonne « n° d'identification de l'exécutant » de Z10)
    out["executants"] = collect_executants(out["tables"]["Z10"])
    return out


RELIABLE = ("concordant", "majoritaire", "corrigé")


def collect_executants(rows) -> list:
    """Zone 9 : numéros d'exécutants distincts des lignes d'acte.
    Une lecture incertaine dont l'un des candidats est un numéro lu de façon fiable sur une autre ligne
    est rattachée à ce numéro (cohérence entre lignes) ; sinon elle est gardée et marquée incertaine."""
    sure = {r["cells"]["executant"]["value"] for r in rows if r.get("kind") == "acte"
            and r["cells"].get("executant", {}).get("value")
            and r["cells"]["executant"].get("agreement") in ("concordant", "corrigé")}
    execs = []
    for r in rows:
        c = r["cells"].get("executant", {})
        v = c.get("value")
        if not v or r.get("kind") != "acte":
            continue
        reliable = c.get("agreement") in RELIABLE
        note = None
        if c.get("agreement") not in ("concordant", "corrigé") and v not in sure:
            alt = next((x["value"] for x in c.get("candidates", []) if x["value"] in sure), None)
            if alt:
                v, reliable, note = alt, True, "lecture incertaine rattachée au numéro lu sur une autre ligne"
        if v in [e["value"] for e in execs]:
            continue
        execs.append({"value": v, "agreement": c.get("agreement"), "reliable": reliable, "note": note,
                      "box": c.get("box"), "box_norm": c.get("box_norm"), "row": r["row"]})
    # Un numéro vu sur une seule ligne et qui ne diffère que d'un chiffre d'un numéro lu sur plusieurs
    # autres lignes est probablement une erreur de lecture : il reste listé mais marqué non fiable.
    from collections import Counter
    counts = Counter(r["cells"]["executant"]["value"] for r in rows if r.get("kind") == "acte"
                     and r["cells"].get("executant", {}).get("value"))
    for e in execs:
        if counts[e["value"]] == 1:
            near = [v for v, n in counts.items() if n >= 2 and len(v) == len(e["value"])
                    and sum(a != b for a, b in zip(v, e["value"])) == 1]
            if near:
                e["reliable"] = False
                e["note"] = f"lu une seule fois, à un chiffre près de {near[0]} (lu {counts[near[0]]} fois) : lecture à vérifier"
    return execs


def _classify_row(row):
    c = row["cells"]
    if row["zone"] in ("Z6", "Z7"):
        row["kind"] = "prestation" if c.get("prestation", {}).get("value") else "autre"
        row["has_amount"] = c.get("montant", {}).get("value") is not None
    else:
        has_hon = c.get("honoraires", {}).get("value") is not None
        has_date = bool(c.get("date", {}).get("value"))
        has_exec = bool(c.get("executant", {}).get("value"))
        # Ligne sans exécutant, date ni honoraires (ex. codes de biologie sous un acte B) :
        # ligne de détail rattachée à l'acte précédent, pas un acte facturé distinct.
        row["kind"] = "acte" if (has_hon or has_date or has_exec) else "detail"
        row["code_len"] = len(c.get("code", {}).get("value") or "")


def _signature(gray, clean, box, W, H, unit, margin, case):
    """Détection de PRÉSENCE (jamais d'authenticité) d'un élément dans une zone de signature."""
    x0, y0, x1, y1 = box
    g = int(round(4 * unit))
    # image brute (sans effacement des traits) : les tracés manuscrits ne doivent pas être supprimés ;
    # la marge intérieure exclut le cadre de la case.
    crop = gray[y0 + g:y1 - g, x0 + g:x1 - g].copy()
    if crop.size == 0:
        return {"case": case, "status": "INDETERMINE", "box": list(box), "box_norm": norm_box(box, W, H)}
    if margin:
        crop[:margin, :margin] = 255           # numéro imprimé de la case (1..8)
    # seuil élevé : les signatures manuscrites numérisées sont souvent des traits fins gris clair
    b = (crop < SIG_THRESHOLD).astype(np.uint8)
    ink = float(b.mean())
    n, lab, st, _ = cv2.connectedComponentsWithStats(b)
    comps = [s for s in st[1:] if s[4] >= 4]
    big = [s for s in comps if s[2] > 0.12 * crop.shape[1] or s[3] > 0.35 * crop.shape[0]]
    if ink < 0.003 or len(comps) < 2:
        status = "VIDE"
    elif ink >= 0.008 and len(comps) >= 4:
        status = "PRESENT"
    else:
        status = "INDETERMINE"
    text, conf = "", None
    if status != "VIDE":
        raw = gray[y0 + g:y1 - g, x0 + g:x1 - g]
        f = 2.0 / unit
        img = cv2.copyMakeBorder(cv2.resize(raw, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC),
                                 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
        r = get_engine("rapidocr").read(img)
        text, conf = r.text, r.conf
    numbers = re.findall(r"(?<!\d)\d{9}(?!\d)", text.replace(" ", ""))
    return {
        "case": case, "box": list(box), "box_norm": norm_box(box, W, H), "ink_ratio": round(ink, 4),
        "components": len(comps), "large_strokes": len(big), "status": status,
        "nature": ("tracé ou cachet graphique probable" if big else "mention imprimée seulement")
        if status != "VIDE" else "",
        "text": text, "conf": conf, "numbers": numbers,
    }
