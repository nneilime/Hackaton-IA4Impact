"""The B2 fixed-width invoice format (the "facture" side).

For each invoice file, extracts the fields listed in the "Données" column of "Les contrôles à implémenter" (see
CONTEXT.md §2.3). Positions are 1-based and inclusive as in the spec; lines are sliced strictly by position.

parse_lines() returns the JSON written by parse_factures_txt.py, plus "Lignes": the type-3/4 records in file order,
which the comparison needs to tie each type-4 act to its 4-M CCAM complement.
"""

from __future__ import annotations

import re
from pathlib import Path

RECORD_TYPES = "0123456"


def field(line: str, start: int, end: int) -> str | None:
    """Return the 1-based inclusive slice [start, end] of a line, stripped (None if empty)."""
    value = line[start - 1:end].strip()
    return value or None


def char_at(line: str, pos: int) -> str:
    return line[pos - 1] if len(line) >= pos else ""


def amount(raw: str | None) -> float | None:
    """(6+2)N amount: last 2 digits are cents."""
    if raw is None or not raw.isdigit():
        return None
    return int(raw) / 100


def subtype(line: str) -> str:
    """Return the record type with its optional sub-type (e.g. '3', '3-S', '4-M')."""
    kind = line[0]
    if kind in ("2", "3") and char_at(line, 39) == "S":
        return kind + "-S"
    if kind == "3" and char_at(line, 36) == "H":
        return "3-H"
    if kind == "4" and char_at(line, 36) in ("S", "M", "B"):
        return "4-" + char_at(line, 36)
    return kind


def parse_lines(lines: list[str], name: str | None = None) -> dict:
    data = {
        "Fichier": name,
        "NumeroTiers": None,
        "NumeroLot": None,
        "NumeroAssure": None,
        "NumeroFacture": None,
        "Acte_Type3": [],
        "NumeroGH_Type3": [],  # aligned with Acte_Type3
        "Acte_Type4": [],
        "NumeroGH_Type4S": [],
        "CodeCCAM_Type4M": [],
        "TotalPrestations": None,
        "TotalHonoraires": None,
        "NomEtablissement": None,  # type 1, positions 30-61
        "DateFichier": None,  # type 1, the YYMMDD after "B2", as YYYY-MM-DD
        "CodeOrganisme": None,  # type 2, positions 49-56: régime (2) + caisse (3) + centre (3)
        "Lignes": [],
    }

    for n, line in enumerate(lines, 1):
        line = line.rstrip("\r\n")
        if not line.strip():
            continue
        kind = subtype(line)
        entry = {"Ligne": n, "Type": kind, "Acte": None, "NumeroGH": None, "CodeCCAM": None, "Brut": line}

        if kind == "1":
            data["NumeroTiers"] = field(line, 2, 10)
            data["NumeroLot"] = field(line, 20, 22)
            data["NomEtablissement"] = field(line, 30, 61)
            if m := re.search(r"B2(\d{2})(\d{2})(\d{2})", line):
                data["DateFichier"] = f"20{m.group(1)}-{m.group(2)}-{m.group(3)}"
        elif kind == "2":
            data["NumeroAssure"] = field(line, 12, 24)
            data["NumeroFacture"] = field(line, 30, 38)
            data["CodeOrganisme"] = field(line, 49, 56)
        elif kind == "3":
            entry["Acte"], entry["NumeroGH"] = field(line, 56, 60), field(line, 110, 113)
            data["Acte_Type3"].append(entry["Acte"])
            data["NumeroGH_Type3"].append(entry["NumeroGH"])
        elif kind == "4":
            entry["Acte"] = field(line, 76, 80)
            data["Acte_Type4"].append(entry["Acte"])
        elif kind == "4-S":
            entry["NumeroGH"] = field(line, 120, 123)
            data["NumeroGH_Type4S"].append(entry["NumeroGH"])
        elif kind == "4-M":
            entry["CodeCCAM"] = field(line, 43, 55)
            data["CodeCCAM_Type4M"].append(entry["CodeCCAM"])
        elif kind == "5":
            data["TotalPrestations"] = amount(field(line, 42, 49))
            data["TotalHonoraires"] = amount(field(line, 58, 65))
        if kind[0] in "234":
            data["Lignes"].append(entry)

    return data


def parse_file(path: Path) -> dict:
    return parse_lines(path.read_text(encoding="latin-1").splitlines(), path.stem)
