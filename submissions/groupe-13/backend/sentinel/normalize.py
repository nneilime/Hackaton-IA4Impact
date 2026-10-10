"""Normalisation déterministe des valeurs lues (sans changer leur signification)."""
from __future__ import annotations

import re
from typing import Optional

_AMOUNT_RE = re.compile(r"(\d{1,3}(?:[   ]\d{3})+|\d+)(?:\s*([.,])\s*(\d{1,2}))?")


def parse_amount(text: Optional[str]) -> Optional[int]:
    """Montant affiché → centimes. Accepte « 1 013,22 », « 1013.22 », « 398,3 », « 0 ».
    Retourne None si aucune lecture univoque n'est possible."""
    if not text:
        return None
    t = text.strip().replace("€", "")
    matches = list(_AMOUNT_RE.finditer(t))
    if not matches:
        return None
    m = matches[-1]                      # le montant est la dernière valeur de la cellule
    ent = re.sub(r"\D", "", m.group(1))
    dec = m.group(3)
    if dec is None:
        return int(ent) * 100
    if len(dec) == 1:
        dec += "0"
    return int(ent) * 100 + int(dec)


def amount_str(cents: Optional[int]) -> str:
    if cents is None:
        return "—"
    s = f"{cents/100:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} €"


def digits(text: Optional[str]) -> str:
    return re.sub(r"\D", "", text or "")


def strip_leading_zeros(s: str) -> str:
    s2 = s.lstrip("0")
    return s2 if s2 else ("0" if s else "")


def code(text: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def cerfa_id(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.replace(" ", "")
    m = re.search(r"(\d{5})\*(\d{1,2})", t)
    if m:
        return f"{m.group(1)}*{m.group(2)}"
    m = re.search(r"(\d{5})[^\d]?(\d{2})$", t)
    if m:
        return f"{m.group(1)}*{m.group(2)}"
    return None


def cerfa_code(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = re.sub(r"\s+", "", text.upper())
    m = re.search(r"([A-Z])(\d{4})", t)
    if m:
        return m.group(1) + m.group(2)
    m = re.search(r"(\d{4,5})", t)
    return m.group(1) if m else None
