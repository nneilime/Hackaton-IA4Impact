"""Dashboard statistics — computed on-the-fly from check results and decisions.

Public API:
    compute_stats(names, checks_fn) -> dict

The function receives its dependencies as arguments so it can be tested
without FastAPI or filesystem access.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from checks import CHECKS

# Build a {code: label} map from the CHECKS registry
LIBELLES = {code: label for code, label, *_ in CHECKS}

# Checks whose attendu/lu fields carry monetary amounts (euros).
_AMOUNT_CHECKS = {"C10", "C13", "C15"}

# Anomaly categories: each check belongs to exactly one category.
# Weights reflect investigative severity (financial > identity > format).
CATEGORIES: dict[str, dict] = {
    "Format":      {"codes": {"C0", "C17"},                   "weight": 1},
    "Identité":    {"codes": {"C1", "C2", "C3", "C4", "C5"}, "weight": 3},
    "Prestations": {"codes": {"C6", "C7", "C8", "C9", "C10", "C10b"}, "weight": 4},
    "Honoraires":  {"codes": {"C11", "C12", "C13"},           "weight": 4},
    "Signatures":  {"codes": {"C14", "C16"},                   "weight": 2},
}
# Max possible score per invoice = sum of all category weights (all categories triggered)
_MAX_SCORE_PER_INVOICE = sum(v["weight"] for v in CATEGORIES.values())  # 14


def parse_amount(s: str | None) -> float | None:
    """Parse a French monetary string to float euros, or return None.

    Handles:
    - Comma or dot decimal separator: "818,97" -> 818.97
    - Spaces as thousands separator: "1 234,56" -> 1234.56
    - Compound C10 strings: "818,97 ; GHS, PH8" -> 818.97 (takes part before " ; ")
    - Non-numeric values: "—", "non lu", "" -> None
    """
    if not s:
        return None
    s = s.split(" ; ")[0]
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _invoice_score(checks: list[dict]) -> tuple[float | None, float, dict[str, int]]:
    """Return (montant_total, score, category_hits) for one invoice's check list.

    montant_total  — parse_amount of C15 lu (MONTANT TOTAL from scan), or None.
    score          — weighted severity score for this invoice (0..14).
    category_hits  — {category_name: 1} for each category that has at least one KO check.
    """
    total = None
    category_hits: dict[str, int] = {}

    for c in checks:
        code = c["code"]
        if code == "C15":
            total = parse_amount(c["lu"])
        if c["statut"] == "KO":
            for cat, meta in CATEGORIES.items():
                if code in meta["codes"]:
                    category_hits[cat] = 1  # flag this category once

    score = sum(CATEGORIES[cat]["weight"] for cat in category_hits)
    return total, float(score), category_hits


def compute_stats(
    names: list[str],
    checks_fn: Callable[[str], list[dict]],
    scanned_fn: Callable[[str], bool] = lambda _: True,
    difficulte_fn: Callable[[str, list[dict]], dict] | None = None,
) -> dict:
    """Compute all dashboard statistics and return them as a plain dict.

    Args:
        names:          Sorted list of all valid invoice IDs.
        checks_fn:      Callable[id] -> list of check dicts (C0-C17).
        scanned_fn:     Callable[id] -> bool — True only when the OCR scan cache exists.
                        Invoices not yet scanned are excluded from every counter and ranking.
                        Defaults to lambda returning True (backward-compatible for tests).
        difficulte_fn:  Callable[id, checks] -> {score, niveau, details} — review difficulty.
                        When None, difficulty stats are omitted from the response.
    """
    # ------------------------------------------------------------------ #
    # Per-invoice data collection                                          #
    # ------------------------------------------------------------------ #
    repartition: dict[str, dict[str, int]] = {
        code: {"KO": 0, "A_VERIFIER": 0} for code in LIBELLES
    }

    # Category counters: {cat: nb_invoices_with_ko_in_this_cat}
    category_counts: dict[str, int] = {cat: 0 for cat in CATEGORIES}

    etab: dict[str, dict] = defaultdict(lambda: {
        "nb_factures": 0, "nb_ko": 0, "nb_a_verifier": 0, "nb_conformes": 0,
        "montant_a_risque": 0.0, "score_total": 0.0,
        "difficulte_sum": 0.0, "difficulte_count": 0,
    })

    # Difficulty distribution across all scanned invoices: {niveau: count}
    _NIVEAUX = ["Facile", "Modérée", "Moyenne", "Difficile", "Très difficile"]
    difficulte_dist: dict[str, int] = {n: 0 for n in _NIVEAUX}
    difficulte_sum_global = 0.0
    difficulte_count_global = 0

    nb_total = 0               # only invoices that passed scanned_fn
    nb_ko_total = 0
    nb_a_verifier_total = 0
    montant_a_risque_total = 0.0
    score_total = 0.0          # sum of per-invoice scores across all KO invoices

    for name in names:
        if not scanned_fn(name):
            continue   # exclude invoices whose scan has not been OCR'd yet

        nb_total += 1
        checks = checks_fn(name)

        diff = difficulte_fn(name, checks) if difficulte_fn else None

        # Malformed B2 file (C0 KO): the other checks come back A_VERIFIER only because the file's values
        # are shifted, i.e. they were not evaluated. Count the invoice once, under C0, not as 17 anomalies.
        b2_ko = any(c["code"] == "C0" and c["statut"] == "KO" for c in checks)
        counted = [c for c in checks if c["code"] == "C0"] if b2_ko else checks

        statuts = [c["statut"] for c in counted]
        has_ko = "KO" in statuts
        has_av = "A_VERIFIER" in statuts

        # Per-check repartition
        for c in counted:
            code = c["code"]
            if code in repartition:
                if c["statut"] == "KO":
                    repartition[code]["KO"] += 1
                elif c["statut"] == "A_VERIFIER":
                    repartition[code]["A_VERIFIER"] += 1

        # Global counters
        if has_ko:
            nb_ko_total += 1
        elif has_av:
            nb_a_verifier_total += 1

        # Amounts + score
        total = _invoice_score(checks)[0]  # the scan's printed total does not depend on the B2 file
        _, inv_score, cat_hits = _invoice_score(counted)
        if has_ko or has_av:
            if total is not None:
                montant_a_risque_total += total
        if has_ko:
            score_total += inv_score
            for cat in cat_hits:
                category_counts[cat] += 1

        # FINESS — use "B2 mal formé" for column-shifted files to avoid polluting the ranking
        c0 = next((c for c in checks if c["code"] == "C0"), None)
        c2 = next((c for c in checks if c["code"] == "C2"), None)
        finess = (c2["attendu"] if c2 else None) or "inconnu"
        if finess in ("—", ""):
            finess = "inconnu"
        if c0 and c0["statut"] == "KO":
            finess = "B2 mal formé"

        e = etab[finess]
        e["nb_factures"] += 1
        if has_ko:
            e["nb_ko"] += 1
        elif has_av:
            e["nb_a_verifier"] += 1
        else:
            e["nb_conformes"] += 1
        if has_ko or has_av:
            if total is not None:
                e["montant_a_risque"] += total
        if has_ko:
            e["score_total"] += inv_score
        if diff is not None:
            e["difficulte_sum"] += diff["score"]
            e["difficulte_count"] += 1
            niv = diff["niveau"]
            if niv in difficulte_dist:
                difficulte_dist[niv] += 1
            difficulte_sum_global += diff["score"]
            difficulte_count_global += 1

    # ------------------------------------------------------------------ #
    # anomalie section                                                       #
    # ------------------------------------------------------------------ #
    # Fraud score 0–100: average invoice score / max possible score * 100
    # (only KO invoices contribute; 0 if no KO)
    fraud_score = 0.0
    if nb_ko_total > 0:
        fraud_score = round((score_total / nb_ko_total) / _MAX_SCORE_PER_INVOICE * 100, 1)

    anomalie = {
        "nb_factures_total": nb_total,
        "nb_factures_ko": nb_ko_total,
        "nb_factures_a_verifier": nb_a_verifier_total,
        "montant_total_a_risque": round(montant_a_risque_total, 2),
        # New metrics replacing montant_ecarts_detectes
        "score_anomalie": fraud_score,
        "repartition_par_categorie": [
            {
                "categorie": cat,
                "nb_invoices_ko": category_counts[cat],
                "poids": CATEGORIES[cat]["weight"],
                "description": _CATEGORY_DESC[cat],
            }
            for cat in CATEGORIES
        ],
        "repartition_par_check": [
            {
                "code": code,
                "libelle": LIBELLES[code],
                "nb_ko": repartition[code]["KO"],
                "nb_a_verifier": repartition[code]["A_VERIFIER"],
            }
            for code in LIBELLES
        ],
    }

    # ------------------------------------------------------------------ #
    # etablissements section                                               #
    # ------------------------------------------------------------------ #
    etablissements = []
    for finess, e in etab.items():
        nb = e["nb_factures"]
        nb_ko = e["nb_ko"]
        diff_moy = round(e["difficulte_sum"] / e["difficulte_count"], 1) if e["difficulte_count"] else None
        entry: dict = {
            "finess": finess,
            "nb_factures": nb,
            "nb_ko": nb_ko,
            "nb_a_verifier": e["nb_a_verifier"],
            "taux_conformite": round(e["nb_conformes"] / nb, 4) if nb else 0.0,
            "montant_a_risque": round(e["montant_a_risque"], 2),
            # Per-establishment score (same 0–100 normalisation)
            "score_anomalie": round(
                (e["score_total"] / nb_ko) / _MAX_SCORE_PER_INVOICE * 100, 1
            ) if nb_ko else 0.0,
        }
        if difficulte_fn is not None:
            from difficulte import niveau as _niveau
            entry["difficulte_moyenne"] = diff_moy
            entry["niveau_moyen"] = _niveau(round(diff_moy)) if diff_moy is not None else None
        etablissements.append(entry)
    etablissements.sort(key=lambda x: (-x["nb_ko"], -x["nb_a_verifier"]))

    if difficulte_fn is not None:
        anomalie["difficulte_globale"] = {
            "moyenne": round(difficulte_sum_global / difficulte_count_global, 1) if difficulte_count_global else None,
            "repartition": [{"niveau": n, "nb": difficulte_dist[n]} for n in _NIVEAUX],
        }

    return {
        "anomalie": anomalie,
        "etablissements": etablissements,
    }


# Human-readable descriptions for each category (used in the API response)
_CATEGORY_DESC: dict[str, str] = {
    "Format":      "Fichier B2 mal formé ou code formulaire incorrect (C0, C17)",
    "Identité":    "Numéro Cerfa, FINESS, lot, facture ou assuré incorrect (C1–C5)",
    "Prestations": "GHS, prestations facturées, numéros GHS ou sous-total incorrect (C6–C10)",
    "Honoraires":  "Actes, codes CCAM, numéros GHS 4-S ou sous-total honoraires incorrect (C11–C13)",
    "Signatures":  "Signature praticien ou directeur absente (C14, C16)",
}
