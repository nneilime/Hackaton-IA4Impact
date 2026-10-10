"""Compare the facture (B2 file) with its bordereau (OCR'd form): controls C1-C22 of CONTEXT.md, plus extra signals.

Every check returns PASS, FAIL or UNVERIFIABLE (a side is missing, usually because the OCR did not read it, or the
check needs a visual inspection the pipeline cannot do). Each check carries:
  category  what it is about (document, identity, prestations, acts, amounts, signatures, file)
  risk      what a failure most likely means: "fraud" (money or identity moved), "error" (clerical / coding mistake)
            or "compliance" (a formality such as a signature)
A failure whose two values differ only by characters the OCR commonly confuses is flagged ocr_suspect: the reviewer
should look at the image before believing it. Details are in French: the review screens show them as they are.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Callable

PASS, FAIL, UNVERIFIABLE = "PASS", "FAIL", "UNVERIFIABLE"
EXPECTED_CERFA_ID_PREFIX = "12278*0"
EXPECTED_CERFA_CODE = "S3404"

# Characters LightOnOCR mixes up on these forms (seen: PH8 -> PHB, 260800008 -> 268800008).
_CONFUSABLE = [set("8B3"), set("0OD6"), set("1I7"), set("5S"), set("2Z"), set("6G"), set("68")]
_CANON = str.maketrans({"B": "8", "O": "0", "D": "0", "I": "1", "S": "5", "Z": "2", "G": "6"})


def ocr_confusable(a: str | None, b: str | None) -> bool:
    """Same length, and every differing character pair is a known OCR confusion."""
    if not a or not b or len(a) != len(b) or a == b:
        return False
    return all(x == y or any({x, y} <= group for group in _CONFUSABLE) for x, y in zip(a.upper(), b.upper()))


def _canon(code: str) -> str:
    return code.upper().translate(_CANON)


def _in(code: str, pool: set[str]) -> str | None:
    """"exact" or "ocr" when code is in pool (directly / after OCR normalisation), else None."""
    if code in pool:
        return "exact"
    return "ocr" if _canon(code) in {_canon(p) for p in pool} else None


def _same_number(a: str | None, b: str | None) -> bool:
    if a and b and a.isdigit() and b.isdigit():
        return int(a) == int(b)
    return a == b


def _euros(cents: int | None) -> str | None:
    return None if cents is None else f"{cents / 100:.2f}"


@dataclass
class CheckResult:
    code: str
    label: str
    category: str
    risk: str
    status: str
    expected: str | None = None  # the reference value, from expected_source
    found: str | None = None  # the value checked, from found_source
    detail: str = ""
    ocr_suspect: bool = False
    expected_source: str = "b2"
    found_source: str = "form"


# Where a check's two values come from. Most compare the B2 file (reference) with the form; some check the form
# against a CERFA rule or against its own figures, and C9 / X1 look at the B2 file alone.
SOURCES = {
    "b2": "the B2 file",
    "form": "the bordereau, as read by the OCR",
    "rule": "a rule of the CERFA form (a fixed expected value)",
    "form_calc": "a calculation on the bordereau's own figures",
    "scan": "the image analysis of the scan",
}


@dataclass
class Check:
    code: str
    label: str
    category: str
    risk: str
    fn: Callable[["Sides"], tuple]
    expected_from: str = "b2"
    found_from: str = "form"


CHECKS: list[Check] = []


def check(code: str, label: str, category: str, risk: str, expected_from: str = "b2", found_from: str = "form"):
    assert expected_from in SOURCES and found_from in SOURCES
    def register(fn: Callable) -> Callable:
        CHECKS.append(Check(code, label, category, risk, fn, expected_from, found_from))
        return fn
    return register


@dataclass
class Sides:
    """What the checks look at, pre-digested from the record."""
    f: dict  # facture record
    b: dict  # bordereau record
    layout_errors: list[str] | None  # None when the raw B2 lines were not available

    def zone(self, n: int) -> list[dict]:
        return [l for l in self.b.get("lines", []) if l["zone"] == n]

    def file_main(self, record_type: str) -> list[dict]:
        return [l for l in self.f["lines"] if l["record_type"] == record_type and not l["sub_type"]]

    def form_ghs(self) -> str | None:
        return next((l["numero_gh"] for l in self.zone(6) if l["code"] == "GHS" and l["numero_gh"]), None)

    def expected_zone10(self) -> list[str] | None:
        """What zone 10 should show for the type-4 records: the CCAM code when a 4-M follows the act, else the act."""
        if not self.f.get("ordered", True):
            return None
        out: list[str] = []
        for l in self.f["lines"]:
            if l["record_type"] != "4":
                continue
            if not l["sub_type"]:
                out.append(l["acte"] or "")
            elif l["sub_type"] == "M" and l["code_ccam"] and out:
                out[-1] = l["code_ccam"]
        return out


def _compare(expected: str | None, found: str | None, equal: bool, what: str) -> tuple:
    if expected is None or found is None:
        missing = "dans le fichier B2" if expected is None else "sur le bordereau (OCR)"
        return UNVERIFIABLE, expected, found, f"{what} : absent {missing}"
    if equal:
        return PASS, expected, found, ""
    return FAIL, expected, found, f"{what} différent", ocr_confusable(expected, found)


# ---- 3.1 document identifier --------------------------------------------------------------------------


@check("C1", "Zone 1 CERFA identifier is 12278*0x", "document", "fraud", expected_from="rule")
def _c1(s: Sides) -> tuple:
    found = s.b.get("cerfa_id")
    if found is None:
        return UNVERIFIABLE, EXPECTED_CERFA_ID_PREFIX + "x", None, "identifiant CERFA non lu"
    ok = found.startswith(EXPECTED_CERFA_ID_PREFIX)
    return (PASS if ok else FAIL), EXPECTED_CERFA_ID_PREFIX + "x", found, "" if ok else "ce n'est pas un formulaire 12278*0x", \
        not ok and ocr_confusable(found[:7], EXPECTED_CERFA_ID_PREFIX)


# ---- 3.2 identification keys --------------------------------------------------------------------------


@check("C2", "Zone 2 FINESS = NumeroTiers", "identity", "fraud")
def _c2(s: Sides) -> tuple:
    return _compare(s.f["numero_tiers"], s.b.get("finess"), _same_number(s.f["numero_tiers"], s.b.get("finess")),
                    "n° d'établissement")


@check("C3", "Zone 3 N° LOT = NumeroLot", "identity", "error")
def _c3(s: Sides) -> tuple:
    return _compare(s.f["numero_lot"], s.b.get("numero_lot"),
                    _same_number(s.f["numero_lot"], s.b.get("numero_lot")), "n° de lot")


@check("C4", "Zone 4 N° FACTURE = NumeroFacture", "identity", "fraud")
def _c4(s: Sides) -> tuple:
    return _compare(s.f["numero_facture"], s.b.get("numero_facture"),
                    _same_number(s.f["numero_facture"], s.b.get("numero_facture")), "n° de facture")


@check("C5", "Zone 5 n° immatriculation (13 chars) = NumeroAssure", "identity", "fraud")
def _c5(s: Sides) -> tuple:
    expected = (s.f["numero_assure"] or "")[:13] or None
    return _compare(expected, s.b.get("numero_assure"), expected == s.b.get("numero_assure"), "n° d'assuré")


# ---- 3.3 frais de structure et de soins (zone 6) ------------------------------------------------------


@check("C6", "Zone 6 has a GHS prestation with its GHS number", "prestations", "error", expected_from="rule")
def _c6(s: Sides) -> tuple:
    if not s.zone(6):
        return UNVERIFIABLE, "GHS + n°", None, "aucune ligne de la zone 6 lue par l'OCR"
    ghs = s.form_ghs()
    return (PASS, "GHS + n°", f"GHS {ghs}", "") if ghs else (FAIL, "GHS + n°", None, "pas de ligne GHS en zone 6")


@check("C7", "Zone 6 GHS number = NumeroGH of the type-3 GHS act", "prestations", "error")
def _c7(s: Sides) -> tuple:
    return _compare(s.f["numero_gh"], s.form_ghs(), s.f["numero_gh"] == s.form_ghs(), "n° GHS")


def _codes_in(codes: list[str], pool: set[str], where: str, codes_side: str = "form") -> tuple:
    """Every code must be in pool. codes_side says which document the codes come from ("form" or "file")."""
    missing, fuzzy = [], []
    for code in codes:
        how = _in(code, pool)
        if how is None:
            missing.append(code)
        elif how == "ocr":
            fuzzy.append(code)
    codes_text, pool_text = ", ".join(codes) or None, ", ".join(sorted(pool)) or None
    expected, found = (pool_text, codes_text) if codes_side == "form" else (codes_text, pool_text)
    if missing:
        return FAIL, expected, found, f"absent {where} : {', '.join(missing)}", False
    note = f"trouvé seulement en corrigeant une erreur de lecture OCR : {', '.join(fuzzy)}" if fuzzy else ""
    return PASS, expected, found, note


@check("C8", "Zone 6 billed prestations exist as type-3 acts", "prestations", "error")
def _c8(s: Sides) -> tuple:
    if not s.zone(6):
        return UNVERIFIABLE, None, None, "aucune ligne de la zone 6 lue par l'OCR"
    billed = [l["code"] for l in s.zone(6) if l["montant"]]
    return _codes_in(billed, {l["acte"] for l in s.file_main("3") if l["acte"]}, "des actes de type 3 du fichier")


@check("C9", "Type-3 acts other than GHS carry the GHS act's NumeroGH", "file", "error", found_from="b2")
def _c9(s: Sides) -> tuple:
    ghs = s.f["numero_gh"]
    if ghs is None:
        return UNVERIFIABLE, None, None, "pas d'acte GHS de type 3 dans le fichier"
    wrong = [f"{l['acte']}={l['numero_gh']}" for l in s.file_main("3") if l["acte"] != "GHS" and l["numero_gh"] != ghs]
    return (FAIL, ghs, ", ".join(wrong), "NumeroGH différent") if wrong else (PASS, ghs, ghs, "")


# ---- 3.4 LPP / pharmacie (zone 7) ---------------------------------------------------------------------


@check("C10", "Type-3 NumeroGH = GHS number read in zone 6", "prestations", "error")
def _c10(s: Sides) -> tuple:
    ghs = s.form_ghs()
    if ghs is None:
        return UNVERIFIABLE, None, None, "aucun n° GHS lu en zone 6"
    wrong = [f"{l['acte']}={l['numero_gh']}" for l in s.file_main("3") if l["numero_gh"] != ghs]
    if wrong:
        return FAIL, ", ".join(wrong), ghs, "actes de type 3 avec un autre GH", any(
            ocr_confusable(l["numero_gh"], ghs) for l in s.file_main("3"))
    return PASS, ghs, ghs, ""


@check("C11", "Zone 7 prestations exist as type-3 acts", "prestations", "error")
def _c11(s: Sides) -> tuple:
    codes = [l["code"] for l in s.zone(7)]
    if not codes:
        return PASS, None, None, "aucune prestation en zone 7 sur le bordereau"
    return _codes_in(codes, {l["acte"] for l in s.file_main("3") if l["acte"]}, "des actes de type 3 du fichier")


# ---- 3.5 recap zones 6 + 7 ----------------------------------------------------------------------------


@check("C12", "Zone 8 sous-total 1+2+3 = TotalPrestations", "amounts", "fraud")
def _c12(s: Sides) -> tuple:
    a, b = s.f["total_prestations"], s.b.get("sous_total_123")
    return _compare(_euros(a), _euros(b), a == b, "total des prestations")


@check("C13", "Every type-3 act appears in zone 6 or 7", "prestations", "fraud")
def _c13(s: Sides) -> tuple:
    if not s.zone(6):
        return UNVERIFIABLE, None, None, "aucune ligne de la zone 6 lue par l'OCR"
    on_form = {l["code"] for l in s.zone(6) + s.zone(7) if l["code"]}
    return _codes_in([l["acte"] for l in s.file_main("3") if l["acte"]], on_form, "des zones 6-7 du bordereau", "file")


# ---- 3.6 honoraires (zones 9-12) ----------------------------------------------------------------------


@check("C14", "Zone 10 codes of <= 4 chars exist as type-4 acts", "acts", "error")
def _c14(s: Sides) -> tuple:
    if not s.zone(10):
        return UNVERIFIABLE, None, None, "aucune ligne de la zone 10 lue par l'OCR"
    codes = [l["code"] for l in s.zone(10) if l["code"] and len(l["code"]) <= 4]
    return _codes_in(codes, {l["acte"] for l in s.file_main("4") if l["acte"]}, "des actes de type 4 du fichier")


@check("C15", "Zone 10 codes of 7 chars exist as 4-M CCAM codes", "acts", "error")
def _c15(s: Sides) -> tuple:
    if not s.zone(10):
        return UNVERIFIABLE, None, None, "aucune ligne de la zone 10 lue par l'OCR"
    codes = [l["code"] for l in s.zone(10) if l["code"] and len(l["code"]) == 7]
    pool = {l["code_ccam"] for l in s.f["lines"] if l["sub_type"] == "M" and l["code_ccam"]}
    return _codes_in(codes, pool, "des codes CCAM du fichier")


@check("C16", "4-S NumeroGH = GHS number read in zone 6", "acts", "error")
def _c16(s: Sides) -> tuple:
    ghs = s.form_ghs()
    values = [l["numero_gh"] for l in s.f["lines"] if l["record_type"] == "4" and l["sub_type"] == "S"]
    if ghs is None:
        return UNVERIFIABLE, None, None, "aucun n° GHS lu en zone 6"
    wrong = [v for v in values if v != ghs]
    return (FAIL, ", ".join(map(str, wrong)), ghs, "lignes 4-S avec un autre GH") if wrong else (PASS, ghs, ghs, "")


@check("C17", "Zone 12 sous-total 4 = TotalHonoraires", "amounts", "fraud")
def _c17(s: Sides) -> tuple:
    a, b = s.f["total_honoraires"], s.b.get("sous_total_4")
    return _compare(_euros(a), _euros(b), a == b, "total des honoraires")


@check("C18", "Each non-establishment executant has signed a zone-11 box", "signatures", "compliance",
       expected_from="form", found_from="scan")
def _c18(s: Sides) -> tuple:
    if not s.zone(10):
        return UNVERIFIABLE, None, None, "aucune ligne de la zone 10 lue par l'OCR"
    needed = sorted({l["executant"] for l in s.zone(10) if l["executant"] and l["executant"][2] != "0"})
    if not needed:
        return PASS, None, None, "seuls des établissements (3e caractère 0) exécutent les actes"
    boxes = s.b.get("signature_boxes") or []
    if not any(b["signed"] is not None for b in boxes):
        return UNVERIFIABLE, ", ".join(needed), None, "scan non analysé : vérifiez les cases de signature sur l'image"

    def box_of(b: dict) -> set[str]:
        """Executants a signed box covers: the one it prints, else those of the rows whose n° de case is it."""
        if b["printed_executant"]:
            return {b["printed_executant"]}
        return {l["executant"] for l in s.zone(10) if l.get("case") == b["box"] and l["executant"]}

    signed = [b for b in boxes if b["signed"]]
    covered = set().union(*(box_of(b) for b in signed)) if signed else set()
    unsigned = [e for e in needed if e not in covered]
    found = ", ".join(f"case {b['box']} : {', '.join(sorted(box_of(b))) or '?'}" for b in signed) or None
    if not unsigned:
        return PASS, ", ".join(needed), found, ""
    unattributed = [b["box"] for b in signed if not box_of(b)]
    if unattributed:
        return UNVERIFIABLE, ", ".join(needed), found, \
            f"aucune signature attribuée à {', '.join(unsigned)} ; case(s) signée(s) {unattributed} illisible(s) : " \
            "vérifiez l'image"
    return FAIL, ", ".join(needed), found, f"aucune case signée pour {', '.join(unsigned)}"


@check("C19", "Every type-4 act / CCAM code appears in zone 10", "acts", "fraud")
def _c19(s: Sides) -> tuple:
    if not s.zone(10):
        return UNVERIFIABLE, None, None, "aucune ligne de la zone 10 lue par l'OCR"
    on_form = {l["code"] for l in s.zone(10) if l["code"]}
    expected = s.expected_zone10()
    if expected is None:  # file order unknown: only the CCAM codes can be checked
        expected = [l["code_ccam"] for l in s.f["lines"] if l["sub_type"] == "M" and l["code_ccam"]]
    return _codes_in(expected, on_form, "de la zone 10 du bordereau", "file")


# ---- 3.7 conclusion / 3.8 CERFA code ------------------------------------------------------------------


@check("C20", "Zone 13 total = zone 8 + zone 12", "amounts", "fraud", expected_from="form_calc")
def _c20(s: Sides) -> tuple:
    st123, st4, total = s.b.get("sous_total_123"), s.b.get("sous_total_4"), s.b.get("montant_total")
    expected = None if st123 is None or st4 is None else st123 + st4
    return _compare(_euros(expected), _euros(total), expected == total, "total du bordereau par rapport à ses sous-totaux")


@check("C21", "Director's signature in zone 14", "signatures", "compliance", expected_from="rule")
def _c21(s: Sides) -> tuple:
    if s.b.get("director_signature"):
        return PASS, "signée", "signée", "mention de signature numérique trouvée"
    return UNVERIFIABLE, "signée", None, "pas de mention de signature : vérifiez la zone 14 sur l'image"


@check("C22", "Zone 15 CERFA code = S3404", "document", "fraud", expected_from="rule")
def _c22(s: Sides) -> tuple:
    found = s.b.get("cerfa_code")
    return _compare(EXPECTED_CERFA_CODE, found, found == EXPECTED_CERFA_CODE, "code CERFA")


# ---- extra signals ------------------------------------------------------------------------------------


@check("X1", "B2 file layout: consistent tiers, no shifted fields", "file", "fraud", found_from="b2")
def _x1(s: Sides) -> tuple:
    if s.layout_errors is None:
        return UNVERIFIABLE, None, None, "enregistrements B2 bruts absents : structure non vérifiée"
    if s.layout_errors:
        return FAIL, None, None, "; ".join(s.layout_errors)
    return PASS, None, None, ""


@check("X2", "No act billed more often in the file than shown on the form", "acts", "fraud")
def _x2(s: Sides) -> tuple:
    if not s.zone(6) or not s.zone(10) or not s.f.get("ordered", True):
        return UNVERIFIABLE, None, None, "nécessite les zones 6 et 10 lues et l'ordre des enregistrements du fichier"
    file_codes = [l["acte"] for l in s.file_main("3") if l["acte"]] + (s.expected_zone10() or [])
    billed = Counter(_canon(c) for c in file_codes)
    shown = Counter(_canon(l["code"]) for l in s.b["lines"] if l["code"])
    names = {_canon(c): c for c in file_codes}  # report the file's spelling, not the normalised key
    extra = {names[code]: n - shown[code] for code, n in billed.items() if n > shown[code]}
    expected, found = ", ".join(sorted(file_codes)), ", ".join(sorted(l["code"] for l in s.b["lines"] if l["code"]))
    if extra:
        return FAIL, expected, found, "facturé plus de fois que sur le bordereau : " + ", ".join(
            f"{c or '(vide)'} +{n}" for c, n in sorted(extra.items()))
    return PASS, expected, found, ""


@check("X3", "Zone 11 box totals match their executant's zone-10 fees", "amounts", "fraud",
       expected_from="form_calc", found_from="scan")
def _x3(s: Sides) -> tuple:
    boxes = s.b.get("signature_boxes") or []
    if not any(b["signed"] is not None for b in boxes):
        return UNVERIFIABLE, None, None, "scan non analysé"
    printed = [b for b in boxes if b["printed_amount"] is not None]
    if not printed:
        if any(b["signed"] for b in boxes) and any(b["text"] is None for b in boxes if b["signed"]):
            return UNVERIFIABLE, None, None, "cases signées non lues : lancez check_signatures.py --ocr"
        return PASS, None, None, "aucun total imprimé dans les cases"
    bad = [f"case {b['box']} : {'; '.join(b['problems'])}" for b in boxes
           if b["amount_ok"] is False or b["executant_ok"] is False]
    expected = ", ".join(f"case {b['box']} {_euros(b['computed_amount']) or '?'}" for b in printed)
    found = ", ".join(f"case {b['box']} {_euros(b['printed_amount'])}" for b in printed)
    st4 = s.b.get("sous_total_4")
    if st4 is not None and all(b["printed_amount"] is not None for b in boxes if b["signed"]):
        total = sum(b["printed_amount"] for b in printed)
        if total != st4:
            bad.append(f"les totaux des cases font {_euros(total)}, le sous-total 4 est de {_euros(st4)}")
    off = [b for b in printed if b["amount_ok"] is False or b["executant_ok"] is False]
    row_totals = [0 if not b["rows"] else b["computed_amount"] for b in off]  # a box left without rows counts 0
    if len(off) > 1 and len(off) == len(bad) and None not in row_totals and \
            sum(b["printed_amount"] for b in off) == sum(row_totals):
        # the differences cancel out: an amount moved between boxes, i.e. a zone-10 row attributed to the wrong
        # executant, which is what the OCR does when it misreads a row; real changes move the total
        return UNVERIFIABLE, expected, found, "les écarts entre cases se compensent (probable erreur de lecture OCR " \
            "d'une ligne, vérifiez le scan) : " + " | ".join(bad)
    if bad:
        return FAIL, expected, found, " | ".join(bad)
    unchecked = [b["box"] for b in printed if b["amount_ok"] is None]
    return PASS, expected, found, f"case(s) {unchecked} non vérifiable(s) (honoraires des lignes manquants)" \
        if unchecked else ""


# ---- assessment ---------------------------------------------------------------------------------------

RISK_WEIGHT = {"fraud": 3.0, "error": 1.0, "compliance": 1.0}
# Checks whose UNVERIFIABLE does not block a CORRECT guess: they depend on the scan / signatures, which the
# reviewer always looks at anyway.
NON_BLOCKING = {"C18", "C21", "X3"}


def run_checks(facture: dict, bordereau: dict, layout_errors: list[str] | None) -> list[CheckResult]:
    sides = Sides(facture, bordereau, layout_errors)
    results = []
    for c in CHECKS:
        status, expected, found, detail, *rest = c.fn(sides)
        results.append(CheckResult(c.code, c.label, c.category, c.risk, status, expected, found, detail,
                                   bool(rest and rest[0]), c.expected_from, c.found_from))
    return results


def assess(results: list[CheckResult]) -> dict:
    """CORRECT only when nothing failed and every non-visual check could be verified; the score orders the queue."""
    failed = [r for r in results if r.status == FAIL]
    unverifiable = [r for r in results if r.status == UNVERIFIABLE]
    blocking = [r for r in unverifiable if r.code not in NON_BLOCKING]
    score = sum(RISK_WEIGHT[r.risk] * (0.3 if r.ocr_suspect else 1) for r in failed) + 0.2 * len(unverifiable)
    return {"verdict": "ISSUES" if failed or blocking else "CORRECT", "risk_score": round(score, 2),
            "failed": [r.code for r in failed], "unverifiable": [r.code for r in unverifiable],
            "fraud_signals": [r.code for r in failed if r.risk == "fraud" and not r.ocr_suspect]}


def results_as_dicts(results: list[CheckResult]) -> list[dict]:
    return [asdict(r) for r in results]
