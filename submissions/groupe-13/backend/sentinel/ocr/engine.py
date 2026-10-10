"""Moteurs OCR locaux (aucun appel réseau).

- Tesseract 5 (moteur principal) via pytesseract ;
- RapidOCR / ONNX (second lecteur facultatif, modèles embarqués dans le paquet pip).

Les scores de confiance renvoyés sont ceux fournis par les moteurs (jamais inventés).
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

WHITELISTS = {
    "digits": "0123456789",
    "amount": "0123456789,.",
    "nir": "0123456789",
    "code": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "date": "0123456789/",
    "cerfa_code": "S0123456789",
}


@dataclass
class OcrResult:
    text: str
    conf: Optional[float]           # 0..1, moyenne des confiances mots fournies par le moteur
    words: list = field(default_factory=list)
    engine: str = ""
    params: str = ""


def _find_tesseract() -> Optional[str]:
    env = os.environ.get("TESSERACT_CMD")
    if env and os.path.exists(env):
        return env
    p = shutil.which("tesseract")
    if p:
        return p
    for cand in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                 r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
        if os.path.exists(cand):
            return cand
    return None


class TesseractEngine:
    name = "tesseract"

    def __init__(self):
        import pytesseract
        self.pt = pytesseract
        cmd = _find_tesseract()
        if not cmd:
            raise RuntimeError("Tesseract introuvable (installer Tesseract-OCR ou définir TESSERACT_CMD)")
        pytesseract.pytesseract.tesseract_cmd = cmd
        self.version = str(pytesseract.get_tesseract_version())

    def read(self, img: np.ndarray, kind: str = "text", psm: int = 7) -> OcrResult:
        cfg = f"--oem 1 --psm {psm}"
        wl = WHITELISTS.get(kind)
        if wl:
            cfg += f" -c tessedit_char_whitelist={wl}"
        d = self.pt.image_to_data(img, lang="eng", config=cfg, output_type=self.pt.Output.DICT)
        words, confs = [], []
        for i, t in enumerate(d["text"]):
            t = (t or "").strip()
            if not t:
                continue
            c = float(d["conf"][i])
            words.append({"text": t, "conf": round(c / 100, 3), "left": int(d["left"][i]), "top": int(d["top"][i]),
                          "width": int(d["width"][i]), "height": int(d["height"][i]), "line": int(d["line_num"][i]),
                          "block": int(d["block_num"][i])})
            if c >= 0:
                confs.append(c)
        # reconstruit les lignes (psm 6) en respectant l'ordre du moteur
        lines, cur, key = [], [], None
        for w in words:
            k = (w["block"], w["line"])
            if key is not None and k != key:
                lines.append(" ".join(cur)); cur = []
            cur.append(w["text"]); key = k
        if cur:
            lines.append(" ".join(cur))
        text = "\n".join(lines)
        conf = round(sum(confs) / len(confs) / 100, 3) if confs else None
        return OcrResult(text, conf, words, f"tesseract {self.version}", cfg)


class RapidEngine:
    name = "rapidocr"

    def recognize(self, img: np.ndarray):
        """Reconnaissance seule (sans détection) d'une image d'une ligne de texte."""
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        res, _ = self.eng.text_recognizer([img])
        if not res:
            return "", None
        t, sc = res[0]
        return t, round(float(sc), 3)

    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR  # modèles ONNX embarqués
        self.eng = RapidOCR()
        self.version = "rapidocr_onnxruntime"

    def read(self, img: np.ndarray, kind: str = "text", psm: int = 7) -> OcrResult:
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        res, _ = self.eng(img)
        res = res or []
        res = sorted(res, key=lambda r: (r[0][0][1], r[0][0][0]))
        words = []
        for r in res:
            xs = [p[0] for p in r[0]]
            ys = [p[1] for p in r[0]]
            words.append({"text": r[1], "conf": round(float(r[2]), 3), "left": int(min(xs)), "top": int(min(ys)),
                          "right": int(max(xs)), "bottom": int(max(ys)), "cy": float(sum(ys) / 4)})
        text = "\n".join(r[1] for r in res)
        conf = round(sum(float(r[2]) for r in res) / len(res), 3) if res else None
        return OcrResult(text, conf, words, "rapidocr (PP-OCRv3 onnx)", "")


_engines: dict = {}


def get_engine(name: str = "tesseract"):
    if name not in _engines:
        _engines[name] = TesseractEngine() if name == "tesseract" else RapidEngine()
    return _engines[name]


def available_engines() -> dict:
    out = {}
    try:
        out["tesseract"] = get_engine("tesseract").version
    except Exception as e:  # noqa
        out["tesseract"] = None
    try:
        import importlib.util
        out["rapidocr"] = "installé" if importlib.util.find_spec("rapidocr_onnxruntime") else None
    except Exception:
        out["rapidocr"] = None
    return out


# ------------------------------------------------------------------ prétraitement
def remove_rules(gray: np.ndarray, min_frac: float = 0.5) -> np.ndarray:
    """Efface les traits de formulaire (horizontaux/verticaux) d'un crop en niveaux de gris."""
    h, w = gray.shape
    inv = (gray < 170).astype(np.uint8) * 255
    out = gray.copy()
    if w > 20:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, int(w * min_frac)), 1))
        hl = cv2.morphologyEx(inv, cv2.MORPH_OPEN, k)
        out[cv2.dilate(hl, np.ones((3, 1), np.uint8)) > 0] = 255
    if h > 20:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, int(h * 0.8))))
        vl = cv2.morphologyEx(inv, cv2.MORPH_OPEN, k)
        out[cv2.dilate(vl, np.ones((1, 3), np.uint8)) > 0] = 255
    return out


def clean_page(gray: np.ndarray) -> np.ndarray:
    """Efface les traits du formulaire sur toute la page puis reconstruit les pixels masqués par
    inpainting (les caractères traversés par un trait sont ainsi préservés au mieux).
    Un trait est « long » s'il dépasse nettement la taille d'un caractère."""
    h, w = gray.shape
    u = w / 1190.0
    inv = (gray < 200).astype(np.uint8) * 255
    hl = cv2.morphologyEx(inv, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (int(45 * u), 1)))
    vl = cv2.morphologyEx(inv, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, int(18 * u))))
    mask = cv2.bitwise_or(hl, vl)
    return cv2.inpaint(gray, mask, 2, cv2.INPAINT_TELEA)


def tight_text(crop: np.ndarray, thr: int = 160, pick: str = "center") -> np.ndarray | None:
    """Isole la ligne de texte principale d'un crop déjà nettoyé (None si vide)."""
    b = text_band(crop, thr, pick)
    if b is None:
        return None
    y0, y1, x0, x1 = b
    return crop[y0:y1, x0:x1]


def text_band(crop: np.ndarray, thr: int = 160, pick: str = "center"):
    """Coordonnées (y0, y1, x0, x1) de la ligne de texte principale d'un crop nettoyé."""
    b = (crop < thr).astype(np.uint8)
    if b.sum() < 4:
        return None
    # ignore les bords verticaux de case (traits fins collés au bord gauche/droit du crop)
    n, lab, st, _ = cv2.connectedComponentsWithStats(b)
    H, W = b.shape
    for i in range(1, n):
        x, y, cw, chh, area = st[i]
        if cw <= 3 and chh >= 0.55 * H and (x <= 3 or x + cw >= W - 3):
            b[lab == i] = 0
    if b.sum() < 4:
        return None
    prof = b.sum(1).astype(np.int64)
    runs, st = [], None
    for y, v in enumerate(prof):
        if v > 0 and st is None:
            st = y
        elif v == 0 and st is not None:
            runs.append((st, y)); st = None
    if st is not None:
        runs.append((st, len(prof)))
    # fusion des petits espaces (accents, virgules)
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] <= 1:
            ha, hb = merged[-1][1] - merged[-1][0], r[1] - r[0]
            # ne fusionne que les petits fragments (accents, virgules, points), pas deux lignes de texte
            if min(ha, hb) < 0.45 * max(ha, hb):
                merged[-1] = (merged[-1][0], r[1])
                continue
        merged.append(r)
    runs = [r for r in merged if r[1] - r[0] >= 3] or merged
    if pick == "center":
        c = crop.shape[0] / 2
        run = min(runs, key=lambda r: (0 if r[0] <= c <= r[1] else min(abs(r[0] - c), abs(r[1] - c)),
                                       -(prof[r[0]:r[1]].sum())))
    else:
        run = max(runs, key=lambda r: prof[r[0]:r[1]].sum())
    y0, y1 = run
    cols = np.where(b[y0:y1].sum(0) > 0)[0]
    x0, x1 = int(cols.min()), int(cols.max()) + 1
    return max(0, y0 - 3), y1 + 3, max(0, x0 - 2), x1 + 3


def prepare(gray_crop: np.ndarray, scale: float, already_clean: bool = False) -> np.ndarray:
    g = gray_crop if already_clean else remove_rules(gray_crop)
    g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    g = cv2.copyMakeBorder(g, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    return g


def ink_ratio(gray_crop: np.ndarray, thr: int = 160) -> float:
    if gray_crop.size == 0:
        return 0.0
    return float((gray_crop < thr).mean())
