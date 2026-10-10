"""Qualité d'image, orientation, identification de la mise en page et recalage géométrique."""
from __future__ import annotations

import cv2
import numpy as np

from pathlib import Path

from .templates import TEMPLATES

REF_DIR = Path(__file__).parent / "refs"
MASK_SIZE = (200, 283)   # (largeur, hauteur) de la carte de traits réduite


def paper_normalized(gray: np.ndarray) -> np.ndarray:
    """Ramène le fond du papier au blanc (scan assombri). Sans effet si le fond est déjà blanc (cas du corpus)."""
    p = float(np.percentile(gray, 90))
    if p >= 250 or p <= 0:
        return gray
    return np.clip(gray.astype(np.float32) * (255.0 / p), 0, 255).astype(np.uint8)


def line_mask_small(gray: np.ndarray) -> np.ndarray:
    b = (paper_normalized(gray) < 150).astype(np.uint8) * 255
    h, w = b.shape
    hk = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, w // 15), 1)))
    vk = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, h // 30))))
    m = cv2.bitwise_or(hk, vk)
    m = cv2.dilate(m, np.ones((5, 5), np.uint8))
    return cv2.resize(m, MASK_SIZE, interpolation=cv2.INTER_AREA).astype(np.float32)


_ref_cache: dict = {}


def _content(mask: np.ndarray) -> np.ndarray:
    """Carte de traits recadrée sur son contenu puis remise à la taille standard (marges neutralisées)."""
    ys, xs = np.nonzero(mask > 0.25 * mask.max()) if mask.max() > 0 else ([], [])
    if len(ys) < 2 or len(xs) < 2:
        return mask
    c = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return cv2.resize(c, MASK_SIZE, interpolation=cv2.INTER_AREA)


def layout_similarity(gray: np.ndarray) -> dict:
    """Similarité (corrélation normalisée, tolérance de translation) entre la carte des traits de
    l'image et la carte de référence de chaque mise en page. Les deux cartes sont recadrées sur leur contenu :
    une marge ajoutée ou un recadrage ne fait pas reconnaître une autre mise en page."""
    m = _content(line_mask_small(gray))
    pad = 8
    mp = cv2.copyMakeBorder(m, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    out = {}
    for fam in TEMPLATES:
        if fam not in _ref_cache:
            p = REF_DIR / f"{fam}.png"
            # np.fromfile + imdecode : fonctionne aussi avec des chemins accentués sous Windows
            _ref_cache[fam] = (_content(cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32))
                               if p.exists() else None)
        ref = _ref_cache[fam]
        if ref is None:
            continue
        r = cv2.matchTemplate(mp, ref, cv2.TM_CCOEFF_NORMED)
        out[fam] = round(float(r.max()), 3)
    return out


def ink_threshold(gray: np.ndarray) -> int:
    """Seuil d'encre adaptatif (Otsu), borné : une image claire ou délavée garde ses traits."""
    otsu, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return int(min(200, max(150, otsu - 10)))


def line_profiles(gray: np.ndarray):
    b = (gray < ink_threshold(gray)).astype(np.uint8)
    h, w = b.shape
    hk = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, w // 15), 1)))
    vk = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, h // 30))))
    return hk.sum(1).astype(float), vk.sum(0).astype(float)


def quality(gray: np.ndarray) -> dict:
    lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean = float(gray.mean())
    dark = float((gray < 128).mean())
    issues = []
    if lap < 50:
        issues.append("image possiblement floue")
    if mean < 120:
        issues.append("image sombre")
    if dark > 0.35:
        issues.append("densité d'encre anormalement élevée")
    return {"sharpness_laplacian_var": round(lap, 1), "mean_gray": round(mean, 1),
            "dark_ratio": round(dark, 4), "issues": issues, "ok": not issues}


def _anchor_score(hprof, vprof, tpl, sx, sy, dx=0, dy=0, tol=3):
    hits, total = 0, 0
    for y in tpl["anchors_h"]:
        Y = int(round(y * sy)) + dy
        total += 1
        lo, hi = max(0, Y - tol), min(len(hprof), Y + tol + 1)
        if hi > lo and hprof[lo:hi].max() > 0:
            hits += 1
    for x in tpl["anchors_v"]:
        X = int(round(x * sx)) + dx
        total += 1
        lo, hi = max(0, X - tol), min(len(vprof), X + tol + 1)
        if hi > lo and vprof[lo:hi].max() > 0:
            hits += 1
    return hits / total if total else 0.0


def identify_and_register(gray: np.ndarray) -> dict:
    """Retourne la famille de gabarit la plus probable, le décalage (dx, dy) et l'orientation.

    Le score est la proportion de lignes d'ancrage du gabarit retrouvées dans l'image.
    """
    h, w = gray.shape
    best = None
    sims_by_rot = {}
    for rot in (0, 180):
        g = gray if rot == 0 else cv2.rotate(gray, cv2.ROTATE_180)
        sims_by_rot[rot] = layout_similarity(g)
    rot_best, fam_best, sim_best = 0, None, -1.0
    for rot, sims in sims_by_rot.items():
        for fam, v in sims.items():
            if v > sim_best:
                rot_best, fam_best, sim_best = rot, fam, v
    for rot in (rot_best,):
        g = gray if rot == 0 else cv2.rotate(gray, cv2.ROTATE_180)
        hp, vp = line_profiles(g)
        for fam, tpl in TEMPLATES.items():
            if fam_best and fam != fam_best:
                continue
            rw, rh = tpl["ref_size"]
            sx, sy = w / rw, h / rh
            if abs(sx - sy) / max(sx, sy) > 0.12:      # rapport d'aspect incompatible
                continue
            # recherche de translation (pas grossier puis fin)
            cand = (-1, 0, 0)
            for dy in range(-30, 31, 3):
                for dx in range(-30, 31, 3):
                    s = _anchor_score(hp, vp, tpl, sx, sy, dx, dy)
                    if s > cand[0]:
                        cand = (s, dx, dy)
            s0, dx0, dy0 = cand
            for dy in range(dy0 - 2, dy0 + 3):
                for dx in range(dx0 - 2, dx0 + 3):
                    s = _anchor_score(hp, vp, tpl, sx, sy, dx, dy, tol=1)
                    if s > cand[0] or (s == cand[0] and abs(dx) + abs(dy) < abs(cand[1]) + abs(cand[2])):
                        cand = (s, dx, dy)
            dxr, dyr = _refine(hp, vp, tpl, sx, sy, cand[1], cand[2])
            # Marges ajoutées, recadrage ou redimensionnement : l'échelle tirée de la taille de l'image peut être
            # fausse. On ajuste échelle et décalage sur chaque axe à partir des traits du formulaire ; l'ajustement
            # n'est retenu que s'il retrouve nettement plus de traits d'ancrage que l'échelle « taille d'image ».
            fit_y = _fit_axis(hp, tpl["anchors_h"], sy)
            fit_x = _fit_axis(vp, tpl["anchors_v"], sx)
            if fit_x and fit_y:
                s_fit = _anchor_score(hp, vp, tpl, fit_x[0], fit_y[0], fit_x[1], fit_y[1], tol=2)
                s_cur = _anchor_score(hp, vp, tpl, sx, sy, dxr, dyr, tol=2)
                if s_fit >= s_cur + 0.15:
                    sx, sy = fit_x[0], fit_y[0]
                    dxr, dyr = _refine(hp, vp, tpl, sx, sy, fit_x[1], fit_y[1])
                    cand = (_anchor_score(hp, vp, tpl, sx, sy, dxr, dyr), dxr, dyr)
            if best is None or cand[0] > best["score"]:
                best = {"family": fam, "score": round(cand[0], 3), "dx": dxr, "dy": dyr,
                        "sx": sx, "sy": sy, "rotation": rot}
    if best is None:
        return {"family": None, "score": 0.0, "dx": 0, "dy": 0, "sx": 1, "sy": 1, "rotation": 0}
    best["label"] = TEMPLATES[best["family"]]["label"]
    best["similarities"] = sims_by_rot.get(best["rotation"], {})
    best["layout_similarity"] = sim_best
    others = [v for f, v in best["similarities"].items() if f != best["family"]]
    # écart avec la 2ᵉ mise en page la plus proche (corpus : ≥ 0,19) ; un écart faible = identification fragile
    best["family_margin"] = round(sim_best - max(others), 3) if others else None
    best["reliable"] = (best["score"] >= 0.8 and sim_best >= 0.6
                        and (best["family_margin"] is None or best["family_margin"] >= 0.05))
    return best


def _fit_axis(prof, anchors, s0, span=0.2):
    """Meilleure échelle et meilleur décalage d'un axe : nombre maximal de traits d'ancrage tombant sur un trait
    réel (tolérance 2 px), pour des échelles de s0 × (1 ± span)."""
    if len(anchors) < 4:
        return None
    near = np.convolve((prof > 0).astype(np.int32), np.ones(5, dtype=np.int32), mode="same") > 0
    A = np.array(anchors, dtype=float)
    S = s0 * np.arange(1 - span, 1 + span + 1e-9, 0.004)
    D = np.arange(-80, 81)
    pos = np.rint(S[:, None, None] * A[None, None, :]).astype(int) + D[None, :, None]
    valid = (pos >= 0) & (pos < len(near))
    hits = (near[np.clip(pos, 0, len(near) - 1)] & valid).sum(-1)
    i, j = np.unravel_index(np.argmax(hits), hits.shape)
    return float(S[i]), int(D[j]), int(hits[i, j])


def _refine(hprof, vprof, tpl, sx, sy, dx0, dy0, win=6):
    """Affine la translation : pour chaque ligne d'ancrage, position du trait réel le plus proche
    (centre du pic du profil), puis médiane des écarts. Évite le biais d'un départage par score."""
    def offsets(prof, anchors, scale, d0):
        out = []
        for a in anchors:
            c = int(round(a * scale)) + d0
            lo, hi = max(0, c - win), min(len(prof), c + win + 1)
            if hi <= lo:
                continue
            seg = prof[lo:hi]
            if seg.max() <= 0:
                continue
            idx = np.where(seg >= 0.6 * seg.max())[0]
            pos = lo + (idx.min() + idx.max()) / 2.0
            out.append(pos - a * scale)
        return out
    oy = offsets(hprof, tpl["anchors_h"], sy, dy0)
    ox = offsets(vprof, tpl["anchors_v"], sx, dx0)
    dy = int(round(float(np.median(oy)))) if len(oy) >= 3 else dy0
    dx = int(round(float(np.median(ox)))) if len(ox) >= 3 else dx0
    return dx, dy


# --------------------------------------------------------------------------------------------- redressement
def estimate_skew(gray: np.ndarray, max_deg: float = 6.0) -> float:
    """Angle d'inclinaison (degrés, sens trigonométrique) d'un scan légèrement penché.

    Méthode du profil de projection : l'image binarisée (réduite) est tournée de -max_deg à +max_deg ;
    l'angle retenu est celui pour lequel les lignes de texte et les traits du formulaire sont les plus
    horizontaux (variance maximale de la projection horizontale). Ne dépend d'aucun contenu attendu."""
    h, w = gray.shape
    k = 700.0 / max(w, h)
    small = cv2.resize(gray, (max(1, int(w * k)), max(1, int(h * k))), interpolation=cv2.INTER_AREA)
    b = (small < 160).astype(np.float32)
    sh, sw = b.shape
    c = (sw / 2, sh / 2)

    def sharp(a):
        M = cv2.getRotationMatrix2D(c, a, 1.0)
        r = cv2.warpAffine(b, M, (sw, sh), flags=cv2.INTER_NEAREST, borderValue=0)
        prof = r.sum(1)
        return float((prof ** 2).sum())
    coarse = np.arange(-max_deg, max_deg + 1e-6, 0.5)
    a0 = max(coarse, key=sharp)
    fine = np.arange(a0 - 0.5, a0 + 0.5 + 1e-6, 0.1)
    return round(float(max(fine, key=sharp)), 2)


def deskew(gray: np.ndarray, angle: float) -> np.ndarray:
    """Redresse l'image de l'angle donné (même taille, fond blanc)."""
    h, w = gray.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)


SKEW_MIN_DEG = 0.3      # en dessous : aucun redressement (les scans du corpus sont droits)


def normalized_image(img: np.ndarray, layout: dict) -> np.ndarray:
    """Image dans le repère où les zones sont exprimées : retournée à 180° puis redressée si nécessaire.
    Sert à l'affichage, aux rapports et au diagnostic (les coordonnées des zones s'y appliquent)."""
    if layout.get("rotation") == 180:
        img = cv2.rotate(img, cv2.ROTATE_180)
    a = layout.get("deskew_deg") or 0
    if a:
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0)
        border = 255 if img.ndim == 2 else (255, 255, 255)
        img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=border)
    return img


# --------------------------------------------------------------------------------------------- fiabilité locale
def anchor_residuals(gray: np.ndarray, reg: dict, tpl: dict, win: int = 8) -> dict:
    """Écart (pixels) entre chaque trait d'ancrage attendu après recalage et le trait réellement présent.
    None = trait non retrouvé dans la fenêtre de recherche."""
    hp, vp = line_profiles(gray)

    def res(prof, anchors, scale, d0):
        out = []
        for a in anchors:
            c = int(round(a * scale)) + d0
            lo, hi = max(0, c - win), min(len(prof), c + win + 1)
            seg = prof[lo:hi] if hi > lo else np.array([])
            if not seg.size or seg.max() <= 0:
                out.append((a, None)); continue
            # traits présents dans la fenêtre (suites de colonnes non nulles) : le plus proche de l'attendu
            on = seg > 0.25 * seg.max()
            runs, st = [], None
            for i, v in enumerate(on):
                if v and st is None:
                    st = i
                if not v and st is not None:
                    runs.append((st, i - 1)); st = None
            if st is not None:
                runs.append((st, len(on) - 1))
            centers = [lo + (r0 + r1) / 2.0 for r0, r1 in runs]
            pos = min(centers, key=lambda x: abs(x - c))
            out.append((a, round(float(pos - c), 1)))
        return out
    return {"h": res(hp, tpl["anchors_h"], reg["sy"], reg["dy"]), "v": res(vp, tpl["anchors_v"], reg["sx"], reg["dx"])}


def box_geometry(box_tpl, residuals: dict, unit: float, tol_px: float = 4.0) -> dict:
    """Fiabilité géométrique locale d'une région : écarts des traits d'ancrage les plus proches
    (deux horizontaux, deux verticaux). Un bon score global ne suffit pas : la région est déclarée « à vérifier »
    si l'écart médian de ses traits voisins dépasse le seuil, ou si moins de trois d'entre eux sont retrouvés
    à leur place (un trait isolé mal détecté ne suffit pas à condamner la région)."""
    x0, y0, x1, y1 = box_tpl
    cy, cx = (y0 + y1) / 2, (x0 + x1) / 2

    def nearest(items, c, k=2):
        return sorted(items, key=lambda t: abs(t[0] - c))[:k]
    near = nearest(residuals["h"], cy) + nearest(residuals["v"], cx)
    limit = tol_px * unit
    vals = [abs(r) for a, r in near if r is not None]
    good = [v for v in vals if v <= limit]
    med = float(np.median(vals)) if vals else None
    ok = med is not None and med <= limit and len(good) >= 3
    return {"residu_px": round(med, 1) if med is not None else None, "residu_max_px": max(vals) if vals else None,
            "seuil_px": round(limit, 1), "traits_voisins": len(near), "traits_retrouves": len(good),
            "traits_introuvables": sum(1 for a, r in near if r is None), "fiable": ok}


def map_box(box, reg) -> tuple:
    """Convertit une boîte du gabarit (pixels de référence) en pixels de l'image recalée."""
    x0, y0, x1, y1 = box
    sx, sy, dx, dy = reg["sx"], reg["sy"], reg["dx"], reg["dy"]
    return (int(round(x0 * sx)) + dx, int(round(y0 * sy)) + dy, int(round(x1 * sx)) + dx, int(round(y1 * sy)) + dy)


def norm_box(box, w, h) -> list:
    x0, y0, x1, y1 = box
    return [round(x0 / w, 5), round(y0 / h, 5), round(x1 / w, 5), round(y1 / h, 5)]
