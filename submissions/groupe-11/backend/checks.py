"""Checks C0-C17 (C10 split into C10 + C10b): compare the B2 text file with the scanned form. Plain deterministic Python.

How it works:
  1. read_b2_file() and read_scan() turn both sources into simple objects with named fields.
  2. Each check is a small function `(b2, scan) -> (ok, attendu, lu)`:
       ok      True / False, or None when it cannot decide
       attendu what the B2 file says (display string)
       lu      what was read on the scan (display string)
  3. run_checks() runs them all and applies the shared status rules (see `status()`).

  uv run python checks.py               # self-test
  uv run python checks.py Facture1_01   # print one invoice's checks
"""
import json
import re
import sys
from dataclasses import dataclass, field

from deserialization.parse_b2 import parse_file
from extract import ROOT, extract

RECEIPTS = ROOT / "receipts"


# ---------------------------------------------------------------- formatting helpers

def cents(euros):
    """818.97 -> 81897. Amounts are always compared in integer cents, never as floats."""
    return None if euros is None else round(euros * 100)


def money(euros):
    """818.97 -> '818,97' for display."""
    return "—" if euros is None else f"{euros:.2f}".replace(".", ",")


def num(number):
    """'000491901' -> '491901': B2 numbers are zero-padded, the form is not."""
    return (number or "").replace(" ", "").lstrip("0")


def codes(values):
    """['GHS', 'PH8', 'GHS'] -> 'GHS, PH8' for display (order kept, duplicates removed)."""
    return ", ".join(dict.fromkeys(v or "?" for v in values)) or "aucun"


# ---------------------------------------------------------------- the two sources

@dataclass
class B2File:
    """What the B2 text file says (one invoice per file)."""
    errors: list                # parser errors, e.g. column shift
    numero_tiers: str | None
    numero_lot: str | None
    numero_facture: str | None
    numero_assure: str | None
    prestations: list           # type-3 lines: {acte, numero_gh}
    actes: list                 # type-4 lines: {acte, details: [{subtype, numero_gh | code_ccam}]}
    total_prestations: float | None
    total_honoraires: float | None

    @property
    def prestation_codes(self):
        return [p["acte"] for p in self.prestations]

    @property
    def ghs(self):
        """NumeroGH of the type-3 'GHS' line."""
        return next((p["numero_gh"] for p in self.prestations if p["acte"] == "GHS"), None)


@dataclass
class Scan:
    """What was read on the scanned form (see extract.py). None = not read."""
    processed: bool             # False until extract.py has OCR'd this image
    unreadable_zones: set
    boxes: dict                 # zone -> [[x0, y0, x1, y1], ...] in image pixels
    cerfa: str | None           # zone 1
    numero_tiers: str | None    # zone 2
    numero_lot: str | None      # zone 3
    numero_facture: str | None  # zone 4
    numero_assure: str | None   # zone 5
    zone6: list                 # frais de structure rows: {acte, numero_gh, montant}
    zone7: list                 # LPP / médicaments rows: {acte, numero_gh}
    sous_total_123: float | None  # zone 8
    executants: list            # zone 9, one per fee row
    zone10: list                # zone 10 codes (code acte or CCAM), one per fee row
    signatures: list | None     # zone 11: 8 booleans, one per practitioner box
    sous_total_4: float | None  # zone 12
    total: float | None         # zone 13
    signature_directeur: bool | None  # zone 14
    form_code: str | None       # zone 15
    scores: dict                # zone -> min OCR line score used to read it (int keys)
    labels: dict = field(default_factory=dict)  # zone -> printed label boxes next to the values (UI crops)
    item_boxes: dict = field(default_factory=dict)  # prestation / act code -> boxes where it is printed

    @property
    def ghs(self):
        """GHS number printed on the 'GHS' row of zone 6."""
        return next((r["numero_gh"] for r in self.zone6 if r["acte"] == "GHS" and r["numero_gh"]), None)


def read_b2_file(name):
    parsed = parse_file(RECEIPTS / f"{name}.txt")
    lot = (parsed["lots"] or [{}])[0]
    facture = (lot.get("factures") or [{}])[0]
    return B2File(
        errors=parsed["errors"],
        numero_tiers=lot.get("numero_tiers"),
        numero_lot=lot.get("numero_lot"),
        numero_facture=facture.get("numero_facture"),
        numero_assure=facture.get("numero_assure"),
        prestations=facture.get("prestations_hospitalieres", []),
        actes=facture.get("actes", []),
        total_prestations=facture.get("total_prestations"),
        total_honoraires=facture.get("total_honoraires"),
    )


def read_scan(name):
    ocr = extract(name)
    if ocr is None:
        return Scan(False, set(range(1, 16)), {}, None, None, None, None, None, [], [], None, [], [],
                    None, None, None, None, None, {})
    sc = ocr["scan"]
    lot = ocr["lots"][0]
    facture = lot["factures"][0]
    scores = {int(z): float(v) for z, v in (sc.get("scores") or {}).items()}
    return Scan(
        processed=True,
        unreadable_zones=set(sc["illisible"]),
        boxes=sc["boxes"],
        cerfa=sc["cerfa"],
        numero_tiers=lot["numero_tiers"],
        numero_lot=lot["numero_lot"],
        numero_facture=facture["numero_facture"],
        numero_assure=facture["numero_assure"],
        zone6=sc["zone6"],
        zone7=sc["zone7"],
        sous_total_123=facture["total_prestations"],
        executants=sc["executants"],
        zone10=[r["code"] for r in sc["zone10"]],
        signatures=sc["signatures"],
        sous_total_4=facture["total_honoraires"],
        total=sc["total"],
        signature_directeur=sc["signature_directeur"],
        form_code=sc["form_code"],
        scores=scores,
        labels=sc.get("labels", {}),
        item_boxes=item_boxes(sc),
    )


def item_boxes(sc):
    """Code -> boxes of the zone 6 / 7 / 10 rows it is printed on, to point at one act or prestation."""
    out = {}
    for r in sc["zone6"] + sc["zone7"] + sc["zone10"]:
        code = r.get("acte") or r.get("code")
        if code and r.get("box"):
            out.setdefault(code, []).append(r["box"])
    return out


# ---------------------------------------------------------------- the checks

def c0_b2_well_formed(b2, scan):
    """The B2 parser reported no error (e.g. Facture2_06 has every column shifted by one)."""
    if not b2.errors:
        return True, "fichier conforme", "fichier conforme"
    first = b2.errors[0]
    what = "décalage de colonnes" if "column shift" in first["message"] else first["message"]
    return False, "fichier conforme", f"Fichier B2 mal formé (ligne {first['line']} : {what})"


def c1_cerfa_number(b2, scan):
    """Zone 1 reads 12278*0 (spec 3.1). OCR often drops the tiny '*' or reads it as '=' (RapidOCR does on
    every Facture1 scan), so '122780' and '12278=0' are accepted: only the digits can make it KO."""
    # Shown as the full printed number "12278*01": with the bare rule "12278*0", the UI diff underlined
    # the trailing "1" of every reading as an error. The check itself still only requires "12278*0".
    if scan.cerfa is None:
        return None, "12278*01", "non lu"
    normalized = scan.cerfa.replace(" ", "")
    return bool(re.search(r"12278[*=]?0", normalized)), "12278*01", scan.cerfa


def same_number(expected, read):
    """Shared by C2-C5: compare two identifiers, ignoring leading zeros and spaces."""
    ok = None if read is None else num(expected) == num(read)
    return ok, expected or "—", read or "non lu"


def c2_finess(b2, scan):
    """Zone 2 = NumeroTiers."""
    return same_number(b2.numero_tiers, scan.numero_tiers)


def c3_lot(b2, scan):
    """Zone 3 = NumeroLot."""
    return same_number(b2.numero_lot, scan.numero_lot)


def c4_invoice_number(b2, scan):
    """Zone 4 = NumeroFacture."""
    return same_number(b2.numero_facture, scan.numero_facture)


def c5_insured_number(b2, scan):
    """Zone 5 (first 13 characters) = NumeroAssure."""
    return same_number(b2.numero_assure, scan.numero_assure)


def c6_ghs(b2, scan):
    """Zone 6 has a GHS row, and its number = NumeroGH of the file's GHS line."""
    ok = None if not scan.zone6 else scan.ghs is not None and num(scan.ghs) == num(b2.ghs)
    return ok, b2.ghs or "GHS absent du fichier", scan.ghs or "GHS absent", {"boxes": scan.item_boxes.get("GHS", [])}


# Words for the per-item lines of the list checks, by grammatical gender
ACTE = ("Acte", "facturé", "présent", "absent")
PRESTATION = ("Prestation", "facturée", "présente", "absente")


def ecarts(kind, scan, b2_only=(), scan_only=()):
    """One line per item found on one side only, so the agent sees exactly what is missing where
    (instead of two full lists to compare). `sens`: which document lacks the item.

    `boxes`: where the item is printed, only for items present on the scan. An item missing from the
    scan has nothing to show: pointing at the acts that *are* printed would only mislead the agent."""
    nom, facture, present, absent = kind
    return ([{"code": c, "sens": "absent_scan", "boxes": [],
              "message": f"{nom} {c} {facture} dans le fichier B2, introuvable sur le bordereau"}
             for c in dict.fromkeys(c or "?" for c in b2_only)]
            + [{"code": c, "sens": "absent_b2", "boxes": scan.item_boxes.get(c, []),
                "message": f"{nom} {c} {present} sur le bordereau, {absent} du fichier B2"}
               for c in dict.fromkeys(c or "?" for c in scan_only)])


def c7_billed_services_in_file(b2, scan):
    """Every zone 6 row with a billed amount is a type-3 line of the file."""
    billed = [r["acte"] for r in scan.zone6 if r["montant"] is not None]
    ok = None if not scan.zone6 else all(code in b2.prestation_codes for code in billed)
    extra = [code for code in billed if code not in b2.prestation_codes]
    return ok, codes(b2.prestation_codes), codes(billed), {"ecarts": ecarts(PRESTATION, scan, scan_only=extra)}


def c8_services_ghs_number(b2, scan):
    """Every type-3 line of the file *other than the GHS one* has NumeroGH = the GHS number read in zone 6
    (rule 3.3). The GHS line itself is C6: checking it here too counted one wrong GHS number twice."""
    others = [p for p in b2.prestations if p["acte"] != "GHS"]
    if not others:
        return True, "aucune autre prestation", "aucune autre prestation"
    ok = None if scan.ghs is None else all(num(p["numero_gh"]) == num(scan.ghs) for p in others)
    return ok, *ghs_pairs([(p["acte"], p["numero_gh"]) for p in others], scan)


def c9_lpp_in_file(b2, scan):
    """Every zone 7 row (LPP / médicaments) is a type-3 line of the file."""
    read = [r["acte"] for r in scan.zone7]
    extra = [code for code in read if code not in b2.prestation_codes]
    return not extra, codes(b2.prestation_codes), codes(read), {"ecarts": ecarts(PRESTATION, scan, scan_only=extra)}


def c10_services_total(b2, scan):
    """Zone 8 (sous-total 1+2+3) = TotalPrestations (rule 3.5, first bullet)."""
    return (cents(scan.sous_total_123) == cents(b2.total_prestations),
            money(b2.total_prestations), money(scan.sous_total_123))


def c10b_services_printed(b2, scan):
    """Every type-3 line of the file is printed in zone 6 or 7 (rule 3.5, second bullet).

    Split from C10 so the agent sees which of the two rules failed, and each card compares one value."""
    printed = [r["acte"] for r in scan.zone6 + scan.zone7]
    missing = [code for code in b2.prestation_codes if code not in printed]
    return not missing, codes(b2.prestation_codes), codes(printed), {"ecarts": ecarts(PRESTATION, scan, b2_only=missing)}


def c11_acts(b2, scan):
    """Zone 10 codes and the file's type-4 acts match both ways.

    On the form, a CCAM act shows its 7-character CCAM code (from its 4-M line), while its
    base line carries a grouping code (ATM, ADC...) that is not printed.
    """
    base_codes = {a["acte"] for a in b2.actes}
    ccam_codes = {d["code_ccam"] for a in b2.actes for d in a["details"] if d.get("code_ccam")}

    def in_file(code):
        return code in ccam_codes if len(code) == 7 else len(code) <= 4 and code in base_codes

    def on_form(act):
        return act["acte"] in scan.zone10 or any(d.get("code_ccam") in scan.zone10 for d in act["details"])

    as_printed = [next((d["code_ccam"] for d in a["details"] if d.get("code_ccam")), a["acte"])
                  for a in b2.actes]
    not_printed = [code for a, code in zip(b2.actes, as_printed) if not on_form(a)]
    not_billed = [c for c in scan.zone10 if not in_file(c)]
    return (not not_printed and not not_billed, codes(as_printed), codes(scan.zone10),
            {"ecarts": ecarts(ACTE, scan, b2_only=not_printed, scan_only=not_billed)})


def c12_acts_ghs_number(b2, scan):
    """Every 4-S line of the file has NumeroGH = the GHS number read in zone 6."""
    # (act as printed on the form: its CCAM code if it has one, else its code acte, NumeroGH of its 4-S line)
    items = [(next((d["code_ccam"] for d in a["details"] if d.get("code_ccam")), a["acte"]), d["numero_gh"])
             for a in b2.actes for d in a["details"] if d["subtype"] == "4-S"]
    if not items:
        return True, "aucune ligne 4-S", "aucune ligne 4-S"
    ok = None if scan.ghs is None else all(num(gh) == num(scan.ghs) for _, gh in items)
    return ok, *ghs_pairs(items, scan)


def ghs_pairs(items, scan):
    """(attendu, lu) for C8 / C12: "code NumeroGH" from the file vs "code <GHS read in zone 6>".

    Only the items whose number is wrong are listed, so the card shows what is actually in error (not the
    correct ones next to it) and the UI diff underlines the wrong digit. All of them when none is wrong."""
    if not scan.ghs:
        return codes(f"{code} {gh}" for code, gh in items), "GHS absent"
    wrong = [(code, gh) for code, gh in items if num(gh) != num(scan.ghs)] or items
    # Highlight the GHS row (the reference number) and the rows of the wrong items, not whole columns
    boxes = scan.item_boxes.get("GHS", []) + [b for code, _ in wrong for b in scan.item_boxes.get(code, [])]
    return (codes(f"{code} {gh}" for code, gh in wrong), codes(f"{code} {scan.ghs}" for code, _ in wrong),
            {"boxes": boxes})


def c13_fees_total(b2, scan):
    """Zone 12 = TotalHonoraires."""
    ok = cents(scan.sous_total_4) == cents(b2.total_honoraires)
    return ok, money(b2.total_honoraires), money(scan.sous_total_4)


def c14_practitioner_signature(b2, scan):
    """If an executant in zone 9 is a person (3rd character != '0'), a box of zone 11 is signed."""
    persons = sorted({e for e in scan.executants if len(e) > 2 and e[2] != "0"})
    signed_boxes = [str(i + 1) for i, signed in enumerate(scan.signatures or []) if signed]
    ok = None if scan.signatures is None else bool(signed_boxes) or not persons
    if not scan.processed:  # zone 9 not read yet: we cannot tell who must sign
        expected = "selon les exécutants (zone 9)"
    elif persons:
        expected = f"signature requise ({', '.join(persons)})"
    else:
        expected = "aucune signature requise (établissement)"
    read = f"signature case {', '.join(signed_boxes)}" if signed_boxes else "aucune signature"
    return ok, expected, read


def c15_grand_total(b2, scan):
    """Zone 13 = zone 8 + zone 12 (both read on the scan)."""
    if scan.sous_total_123 is None or scan.sous_total_4 is None:
        return None, "—", money(scan.total)
    parts = cents(scan.sous_total_123) + cents(scan.sous_total_4)
    ok = None if scan.total is None else cents(scan.total) == parts
    return ok, f"{money(parts / 100)} ({money(scan.sous_total_123)} + {money(scan.sous_total_4)})", money(scan.total)


def c16_director_signature(b2, scan):
    """Zone 14 is signed."""
    read = {None: "non lu", True: "signature présente", False: "signature absente"}[scan.signature_directeur]
    return scan.signature_directeur, "signature présente", read


def c17_form_code(b2, scan):
    """Zone 15 = S3404 (spaces ignored). Like C1, tolerates a known OCR confusion: the small 'S' is
    sometimes read '8' or '5' (the code is the same on every form, so only the digits can be wrong)."""
    if scan.form_code is None:
        return None, "S 3404", "non lu"
    return bool(re.fullmatch(r"[S85]3404", scan.form_code.replace(" ", "").upper())), "S 3404", scan.form_code


#  code, label shown to the agent, scan zones involved, check function
CHECKS = [
    ("C0", "Fichier B2 bien formé", [], c0_b2_well_formed),
    ("C1", "N° Cerfa = 12278*0", [1], c1_cerfa_number),
    ("C2", "N° FINESS = NumeroTiers", [2], c2_finess),
    ("C3", "N° de lot = NumeroLot", [3], c3_lot),
    ("C4", "N° de facture = NumeroFacture", [4], c4_invoice_number),
    ("C5", "N° d'immatriculation = NumeroAssure", [5], c5_insured_number),
    ("C6", "Prestation GHS présente, n° GHS = NumeroGH", [6], c6_ghs),
    ("C7", "Prestations facturées (frais de structure) présentes dans le fichier", [6],
     c7_billed_services_in_file),
    ("C8", "NumeroGH des prestations = n° GHS", [6], c8_services_ghs_number),
    ("C9", "Produits LPP / médicaments présents dans le fichier", [7], c9_lpp_in_file),
    ("C10", "Sous-total 1+2+3 = TotalPrestations", [8], c10_services_total),
    ("C10b", "Prestations du fichier présentes sur le bordereau", [6, 7], c10b_services_printed),
    ("C11", "Actes (code acte / CCAM) = actes du fichier", [10], c11_acts),
    ("C12", "NumeroGH des actes (4-S) = n° GHS", [6, 10], c12_acts_ghs_number),
    ("C13", "Sous-total 4 = TotalHonoraires", [12], c13_fees_total),
    ("C14", "Signature des praticiens exécutants", [9, 11], c14_practitioner_signature),
    ("C15", "Montant total = sous-total 1+2+3 + sous-total 4", [13, 8, 12], c15_grand_total),
    ("C16", "Signature du directeur de l'établissement", [14], c16_director_signature),
    ("C17", "Code formulaire = S 3404", [15], c17_form_code),
]


# ---------------------------------------------------------------- running them

def status(ok, needs_review):
    """OK / KO, or A_VERIFIER when a human must look (unreadable data or undecidable check)."""
    if needs_review or ok is None:
        return "A_VERIFIER"
    return "OK" if ok else "KO"


def confiance_zones(scan, zones):
    """Min OCR line score over a check's zones, or None (no zones, scan unprocessed,
    or zones with no OCR score such as the ink-density signatures 11/14)."""
    valeurs = [scan.scores[z] for z in zones if z in scan.scores]
    return round(min(valeurs), 3) if valeurs else None


# Boxes filed under a non-zone key in extract.py, shown only by the checks they concern
EXTRA_BOXES = {"C7": ["6m"]}  # zone 6 billed amounts: C7 is about the billed prestations


def run_checks(name):
    """All checks for one invoice, in the API format (see PROMPT_BACKEND.md)."""
    b2, scan = read_b2_file(name), read_scan(name)
    results = []
    for code, label, zones, check in CHECKS:
        # Some checks also return options: {"ecarts": per-item lines} (list checks), {"boxes": the exact boxes
        # of the error} (C6, C8, C12), which replace the whole zones' boxes when the check fails
        ok, attendu, lu, *extra = check(b2, scan)
        opts = extra[0] if extra else {}
        needs_review = False
        if zones:  # this check uses the scan
            if not scan.processed:
                needs_review, lu = True, "scan non traité (OCR)"
            elif any(z in scan.unreadable_zones for z in zones):
                needs_review, lu = True, f"{lu} (illisible)"
            if b2.errors:  # malformed B2: its values are garbage, every scan check needs a human
                needs_review = True
        results.append({
            "code": code, "libelle": label, "statut": status(ok, needs_review),
            "attendu": attendu, "lu": lu, "zones": zones,
            "boxes": [box for z in zones + EXTRA_BOXES.get(code, []) for box in scan.boxes.get(str(z), [])],
            "confiance": confiance_zones(scan, zones),
            # Printed labels next to the values: crop context only, not highlighted on the scan
            "contexte": [box for z in zones for box in scan.labels.get(str(z), [])],
        })
        # One line per missing item, only when the check failed (otherwise the lists may be unread).
        # A failed check then points only at the boxes of its error: the items printed on the scan (none if
        # they are all missing from it), or the exact rows a check named
        ko = results[-1]["statut"] == "KO"
        results[-1]["ecarts"] = opts.get("ecarts", []) if ko else []
        if ko and "ecarts" in opts:
            results[-1]["boxes"] = [box for e in opts["ecarts"] for box in e["boxes"]]
        elif ko and opts.get("boxes"):
            results[-1]["boxes"] = opts["boxes"]
    return results


def test():
    b2 = read_b2_file("Facture1_01")
    assert (b2.numero_tiers, b2.numero_lot) == ("200200145", "574")
    assert (b2.numero_assure, b2.numero_facture) == ("2520299007001", "260800001")
    assert (cents(b2.total_prestations), cents(b2.total_honoraires)) == (81897, 2880)
    assert (num("000491901"), money(28.8), cents(398.3)) == ("491901", "28,80", 39830)

    res = {c["code"]: c for c in run_checks("Facture1_01")}
    assert len(res) == 19 and res["C0"]["statut"] == "OK"
    if extract("Facture1_01"):  # needs the OCR cache
        for code in ["C1", "C2", "C3", "C4", "C5", "C6", "C8", "C10", "C10b", "C11", "C12", "C13", "C15", "C17"]:
            assert res[code]["statut"] == "OK", res[code]
        from difficulte import evaluer
        facile = evaluer(run_checks("Facture1_01"), extract("Facture1_01")["scan"])
        assert facile["score"] <= 20 and facile["niveau"] == "Facile", facile
        dur = evaluer(run_checks("Facture2_06"), extract("Facture2_06")["scan"])
        assert dur["score"] >= 40 and dur["details"]["c0_ko"], dur

    res = {c["code"]: c for c in run_checks("Facture2_06")}
    assert res["C0"]["statut"] == "KO" and "décalage de colonnes" in res["C0"]["lu"], res["C0"]
    assert all(c["statut"] == "A_VERIFIER" for k, c in res.items() if k != "C0")
    if extract("Facture3_15"):  # needs the OCR cache: an act billed in the B2 file but not on the form
        c11 = next(c for c in run_checks("Facture3_15") if c["code"] == "C11")
        assert c11["statut"] == "KO" and [e["code"] for e in c11["ecarts"]] == ["JVRP009"], c11
        assert c11["ecarts"][0]["sens"] == "absent_scan" and "introuvable sur le bordereau" in c11["ecarts"][0]["message"]
        assert c11["boxes"] == [], "an act missing from the form: nothing to point at on the scan"
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:]:
        for c in run_checks(sys.argv[1]):
            print(json.dumps(c, ensure_ascii=False))
    else:
        test()
