"""Normalisation et tokenisation du français pour la recherche lexicale."""
import re
import unicodedata

STOP = set("""
a au aux avec ce ces cet cette comment dans de des du elle en est et etre il ils je la le les leur lui ma mais me mes moi mon ne nos notre nous on ou par pas pour qu que quel quelle quelles quels qui sa se ses son sont sur ta te tes toi ton tu un une vos votre vous y d l j s n c m t qu est-ce faire fait peux peut puis-je dois doit veux voudrais souhaite
il-y-a ya bonjour merci svp stp
""".split())

# Équivalences métier : la question du client vs le vocabulaire de la FAQ.
SYNONYMS = {
    "cb": "carte", "bancaire": "carte", "visa": "carte", "mastercard": "carte",
    "perdu": "perte", "perdue": "perte", "oublie": "oubli", "oubliee": "oubli",
    "vole": "vol", "volee": "vol", "pret": "credit", "emprunt": "credit", "emprunter": "credit",
    "appli": "application", "app": "application", "mdp": "code", "password": "code", "identifiant": "identifiant",
    "rib": "rib", "iban": "rib", "virer": "virement", "plafonds": "plafond",
    "bloquer": "opposition", "bloquee": "bloque", "piratage": "fraude", "arnaque": "fraude", "escroquerie": "fraude",
    "plainte": "reclamation", "reclamer": "reclamation", "mecontent": "reclamation",
    "cheques": "cheque", "chequier": "cheque", "livret": "livret", "conseillere": "conseiller",
}


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold().replace("’", "'"))
    return "".join(c for c in text if not unicodedata.combining(c))


def stem(t: str) -> str:
    # Racinisation légère : pluriels et quelques suffixes fréquents.
    for suf in ("ements", "ement", "ations", "ation", "euses", "euse", "eurs", "eur", "ees", "es", "s", "e"):
        if len(t) > len(suf) + 3 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def tokens(text: str):
    out = []
    for t in re.findall(r"[a-z0-9@]+", fold(text)):
        if t in STOP or len(t) < 2:
            continue
        t = SYNONYMS.get(t, t)
        out.append(stem(t))
    return out
