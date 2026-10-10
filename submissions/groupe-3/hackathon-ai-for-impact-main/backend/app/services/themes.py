"""Vocabulaire des thèmes pédagogiques : synonymes -> thème canonique du catalogue."""
from __future__ import annotations

from .texte import normaliser

SYNONYMES: dict[str, list[str]] = {
    "Moyen Âge": ["moyen age", "moyen ages", "moyenage", "medieval", "medievale", "medievaux",
                  "medievales", "epoque medievale", "chateau fort", "chateaux forts", "chevaliers",
                  "chevalerie", "cathares", "catharisme", "feodalite", "feodal", "seigneurs",
                  "art roman", "art gothique", "croisades", "croisade", "cathedrales"],
    "Antiquité": ["antiquite", "antique", "romains", "romaine", "rome antique", "gallo romain",
                  "gallo romaine", "gallo romains", "gaule romaine", "grece antique", "grecs",
                  "gladiateurs", "empire romain", "monde romain"],
    "Préhistoire": ["prehistoire", "prehistorique", "prehistoriques", "paleolithique",
                    "neolithique", "cro magnon", "art parietal", "grottes ornees"],
    "Espace et astronomie": ["espace", "astronomie", "systeme solaire", "planetes", "etoiles",
                             "astronautes", "conquete spatiale", "fusees", "univers"],
    "Sciences et nature": ["sciences", "science", "svt", "sciences de la vie", "nature",
                           "biodiversite", "evolution", "dinosaures", "animaux", "environnement",
                           "ecologie", "ocean", "oceans", "mer", "vivant"],
    "Arts": ["art", "arts", "arts plastiques", "histoire des arts", "peinture", "peintres",
             "musee d art", "beaux arts", "sculpture", "art contemporain"],
    "Temps modernes": ["temps modernes", "louis xiv", "xviie siecle", "17e siecle", "renaissance",
                       "canal du midi", "riquet", "grands travaux", "monarchie absolue"],
    "Première Guerre mondiale": ["premiere guerre mondiale", "grande guerre", "guerre de 14 18",
                                 "14 18", "1914 1918", "poilus"],
}

_INDEX = sorted(((s, canon) for canon, syns in SYNONYMES.items() for s in syns),
                key=lambda x: -len(x[0]))


def theme_dans_texte(texte: str) -> str | None:
    """Thème canonique mentionné dans le texte (le synonyme le plus long l'emporte)."""
    n = f" {normaliser(texte)} "
    meilleur = None
    for syn, canon in _INDEX:
        i = n.find(f" {syn} ")
        if i >= 0 and (meilleur is None or len(syn) > meilleur[0]):
            meilleur = (len(syn), canon)
    return meilleur[1] if meilleur else None


def _occurrences(texte: str) -> tuple[list[str], list[tuple[int, int, str]]]:
    """Synonymes trouvés (les plus longs d'abord, sans chevauchement) : (mots, [(début, fin, thème)])."""
    toks = normaliser(texte).split()
    pris = [False] * len(toks)
    occ: list[tuple[int, int, str]] = []
    for syn, canon in _INDEX:
        mots = syn.split()
        k = len(mots)
        for i in range(len(toks) - k + 1):
            if toks[i:i + k] == mots and not any(pris[i:i + k]):
                occ.append((i, i + k, canon))
                for j in range(i, i + k):
                    pris[j] = True
    occ.sort()
    return toks, occ


def themes_dans_texte(texte: str) -> list[str]:
    """Tous les thèmes canoniques évoqués par le texte, dans l'ordre où ils apparaissent."""
    return list(dict.fromkeys(c for _, _, c in _occurrences(texte)[1]))


def canonique(theme: str | None) -> str | None:
    """Thème canonique d'un libellé, ou None s'il n'existe pas tel quel.

    Nom exact du thème, sinon texte qui n'évoque qu'UN seul thème. Un libellé qui en évoque
    plusieurs (« Sciences et espace » : sciences + espace) n'est jamais ramené à l'un d'eux en
    silence (audit n°1) : il reste tel quel et l'appelant doit le signaler.
    """
    if not theme:
        return None
    n = normaliser(theme)
    for canon in SYNONYMES:
        if normaliser(canon) == n:
            return canon
    trouves = themes_dans_texte(theme)
    return trouves[0] if len(trouves) == 1 else None


def themes_ambigus(texte: str) -> list[str]:
    """Thèmes en concurrence dans un libellé comme « Sciences et espace » (sciences ET espace).

    Vide si le texte n'évoque qu'un thème. Dans un texte court (6 mots ou moins), deux thèmes
    différents sont toujours ambigus ; dans une phrase plus longue, seulement s'ils se touchent
    (au plus 2 mots d'écart), pour ne pas gêner « Moyen Âge, avec un détour par la Cité de l'espace ».
    """
    toks, occ = _occurrences(texte)
    canons = list(dict.fromkeys(c for _, _, c in occ))
    if len(canons) < 2:
        return []
    if len(toks) <= 6:
        return canons
    amb: list[str] = []
    for (_, b1, c1), (a2, _, c2) in zip(occ, occ[1:]):
        if c1 != c2 and a2 - b1 <= 2:
            for c in (c1, c2):
                if c not in amb:
                    amb.append(c)
    return amb
