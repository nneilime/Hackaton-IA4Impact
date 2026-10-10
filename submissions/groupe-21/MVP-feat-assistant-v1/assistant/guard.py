"""Garde-fou : un message qui semble contenir un secret n'est ni transmis au modèle ni conservé.

Motifs proches de ceux de l’interface (front/index.html, fonction `guard`), qui masque déjà l’envoi :
ce contrôle serveur couvre un client qui contournerait l'interface.
"""
import re

_KEYWORD = r"\b(?:mot\s+de\s+passe|mdp|password|codes?(?!\s+postal)|pin|identifiant|cryptogramme|cvv)\b"
_PATTERNS = [
    re.compile(r"(?<!\d)(?:\d[ .-]?){12,18}\d(?!\d)"),                       # numéro de carte (13 à 19 chiffres)
    re.compile(r"\bFR\d{2}(?: ?[0-9A-Z]{4}){5} ?[0-9A-Z]{3}\b", re.I),        # IBAN français
    re.compile(_KEYWORD + r"[^\d\n]{0,25}\d{3,}", re.I),                       # « mon code est 1234 »
    re.compile(r"\d{4,}[^\d\n]{0,25}\b(?:est|c'est|c’est|comme)\s+(?:mon|ma|le|la)\s+" + _KEYWORD, re.I),
    re.compile(r"\b(?:mot\s+de\s+passe|mdp|password)\s*(?:est|:|=|c'est|c’est)\s*\S*\d\S*", re.I),
]

WARNING = ("Par sécurité, votre message n'a pas été envoyé : il semble contenir un code, un mot de passe, "
           "un identifiant ou un numéro de carte. Ne communiquez jamais ces informations, même à un conseiller. "
           "Reformulez votre question sans elles.")


def contains_secret(text: str) -> bool:
    return any(p.search(text) for p in _PATTERNS)
