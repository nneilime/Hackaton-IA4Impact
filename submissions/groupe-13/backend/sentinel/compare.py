"""Module A — comparaison IMAGE ↔ IMAGE de deux bordereaux du corpus.

1. vérification préalable : mise en page compatible ? mêmes identifiants (FINESS, facture, assuré) ?
   → « même dossier » ou « documents non homologues — comparaison exploratoire » ;
2. alignement géométrique (translation estimée sur les traits du formulaire) ;
3. différence de pixels robuste (flou léger + seuil + filtrage des petites zones : un décalage
   d'impression de quelques pixels n'est pas une différence métier) ;
4. localisation des régions modifiées, rattachement à la zone du formulaire, lecture OCR des deux
   versions de chaque région → valeur ajoutée / supprimée / modifiée ;
5. comparaison sémantique des champs extraits.
Aucune version n'est présumée correcte.
"""
from __future__ import annotations

import cv2
import numpy as np

from .ocr.layout import identify_and_register, map_box
from .ocr.templates import TEMPLATES, ZONE_LABELS


def _load(path):
    arr = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if arr is None:
        raise ValueError(f"Image illisible : {path}")
    return arr


def _zone_of(box, reg) -> str:
    """Zone du gabarit qui recouvre le plus la région (sinon « hors zone contrôlée »)."""
    if not reg.get("family"):
        return "—"
    tpl = TEMPLATES[reg["family"]]
    cands = []
    for fid, f in tpl["fields"].items():
        cands.append((fid if fid.startswith("Z") else {"ST1": "Z6", "ST2": "Z6", "ST3": "Z7"}.get(fid, fid),
                      map_box(f["box"], reg)))
    for tid, t in tpl["tables"].items():
        cands.append((t["zone"], map_box(t["body"], reg)))
    for z, bs in tpl["signature_boxes"].items():
        for b in bs:
            cands.append((z, map_box(b, reg)))
    x0, y0, x1, y1 = box
    best, area = None, 0
    for z, (a0, b0, a1, b1) in cands:
        ix = max(0, min(x1, a1) - max(x0, a0)); iy = max(0, min(y1, b1) - max(y0, b0))
        if ix * iy > area:
            best, area = z, ix * iy
    return best or "hors zone contrôlée"


def compare_images(path_a, path_b, ext_a: dict | None = None, ext_b: dict | None = None, ocr: bool = True) -> dict:
    ga, gb = _load(path_a), _load(path_b)
    ra, rb = identify_and_register(ga), identify_and_register(gb)
    same_layout = ra.get("family") and ra.get("family") == rb.get("family") and ga.shape == gb.shape

    # ---- vérification préalable d'homologie
    ids = {}
    for k, lab in (("Z2", "FINESS"), ("Z4", "N° facture"), ("Z5", "N° assuré")):
        va = ((ext_a or {}).get("fields", {}).get(k) or {}).get("value")
        vb = ((ext_b or {}).get("fields", {}).get(k) or {}).get("value")
        ids[lab] = {"a": va, "b": vb, "egal": (va == vb) if va and vb else None}
    same_case = all(v["egal"] for v in ids.values() if v["egal"] is not None) and any(
        v["egal"] is not None for v in ids.values())
    if not same_layout:
        mode = "Comparaison exploratoire — mises en page différentes"
    elif same_case:
        mode = "Même dossier — comparaison de deux versions"
    else:
        mode = "Documents non homologues — comparaison exploratoire"

    out = {"mode": mode, "homologous": bool(same_layout and same_case), "same_layout": bool(same_layout),
           "identifiers": ids, "layout_a": ra.get("family"), "layout_b": rb.get("family"),
           "regions": [], "field_diffs": [], "size_a": list(ga.shape[::-1]), "size_b": list(gb.shape[::-1]),
           "warning": None if same_case else
           "Les deux images ne concernent pas le même dossier : les différences listées sont descriptives et ne "
           "constituent pas une conclusion de conformité."}
    if not same_layout:
        out["zones"] = []
        out["zones_note"] = ("Mises en page différentes : la différence porte sur le modèle de formulaire lui-même ; "
                             "une comparaison zone par zone n'aurait pas de sens.")
        return out

    # ---- alignement (translation relative)
    dx, dy = rb["dx"] - ra["dx"], rb["dy"] - ra["dy"]
    M = np.float32([[1, 0, -dx], [0, 1, -dy]])
    gb_al = cv2.warpAffine(gb, M, (gb.shape[1], gb.shape[0]), borderValue=255)
    out["alignment"] = {"dx": int(dx), "dy": int(dy), "method": "translation estimée sur les traits du formulaire"}

    # ---- différence robuste
    u = ga.shape[1] / 1190.0
    a_bl = cv2.GaussianBlur(ga, (3, 3), 0)
    b_bl = cv2.GaussianBlur(gb_al, (3, 3), 0)
    d = cv2.absdiff(a_bl, b_bl)
    m = (d > 70).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    m = cv2.dilate(m, np.ones((int(7 * u), int(17 * u)), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    regions = []
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area < 60 * u * u:
            continue
        core = (d[y:y + h, x:x + w] > 70).sum()
        if core < 12 * u:
            continue
        regions.append([int(x), int(y), int(x + w), int(y + h)])
    regions.sort(key=lambda b: (b[1], b[0]))

    rap = None
    if ocr:
        try:
            from .ocr.engine import get_engine
            rap = get_engine("rapidocr")
        except Exception:
            rap = None
    for i, (x0, y0, x1, y1) in enumerate(regions[:60]):
        pad = int(3 * u)
        ca = ga[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
        cb = gb_al[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
        ink_a, ink_b = float((ca < 150).mean()), float((cb < 150).mean())
        ta = tb = None
        if rap is not None:
            ta = rap.read(cv2.copyMakeBorder(ca, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=255)).text if ink_a > 0.003 else ""
            tb = rap.read(cv2.copyMakeBorder(cb, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=255)).text if ink_b > 0.003 else ""
        empty_a = ink_a <= 0.003 or (ta is not None and not ta.strip())
        empty_b = ink_b <= 0.003 or (tb is not None and not tb.strip())
        if empty_a and not empty_b:
            kind = "ajout (présent seulement dans B)"
        elif empty_b and not empty_a:
            kind = "suppression (présent seulement dans A)"
        elif ta is not None and ta.replace(" ", "") == tb.replace(" ", ""):
            kind = "différence visuelle sans changement de texte lu"
        else:
            kind = "modification"
        zone = _zone_of((x0, y0, x1, y1), ra)
        out["regions"].append({"id": i + 1, "box": [x0, y0, x1, y1],
                               "box_norm": [x0 / ga.shape[1], y0 / ga.shape[0], x1 / ga.shape[1], y1 / ga.shape[0]],
                               "zone": zone, "zone_label": ZONE_LABELS.get(zone, zone), "kind": kind,
                               "text_a": ta, "text_b": tb, "ink_a": round(ink_a, 4), "ink_b": round(ink_b, 4)})

    out["zones"] = _zones_compare(ra, ga.shape[::-1], out["regions"], ext_a, ext_b)

    # ---- comparaison sémantique des champs extraits
    if ext_a and ext_b:
        for k, fa in (ext_a.get("fields") or {}).items():
            fb = (ext_b.get("fields") or {}).get(k)
            va, vb = fa.get("value"), (fb or {}).get("value")
            if va != vb:
                out["field_diffs"].append({"field": k, "label": fa.get("business"), "zone": fa.get("zone"),
                                           "a": va, "b": vb, "box_a": fa.get("box_norm"),
                                           "box_b": (fb or {}).get("box_norm"),
                                           "type": "ajouté" if va is None else "supprimé" if vb is None else "modifié"})
        sa = [s["status"] for s in ext_a.get("signatures", {}).get("Z14", [])]
        sb = [s["status"] for s in ext_b.get("signatures", {}).get("Z14", [])]
        if sa != sb:
            out["field_diffs"].append({"field": "Z14", "label": "Signature du directeur", "zone": "Z14",
                                       "a": ", ".join(sa), "b": ", ".join(sb), "type": "modifié"})
        ca = [s["status"] for s in ext_a.get("signatures", {}).get("Z11", [])]
        cb = [s["status"] for s in ext_b.get("signatures", {}).get("Z11", [])]
        for i, (x, y) in enumerate(zip(ca, cb), start=1):
            if x != y:
                out["field_diffs"].append({"field": f"Z11.{i}", "label": f"Signature praticien — case {i}",
                                           "zone": "Z11", "a": x, "b": y, "type": "modifié"})
    return out


def diff_overlay(path_a, path_b, mode: str = "diff") -> bytes:
    """Image PNG : « diff » (A en gris, différences en couleur), « overlay » (superposition 50 %)."""
    ga, gb = _load(path_a), _load(path_b)
    if ga.shape != gb.shape:
        gb = cv2.resize(gb, (ga.shape[1], ga.shape[0]))
    ra, rb = identify_and_register(ga), identify_and_register(gb)
    dx, dy = rb["dx"] - ra["dx"], rb["dy"] - ra["dy"]
    gb = cv2.warpAffine(gb, np.float32([[1, 0, -dx], [0, 1, -dy]]), (gb.shape[1], gb.shape[0]), borderValue=255)
    if mode == "overlay":
        img = cv2.merge([gb, ga, np.minimum(ga, gb)])     # A en vert/rouge, B en bleu
    else:
        base = cv2.cvtColor((ga * 0.35 + 165).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        d = cv2.absdiff(cv2.GaussianBlur(ga, (3, 3), 0), cv2.GaussianBlur(gb, (3, 3), 0)) > 70
        only_a = d & (ga < gb)
        only_b = d & (gb < ga)
        base[only_a] = (40, 40, 220)    # encre présente dans A (rouge)
        base[only_b] = (200, 120, 20)   # encre présente dans B (bleu)
        img = base
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes()


FIELD_OF_ZONE = {"Z1": "Z1", "Z2": "Z2", "Z3": "Z3", "Z4": "Z4", "Z5": "Z5", "Z8": "Z8", "Z12": "Z12", "Z13": "Z13", "Z15": "Z15"}


def _zones_compare(reg, size, regions, ext_a, ext_b) -> list:
    """Comparaison zone par zone (Z1 à Z15) : régions de différence situées dans la zone, valeurs lues dans A
    et dans B, nature de la différence (documentaire ou purement graphique)."""
    from .zones import ZONE_IDS, ZONE_INFO, zone_geometry
    geo = zone_geometry(reg.get("family"), reg, list(size))
    out = []
    for z in ZONE_IDS:
        rs = geo.get(z, [])
        hits = []
        for r in regions:
            x0, y0, x1, y1 = r["box"]
            for g in rs:
                a0, b0, a1, b1 = g["box"]
                if min(x1, a1) > max(x0, a0) and min(y1, b1) > max(y0, b0):
                    hits.append(r["id"]); break
        kinds = {r["kind"] for r in regions if r["id"] in hits}
        f = FIELD_OF_ZONE.get(z)
        va = (((ext_a or {}).get("fields") or {}).get(f) or {}).get("value") if f else None
        vb = (((ext_b or {}).get("fields") or {}).get(f) or {}).get("value") if f else None
        if not hits and (va == vb):
            nature = "identique"
        elif hits and kinds <= {"différence visuelle sans changement de texte lu"} and va == vb:
            nature = "différence purement graphique"
        else:
            nature = "différence documentaire"
        bb = None
        if rs:
            bb = [min(g["box"][0] for g in rs), min(g["box"][1] for g in rs), max(g["box"][2] for g in rs), max(g["box"][3] for g in rs)]
        out.append({"zone_id": z, "label": ZONE_INFO[z]["label"], "regions": hits, "nature": nature, "bbox": bb,
                    "valeur_a": va, "valeur_b": vb})
    return out
