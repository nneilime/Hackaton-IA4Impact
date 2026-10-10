"""Reading the OCR output of a bordereau (CERFA 12278 form): segments, tables, amounts and labelled fields.

Coordinates are the OCR's 0-1000 grid. A field is looked up with three strategies, in order:
  inline   label and value in the same text block   ("N° LOT 574")
  table    label cell, then the following cells     (| N° LOT | 925 |)
  spatial  label block, then the nearest block on the same line or just below that is only the value
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Callable

Box = tuple[int, int, int, int]

DECIMAL = r"\d{1,3}(?:[ .]\d{3})+[.,]\d{1,2}(?!\d)|\d+[.,]\d{1,2}(?!\d)"
DECIMAL_OR_INT = DECIMAL + r"|\b\d+\b"
DATE = re.compile(r"^\d{2}/\d{2}/\d{2,4}$")
GHS = re.compile(r"^\d{4}$")
GHS_AND_CODE = re.compile(r"^(\d{4})\s*([A-Z][A-Z0-9]{0,6})$")
PRESTATION = re.compile(r"^[A-Z][A-Z0-9]{1,3}$")
COEFFICIENT = re.compile(r"1[.,]0{1,2}")
PRESTATION_AND_GHS = re.compile(r"^([A-Z][A-Z0-9]{1,3})\s+(\d{4})$")
ACT_CODE = re.compile(r"^(?:[A-Z]{4}\d{3}|[A-Z][A-Z0-9]{0,3})$")
EXECUTANT = re.compile(r"^\d{9}$")
SIGNATURE_BOX = re.compile(r"^\s*([1-8])\s+(\d{9}\b.*)$")  # a box's text that landed in a row cell
CASE = re.compile(r"^[1-8]$")


def to_cents(text: str) -> int | None:
    m = re.fullmatch(r"(\d[\d .]*?)(?:[.,](\d{1,2}))?", text.strip())
    if not m:
        return None
    return int(re.sub(r"\D", "", m.group(1))) * 100 + int((m.group(2) or "0").ljust(2, "0"))


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"^#+\s*|\*\*", "", text)
    text = re.sub(r"[□☐■☒]", " ", text)
    text = re.sub(r"\bn\s+°", "n°", text, flags=re.I)
    return re.sub(r"[ \t]+", " ", text).strip()


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(clean_text(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)  # header rows are kept: the row readers skip them by content
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def parse_table(html: str) -> list[list[str]]:
    parser = _TableParser()
    parser.feed(html)
    return parser.rows


@dataclass
class Segment:
    label: str
    bbox: Box
    text: str
    rows: list[list[str]] | None = None  # set for tables
    header: str = ""  # tables only: lower-cased text of the <th> cells, for classification

    @property
    def is_table(self) -> bool:
        return self.rows is not None


def segments_from_blocks(blocks: list[dict]) -> list[Segment]:
    out = []
    for b in blocks:
        bbox = tuple(b["bbox"])
        if b["label"] == "table" or "<table" in b["text"]:
            header = " ".join(re.findall(r"<th>(.*?)</th>", b["text"], re.S)).lower()
            out.append(Segment(b["label"], bbox, "", parse_table(b["text"]), header))
        else:
            out.append(Segment(b["label"], bbox, b["text"]))
    return out


# ---- labelled fields -----------------------------------------------------------------------------------


@dataclass
class FieldSpec:
    name: str
    label: re.Pattern
    value: re.Pattern
    convert: Callable[[str], Any] = str
    pick: str = "first"  # which value match to keep in an inline/table hit: "first" or "last"
    region: Box | None = None  # where the label must be (x1, y1, x2, y2)
    below: bool = False  # the value may sit under the label (stacked layouts), not only to its right
    required: bool = True  # False: the box is often legitimately empty, so a miss is only "info"


@dataclass
class Found:
    value: Any
    raw: str
    strategy: str
    bbox: Box


def _inside(box: Box, region: Box | None) -> bool:
    if region is None:
        return True
    return region[0] <= box[0] <= region[2] and region[1] <= box[1] <= region[3]


def _match(spec: FieldSpec, text: str) -> str | None:
    hits = [m.group(0) for m in spec.value.finditer(text)]
    if not hits:
        return None
    return hits[0] if spec.pick == "first" else hits[-1]


def _same_line(a: Box, b: Box) -> bool:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    return overlap >= 0.5 * min(a[3] - a[1], b[3] - b[1])


def _below(a: Box, b: Box) -> bool:
    """b starts on the next line under a, either overlapping it horizontally or further right."""
    return 0 <= b[1] - a[1] and b[1] - a[3] <= 15 and (min(a[2], b[2]) - max(a[0], b[0]) > 0 or b[0] >= a[2])


def find_field(segments: list[Segment], spec: FieldSpec) -> Found | None:
    texts = [s for s in segments if not s.is_table]
    labels = [(s, m) for s in texts if (m := spec.label.search(s.text)) and _inside(s.bbox, spec.region)]

    for s, m in labels:
        if (raw := _match(spec, s.text[m.end():])) is not None:
            return Found(spec.convert(raw), raw, "inline", s.bbox)

    for s in segments:
        if not s.is_table or not _inside(s.bbox, spec.region):
            continue
        for row in s.rows:
            for i, cell in enumerate(row):
                if not (m := spec.label.search(cell)):
                    continue
                if (raw := _match(spec, cell[m.end():])) is not None:
                    return Found(spec.convert(raw), raw, "table", s.bbox)
                following = next((c for c in row[i + 1:] if c), "")  # the value cell, or nothing
                if (raw := _match(spec, following)) is not None:
                    return Found(spec.convert(raw), raw, "table", s.bbox)

    for s, _ in labels:
        near = [t for t in texts if t is not s and (
            (_same_line(s.bbox, t.bbox) and t.bbox[0] >= s.bbox[0]) or (spec.below and _below(s.bbox, t.bbox)))]
        near.sort(key=lambda t: (t.bbox[0] - s.bbox[2]) if _same_line(s.bbox, t.bbox)
                  else 2 * (t.bbox[1] - s.bbox[1]) + max(0, t.bbox[0] - s.bbox[2]))
        for t in near:
            if spec.value.fullmatch(t.text.strip()):
                return Found(spec.convert(t.text.strip()), t.text.strip(), "spatial", t.bbox)
    return None


def _digits(n: int | None = None) -> Callable[[str], str]:
    return lambda raw: re.sub(r"\D", "", raw)[:n]


FIELDS = [
    FieldSpec("finess", re.compile(r"dont n°\s*FINESS", re.I), re.compile(r"\b\d{9}\b"), region=(0, 0, 600, 150),
              below=True),
    FieldSpec("numero_lot", re.compile(r"N°\s*LOT", re.I), re.compile(r"\b\d{1,3}\b"), below=True),
    FieldSpec("numero_facture", re.compile(r"N°\s*FACTURE", re.I), re.compile(r"\b\d{4,9}\b"), below=True),
    FieldSpec("numero_assure", re.compile(r"immatriculation et cl[ée]", re.I), re.compile(r"\d[\d ]{11,}\d"),
              convert=_digits(13)),
    FieldSpec("sous_total_1", re.compile(r"sous-total 1(?!\s*\+)", re.I), re.compile(DECIMAL_OR_INT), to_cents, "last"),
    FieldSpec("sous_total_2", re.compile(r"sous-total 2", re.I), re.compile(DECIMAL_OR_INT), to_cents, "last",
              required=False),
    FieldSpec("sous_total_3", re.compile(r"sous-total 3", re.I), re.compile(DECIMAL_OR_INT), to_cents, "last",
              required=False),
    FieldSpec("sous_total_123", re.compile(r"sous-total 1\s*\+\s*2\s*\+\s*3", re.I), re.compile(DECIMAL_OR_INT),
              to_cents, "last"),
    FieldSpec("sous_total_4", re.compile(r"sous-total 4", re.I), re.compile(DECIMAL_OR_INT), to_cents, "last"),
    FieldSpec("montant_total", re.compile(r"MONTANT TOTAL"), re.compile(DECIMAL), to_cents, "last"),
]


def find_cerfa_id(segments: list[Segment]) -> Found | None:
    """The form number next to "cerfa n°" (expected 12278*0x; other values are kept for the controls to reject)."""
    for s in segments:
        if not s.is_table and s.bbox[1] < 100 and (m := re.search(r"(\d{5})\s*\*\s*(\d{2})", s.text)):
            return Found(f"{m.group(1)}*{m.group(2)}", m.group(0), "regex", s.bbox)
    return None


def find_cerfa_code(segments: list[Segment]) -> Found | None:
    """The small code in the bottom-right corner (expected S3404)."""
    for s in segments:
        if not s.is_table and s.bbox[0] >= 850 and s.bbox[1] >= 900 and (m := re.fullmatch(r"([A-Z])\s*(\d{4})", s.text)):
            return Found(m.group(1) + m.group(2), m.group(0), "regex", s.bbox)
    return None


# ---- tables --------------------------------------------------------------------------------------------


def table_kind(seg: Segment, segments: list[Segment]) -> str | None:
    """"frais" (zone 6), "lpp" (zone 7), "honoraires" (zones 9-11) or None, from the table's text or the title above it."""
    text = (seg.header + " " + " ".join(c for row in seg.rows for c in row)).lower()
    if "exécutant" in text or "executant" in text:
        return "honoraires"
    if "libellé" in text or "implantation" in text:
        return "lpp"
    if "période" in text or "prix unitaire" in text:
        return "frais"
    above = [t for t in segments if not t.is_table and t.bbox[3] <= seg.bbox[1] + 15 and seg.bbox[1] - t.bbox[1] < 30]
    for t in sorted(above, key=lambda t: -t.bbox[1]):
        title = t.text.lower()
        if "honoraires" in title:
            return "honoraires"
        if "lpp" in title:
            return "lpp"
        if "frais de structure" in title:
            return "frais"
    return None


def _cell_cents(cell: str) -> int | None:
    return to_cents(cell) if re.fullmatch(DECIMAL, cell) else None


def _split_prestation_ghs(cell: str) -> tuple[str, ...]:
    m = PRESTATION_AND_GHS.match(cell)
    return m.groups() if m else (cell,)


def prestation_rows(rows: list[list[str]], zone: int) -> list[dict]:
    """Rows of the frais (zone 6) or LPP (zone 7) tables, read relative to the prestation cell."""
    out = []
    for row in rows:
        row = [part for c in row for part in _split_prestation_ghs(c)]
        i = next((i for i, c in enumerate(row) if PRESTATION.fullmatch(c)), None)
        if i is None:
            continue
        ghs = row[i + 1] if i + 1 < len(row) and GHS.fullmatch(row[i + 1]) else None
        if ghs is None and not any(DATE.match(c) for c in row):
            continue  # a header row such as "DMT"
        if zone == 6:  # prestation, GHS, du, au, prix unitaire, quantité, coeff., montant facturé
            montant = _cell_cents(row[i + 7]) if i + 7 < len(row) else None
            if montant is None:  # a dropped cell shifted the row: take the last amount after the unit price
                prices = [j for j in range(i + 1, len(row)) if _cell_cents(row[j]) is not None]
                after = [row[j] for j in prices[1:] if not COEFFICIENT.fullmatch(row[j])]
                montant = _cell_cents(after[-1]) if after else None
        else:  # the LPP table has free-form columns in between; the billed amount is the last amount
            montant = next((v for c in reversed(row[i + 1:]) if (v := _cell_cents(c)) is not None), None)
        out.append({"zone": zone, "code": row[i], "numero_gh": ghs, "montant": montant, "executant": None,
                    "case": None, "raw": " | ".join(row)})
    return out


def honoraires_rows(rows: list[list[str]]) -> tuple[list[dict], dict[int, str]]:
    """Act lines (zones 9-10, with their "n° de case") and the zone-11 box texts the page OCR put in row cells."""
    lines, box_texts = [], {}
    for row in rows:
        for cell in row:
            if m := SIGNATURE_BOX.match(cell):
                box_texts.setdefault(int(m.group(1)), m.group(2))
        d = next((i for i, c in enumerate(row) if DATE.match(c)), None)
        if d is None:
            continue  # sub-header or empty signature-box rows
        executant = next((c for c in reversed(row[:d]) if EXECUTANT.fullmatch(c)), None)
        case = next((int(c) for c in row[:d] if CASE.fullmatch(c)), None)  # the signature box of the row
        ghs = code = None
        code_at = None
        for j in range(d + 1, len(row)):
            if m := GHS_AND_CODE.fullmatch(row[j]):
                ghs, code, code_at = m.group(1), m.group(2), j
                break
            if GHS.fullmatch(row[j]):
                ghs = row[j]
                for k in range(j + 1, min(j + 3, len(row))):
                    if ACT_CODE.fullmatch(row[k]):
                        code, code_at = row[k], k
                        break
                break
        if code is None:
            code_at = next((j for j in range(d + 1, len(row)) if ACT_CODE.fullmatch(row[j])), None)
            code = row[code_at] if code_at is not None else None
        start = (code_at if code_at is not None else d) + 1
        montant = next((v for c in reversed(row[start:]) if (v := _cell_cents(c)) is not None), None)
        lines.append({"zone": 10, "code": code, "numero_gh": ghs, "montant": montant, "executant": executant,
                      "case": case, "raw": " | ".join(row)})
    return lines, box_texts
