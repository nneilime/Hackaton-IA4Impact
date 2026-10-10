"""Comprendre la demande : texte libre -> champs de la Demande, lieu -> gare de départ.

Le parseur à base de règles sert en mode démo et de filet de sécurité en mode LLM.
`completer()` est appliqué par toutes les routes : valeurs par défaut, gare retrouvée par son nom,
géocodage du lieu, gare la plus proche, champs manquants.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import date

from .. import config, schemas
from . import geo, themes
from .texte import capitaliser, normaliser

OBLIGATOIRES = ["niveau", "theme", "nb_eleves", "nb_accompagnateurs", "date", "lieu_depart"]

_UNITES = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
           "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14,
           "quinze": 15, "seize": 16}
_DIZAINES = {"vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60}
_MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre",
         "octobre", "novembre", "decembre"]
_ORDINAUX = {"sixieme": "6e", "cinquieme": "5e", "quatrieme": "4e", "troisieme": "3e"}

INCERTAIN = re.compile(r"\b(je ne sais pas|sais pas|sait pas|aucune idee|pas d idee|peu importe|"
                       r"n importe|surprenez moi|a vous de voir|je ne suis pas sur|pas encore decide)\b")

ELEVES = r"(?:eleves?|enfants?|jeunes|collegiens?|lyceens?|ecoliers?|etudiants?)"
ADULTES = (r"(?:accompagnat(?:eur|rice)s?|accompagnants?|adultes?|enseignant(?:e)?s?|professeurs?|"
           r"profs?|parents?|encadrants?|animat(?:eur|rice)s?)")


def _sans_accents(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def _chiffrer(norm: str) -> str:
    """Convertit les nombres écrits en lettres (« quarante deux » -> « 42 »), sauf « un/une »."""
    mots, out, i = norm.split(), [], 0
    while i < len(mots):
        m = mots[i]
        if m in _DIZAINES:
            v = _DIZAINES[m]
            j = i + 1
            if j < len(mots) and mots[j] == "et":
                j += 1
            if j < len(mots) and mots[j] in _UNITES and _UNITES[mots[j]] < 10:
                v += _UNITES[mots[j]]
                i = j
            out.append(str(v))
        elif m in _UNITES and m not in ("un", "une"):
            out.append(str(_UNITES[m]))
        else:
            out.append(m)
        i += 1
    return " ".join(out)


def _prochaine_date(jour: int, mois: int, annee: int | None, aujourdhui: date) -> str | None:
    try:
        if annee:
            return date(annee, mois, jour).isoformat()
        d = date(aujourdhui.year, mois, jour)
        if d < aujourdhui:
            d = date(aujourdhui.year + 1, mois, jour)
        return d.isoformat()
    except ValueError:
        return None


def extraire_date(texte: str, aujourdhui: date) -> str | None:
    s = _sans_accents(texte)
    m = re.search(r"\b(20\d\d)-(\d{1,2})-(\d{1,2})\b", s)
    if m:
        return _prochaine_date(int(m.group(3)), int(m.group(2)), int(m.group(1)), aujourdhui)
    m = re.search(r"\b(1er|\d{1,2})\s+(" + "|".join(_MOIS) + r")(?:\s+(20\d\d))?\b", s)
    if m:
        j = 1 if m.group(1) == "1er" else int(m.group(1))
        return _prochaine_date(j, _MOIS.index(m.group(2)) + 1,
                               int(m.group(3)) if m.group(3) else None, aujourdhui)
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", s)
    if m:
        a = m.group(3)
        annee = (2000 + int(a) if len(a) == 2 else int(a)) if a else None
        return _prochaine_date(int(m.group(1)), int(m.group(2)), annee, aujourdhui)
    return None


def _heure(h: str, mn: str | None) -> str | None:
    h_, m_ = int(h), int(mn or 0)
    if 0 <= h_ <= 23 and 0 <= m_ <= 59:
        return f"{h_:02d}:{m_:02d}"
    return None


def extraire_niveau(norm: str) -> str | None:
    m = re.search(r"\b(cp|ce1|ce2|cm1|cm2)\b", norm)
    if m:
        return m.group(1).upper()
    m = re.search(r"\b([3-6])\s*(?:e|eme|ieme|em)\b", norm)
    if m:
        return f"{m.group(1)}e"
    m = re.search(r"\b(?:classe|eleves|niveau|en|de|des)\s+(?:de\s+)?(sixieme|cinquieme|quatrieme|troisieme)\b", norm) or \
        re.search(r"^(sixieme|cinquieme|quatrieme|troisieme)\b", norm)
    if m:
        return _ORDINAUX[m.group(1)]
    # « seconde » seul est ambigu (une durée) : on l'accepte après un mot de classe, en tête du message
    # (« Seconde, thème… ») ou suivi de sa voie (« seconde générale »). La ponctuation est déjà retirée.
    if re.search(r"\b(2nde|2de|2nd)\b", norm) or \
            re.search(r"\b(?:classe|eleves|en|niveau|une|de)\s+(?:de\s+)?seconde\b", norm) or \
            re.search(r"^seconde\b", norm) or \
            re.search(r"\bseconde\s+(?:generale|gt|pro|professionnelle|technologique)\b", norm):
        return "2de"
    if re.search(r"\b1(?:re|ere)\b(?!\s+guerre)", norm) or \
            re.search(r"\b(?:classe|eleves|en|niveau)\s+(?:de\s+)?premiere\b(?!\s+guerre)", norm):
        return "1re"
    if re.search(r"\b(terminale|tle)\b", norm):
        return "Tle"
    return None


_ETAB = re.compile(
    r"\b((?:coll[eè]ge|lyc[eé]e|[eé]cole(?:\s+(?:primaire|[eé]l[eé]mentaire|maternelle))?|"
    r"groupe\s+scolaire|cit[eé]\s+scolaire|[eé]tablissement)\b[^,.;!?\n]{0,60})", re.IGNORECASE)
_CONTEXTE_DEPART = re.compile(
    r"\b(?:partons|partirons|partira|part|départ|depart|venons|sommes situés|sommes basés|"
    r"situé|située|situés|basé|basée|basés)\s+(?:de|d'|d’|du|depuis|à|a|au)\s+([^,.;!?\n]{2,50})",
    re.IGNORECASE)


def extraire_lieu(texte: str) -> tuple[str, str | None] | None:
    """(libellé de l'établissement ou du lieu, commune reconnue) si le texte en parle."""
    m = _ETAB.search(texte)
    if m:
        phrase = m.group(1).strip()
        commune = geo.commune_dans_texte(phrase)
        if commune:
            # couper la phrase après le nom de la commune
            norm_c = normaliser(commune).split()
            mots = phrase.split()
            for k in range(len(mots)):
                if normaliser(" ".join(mots[: k + 1])).endswith(" ".join(norm_c)):
                    phrase = " ".join(mots[: k + 1])
                    break
        else:
            phrase = re.split(r"\s+(?:et|pour|avec|le|la|les|en|nous)\s+", phrase)[0]
        return capitaliser(phrase.strip(" .,'’")), commune
    m = _CONTEXTE_DEPART.search(texte)
    if m:
        commune = geo.commune_dans_texte(m.group(1))
        if commune:
            return commune, commune
    return None


def _variantes_site(nom: str, communes: set[str]) -> list[str]:
    n = normaliser(nom)
    variantes = [n]
    mots = n.split()
    generiques = {"basilique", "couvent", "musee", "cite", "chateau", "palais", "cathedrale",
                  "ecluses", "pont", "maison", "parc", "grand", "museum", "arenes", "natale"}
    vides = {"de", "des", "du", "la", "le", "les", "l", "d"}
    while mots and (mots[0] in generiques or mots[0] in vides):
        mots = mots[1:]
    court = " ".join(mots)
    if len(court) >= 7 and court not in communes and not themes.theme_dans_texte(court):
        variantes.append(court)
    return variantes


def extraire_destination(texte: str, catalogue: list[tuple[str, str]], commune_depart: str | None) -> str | None:
    """Nom d'un site du catalogue (ou d'une commune qui en a) que l'enseignant veut visiter."""
    norm = f" {normaliser(texte)} "
    declencheur = re.search(r"\b(aller|allons|visiter|decouvrir|voir|destination|direction|sortie a|sortie au)\b", norm)
    if not declencheur:
        return None
    suite = norm[declencheur.start():]
    communes = {normaliser(c) for _, c in catalogue}
    for nom, _ in sorted(catalogue, key=lambda x: -len(x[0])):
        for v in _variantes_site(nom, communes):
            if f" {v} " in suite:
                return nom
    for _, commune in catalogue:
        c = normaliser(commune)
        if f" {c} " in suite and commune != commune_depart:
            return commune
    return None


def extraire(texte: str, aujourdhui: date, champ_attendu: str | None = None,
             catalogue: list[tuple[str, str]] | None = None, commune_depart: str | None = None) -> dict:
    """Parseur à base de règles. Retourne seulement les champs trouvés dans le texte."""
    out: dict = {}
    norm = _chiffrer(normaliser(texte))
    simple = _sans_accents(texte)

    niv = extraire_niveau(norm)
    if niv:
        out["niveau"] = niv

    m = re.search(r"\b(\d{1,3})\s+" + ELEVES + r"\b", norm)
    if m:
        out["nb_eleves"] = int(m.group(1))
    m = re.search(r"\b(\d{1,2})\s+" + ADULTES + r"\b", norm)
    if m:
        out["nb_accompagnateurs"] = int(m.group(1))
    elif re.search(r"\b(?:un|une|seul|seule)\s+" + ADULTES + r"\b", norm):
        out["nb_accompagnateurs"] = 1

    d = extraire_date(texte, aujourdhui)
    if d:
        out["date"] = d

    if re.search(r"\bdemi journee\b|\bmatinee\b|\bapres midi\b", norm):
        out["duree"] = "demi-journee"
    elif re.search(r"\bjournee\b|\bjour entier\b", norm):
        out["duree"] = "journee"

    m = re.search(r"(?:retour|rentrer|rentres|rentrees|revenir|revenus|arrivee)\D{0,30}?"
                  r"\b(?:avant|pour|vers|a|au plus tard a|d'ici)\s*(\d{1,2})\s*(?:h|:)\s*(\d{2})?",
                  simple)
    if m:
        h = _heure(m.group(1), m.group(2))
        if h:
            out["heure_retour_max"] = h
    m = re.search(r"(?:depart|partir|partirons|partons)\D{0,20}?"
                  r"\b(?:a partir de|apres|vers|a|des|pas avant)\s*(\d{1,2})\s*(?:h|:)\s*(\d{2})?", simple)
    if m:
        h = _heure(m.group(1), m.group(2))
        if h:
            out["heure_depart_min"] = h
    elif re.search(r"\bdepart (?:le|en|dans la) matin(?:ee)?\b|\bpartir le matin\b", norm):
        out["heure_depart_min"] = config.HEURE_DEPART_DEFAUT

    th = themes.theme_dans_texte(norm)
    if th:
        out["theme"] = th
    else:
        m = re.search(r"(?:sur le theme|thematique|theme)\s+(?:de |du |des |d'|:\s*)?([^,.;!?\n]{3,40})", simple)
        if m:
            out["theme"] = capitaliser(m.group(1).strip())

    lieu = extraire_lieu(texte)
    if lieu:
        out["lieu_depart"] = {"libelle": lieu[0], "commune": lieu[1]}
        commune_depart = lieu[1] or commune_depart

    if catalogue:
        dest = extraire_destination(texte, catalogue, commune_depart)
        if dest:
            out["destination_souhaitee"] = dest

    # Réponse courte à la question qui vient d'être posée
    if champ_attendu in ("nb_eleves", "nb_accompagnateurs") and champ_attendu not in out:
        m = re.fullmatch(r"\D*?(\d{1,3})\D*", norm)
        if m:
            out[champ_attendu] = int(m.group(1))
    elif champ_attendu == "niveau" and "niveau" not in out:
        m = re.fullmatch(r"\s*([3-6])\s*", norm)
        if m:
            out["niveau"] = f"{m.group(1)}e"
    elif champ_attendu == "theme" and "theme" not in out and 2 < len(texte.strip()) <= 60 \
            and not INCERTAIN.search(norm) and len(norm.split()) <= 6:
        out["theme"] = capitaliser(texte.strip(" .!"))
    elif champ_attendu == "destination_souhaitee" and "destination_souhaitee" not in out and catalogue:
        dest = extraire_destination("aller " + texte, catalogue, commune_depart)
        if dest:
            out["destination_souhaitee"] = dest
    elif champ_attendu in ("lieu_depart", "gare_depart") and "lieu_depart" not in out \
            and not INCERTAIN.search(norm):
        commune = geo.commune_dans_texte(texte)
        if commune or 2 < len(texte.strip()) <= 80:
            out["lieu_depart"] = {"libelle": capitaliser(texte.strip(" .!")), "commune": commune}
    return out


def fusionner(demande: schemas.Demande, extrait: dict) -> schemas.Demande:
    """Les nouvelles valeurs remplacent les anciennes (l'enseignant peut corriger)."""
    data = demande.model_dump()
    for k, v in extrait.items():
        if v is None or k not in data:
            continue
        if k == "lieu_depart":
            libelle = v["libelle"] if isinstance(v, dict) else str(v)
            ancien = data.get("lieu_depart") or {}
            if normaliser(ancien.get("libelle") or "") != normaliser(libelle):
                data["lieu_depart"] = {"libelle": libelle, "lat": None, "lon": None}
                data["gare_depart"] = None  # nouveau lieu : on recherche la gare
        else:
            data[k] = v
    return schemas.Demande.model_validate(data)


# --- Compléter et valider -------------------------------------------------------------------

def _gare_schema(row: sqlite3.Row, lieu: schemas.LieuDepart | None) -> schemas.Gare:
    dist = None
    if lieu and lieu.lat is not None and lieu.lon is not None and row["lat"] is not None:
        dist = round(geo.distance_m(lieu.lat, lieu.lon, row["lat"], row["lon"]))
    return schemas.Gare(code_uic=row["code_uic"], nom=row["nom"], lat=row["lat"] or 0.0,
                        lon=row["lon"] or 0.0, distance_m=dist)


def gare_par_nom(conn: sqlite3.Connection, nom: str) -> sqlite3.Row | None:
    """Gare de la base dont le nom correspond (insensible à la casse et aux accents).

    Égalité d'abord, puis nom qui commence par le texte (« toulouse » -> Toulouse Matabiau), puis
    nom qui le contient. Les gares desservies par des trains groupes passent en premier.
    """
    cible = normaliser(nom)
    if not cible:
        return None
    rows = conn.execute(
        """SELECT g.*, EXISTS (SELECT 1 FROM desserte d JOIN train t ON t.numero = d.train_numero
                               WHERE d.gare_uic = g.code_uic AND t.autorise_groupe = 1) AS groupes
           FROM gare g"""
    ).fetchall()
    for test in (lambda n: n == cible, lambda n: n.startswith(cible + " "),
                 lambda n: f" {cible} " in f" {n} "):
        ok = [r for r in rows if test(normaliser(r["nom"]))]
        if ok:
            return sorted(ok, key=lambda r: (-r["groupes"], len(r["nom"])))[0]
    return None


def champs_manquants(d: schemas.Demande) -> list[str]:
    manquants = []
    for c in OBLIGATOIRES:
        if c == "theme" and d.destination_souhaitee:
            continue
        v = getattr(d, c)
        if v is None or (isinstance(v, str) and not v.strip()):
            manquants.append(c)
    if d.lieu_depart is not None and d.gare_depart is None:
        manquants.append("gare_depart")
    return manquants


def completer(conn: sqlite3.Connection, d: schemas.Demande) -> schemas.Demande:
    data = d.model_dump()
    data["duree"] = data.get("duree") or config.DUREE_DEFAUT
    data["heure_depart_min"] = data.get("heure_depart_min") or config.HEURE_DEPART_DEFAUT
    data["heure_retour_max"] = data.get("heure_retour_max") or config.HEURE_RETOUR_DEFAUT
    for k in ("heure_depart_min", "heure_retour_max"):
        m = re.fullmatch(r"(\d{1,2})[:h](\d{2})(?::\d{2})?", str(data[k]).strip())
        data[k] = f"{int(m.group(1)):02d}:{m.group(2)}" if m else None
    if data.get("niveau"):
        data["niveau"] = extraire_niveau(_chiffrer(normaliser(data["niveau"]))) or data["niveau"]
    if data.get("theme"):
        data["theme"] = themes.canonique(data["theme"]) or data["theme"].strip()
    if data.get("date"):
        try:
            date.fromisoformat(data["date"])
        except ValueError:
            data["date"] = extraire_date(data["date"], config.aujourdhui())
    lieu = data.get("lieu_depart")
    gare = data.get("gare_depart")

    # 1. Lieu de départ : géocodage si les coordonnées manquent
    if lieu and lieu.get("libelle") and (lieu.get("lat") is None or lieu.get("lon") is None):
        g = geo.geocoder(lieu["libelle"])
        if g:
            lieu.update(lat=g.lat, lon=g.lon)
    lieu_s = schemas.LieuDepart(**lieu) if lieu and lieu.get("libelle") else None

    # 2. Gare de départ : par son code, sinon par son nom, sinon la plus proche du lieu
    row = None
    if gare:
        if gare.get("code_uic"):
            row = conn.execute("SELECT * FROM gare WHERE code_uic = ?", (gare["code_uic"],)).fetchone()
        if row is None and gare.get("nom"):
            row = gare_par_nom(conn, gare["nom"])
    if row is None and lieu_s and lieu_s.lat is not None:
        proche = geo.gare_la_plus_proche(conn, lieu_s.lat, lieu_s.lon)
        if proche:
            row = proche[0]
    data["gare_depart"] = _gare_schema(row, lieu_s).model_dump() if row is not None else None

    # 3. Sans lieu mais avec une gare : on part de la gare
    if lieu_s is None and row is not None:
        data["lieu_depart"] = {"libelle": f"Gare de {row['nom']}", "lat": row["lat"], "lon": row["lon"]}
        data["gare_depart"]["distance_m"] = 0
    out = schemas.Demande.model_validate(data)
    out.champs_manquants = champs_manquants(out)
    return out


def commune_de_depart(d: schemas.Demande) -> str | None:
    if d.lieu_depart:
        c = geo.commune_dans_texte(d.lieu_depart.libelle)
        if c:
            return c
        if d.lieu_depart.lat is not None:
            return geo.commune_proche(d.lieu_depart.lat, d.lieu_depart.lon)
    return None
