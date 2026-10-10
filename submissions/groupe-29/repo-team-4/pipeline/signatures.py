"""Zones 9-11 of the bordereau: the executants (9), their acts (10) and the 8 signature boxes (11).

The OCR text of the page does not show signatures and often misses the box texts, so this module works on the scan:
  locate_boxes()  finds the 8 boxes of the right-hand column from the ruling lines (a regular grid is fitted, so a
                  faint or broken line does not shift the boxes)
  box_ink()       measures the ink inside a box, leaving out its borders and the printed box number
  parse_box_text() reads what a box prints when it is stamped ("491702593 LEONARD Grégoire 622.02")
  assess_boxes()  ties the boxes to the zone-10 rows through the "n° de case" column and checks, per box, that it is
                  signed when used, that it names the rows' executant and that its printed total equals their fees.

Coordinates: pixel boxes are (x1, y1, x2, y2) in the scan; "norm" boxes are the OCR's 0-1000 grid.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from .bordereau import DECIMAL, to_cents

BOX_COUNT = 8
DARK = 160  # grey level under which a pixel counts as ink for line detection
FAINT = 200  # looser level for the column's vertical borders, printed lighter on some layouts
INK = 128  # stricter level for the content of a box (ignores the light background noise of the scans)
SIGNED_INK_RATIO = 0.015  # share of dark pixels above which a box counts as filled (empty boxes stay under 0.003)
COLUMN = (0.815, 0.99)  # horizontal span of the signature column, as page-width fractions (all three layouts)
GRID_Y = (0.50, 0.92)  # vertical search range for the grid
GAP = (0.030, 0.050)  # expected box height, as page-height fractions
EXPECTED_TOP = 0.551  # where the grid starts on all three layouts; breaks ties between equally good fits

PxBox = tuple[int, int, int, int]


def _runs(indices: np.ndarray, join: int = 2) -> list[int]:
    """Centres of runs of consecutive indices (a line drawn several pixels thick is one line)."""
    runs: list[list[int]] = []
    for i in indices.tolist():
        if runs and i - runs[-1][1] <= join:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    return [(a + b) // 2 for a, b in runs]


def _fit_grid(lines: list[int], h: int) -> tuple[float, float] | None:
    """(top, step) of the 9-line grid that matches the most detected lines."""
    gaps = [b - a for a, b in zip(lines, lines[1:]) if GAP[0] * h <= b - a <= GAP[1] * h]
    if not gaps:
        return None
    step = float(np.median(gaps))
    tol = 0.2 * step
    best: tuple[int, float, float] | None = None  # (lines matched, distance to the expected top, top)
    for y in lines:
        for k in range(BOX_COUNT + 1):  # y may be any of the 9 lines of the grid
            top = y - k * step
            if top < GRID_Y[0] * h or top + BOX_COUNT * step > GRID_Y[1] * h:
                continue
            score = sum(min(abs(l - (top + i * step)) for l in lines) <= tol for i in range(BOX_COUNT + 1))
            distance = abs(top - EXPECTED_TOP * h)
            if best is None or (score, -distance) > (best[0], -best[1]):
                best = (score, distance, top)
    if best is None or best[0] < 5:  # fewer than 5 of the 9 lines seen: not a box column
        return None
    return best[2], step


def locate_boxes(gray: np.ndarray) -> list[PxBox]:
    """The 8 signature boxes, top to bottom, or [] when the column cannot be found."""
    h, w = gray.shape
    x1, x2 = int(w * COLUMN[0]), int(w * COLUMN[1])
    dark = gray < DARK
    rows = dark[:, x1:x2].mean(axis=1)
    lines = [y for y in _runs(np.where(rows > 0.6)[0]) if GRID_Y[0] * h <= y <= GRID_Y[1] * h]
    grid = _fit_grid(lines, h)
    if grid is None:
        return []
    top, step = grid
    # snap each grid line to the detected line next to it, when there is one
    ys = []
    for i in range(BOX_COUNT + 1):
        y = top + i * step
        near = [l for l in lines if abs(l - y) <= 0.2 * step]
        ys.append(int(min(near, key=lambda l: abs(l - y))) if near else int(round(y)))
    # the column's vertical borders, measured over the grid's height
    cols = (gray[ys[0]:ys[-1], int(w * 0.78):] < FAINT).mean(axis=0)
    xs = [x + int(w * 0.78) for x in _runs(np.where(cols > 0.6)[0])]
    left = max([x for x in xs if x < w * 0.86] or [x1])
    right = min([x for x in xs if x > w * 0.93] or [x2])
    return [(left, ys[i], right, ys[i + 1]) for i in range(BOX_COUNT)]


def box_ink(gray: np.ndarray, box: PxBox) -> float:
    """Share of dark pixels inside the box, without its borders and its printed number (top-left corner)."""
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    inner = gray[y1 + max(3, bh // 12):y2 - max(3, bh // 12), x1 + max(3, bw // 30):x2 - max(3, bw // 30)]
    if inner.size == 0:
        return 0.0
    ink = inner < INK
    ink[: int(inner.shape[0] * 0.35), : int(inner.shape[1] * 0.10)] = False  # the box number
    return float(ink.mean())


EXECUTANT_IN_TEXT = re.compile(r"\b(\d{9})\b")
AMOUNT_IN_TEXT = re.compile(DECIMAL)
NOISE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b|\bPAR\s+MANDAT\b|stamp\s*\"[^\"]*\"|\bMANDAT\b|\bDr\.?(?=\s)|-", re.I)


def parse_box_text(text: str) -> dict:
    """The executant, name and total printed in a stamped box ("491702593 LEONARD Grégoire 622.02"); else None."""
    text = " ".join(text.split())
    m = EXECUTANT_IN_TEXT.search(text)
    rest = text[m.end():] if m else text
    amounts = list(AMOUNT_IN_TEXT.finditer(NOISE.sub(" ", rest)))  # dates are blanked first: 01/01/2005 is no amount
    name = None
    if m:
        cleaned = NOISE.sub(" ", rest)
        name_part = cleaned[:amounts[0].start()] if amounts else cleaned
        name = " ".join(w for w in name_part.split() if not re.fullmatch(r"\W+", w)) or None
    return {"executant": m.group(1) if m else None, "name": name,
            "amount": to_cents(amounts[0].group(0)) if amounts else None}


@dataclass
class BoxResult:
    box: int
    bbox: PxBox | None = None
    ink_ratio: float | None = None
    signed: bool | None = None  # None: no image / boxes not found
    text: str | None = None
    text_source: str | None = None  # "box_ocr" (dedicated OCR of the column) or "page_ocr"
    printed_executant: str | None = None
    printed_name: str | None = None
    printed_amount: int | None = None  # cents
    rows: int = 0  # zone-10 rows of this box
    rows_by: str | None = None  # "executant": rows by the executant the box prints; "case": rows whose n° de case is it
    row_executants: list[str] = field(default_factory=list)
    computed_amount: int | None = None  # cents: sum of those rows' fees
    executant_ok: bool | None = None
    amount_ok: bool | None = None
    problems: list[str] = field(default_factory=list)


def analyse_image(image_path: str | Path | None) -> tuple[list[PxBox], list[float]] | None:
    if not image_path or not Path(image_path).is_file():
        return None
    gray = np.asarray(Image.open(image_path).convert("L"))
    boxes = locate_boxes(gray)
    return boxes, [box_ink(gray, b) for b in boxes]


def assess_boxes(lines: list[dict], texts: dict[int, tuple[str, str]],
                 image: tuple[list[PxBox], list[float]] | None) -> list[BoxResult]:
    """One BoxResult per box. texts: box number -> (text, source). lines: zone-10 rows with "case" and "executant"."""
    results = []
    for n in range(1, BOX_COUNT + 1):
        r = BoxResult(n)
        if image and image[0]:
            r.bbox, r.ink_ratio = image[0][n - 1], round(image[1][n - 1], 4)
            r.signed = r.ink_ratio >= SIGNED_INK_RATIO
        if n in texts:
            r.text, r.text_source = texts[n]
            printed = parse_box_text(r.text)
            r.printed_executant, r.printed_name, r.printed_amount = (printed["executant"], printed["name"],
                                                                     printed["amount"])
        # the 9-digit executant printed in the box is read far more reliably than the 1-digit "n° de case"
        if r.printed_executant:
            used, r.rows_by = [l for l in lines if l.get("executant") == r.printed_executant], "executant"
        else:
            used, r.rows_by = [l for l in lines if l.get("case") == n], "case"
        r.rows = len(used)
        r.row_executants = sorted({l["executant"] for l in used if l.get("executant")})
        amounts = [l["montant"] for l in used]
        r.computed_amount = sum(amounts) if used and None not in amounts else None

        if r.printed_executant:
            r.executant_ok = bool(used)
            if not used:
                r.problems.append(f"la case nomme {r.printed_executant}, qui n'a aucun acte en zone 10")
        if r.printed_amount is not None and r.computed_amount is not None:
            r.amount_ok = r.printed_amount == r.computed_amount
            if not r.amount_ok:
                r.problems.append(f"total de la case {r.printed_amount / 100:.2f} ≠ honoraires de ses lignes "
                                  f"{r.computed_amount / 100:.2f}")
        results.append(r)

    # An empty box only matters if one of its rows' executants signed nowhere else: the 1-digit n° de case that
    # ties rows to an unprinted box is often misread by the OCR.
    covered = {r.printed_executant for r in results if r.signed and r.printed_executant}
    for r in results:
        if r.signed is False and r.rows:
            uncovered = [e for e in r.row_executants if e not in covered] or (["?"] if not r.row_executants else [])
            if uncovered:
                r.problems.append(f"case vide (pas de signature) alors que des lignes de {', '.join(uncovered)} y renvoient")
    return results


def as_dicts(results: list[BoxResult]) -> list[dict]:
    return [{**asdict(r), "bbox": list(r.bbox) if r.bbox else None} for r in results]
