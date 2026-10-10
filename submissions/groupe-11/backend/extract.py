"""Batch OCR of the scans + field extraction by anchors.

  uv run python extract.py               # OCR every image without a cache (~20-30 s/page on CPU)
                                         # (main.py starts this batch by itself at server startup)
  uv run python extract.py Facture1_01   # OCR if needed, then print that extraction

OCR runs only here and is cached in cache/<name>.json as [{text, box, score}].
extract(name) only reads the cache + the image (signatures), so it is cheap.
Output is raw by design: values are never corrected, low scores go to `illisible`.
"""
import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "images"
CACHE = Path(__file__).resolve().parent / "cache"
SCHEMA = json.loads((Path(__file__).resolve().parent / "deserialization" / "b2.schema.json").read_text())

# Tunable knobs (calibrated with eval.py)
MIN_SCORE = 0.80        # OCR score below this -> zone "illisible"
INK_LEVEL = 200         # grey level below this counts as ink
SIGN_MIN_INK = 0.005    # practitioner box (zone 11): ink ratio for "signed"
DIRECTOR_MIN_INK = 0.005  # zone 14

AMOUNT = r"\d{1,6}(?:[.,]\d{1,2})?"
# "n° GHS" column header. Tolerates one stray character after the "n" (the mobile model reads "n.a GHS")
GHS_HEADER = r"^(n\W*\w?\W*\s*)?GHS$"


# ---------------------------------------------------------------- OCR batch

LOCK = CACHE / "ocr.pid"  # pid of the batch currently OCR'ing (main.py starts one at server startup)


def batch_running():
    """True while another process is running the OCR batch."""
    try:
        pid = int(LOCK.read_text())
        os.kill(pid, 0)
    except (FileNotFoundError, ValueError, ProcessLookupError):
        return False
    except PermissionError:  # alive, owned by another user
        return True
    return pid != os.getpid()


def run_ocr(names):
    todo = [n for n in names if not (CACHE / f"{n}.json").exists()]
    if not todo:
        return
    if batch_running():
        print(f"OCR batch already running (pid {LOCK.read_text().strip()}), nothing to do", flush=True)
        return
    CACHE.mkdir(exist_ok=True)
    LOCK.write_text(str(os.getpid()))
    try:
        _ocr(todo)
    finally:
        if LOCK.exists() and LOCK.read_text().strip() == str(os.getpid()):
            LOCK.unlink()


def ocr_device():
    """OpenVINO device for the OCR: MELEE_OCR_DEVICE if set, else the GPU when its driver is installed."""
    import openvino as ov
    return os.environ.get("MELEE_OCR_DEVICE") or ("GPU" if "GPU" in ov.Core().available_devices else "CPU")


def _ocr(todo):
    """RapidOCR running PP-OCRv6 medium (French) on OpenVINO: same model as PaddleOCR's default, ~4x faster
    on CPU than PaddlePaddle without oneDNN, and able to use the Intel iGPU (needs the `intel-opencl-icd`
    system package). Checked at 165/165 on devtools/eval.py."""
    import openvino as ov  # heavy imports, only for the batch
    from rapidocr import EngineType, ModelType, OCRVersion, RapidOCR

    device = ocr_device()
    # RapidOCR's OpenVINO engine hard-codes device_name="CPU": send its models to the chosen device
    compile_model = ov.Core.compile_model
    ov.Core.compile_model = lambda self, model, device_name=None, *a, **kw: compile_model(self, model, device, *a, **kw)
    engine = {"engine_type": EngineType.OPENVINO, "ocr_version": OCRVersion.PPOCRV6, "model_type": ModelType.MEDIUM}
    ocr = RapidOCR(params={"Global.use_cls": False,  # scans are upright: no text-direction classifier
                           **{f"Det.{k}": v for k, v in engine.items()},
                           **{f"Rec.{k}": v for k, v in engine.items()},
                           "Rec.lang_type": "fr"})
    print(f"OCR: RapidOCR + OpenVINO on {device}", flush=True)
    for name in todo:
        out = CACHE / f"{name}.json"
        res = ocr(str(IMAGES / f"{name}.jpg"))
        lines = [{"text": t,
                  "box": [int(min(x for x, _ in q)), int(min(y for _, y in q)),
                          int(max(x for x, _ in q)), int(max(y for _, y in q))],
                  "score": round(float(s), 4)}
                 for q, t, s in zip(res.boxes if res.boxes is not None else [], res.txts or [], res.scores or [])]
        # Write then rename: the API polls the cache and must never read a half-written file
        tmp = out.with_suffix(".tmp")
        tmp.write_text("[\n" + ",\n".join(json.dumps(l, ensure_ascii=False) for l in lines) + "\n]\n")
        tmp.replace(out)
        print(f"{name}: {len(lines)} lines", flush=True)


def all_names():
    return sorted(p.stem for p in IMAGES.glob("*.jpg"))


# ---------------------------------------------------------------- helpers

class Box:
    def __init__(self, d):
        self.text = d["text"].strip()
        self.x0, self.y0, self.x1, self.y1 = d["box"]
        self.score = d["score"]

    @property
    def xc(self):
        return (self.x0 + self.x1) / 2

    @property
    def yc(self):
        return (self.y0 + self.y1) / 2

    @property
    def rect(self):
        return [self.x0, self.y0, self.x1, self.y1]


def find(boxes, pattern, where=lambda b: True):
    """Boxes whose text matches `pattern` (case-insensitive), top-to-bottom."""
    rx = re.compile(pattern, re.I)
    return sorted((b for b in boxes if rx.search(b.text) and where(b)), key=lambda b: (b.y0, b.x0))


def rows(boxes, tol):
    """Group boxes into rows by y-centre."""
    out = []
    for b in sorted(boxes, key=lambda b: b.yc):
        if out and b.yc - out[-1][0].yc <= tol:
            out[-1].append(b)
        else:
            out.append([b])
    return [sorted(r, key=lambda b: b.x0) for r in out]


def in_cols(row, x0, x1):
    return [b for b in row if x0 <= b.xc <= x1]


def joined(bs):
    return " ".join(b.text for b in bs).strip()


def to_amount(text):
    """Last amount in the text ('1   50,48' -> 50.48) as float euros, or None."""
    found = re.findall(AMOUNT, text or "")
    return float(found[-1].replace(",", ".")) if found else None


def union(bs):
    """Smallest [x0, y0, x1, y1] around some boxes (None if there are none)."""
    bs = [b for b in bs if b is not None]
    if not bs:
        return None
    return [min(b.x0 for b in bs), min(b.y0 for b in bs), max(b.x1 for b in bs), max(b.y1 for b in bs)]


def ink_ratio(gray, rect, s, masks=()):
    """Share of ink pixels in rect, with ruled lines and `masks` rectangles removed."""
    x0, y0, x1, y1 = (int(round(v)) for v in rect)
    h, w = gray.shape
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    ink = (gray[y0:y1, x0:x1] < INK_LEVEL).astype(np.uint8)
    k = max(int(25 * s), 5)
    lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1)))
    lines |= cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, k)))
    ink &= 1 - cv2.dilate(lines, np.ones((3, 3), np.uint8))
    for m in masks:
        pad = int(4 * s)
        ink[max(m[1] - y0 - pad, 0):max(m[3] - y0 + pad, 0), max(m[0] - x0 - pad, 0):max(m[2] - x0 + pad, 0)] = 0
    return float(ink.mean())


# ---------------------------------------------------------------- extraction

class Page:
    def __init__(self, name):
        self.name = name
        self.boxes = [Box(d) for d in json.loads((CACHE / f"{name}.json").read_text())]
        self.gray = cv2.imread(str(IMAGES / f"{name}.jpg"), cv2.IMREAD_GRAYSCALE)
        self.h, self.w = self.gray.shape
        self.s = self.w / 1190  # Facture1/2 ~1190 px wide, Facture3 ~1684
        self.boxes_by_zone, self.scores = {}, {}
        self.labels = {}  # zone -> boxes of the printed label a value was found next to (crop context)

    def note(self, zone, used, box_key=None):
        """Record the OCR boxes a zone was read from (for the UI crops and scores).
        `box_key` files the boxes under another key (e.g. "6m": zone 6 amounts, only highlighted by C7),
        while their OCR scores still count for the zone."""
        used = [b for b in used if b is not None]
        self.boxes_by_zone.setdefault(box_key or zone, []).extend(b.rect for b in used)
        if used:
            self.scores[zone] = min([self.scores.get(zone, 1.0)] + [b.score for b in used])

    def right_of(self, zone, label_rx, value_rx, rightmost=False, dy=0.5, xmax=None, where=lambda b: True):
        """Value printed right of a label: in the label box itself (merged OCR) or the next box."""
        labels = find(self.boxes, label_rx, where)
        if not labels:
            return None
        lab = labels[0]
        rest = re.split(label_rx, lab.text, maxsplit=1, flags=re.I)[-1].strip()
        m = re.search(value_rx, rest)
        if m and not rightmost:
            self.note(zone, [lab])
            return m.group(0).strip()
        lh = lab.y1 - lab.y0
        cands = [b for b in self.boxes if b is not lab and b.xc > lab.x1
                 and abs(b.yc - lab.yc) <= dy * lh + 3 * self.s
                 and (xmax is None or b.x1 <= xmax) and re.search(value_rx, b.text)]
        if not cands:
            return None
        b = max(cands, key=lambda b: b.x0) if rightmost else min(cands, key=lambda b: b.x0)
        self.note(zone, [b])
        self.labels.setdefault(zone, []).append(lab.rect)  # so the UI crop shows which field the value is
        return re.search(value_rx, b.text).group(0).strip()

    def table_rows(self, top, bottom, xmax=None):
        """Data rows between two y limits (tall vertical header boxes dropped)."""
        bs = [b for b in self.boxes if top < b.yc < bottom and (b.y1 - b.y0) < 25 * self.s
              and (xmax is None or b.xc < xmax)]
        return rows(bs, 6 * self.s)

    def code_and_ghs(self, row, ghs_hdr):
        """Prestation code + GHS number, left of / under the 'GHS' header (handles 'GHS9606')."""
        s = self.s
        bs = in_cols(row, ghs_hdr.x0 - 40 * s, ghs_hdr.x1 + 15 * s)
        m = re.fullmatch(r"([A-Z][A-Z0-9]{0,4}?)?\s*(\d{4})?", joined(bs).upper())
        if not bs or not m or not any(m.groups()):
            return None, None, bs
        return m.group(1), m.group(2), bs

    def extract(self):
        s, B = self.s, self.boxes
        sc = {"illisible": []}

        # zone 1: cerfa number, top-left corner
        z1 = find(B, r"\d{4}", lambda b: b.x0 < 0.2 * self.w and b.y0 < 0.08 * self.h)
        sc["cerfa"] = re.sub(r"^n\W*\s*", "", z1[0].text, flags=re.I) if z1 else None
        self.note(1, z1[:1])

        tiers = self.right_of(2, r"dont\s*n\W*\s*FINESS", r"\d{9}")
        lot = self.right_of(3, r"N\W{0,2}\s*LOT", r"\d+")
        facture = self.right_of(4, r"N\W{0,2}\s*FACTURE", r"\d+")
        # The same label is printed again on the right, in the empty "l'assuré(e)" block: take the
        # beneficiary's (left half). Ordering by y alone picked the wrong one when it sat 1-4 px higher.
        assure = self.right_of(5, r"immatriculation\s*et\s*[^\W\d]{2,3}", r"[\dAB][\dAB ]{12,}",
                               where=lambda b: b.x0 < 0.5 * self.w)
        if assure:
            assure = assure.replace(" ", "")[:13]

        # zones 6 / 7: hospital services tables
        prest = []
        st1 = find(B, r"sous-?\s*total\s*1\b(?!\s*\+)")
        title6 = find(B, r"frais de structure")
        sc["zone6"] = []
        if st1 and title6:
            band = (title6[0].y0, title6[0].y1 + 50 * s)
            ghs_h = find(B, GHS_HEADER, lambda b: band[0] < b.yc < band[1])
            mnt_h = find(B, r"^montant$", lambda b: band[0] < b.yc < band[1])
            ghs_h.sort(key=lambda b: b.x0), mnt_h.sort(key=lambda b: b.x0)
            for row in self.table_rows(band[1], st1[0].y0):
                for g, m in zip(ghs_h, mnt_h):
                    code, ghs, used = self.code_and_ghs(row, g)
                    if not used:
                        continue
                    mb = in_cols(row, m.x0 - 15 * s, m.x1 + 25 * s)
                    sc["zone6"].append({"acte": code, "numero_gh": ghs, "montant": to_amount(joined(mb)),
                                        "box": union(used)})  # where this prestation is printed
                    self.note(6, used)
                    self.note(6, mb, box_key="6m")  # billed amount: only relevant to C7, not to the GHS checks
        st3 = find(B, r"sous-?\s*total\s*3")
        sc["zone7"] = []
        if st1 and st3:
            g7 = find(B, GHS_HEADER, lambda b: st1[0].y1 < b.yc < st3[0].y0 and b.text.lower().startswith("n"))
            if g7:
                for row in self.table_rows(g7[0].y1 + 8 * s, st3[0].y0):
                    code, ghs, used = self.code_and_ghs(row, g7[0])
                    if used:
                        sc["zone7"].append({"acte": code, "numero_gh": ghs, "box": union(used)})
                        self.note(7, used)
        for r in sc["zone6"] + sc["zone7"]:
            prest.append({"acte": r["acte"], "numero_gh": r["numero_gh"], "details": []})

        total_prest = to_amount(self.right_of(8, r"sous-?\s*total\s*1\s*\+\s*2\s*\+\s*3", AMOUNT))

        # zones 9 / 10: fees table
        actes, sc["executants"], sc["zone10"] = [], [], []
        exech = find(B, r"de l.\s*ex[ée]cutant")
        codeh = find(B, r"^code acte")
        clef = find(B, r"ou lettre")
        st4 = find(B, r"sous-?\s*total\s*4")
        sigh = find(B, r"signat\w* des prat")
        if exech and codeh and clef and st4:
            ghsh = find(B, r"^GHS$", lambda b: abs(b.yc - codeh[0].yc) < 15 * s)
            xmax = sigh[0].x0 - 5 * s if sigh else None
            for row in self.table_rows(clef[0].y1, st4[0].y0, xmax):
                eb = in_cols(row, exech[0].x0 - 10 * s, exech[0].x1 + 10 * s)
                ex = re.search(r"\d{9}", joined(eb))
                cb = in_cols(row, codeh[0].x0 - 10 * s, codeh[0].x1 + 10 * s)
                gb = in_cols(row, ghsh[0].x0 - 10 * s, ghsh[0].x1 + 10 * s) if ghsh else []
                m = re.fullmatch(r"(\d{4})?\s*(.*)", joined(gb + cb))
                code = m.group(2).replace(" ", "").upper()
                if not ex and re.fullmatch(r"[\d\s]+", m.group(2) or "-"):
                    continue  # NABM sub-line of a 'B' act (4-B), not a code acte
                if ex:
                    sc["executants"].append(ex.group(0))
                    self.note(9, eb)
                if code:
                    sc["zone10"].append({"code": code, "numero_gh": m.group(1), "executant": ex and ex.group(0),
                                         "box": union(gb + cb)})  # where this act is printed
                    self.note(10, gb + cb)
                    if len(code) == 7:
                        actes.append({"acte": None, "details": [{"subtype": "4-M", "code_ccam": code}]})
                    else:
                        actes.append({"acte": code, "details": []})
        total_hono = to_amount(self.right_of(12, r"sous-?\s*total\s*4", AMOUNT, rightmost=True,
                                             xmax=sigh[0].x0 if sigh else None))

        mt = find(B, r"^MONTANT\s*TOTAL(?!\s*des)")
        unpaid = find(B, r"n.a pas pay")
        sc["total"] = to_amount(self.right_of(13, r"^MONTANT\s*TOTAL(?!\s*des)", AMOUNT, dy=1.5,
                                              xmax=unpaid[0].x0 if unpaid else None))

        # zone 11: practitioner signature boxes 1-8 (ink density, no OCR)
        sc["signatures"], sc["signature_ink"] = None, None
        if sigh:
            col = [b for b in B if b.x0 >= sigh[0].x0 - 5 * s and b.y0 >= sigh[0].y0 - 2 * s]
            colx1 = max(b.x1 for b in col if b.y0 < sigh[0].y1 + 60 * s)
            labels = {int(b.text): b for b in col if re.fullmatch(r"[1-8]", b.text)
                      and b.x0 < sigh[0].x0 + 25 * s and b.yc > sigh[0].y1 + 40 * s}
            if len(labels) >= 2:
                ks = sorted(labels)
                pitch = np.median([(labels[b].y0 - labels[a].y0) / (b - a) for a, b in zip(ks, ks[1:])])
                ref = labels[ks[0]]
                rects, inks = [], []
                for i in range(1, 9):
                    top = labels[i].y0 if i in labels else ref.y0 + (i - ks[0]) * pitch
                    r = [sigh[0].x0, top - 2 * s, colx1, top + pitch - 8 * s]
                    rects.append([int(v) for v in r])
                    inks.append(round(ink_ratio(self.gray, r, s, [labels[i].rect] if i in labels else []), 4))
                sc["signatures"] = [v >= SIGN_MIN_INK for v in inks]
                sc["signature_ink"] = inks
                self.boxes_by_zone[11] = rects

        # zone 14: director signature, right of MONTANT TOTAL (Facture3's stamp overflows its box)
        sc["signature_directeur"], sc["signature_directeur_ink"] = None, None
        if mt and sigh:
            lh = 14 * s
            r = [sigh[0].x0 - 5 * s, mt[0].y0 - 3 * lh, self.w - 10 * s, mt[0].y1 + 1.5 * lh]
            labels = find(B, r"signat|[ée]tab|directeur", lambda b: b.y0 > r[1] - lh)
            ink = round(ink_ratio(self.gray, r, s, [b.rect for b in labels]), 4)
            sc["signature_directeur"], sc["signature_directeur_ink"] = ink >= DIRECTOR_MIN_INK, ink
            self.boxes_by_zone[14] = [[int(v) for v in r]]

        # zone 15: form code, bottom-right corner
        z15 = find(B, r"^\S\s*\d{3,}", lambda b: b.x0 > 0.8 * self.w and b.y0 > 0.9 * self.h)
        sc["form_code"] = z15[0].text if z15 else None
        self.note(15, z15[:1])

        values = {2: tiers, 3: lot, 4: facture, 5: assure, 8: total_prest, 12: total_hono,
                  13: sc["total"], 1: sc["cerfa"], 15: sc["form_code"]}
        errors = []
        for zone in range(1, 16):
            score = self.scores.get(zone)
            if zone in values and values[zone] is None:
                errors.append({"line": zone, "message": f"zone {zone} non trouvée"})
                sc["illisible"].append(zone)
            elif score is not None and score < MIN_SCORE:
                errors.append({"line": zone, "message": f"zone {zone} illisible (score {score:.2f})"})
                sc["illisible"].append(zone)
        sc["boxes"] = {str(z): v for z, v in sorted(self.boxes_by_zone.items(), key=lambda kv: str(kv[0]))}
        sc["labels"] = {str(z): v for z, v in sorted(self.labels.items())}
        sc["scores"] = {str(z): v for z, v in sorted(self.scores.items())}
        sc["image"] = {"largeur": self.w, "hauteur": self.h}

        return {
            "source_file": f"{self.name}.jpg",
            "header": None,
            "errors": errors,
            "lots": [{"numero_tiers": tiers, "numero_lot": lot, "factures": [{
                "numero_assure": assure, "numero_facture": facture, "complements_2S": [],
                "prestations_hospitalieres": prest, "actes": actes,
                "total_prestations": total_prest, "total_honoraires": total_hono}]}],
            "scan": sc,
        }


def extract(name):
    """Scan model (b2.schema.json + extra `scan` object) from the OCR cache, or None if not OCR'd yet."""
    return _extract(name) if (CACHE / f"{name}.json").exists() else None


@lru_cache(maxsize=None)
def _extract(name):
    out = Page(name).extract()
    Draft202012Validator(SCHEMA).validate(out)
    return out


if __name__ == "__main__":
    names = sys.argv[1:] or all_names()
    run_ocr(names)
    if sys.argv[1:]:
        for n in names:
            print(json.dumps(extract(n), ensure_ascii=False, indent=1))
