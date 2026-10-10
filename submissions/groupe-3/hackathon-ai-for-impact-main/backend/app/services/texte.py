"""Petits utilitaires de texte, d'heures et de dates en français."""
from __future__ import annotations

import unicodedata
from datetime import date

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
        "octobre", "novembre", "décembre"]


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, tirets et apostrophes remplacés par des espaces."""
    t = unicodedata.normalize("NFKD", texte or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = t.replace("œ", "oe").replace("æ", "ae")
    for c in "-'’_/.,()«»\"!?;:":
        t = t.replace(c, " ")
    return " ".join(t.split())


def arrondi(x: float) -> int:
    """Arrondi commercial (0,5 -> 1), contrairement au round() bancaire de Python."""
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def hm(t: str | None) -> int | None:
    if not t:
        return None
    h, m = t.split(":")[:2]
    return int(h) * 60 + int(m)


def fmt_hm(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def heure_fr(t: str | int | None) -> str:
    """'09:05' ou 545 -> '9h05'."""
    if t is None:
        return "?"
    m = hm(t) if isinstance(t, str) else t
    m %= 24 * 60
    return f"{m // 60}h{m % 60:02d}" if m % 60 else f"{m // 60}h"


def duree_fr(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h}h{m:02d}" if m else f"{h}h"


def date_fr(d: str | date, avec_jour: bool = True) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d)
    jour = "1er" if d.day == 1 else str(d.day)
    base = f"{jour} {MOIS[d.month - 1]} {d.year}"
    return f"{JOURS[d.weekday()]} {base}" if avec_jour else base


def pourcent_fr(x: float, decimales: int = 0) -> str:
    s = f"{x:.{decimales}f}".replace(".", ",")
    return f"{s} %"


def capitaliser(t: str) -> str:
    return t[:1].upper() + t[1:] if t else t
