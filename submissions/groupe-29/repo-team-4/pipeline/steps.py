"""The steps used by the built-in flows. Each one does one thing; flows (flows.py) put them in order."""

from __future__ import annotations

import re

from . import b2, compare, geo, signatures
from .bordereau import (FIELDS, clean_text, find_cerfa_code, find_cerfa_id, find_field, honoraires_rows,
                        prestation_rows, segments_from_blocks, table_kind)
from .core import Cleanup, Context, Filter, Transform, Validate

# ---- facture (B2 file) ---------------------------------------------------------------------------------


class NormalizeB2Lines(Cleanup):
    """Strip line endings. Skipped when the facture arrives already parsed (parse_factures_txt.py JSON)."""

    def run(self, ctx: Context) -> None:
        if "lines" in ctx.facture:
            ctx.facture["lines"] = [line.rstrip("\r\n") for line in ctx.facture["lines"]]


class FilterB2Records(Filter):
    """Drop blank lines and records whose type is not 0-6."""

    def run(self, ctx: Context) -> None:
        if "lines" not in ctx.facture:
            return
        kept = []
        for n, line in enumerate(ctx.facture["lines"], 1):
            if not line.strip():
                continue
            if line[0] not in b2.RECORD_TYPES:
                self.issue(ctx, "warning", f"line {n}: unknown record type {line[0]!r}, dropped")
                continue
            kept.append(line)
        ctx.facture["lines"] = kept


def _cents(euros: float | None) -> int | None:
    return None if euros is None else round(euros * 100)


def _lines_from_lists(parsed: dict) -> list[dict]:
    """Rebuild records from the per-type lists of an older JSON without "Lignes" (file order is lost)."""
    out = [{"Type": "3", "Acte": a, "NumeroGH": g, "CodeCCAM": None, "Brut": None}
           for a, g in zip(parsed["Acte_Type3"], parsed["NumeroGH_Type3"])]
    out += [{"Type": "4", "Acte": a, "NumeroGH": None, "CodeCCAM": None, "Brut": None} for a in parsed["Acte_Type4"]]
    out += [{"Type": "4-S", "Acte": None, "NumeroGH": g, "CodeCCAM": None, "Brut": None}
            for g in parsed["NumeroGH_Type4S"]]
    out += [{"Type": "4-M", "Acte": None, "NumeroGH": None, "CodeCCAM": c, "Brut": None}
            for c in parsed["CodeCCAM_Type4M"]]
    return out


class ParseB2(Transform):
    """Parse the B2 records with pipeline.b2 (the parse_factures_txt.py parser) and build the facture record."""

    def run(self, ctx: Context) -> None:
        if "lines" in ctx.facture:
            parsed = b2.parse_lines(ctx.facture["lines"], ctx.facture.get("name"))
        else:
            parsed = ctx.facture["parsed"]
        ordered = "Lignes" in parsed
        records = parsed["Lignes"] if ordered else _lines_from_lists(parsed)
        if not ordered:
            self.issue(ctx, "info", "facture JSON has no 'Lignes': act / CCAM pairing (C19) is approximate")
        invoices = sum(1 for r in records if r["Type"] == "2")
        if invoices > 1:
            self.issue(ctx, "warning", f"the file holds {invoices} invoice starts, the last one's keys are kept")

        lines = [{"record_type": r["Type"][0], "sub_type": r["Type"][2:], "acte": r["Acte"],
                  "numero_gh": r["NumeroGH"], "code_ccam": r["CodeCCAM"], "raw": r["Brut"]}
                 for r in records if r["Type"][0] in "34"]
        ghs = next((l for l in lines if l["record_type"] == "3" and not l["sub_type"] and l["acte"] == "GHS"), None)
        ctx.facture["parsed"] = parsed
        ctx.record["facture"] = {
            "numero_tiers": parsed["NumeroTiers"], "numero_lot": parsed["NumeroLot"],
            "numero_facture": parsed["NumeroFacture"], "numero_assure": parsed["NumeroAssure"],
            "numero_gh": ghs["numero_gh"] if ghs else None,
            "total_prestations": _cents(parsed["TotalPrestations"]),
            "total_honoraires": _cents(parsed["TotalHonoraires"]),
            "date_fichier": parsed.get("DateFichier"), "code_organisme": parsed.get("CodeOrganisme"),
            "nom_etablissement": parsed.get("NomEtablissement"),
            "ordered": ordered, "lines": lines,
        }


class CheckB2Layout(Validate):
    """Every record must carry the type-1 tiers number at 2-10 followed by one blank: a shifted line breaks slicing."""

    def run(self, ctx: Context) -> None:
        if "lines" in ctx.facture:
            raw = list(enumerate(ctx.facture["lines"], 1))
        else:  # parse_factures_txt.py JSON: its "Lignes" keep the type-2/3/4 records with their line numbers
            raw = [(l["Ligne"], l["Brut"]) for l in ctx.facture["parsed"].get("Lignes", []) if l.get("Brut")]
        ctx.scratch["layout_checked"] = bool(raw)
        if not raw:
            self.issue(ctx, "info", "no raw B2 records in the facture JSON: layout not checked", "layout")
            return
        tiers = ctx.record["facture"]["numero_tiers"]
        other_tiers, shifted = {}, []
        for n, line in raw:
            if line[0] not in "23456":
                continue
            if tiers and b2.field(line, 2, 10) != tiers:
                other_tiers.setdefault(b2.field(line, 2, 10), []).append(n)
            if line[0] in "2345" and (b2.char_at(line, 11) != " " or b2.char_at(line, 12) in (" ", "")):
                shifted.append(n)
        for value, lines in other_tiers.items():
            self.issue(ctx, "error", f"n° de tiers {value!r} ≠ celui de l'enregistrement 1 ({tiers!r}) sur {_lines(lines)}", "numero_tiers")
        if shifted:
            self.issue(ctx, "error", f"champs décalés après la position 11 sur {_lines(shifted)}", "layout")


def _lines(numbers: list[int]) -> str:
    return f"la ligne {numbers[0]}" if len(numbers) == 1 else f"{len(numbers)} lignes ({numbers[0]}-{numbers[-1]})"


class CheckFacture(Validate):
    def run(self, ctx: Context) -> None:
        rec = ctx.record["facture"]
        for key in ("numero_tiers", "numero_lot", "numero_facture", "numero_assure", "total_prestations",
                    "total_honoraires"):
            if rec[key] in (None, ""):
                self.issue(ctx, "error", "missing in the B2 file", key)
        if rec["numero_gh"] is None:
            self.issue(ctx, "warning", "no type-3 GHS line", "numero_gh")


# ---- bordereau (OCR output) ----------------------------------------------------------------------------

BOILERPLATE = re.compile(r"^(Quiconque|Les informations figurant|En application de la loi|Le règlement est effectué|"
                         r"articles? [RL]\.)", re.I)


class CleanupOcrBlocks(Cleanup):
    """Normalise text (unicode, markdown markers, checkboxes, spacing) and fix swapped bbox corners."""

    def run(self, ctx: Context) -> None:
        for b in ctx.bordereau["blocks"]:
            x1, y1, x2, y2 = b["bbox"]
            b["bbox"] = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
            if "<table" not in b["text"]:
                b["text"] = clean_text(b["text"])


class FilterOcrBlocks(Filter):
    """Drop empty blocks and the legal boilerplate, and empty table rows (via the segment builder)."""

    def run(self, ctx: Context) -> None:
        kept = [b for b in ctx.bordereau["blocks"] if b["text"].strip() and not BOILERPLATE.match(b["text"])]
        segments = segments_from_blocks(kept)
        for s in segments:
            if s.is_table:
                s.rows = [r for r in s.rows if any(c.strip() for c in r)]
        ctx.scratch["segments"] = segments


class ExtractBordereauFields(Transform):
    """Zones 1-5, 8, 12, 13, 15 and the self-check sub-totals, with where each value came from."""

    def run(self, ctx: Context) -> None:
        segments = ctx.scratch["segments"]
        rec: dict = {}
        provenance: dict = {}
        found = {"cerfa_id": (find_cerfa_id(segments), True), "cerfa_code": (find_cerfa_code(segments), True)}
        found |= {spec.name: (find_field(segments, spec), spec.required) for spec in FIELDS}
        for name, (f, required) in found.items():
            rec[name] = f.value if f else None
            provenance[name] = {"raw": f.raw, "strategy": f.strategy, "bbox": list(f.bbox)} if f else None
            if f is None:
                self.issue(ctx, "warning" if required else "info", "not found in the OCR output", name)
        signed = any(not s.is_table and re.search(r"sign[ée] num[ée]riquement", s.text, re.I) for s in segments)
        rec["director_signature"] = True if signed else None  # None = unknown, needs image analysis
        rec["provenance"] = provenance
        ctx.record["bordereau"] = rec


class ExtractBordereauTables(Transform):
    """Zones 6, 7 (prestations) and 9-11 (acts, executants, signature-box texts)."""

    def run(self, ctx: Context) -> None:
        segments = ctx.scratch["segments"]
        lines, box_texts, kinds = [], {}, []
        for s in segments:
            if not s.is_table:
                continue
            kind = table_kind(s, segments)
            kinds.append(kind)
            if kind == "frais":
                lines += prestation_rows(s.rows, 6)
            elif kind == "lpp":
                lines += prestation_rows(s.rows, 7)
            elif kind == "honoraires":
                acts, texts = honoraires_rows(s.rows)
                lines += acts
                box_texts.update(texts)
        for kind, zone, label in (("frais", 6, "frais de structure"), ("honoraires", 10, "honoraires")):
            if kind not in kinds:
                self.issue(ctx, "warning", f"no '{label}' table found", "lines")
            elif not any(line["zone"] == zone for line in lines):
                self.issue(ctx, "warning", f"the '{label}' table has no readable rows (OCR missed them?)", "lines")
        for line in lines:
            if line["code"] is None:
                self.issue(ctx, "warning", f"line without an act code: {line['raw']}", "lines")
        ctx.record["bordereau"]["lines"] = lines
        ctx.scratch["page_box_texts"] = box_texts


class CheckSignatureBoxes(Transform):
    """Zones 9-11: find the 8 signature boxes on the scan, measure their ink, read their texts (the cached box OCR,
    else what the page OCR caught) and check each box against the zone-10 rows of its executant."""

    def run(self, ctx: Context) -> None:
        texts = {n: (t, "page_ocr") for n, t in ctx.scratch.get("page_box_texts", {}).items()}
        cached = ctx.assets.get("signature_boxes_ocr") or {}
        texts |= {int(n): (t, "box_ocr") for n, t in cached.get("boxes", {}).items() if t}
        image = signatures.analyse_image(ctx.assets.get("image_path"))
        if image is None:
            self.issue(ctx, "info", "no scan available: signature boxes not analysed", "signature_boxes")
        elif not image[0]:
            self.issue(ctx, "warning", "signature column not found on the scan", "signature_boxes")
        rec = ctx.record["bordereau"]
        results = signatures.assess_boxes([l for l in rec["lines"] if l["zone"] == 10], texts, image)
        rec["signature_boxes"] = signatures.as_dicts(results)
        for r in results:
            for problem in r.problems:
                self.issue(ctx, "warning", f"box {r.box}: {problem}", "signature_boxes")


class CheckOcrComplete(Validate):
    """Flag OCR runs that stopped at their token budget: the bottom of the page is then missing."""

    def run(self, ctx: Context) -> None:
        m = re.search(r"([\d,]+) tokens", ctx.bordereau.get("message", ""))
        limit = ctx.bordereau.get("max_tokens", 6144)
        truncated = bool(m) and int(m.group(1).replace(",", "")) >= limit
        ctx.record["bordereau"]["ocr_truncated"] = truncated
        if truncated:
            self.issue(ctx, "warning", f"the OCR hit its {limit}-token limit, the end of the page is missing")


class CheckBordereauSums(Validate):
    """Cross-check the amounts read on the form; a mismatch usually means an OCR misread."""

    def run(self, ctx: Context) -> None:
        rec = ctx.record["bordereau"]

        def total(zone: int) -> int | None:
            amounts = [l["montant"] for l in rec["lines"] if l["zone"] == zone and l["montant"] is not None]
            return sum(amounts) if amounts else None

        def check(label: str, left: int | None, right: int | None) -> None:
            if left is not None and right is not None and left != right:
                self.issue(ctx, "warning", f"{label}: {left / 100:.2f} != {right / 100:.2f}", "amounts")

        st1, st2, st3 = rec["sous_total_1"], rec["sous_total_2"], rec["sous_total_3"]
        check("zone 6 lines vs sous-total 1+2", total(6), (st1 or 0) + (st2 or 0) if st1 is not None else None)
        check("zone 7 lines vs sous-total 3", total(7), st3)
        check("zone 10 lines vs sous-total 4", total(10), rec["sous_total_4"])
        if None not in (st1, st3):
            check("sous-totals 1+2+3", st1 + (st2 or 0) + st3, rec["sous_total_123"])
        if None not in (rec["sous_total_123"], rec["sous_total_4"]):
            check("sous-total 1+2+3 + sous-total 4 vs montant total", rec["sous_total_123"] + rec["sous_total_4"],
                  rec["montant_total"])


# ---- comparison ----------------------------------------------------------------------------------------


class CompareDocuments(Transform):
    """Run the controls (pipeline.compare) between the facture and the bordereau records."""

    def run(self, ctx: Context) -> None:
        layout_errors = None if not ctx.scratch.get("layout_checked") else [  # None: no raw records to check
            i.message for i in ctx.issues if i.step == CheckB2Layout.__name__ and i.severity == "error"]
        results = compare.run_checks(ctx.record["facture"], ctx.record["bordereau"], layout_errors)
        ctx.record["checks"] = compare.results_as_dicts(results)
        ctx.record["assessment"] = compare.assess(results)


# ---- establishment -------------------------------------------------------------------------------------

POSTCODE_CITY = re.compile(r"\b(\d{5})\s+([A-ZÀ-Ý][A-ZÀ-Ý' -]*[A-ZÀ-Ý])(?:\s+CEDEX\b.*)?$")


class IdentifyClinic(Transform):
    """The establishment the pair belongs to: FINESS (both documents), name (B2 type 1), postcode and city (the
    bordereau's address block), department and region (postcode), fund (B2 code organisme)."""

    def run(self, ctx: Context) -> None:
        fac, bor = ctx.record["facture"], ctx.record.get("bordereau", {})
        postcode = city = None
        for s in ctx.scratch.get("segments", []):
            if s.bbox[1] > 130:  # the address sits in the header
                continue
            texts = [c for row in s.rows for c in row] if s.is_table else [s.text]
            for text in texts:
                if m := POSTCODE_CITY.search(text.strip()):
                    postcode, city = m.group(1), m.group(2).strip()
                    break
            if postcode:
                break
        department = geo.department_of_postcode(postcode)
        name = fac.get("nom_etablissement")
        ctx.record["clinic"] = {
            "finess_candidates": [v for v in (bor.get("finess"), fac.get("numero_tiers")) if v],
            "name": " ".join(name.replace("*", " ").split()) if name else None,
            "postal_code": postcode,
            "city": city.title() if city else None,
            "department": department,
            "region": geo.DEPARTMENTS[department][1] if department in geo.DEPARTMENTS else None,
            "caisse": geo.caisse_name(fac.get("code_organisme")),
            "coordinates": geo.CITY_COORDINATES.get(city.upper()) if city else None,
        }
        if not ctx.record["clinic"]["finess_candidates"]:
            self.issue(ctx, "warning", "no FINESS on either document: pair not attached to a clinic", "clinic")
