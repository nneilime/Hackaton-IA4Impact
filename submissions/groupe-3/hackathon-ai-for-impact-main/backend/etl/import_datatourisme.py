"""Importe les lieux culturels de DATAtourisme (Occitanie) dans la table `site_culturel`.

Source : DATAtourisme (https://www.datatourisme.fr), fichier `data/datatourisme-reg-occ.csv`,
Licence Ouverte Etalab 2.0. La source doit être citée : elle est mémorisée dans la table `meta`
(clé `source_datatourisme`) et chaque lieu garde l'URI DATAtourisme dans `source_url`.

Usage : python -m etl.import_datatourisme [--csv CHEMIN] [--db CHEMIN] [--max 600]
                                          [--max-par-gare 40] [--dry-run]

Principes :
- seuls les lieux permanents à vocation culturelle, patrimoniale ou naturelle sont gardés
  (pas d'événements, d'hébergements, de restaurants, de commerces, de producteurs, d'itinéraires) ;
- chaque lieu est rattaché à la gare la plus proche de la table `gare` (3 km au plus) ; la marche
  est estimée à vol d'oiseau, à 80 m/min, puis convertie en temps de groupe comme partout ailleurs
  (`commun.minutes_groupe` : individuel × 1,3 + 5 min) ;
- un lieu sans thème pédagogique reconnu n'est pas importé ; rien n'est inventé : pas d'horaires,
  pas de capacité, activités déduites des seules catégories ;
- AUCUNE donnée de contact (noms, e-mails, téléphones) n'est lue ni stockée ;
- le volume est plafonné (total et par gare), les lieux les mieux notés d'abord.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from app import config, db
from app.services import geo
from app.services.texte import arrondi, normaliser
from . import catalogue, commun

NOM_FICHIER = "datatourisme-reg-occ.csv"
LICENCE = "DATAtourisme, Licence Ouverte Etalab 2.0"

# --- Paramètres --------------------------------------------------------------------------------
MAX_TOTAL = 600
MAX_PAR_GARE = 40
RAYON_MARCHE_KM = 1.5      # lieu « marchable »
RAYON_MAX_KM = 3.0         # au-delà, le lieu est ignoré
SEUIL_THEME = 2            # score minimal pour retenir un thème
DEBUT_DESCRIPTION = 250    # début de description : là où un lieu dit ce qu'il est
MAX_THEMES = 3
DOUBLON_M = 150            # même nom à moins de 150 m = même lieu
DOUBLON_CATALOGUE_M = 300  # idem face au catalogue fait main
RESUME_MAX = 200
HORAIRES = "À vérifier auprès du site"
# Emprise de validité des coordonnées (Occitanie)
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 42.3, 45.1, -0.4, 4.9

# --- Types DATAtourisme -------------------------------------------------------------------------
EVENEMENTS = {"Event", "EntertainmentAndEvent", "CulturalEvent", "SocialEvent", "SaleEvent",
              "SportsEvent", "TheaterEvent", "ShowEvent", "MusicEvent", "Festival", "Concert",
              "ScreeningEvent", "ExhibitionEvent", "ChildrensEvent"}
HEBERGEMENTS = {"Accommodation", "LodgingBusiness", "HotelTrade", "CollectiveAccommodation",
                "RentalAccommodation", "CampingAndCaravanning", "Camping", "Hotel", "Guesthouse",
                "BedAndBreakfast", "StopOverOrGroupLodge", "CamperVanArea", "ClubOrHolidayVillage",
                "ResidentialLeisurePark"}
RESTAURATION = {"FoodEstablishment", "Restaurant", "BarOrPub", "FastFoodRestaurant",
                "HotelRestaurant"}
COMMERCES = {"Store", "TastingProvider", "Producer", "Farmer", "Farm", "CraftsmanShop",
             "BoutiqueOrLocalShop", "Market", "ServiceProvider", "ConvenientService", "Tasting"}
ITINERAIRES = {"Tour", "WalkingTour", "CyclingTour", "OrderedList"}

# Un lieu est « culturel » s'il porte au moins un de ces types.
TYPES_CULTURELS = {
    "CulturalSite", "NaturalHeritage", "ParkAndGarden", "Museum", "Castle", "ReligiousSite",
    "DefenceSite", "TechnicalHeritage", "CityHeritage", "RemarkableBuilding", "ArcheologicalSite",
    "Church", "Chapel", "Cathedral", "Abbey", "Cloister", "Fort", "FortifiedCastle",
    "FortifiedSet", "CastleAndPrestigeMansion", "Palace", "Bastide", "Aqueduct", "RomanPath",
    "MegalithDolmenMenhir", "CaveSinkholeOrAven", "NaturalCuriosity", "Zoo", "Aquarium",
    "ZooAnimalPark", "VivariumAquarium", "ArtGalleryOrExhibitionGallery", "InterpretationCentre",
    "RemembranceSite", "MilitaryCemetery", "Mill", "Mine", "IndustrialSite",
}
# Le type LocalBusiness est porté par TOUS les musées du jeu de données : on ne l'exclut que s'il
# n'est accompagné d'aucun de ces types « patrimoine » (alors c'est une boutique ou un atelier).
TYPES_PATRIMOINE = TYPES_CULTURELS - {"CulturalSite", "TechnicalHeritage", "InterpretationCentre",
                                      "Mill", "Mine", "IndustrialSite"}

# (types, libellé du lieu, activité déduite) : l'ordre donne la priorité du libellé.
ACTIVITES: list[tuple[set[str], str, str]] = [
    ({"Museum"}, "Musée", "Visite du musée"),
    ({"Castle", "FortifiedCastle", "CastleAndPrestigeMansion", "Palace", "Fort", "FortifiedSet",
      "DefenceSite"}, "Château ou site fortifié", "Visite du château ou du site fortifié"),
    ({"Abbey", "Cloister", "Cathedral", "Church", "Chapel", "ReligiousSite"},
     "Édifice religieux", "Visite de l'édifice religieux"),
    ({"ArcheologicalSite", "Aqueduct", "RomanPath"}, "Site archéologique",
     "Découverte du site archéologique ou des vestiges"),
    ({"MegalithDolmenMenhir"}, "Site mégalithique", "Découverte du site mégalithique"),
    ({"CaveSinkholeOrAven"}, "Grotte ou gouffre", "Visite de la grotte ou du gouffre"),
    ({"Zoo", "Aquarium", "ZooAnimalPark", "VivariumAquarium"}, "Parc animalier",
     "Visite du parc animalier"),
    ({"ParkAndGarden"}, "Parc ou jardin", "Promenade dans le parc ou le jardin"),
    ({"ArtGalleryOrExhibitionGallery"}, "Galerie d'exposition", "Visite de la galerie d'exposition"),
    ({"RemembranceSite", "MilitaryCemetery"}, "Lieu de mémoire", "Visite du lieu de mémoire"),
    ({"TechnicalHeritage", "IndustrialSite", "Mill", "Mine"}, "Site de patrimoine technique",
     "Visite du site de patrimoine technique"),
    ({"InterpretationCentre"}, "Centre d'interprétation", "Visite du centre d'interprétation"),
    ({"NaturalHeritage", "NaturalCuriosity"}, "Site naturel", "Découverte du site naturel"),
    ({"CityHeritage", "RemarkableBuilding", "Bastide"}, "Patrimoine bâti",
     "Découverte du patrimoine bâti"),
]

# --- Thèmes (vocabulaire canonique de app/services/themes.py) -----------------------------------
# mot-clé normalisé -> poids. Dans le nom, le poids est doublé. Un thème est retenu à partir de 2.
MOTS_CLES: dict[str, dict[str, int]] = {
    "Moyen Âge": {
        "moyen age": 2, "medieval": 2, "medievale": 2, "medievaux": 2, "medievales": 2,
        "chateau fort": 2, "cathare": 2, "cathares": 2, "catharisme": 2, "remparts": 2,
        "rempart": 1, "cite fortifiee": 2, "cite medievale": 2, "templiers": 2, "croisade": 1,
        "chateau": 1, "abbaye": 1, "prieure": 1, "monastere": 1, "cloitre": 1, "donjon": 1,
        "forteresse": 1, "bastide": 1, "romane": 1, "art roman": 2, "gothique": 1,
        "cathedrale": 1, "collegiale": 1, "chevalier": 1, "chevaliers": 1, "inquisition": 2, "seigneurie": 1,
        "seigneurs": 1, "feodal": 1, "pelerinage": 1, "saint jacques de compostelle": 1,
        "comte de foix": 1, "chartreuse": 1, "commanderie": 1, "fortifie": 1, "fortifiee": 1,
    },
    "Antiquité": {
        "gallo romain": 2, "gallo romaine": 2, "gallo romains": 2, "amphitheatre": 2,
        "oppidum": 2, "antiquite": 2, "antique": 2, "empire romain": 2, "romain": 1,
        "romaine": 1, "villa romaine": 2, "theatre antique": 2, "aqueduc": 1, "thermes": 1,
        "gaulois": 1, "gauloise": 1, "gaule": 1, "voie domitienne": 2, "mosaique": 1,
        "archeologie": 1, "archeologique": 1, "vestiges": 1, "forum": 1, "romanite": 2,
        "horreum": 2, "cryptoportique": 2, "via domitia": 2, "arenes": 1, "segodunum": 2,
    },
    "Préhistoire": {
        "prehistoire": 2, "prehistorique": 2, "paleolithique": 2, "neolithique": 2,
        "mesolithique": 2, "cro magnon": 2, "art parietal": 2, "grotte ornee": 2,
        "dinosaure": 2, "dinosaures": 2, "mammouth": 1, "dolmen": 2, "menhir": 2,
        "megalithe": 2, "megalithes": 2, "megalithique": 2, "tumulus": 1, "silex": 1,
        "age du bronze": 1, "age du fer": 1, "protohistoire": 2, "abri sous roche": 1,
        "grotte": 1, "homme prehistorique": 2, "fossile": 1, "fossiles": 1,
    },
    "Espace et astronomie": {
        "astronomie": 2, "astronome": 2, "astronomique": 2, "planetarium": 2, "observatoire": 2,
        "cosmos": 1, "spatial": 1, "spatiale": 1, "fusee": 1, "fusees": 1, "satellite": 1,
        "satellites": 1, "astronaute": 2, "astronautes": 2, "telescope": 2, "etoiles": 1,
        "systeme solaire": 2, "cite de l espace": 2, "univers": 1,
    },
    "Sciences et nature": {
        "science": 1, "sciences": 1, "scientifique": 1, "geologie": 2, "geologique": 2,
        "faune": 2, "flore": 2, "gouffre": 2, "reserve naturelle": 2, "reserve": 1,
        "biodiversite": 2, "ecosysteme": 1, "paleontologie": 2, "mineraux": 1, "mineralogie": 2,
        "volcan": 1, "aeronautique": 2, "aviation": 1, "industriel": 1, "industrielle": 1,
        "patrimoine industriel": 2, "technique": 1, "techniques": 1, "ecologie": 1,
        "environnement": 1, "zoo": 2, "aquarium": 2, "animaux": 1, "botanique": 2,
        "arboretum": 2, "jardin botanique": 2, "herbier": 1, "energie": 1, "hydroelectrique": 2,
        "machines": 1, "usine": 1, "forge": 1, "metallurgie": 1, "mine": 1, "mines": 1,
        "geoparc": 2, "histoire naturelle": 2, "musee de la mer": 2, "oceanographie": 2,
        "anatomie": 2, "apothicairerie": 1, "ferroviaire": 1, "chemin de fer": 1, "espaces naturels": 1, "cirque": 1, "gorges": 1, "avens": 1, "stalactites": 2,
        "concretions": 2, "oiseaux": 1, "plantes": 1, "grotte": 1, "observatoire": 1,
    },
    "Arts": {
        "beaux arts": 2, "peinture": 1, "peintures": 1, "peintre": 1, "peintres": 1,
        "sculpture": 1, "sculptures": 1, "sculpteur": 1, "art contemporain": 2,
        "art moderne": 2, "arts plastiques": 2, "musee d art": 2, "galerie d art": 2,
        "oeuvres d art": 1, "tableaux": 1, "gravure": 1, "estampes": 1, "photographie": 1,
        "art sacre": 1, "fresques": 1, "fresque": 1, "vitraux": 1, "vitrail": 1,
        "artiste": 1, "artistes": 1, "arts decoratifs": 2, "street art": 2, "orfevrerie": 1,
        "tapisserie": 1, "tapisseries": 1, "histoire des arts": 2, "galerie": 1, "frac": 2, "centre d art": 2, "art brut": 2,
        "arts modestes": 2, "arts visuels": 2, "lieu d exposition": 1, "espace d exposition": 1,
    },
    "Temps modernes": {
        "temps modernes": 2, "renaissance": 1, "canal du midi": 2, "louis xiv": 2,
        "louis xv": 1, "louis xvi": 1, "guerres de religion": 2, "huguenots": 2, "riquet": 2,
        "monarchie absolue": 2, "ancien regime": 1, "vauban": 2, "pastel": 1,
    },
    "Première Guerre mondiale": {
        "premiere guerre mondiale": 2, "grande guerre": 2, "14 18": 2, "1914 1918": 2,
        "poilus": 2, "poilu": 2, "monument aux morts": 1, "morts pour la france": 1,
        "cimetiere militaire": 1, "tranchees": 1, "armistice": 1,
    },
}
# Types DATAtourisme qui orientent vers un thème : (type, thème, poids).
THEME_PAR_TYPE: list[tuple[str, str, int]] = [
    ("Castle", "Moyen Âge", 1), ("FortifiedCastle", "Moyen Âge", 2), ("Abbey", "Moyen Âge", 2),
    ("Cloister", "Moyen Âge", 2), ("Bastide", "Moyen Âge", 1), ("FortifiedSet", "Moyen Âge", 1),
    ("Aqueduct", "Antiquité", 2), ("RomanPath", "Antiquité", 2),
    ("MegalithDolmenMenhir", "Préhistoire", 2),
    ("CaveSinkholeOrAven", "Sciences et nature", 2), ("NaturalCuriosity", "Sciences et nature", 1),
    ("NaturalHeritage", "Sciences et nature", 1), ("ParkAndGarden", "Sciences et nature", 1),
    ("Zoo", "Sciences et nature", 2), ("Aquarium", "Sciences et nature", 2),
    ("ZooAnimalPark", "Sciences et nature", 2), ("VivariumAquarium", "Sciences et nature", 2),
    ("IndustrialSite", "Sciences et nature", 1), ("TechnicalHeritage", "Sciences et nature", 1),
    ("ArtGalleryOrExhibitionGallery", "Arts", 2),
    ("MilitaryCemetery", "Première Guerre mondiale", 1),
    ("RemembranceSite", "Première Guerre mondiale", 1),
]
ORDRE_THEMES = list(MOTS_CLES)
NIVEAUX_PAR_THEME: dict[str, list[str]] = {
    "Moyen Âge": catalogue.MOYEN_AGE, "Antiquité": catalogue.ANTIQUITE,
    "Préhistoire": catalogue.PREHISTOIRE, "Espace et astronomie": catalogue.SCIENCES,
    "Sciences et nature": catalogue.SCIENCES, "Arts": catalogue.TOUS,
    "Temps modernes": catalogue.TEMPS_MODERNES, "Première Guerre mondiale": catalogue.GUERRE_14,
}

# Labels « Classements_du_POI » qui signalent un lieu reconnu (richesse).
LABELS_FORTS = {normaliser(x) for x in (
    "Monument Historique", "Musée de France", "Ville ou Pays d'art et d'histoire",
    "Patrimoine Mondial UNESCO", "Jardin remarquable", "Maison des Illustres",
    "Grand Site de France", "Architecture contemporaine remarquable")}

# Expressions à retirer avant la recherche de mots-clés (faux amis).
_FAUX_AMIS = re.compile(r"\b(chateau d ?eau|saint romain|romain rolland|romain gary|"
                        r"salade romaine|chateau de sable)\b")
_ROMAINS = {"v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12,
            "xiii": 13, "xiv": 14, "xv": 15, "xvi": 16, "xvii": 17, "xviii": 18}
_SIECLES = re.compile(r"((?:\b[ivx]{1,5}(?:e|eme|er)\b[\s,et/ou]*)+)\s*siecles?\b")
_ROMAIN_TOKEN = re.compile(r"\b([ivx]{1,5})(?:e|eme|er)\b")


def _regex_theme(mots: dict[str, int]) -> re.Pattern:
    alternatives = "|".join(re.escape(m) for m in sorted(mots, key=len, reverse=True))
    return re.compile(rf"(?<![a-z0-9])({alternatives})(?:s|x)?(?![a-z0-9])")


_REGEX_THEMES = {t: _regex_theme(m) for t, m in MOTS_CLES.items()}


def _mots_trouves(texte_norm: str) -> dict[str, dict[str, int]]:
    """{thème: {mot-clé: poids}} pour un texte déjà normalisé."""
    texte = _FAUX_AMIS.sub(" ", texte_norm)
    trouves: dict[str, dict[str, int]] = {}
    for theme, rx in _REGEX_THEMES.items():
        mots = MOTS_CLES[theme]
        hits = {m: mots[m] for m in set(rx.findall(texte))}
        if hits:
            trouves[theme] = hits
    for groupe in _SIECLES.findall(texte):
        for r in _ROMAIN_TOKEN.findall(groupe):
            n = _ROMAINS.get(r)
            if n is None:
                continue
            if n <= 15:
                trouves.setdefault("Moyen Âge", {})["@siecle"] = 1
            elif n <= 18:
                trouves.setdefault("Temps modernes", {})["@siecle"] = 1
    return trouves


def detecter_themes(nom: str, description: str, types: set[str],
                    commune: str = "") -> list[tuple[str, int]]:
    """Thèmes retenus, du plus fort au plus faible : [(thème, score)].

    Le nom compte double, le début de la description (DEBUT_DESCRIPTION caractères) et le type
    comptent simple. Un thème est retenu à partir de SEUIL_THEME ; si la seule preuve est la suite
    de la description, il en faut 3 : une simple mention en passant ne suffit pas.
    Le nom de la commune est ignoré (« Ax-les-Thermes » n'est pas un thème « Antiquité »).
    """
    n_nom, n_desc = normaliser(nom), normaliser(description)
    if commune:
        rx = re.compile(rf"(?<![a-z0-9]){re.escape(normaliser(commune))}(?![a-z0-9])")
        n_nom, n_desc = rx.sub(" ", n_nom), rx.sub(" ", n_desc)
    dans_nom, dans_desc = _mots_trouves(n_nom), _mots_trouves(n_desc)
    dans_debut = _mots_trouves(n_desc[:DEBUT_DESCRIPTION])
    fort: Counter = Counter()   # nom, type, début de la description
    faible: Counter = Counter()  # reste de la description
    for theme in ORDRE_THEMES:
        n, deb, d = (dans_nom.get(theme, {}), dans_debut.get(theme, {}), dans_desc.get(theme, {}))
        fort[theme] += sum(2 * p for p in n.values())
        fort[theme] += sum(p for m, p in deb.items() if m not in n)
        faible[theme] += min(4, sum(p for m, p in d.items() if m not in n and m not in deb))
    texte_fort = Counter(fort)   # preuve venue du seul texte (nom, début de description)
    type_max: Counter = Counter()
    for t, theme, poids in THEME_PAR_TYPE:
        if t in types:
            fort[theme] += poids
            type_max[theme] = max(type_max[theme], poids)
    retenus = []
    for theme in ORDRE_THEMES:
        total = fort[theme] + faible[theme]
        # Le type seul ne suffit que s'il est parlant (grotte, aqueduc, mégalithe, abbaye...).
        appuye = texte_fort[theme] > 0 or type_max[theme] >= 2 or faible[theme] > SEUIL_THEME
        if total >= SEUIL_THEME and appuye:
            retenus.append((theme, total))
    retenus.sort(key=lambda x: (-x[1], ORDRE_THEMES.index(x[0])))
    return retenus[:MAX_THEMES]


# --- Nettoyage de texte -------------------------------------------------------------------------
_BALISES = re.compile(r"<[^>]+>")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
_EMAIL = re.compile(r"\S+@\S+")
_TEL = re.compile(r"(?:\+33|\b0033|\b0)\s?[1-9](?:[\s.\-]?\d{2}){4}\b")
_CONTACT = re.compile(r"\b(?:t[ée]l|t[ée]l[ée]phone|fax|portable|mobile|contactez|courriel|e-?mail|"
                      r"mail|appelez|whatsapp)\b", re.I)
_PHRASES = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÀ-ÖØ-Ý0-9«\"“'‘])")


def _phrases_propres(description: str) -> list[str]:
    t = html.unescape(description or "")
    t = _BALISES.sub(" ", t)
    t = " ".join(t.split())
    sorties = []
    for ph in _PHRASES.split(t):
        ph = ph.strip()
        if not ph or _URL.search(ph) or _EMAIL.search(ph) or _TEL.search(ph) or _CONTACT.search(ph):
            continue
        sorties.append(ph)
    return sorties


def resume(description: str, maxi: int = RESUME_MAX) -> str:
    """Résumé propre : phrases entières, `maxi` caractères au plus, sans balises ni contacts."""
    phrases = _phrases_propres(description)
    if not phrases:
        return ""
    sortie = phrases[0]
    if len(sortie) > maxi:
        coupe = sortie[:maxi - 1]
        ancre = max(coupe.rfind(c) for c in (";", ":", " —", " –"))
        if ancre < maxi // 2:
            ancre = coupe.rfind(" ")
        coupe = coupe[:ancre] if ancre > 0 else coupe
        return coupe.rstrip(" ,;:-–—.") + "…"
    for ph in phrases[1:]:
        if len(sortie) + 1 + len(ph) > maxi:
            break
        sortie += " " + ph
    return sortie


_PETITS_MOTS = {"de", "du", "des", "la", "le", "les", "et", "en", "aux", "au", "à", "sur", "sous",
                "d", "l", "un", "une", "dans", "par", "pour"}


def joli_nom(nom: str) -> str:
    """NOM EN MAJUSCULES -> Nom en casse de titre ; les autres noms sont laissés tels quels."""
    nom = " ".join((nom or "").split())
    lettres = [c for c in nom if c.isalpha()]
    if len(lettres) < 4 or not all(c.isupper() for c in lettres):
        return nom
    mots = []
    for i, mot in enumerate(nom.lower().split(" ")):
        morceaux = re.split(r"(['’\-])", mot)
        res = []
        for j, m in enumerate(morceaux):
            if m in ("'", "’", "-") or not m:
                res.append(m)
            elif (i > 0 or j > 0) and m in _PETITS_MOTS:
                res.append(m)
            else:
                res.append(m[:1].upper() + m[1:])
        mots.append("".join(res))
    return " ".join(mots)


# --- Lecture des lignes -------------------------------------------------------------------------
def _types(categories: str) -> set[str]:
    return {u.rsplit("#", 1)[-1].rsplit("/", 1)[-1] for u in (categories or "").split("|") if u}


def _flottant(valeur: str) -> float | None:
    try:
        return float((valeur or "").strip().replace(",", "."))
    except ValueError:
        return None


def _commune(champ: str, adresse: str = "") -> str:
    premier = (champ or "").split("|")[0]
    if "#" in premier:
        return premier.split("#", 1)[1].strip()
    return premier.strip()


def _labels(classements: str) -> set[str]:
    return {normaliser(c.split("#")[0]) for c in (classements or "").split("|") if c}


def identifiant(uri: str) -> str:
    """id stable : « dt- » + 10 caractères du SHA-1 de l'URI DATAtourisme."""
    return "dt-" + hashlib.sha1(uri.strip().encode("utf-8")).hexdigest()[:10]


def motif_exclusion(types: set[str]) -> str | None:
    """Motif d'exclusion d'après les seuls types, ou None si le lieu est un candidat."""
    if types & EVENEMENTS:
        return "evenement"
    if types & HEBERGEMENTS:
        return "hebergement"
    if types & RESTAURATION:
        return "restauration"
    if types & COMMERCES:
        return "commerce_ou_producteur"
    if types & ITINERAIRES:
        return "itineraire"
    if not types & TYPES_CULTURELS:
        return "hors_culture_patrimoine"
    if "Library" in types and "Museum" not in types:
        return "bibliotheque"
    if "LocalBusiness" in types and not types & TYPES_PATRIMOINE:
        return "commerce_ou_producteur"
    return None


_NOM_ITINERAIRE = re.compile(r"^(?:itineraire|sentier|circuit|parcours|randonnee|balade|boucle)\b")
_NOM_COMMERCIAL = re.compile(r"\b(?:restaurant|boutique|gites?|chambres? d hotes?|hebergement|"
                             r"degustation|cave|caves|vigneron|vignoble|domaine viticole)\b")
_TEXTE_COMMERCIAL = re.compile(r"\b(?:vente (?:directe|de|d)|bijoux|chambres? d hotes?|gites?|"
                               r"hebergement|degustation|bar a cocktails|atelier d artiste)\b")


def motif_exclusion_texte(nom: str, description: str, types: set[str], labels: set[str]) -> str | None:
    """Exclusions qui demandent le texte : itinéraires déguisés, ateliers et lieux de vente.
    Un lieu à label fort (Monument historique, Musée de France...) n'est jamais écarté ici."""
    n_nom = normaliser(nom)
    if _NOM_ITINERAIRE.match(n_nom) or n_nom.startswith(("visite guidee", "visite commentee")):
        return "itineraire"
    if labels & LABELS_FORTS:
        return None
    if re.match(r"^(?:atelier|galerie)\b", n_nom):
        return "commerce_ou_producteur"
    if _NOM_COMMERCIAL.search(n_nom) and "Museum" not in types:
        return "commerce_ou_producteur"
    if _TEXTE_COMMERCIAL.search(normaliser(description)) and "Museum" not in types:
        return "commerce_ou_producteur"
    return None


def _activites_et_libelle(types: set[str]) -> tuple[list[str], str]:
    acts, libelle = ["Visite libre"], ""
    for groupe, lib, act in ACTIVITES:
        if groupe & types:
            libelle = libelle or lib
            if act not in acts:
                acts.append(act)
    return acts[:3], libelle or "Site patrimonial"


def _niveaux(themes: list[str]) -> list[str]:
    ensemble: set[str] = set()
    for t in themes:
        ensemble.update(NIVEAUX_PAR_THEME[t])
    return [n for n in catalogue.TOUS if n in ensemble]


def _richesse(labels: set[str], resume_txt: str) -> int:
    return 1 + (1 if labels & LABELS_FORTS else 0) + (1 if len(resume_txt) >= 80 else 0)


# --- Bilan --------------------------------------------------------------------------------------
@dataclass
class Bilan:
    lus: int = 0
    exclus: Counter = field(default_factory=Counter)
    doublons: int = 0
    deja_catalogue: int = 0
    candidats: int = 0
    importes: int = 0
    par_gare: Counter = field(default_factory=Counter)
    par_theme: Counter = field(default_factory=Counter)
    exemples: list[dict] = field(default_factory=list)
    duree_s: float = 0.0

    def texte(self) -> str:
        sortie = [f"DATAtourisme : {self.lus} lignes lues, {self.candidats} lieux retenus avant "
                  f"plafond, {self.importes} importés ({self.duree_s:.1f} s)",
                  "Exclus par motif :"]
        sortie += [f"  {n:6d}  {m}" for m, n in self.exclus.most_common()]
        sortie.append(f"  {self.doublons:6d}  doublons (même nom, même lieu)")
        sortie.append(f"  {self.deja_catalogue:6d}  déjà au catalogue fait main")
        sortie.append("Importés par gare :")
        sortie += [f"  {n:4d}  {g}" for g, n in self.par_gare.most_common()]
        sortie.append("Importés par thème (un lieu peut avoir plusieurs thèmes) :")
        sortie += [f"  {n:4d}  {t}" for t, n in self.par_theme.most_common()]
        return "\n".join(sortie)


# --- Import -------------------------------------------------------------------------------------
def _gares(conn: sqlite3.Connection) -> list[tuple[str, str, float, float]]:
    """Gares candidates : desservies par un train autorisé aux groupes (sinon, toutes)."""
    rows = conn.execute(
        """SELECT g.code_uic, g.nom, g.lat, g.lon FROM gare g
           WHERE g.lat IS NOT NULL AND g.lon IS NOT NULL AND EXISTS (
             SELECT 1 FROM desserte d JOIN train t ON t.numero = d.train_numero
             WHERE d.gare_uic = g.code_uic AND t.autorise_groupe = 1)"""
    ).fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT code_uic, nom, lat, lon FROM gare WHERE lat IS NOT NULL AND lon IS NOT NULL"
        ).fetchall()
    return [(r[0], r[1], r[2], r[3]) for r in rows]


def _gare_proche(gares, lat: float, lon: float, rayon_m: float):
    meilleur, d_min = None, rayon_m
    marge = rayon_m / 111_000 * 1.2
    for g in gares:
        if abs(g[2] - lat) > marge:
            continue
        d = geo.distance_m(lat, lon, g[2], g[3])
        if d <= d_min:
            meilleur, d_min = g, d
    return (meilleur, d_min) if meilleur else None


_BRUIT_NOM = re.compile(r"\b(?:visites? guidees?|groupes?|scolaires?)\b")


def _cle_nom(nom: str) -> str:
    """Nom normalisé sans les mentions « Visite guidée », « (groupes) » : même lieu, même clé."""
    n = " ".join(_BRUIT_NOM.sub(" ", normaliser(nom)).split())
    return re.sub(r"^(?:le|la|les|l|un|une) ", "", n)


def _dedupliquer(candidats: list[dict]) -> tuple[list[dict], int]:
    """Même nom normalisé à moins de DOUBLON_M mètres : on garde la meilleure fiche."""
    par_nom: dict[str, list[dict]] = defaultdict(list)
    for c in candidats:
        par_nom[_cle_nom(c["nom"])].append(c)
    gardes, doublons = [], 0
    for fiches in par_nom.values():
        fiches.sort(key=lambda c: (-c["richesse"], -len(c["interet"]), c["uri"]))
        retenues: list[dict] = []
        for c in fiches:
            if any(geo.distance_m(c["lat"], c["lon"], r["lat"], r["lon"]) <= DOUBLON_M
                   for r in retenues):
                doublons += 1
            else:
                retenues.append(c)
        gardes += retenues
    return gardes, doublons


def _sites_existants(conn: sqlite3.Connection) -> list[tuple[str, float, float]]:
    return [(_cle_nom(r["nom"]), r["lat"], r["lon"]) for r in conn.execute(
        "SELECT nom, lat, lon FROM site_culturel WHERE id NOT LIKE 'dt-%' AND lat IS NOT NULL")]


_GENERIQUES = {"musee", "cathedrale", "eglise", "chateau", "abbaye", "chapelle", "palais", "maison",
               "saint", "sainte", "de", "du", "des", "la", "le", "les", "et", "d", "l", "au", "aux",
               "en", "centre", "site", "ancien", "ancienne", "notre", "dame", "cite", "jardin",
               "parc", "ville", "tour", "porte", "pont", "place", "hotel"}


def _distinctifs(nom_norm: str) -> set[str]:
    return {m for m in nom_norm.split() if m not in _GENERIQUES and len(m) > 2}


def _double_le_catalogue(c: dict, existants) -> bool:
    """Même lieu que dans le catalogue fait main : nom contenu dans l'autre, ou noms qui partagent
    au moins la moitié de leurs mots distinctifs (« Cathédrale Saint-Nazaire de Béziers » et
    « Cathédrale Saint Nazaire et Saint Celse »), à moins de 300 m (1 km si le nom est identique)."""
    mien = _cle_nom(c["nom"])
    d_mien = _distinctifs(mien)
    for nom, lat, lon in existants:
        d = geo.distance_m(c["lat"], c["lon"], lat, lon)
        # Les coordonnées du catalogue sont approximatives : même nom = même lieu jusqu'à 1 km.
        if d <= 3 * DOUBLON_CATALOGUE_M and (
                mien == nom or (len(mien) > 6 and (mien in nom or nom in mien))):
            return True
        if d > DOUBLON_CATALOGUE_M:
            continue
        d_nom = _distinctifs(nom)
        commun_ = d_mien & d_nom
        if commun_ and len(commun_) >= 0.5 * min(len(d_mien), len(d_nom)):
            return True
    return False


def importer(conn: sqlite3.Connection, csv_path: str | Path, *, max_total: int = MAX_TOTAL,
             max_par_gare: int = MAX_PAR_GARE, rayon_marche_km: float = RAYON_MARCHE_KM,
             rayon_max_km: float = RAYON_MAX_KM) -> Bilan:
    """Lit le CSV DATAtourisme et ajoute les lieux retenus à `site_culturel`. Le commit est laissé
    à l'appelant. Relançable : les lieux `dt-` sont mis à jour (upsert), jamais dupliqués."""
    debut = time.perf_counter()
    bilan = Bilan()
    gares = _gares(conn)
    existants = _sites_existants(conn)
    csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))
    candidats: list[dict] = []

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            bilan.lus += 1
            uri = (row.get("URI_ID_du_POI") or "").strip()
            nom = joli_nom(row.get("Nom_du_POI") or "")
            types = _types(row.get("Categories_de_POI", ""))
            motif = motif_exclusion(types)
            if motif:
                bilan.exclus[motif] += 1
                continue
            lat, lon = _flottant(row.get("Latitude", "")), _flottant(row.get("Longitude", ""))
            if lat is None or lon is None or not uri or not nom:
                bilan.exclus["sans_coordonnees_ou_nom"] += 1
                continue
            if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
                bilan.exclus["hors_occitanie"] += 1
                continue
            labels = _labels(row.get("Classements_du_POI", ""))
            motif = motif_exclusion_texte(nom, row.get("Description") or "", types, labels)
            if motif:
                bilan.exclus[motif] += 1
                continue
            proche = _gare_proche(gares, lat, lon, rayon_max_km * 1000)
            if not proche:
                bilan.exclus["aucune_gare_a_moins_de_%g_km" % rayon_max_km] += 1
                continue
            description = row.get("Description") or ""
            commune = _commune(row.get("Code_postal_et_commune", ""))
            themes = detecter_themes(nom, description, types, commune)
            if not themes:
                bilan.exclus["sans_theme_pedagogique"] += 1
                continue
            gare, dist = proche
            activites, libelle = _activites_et_libelle(types)
            noms_themes = [t for t, _ in themes]
            interet = resume(description)
            richesse = _richesse(labels, interet)
            if not interet:
                interet = (f"{libelle} à {commune or 'proximité de la gare'} "
                           f"(thèmes : {', '.join(noms_themes)}). Descriptif à vérifier auprès du site.")
            individuel = max(1, arrondi(dist / config.VITESSE_MARCHE_M_MIN))
            candidats.append({
                "id": identifiant(uri), "uri": uri, "nom": nom, "commune": commune,
                "lat": lat, "lon": lon, "gare_uic": gare[0], "gare_nom": gare[1],
                "distance_m": dist, "marchable": dist <= rayon_marche_km * 1000,
                "minutes_pied": individuel, "minutes_pied_groupe": commun.minutes_groupe(individuel),
                "themes": noms_themes, "score_themes": sum(s for _, s in themes),
                "niveaux": _niveaux(noms_themes), "activites": activites,
                "interet": interet, "richesse": richesse,
            })

    bilan.candidats = len(candidats)
    candidats, bilan.doublons = _dedupliquer(candidats)
    avant = len(candidats)
    candidats = [c for c in candidats if not _double_le_catalogue(c, existants)]
    bilan.deja_catalogue = avant - len(candidats)

    # Les meilleurs d'abord : marchables, puis richesse, force du thème, proximité.
    candidats.sort(key=lambda c: (not c["marchable"], -c["richesse"], -c["score_themes"],
                                  c["distance_m"], c["nom"], c["id"]))
    retenus: list[dict] = []
    for c in candidats:
        if len(retenus) >= max_total:
            bilan.exclus["plafond_total"] += 1
        elif bilan.par_gare[c["gare_nom"]] >= max_par_gare:
            bilan.exclus["plafond_par_gare"] += 1
        else:
            retenus.append(c)
            bilan.par_gare[c["gare_nom"]] += 1
            bilan.par_theme.update(c["themes"])

    for c in retenus:
        conn.execute(
            """INSERT INTO site_culturel (id, nom, commune, lat, lon, gare_uic, minutes_pied,
                 minutes_pied_groupe, themes, niveaux, activites, interet_pedagogique, richesse,
                 horaires, capacite_accueil, source_url, est_simule)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?,0)
               ON CONFLICT(id) DO UPDATE SET
                 nom=excluded.nom, commune=excluded.commune, lat=excluded.lat, lon=excluded.lon,
                 gare_uic=excluded.gare_uic, minutes_pied=excluded.minutes_pied,
                 minutes_pied_groupe=excluded.minutes_pied_groupe, themes=excluded.themes,
                 niveaux=excluded.niveaux, activites=excluded.activites,
                 interet_pedagogique=excluded.interet_pedagogique, richesse=excluded.richesse,
                 horaires=excluded.horaires, source_url=excluded.source_url""",
            (c["id"], c["nom"], c["commune"], round(c["lat"], 6), round(c["lon"], 6), c["gare_uic"],
             c["minutes_pied"], c["minutes_pied_groupe"], ";".join(c["themes"]),
             ";".join(c["niveaux"]), json.dumps(c["activites"], ensure_ascii=False), c["interet"],
             c["richesse"], HORAIRES, c["uri"]),
        )
    # Lieux dt- d'un import précédent qui ne sont plus retenus : retirés s'ils ne sont pas utilisés.
    ids = {c["id"] for c in retenus}
    for (sid,) in conn.execute("SELECT id FROM site_culturel WHERE id LIKE 'dt-%'").fetchall():
        if sid in ids:
            continue
        utilise = any(conn.execute(f"SELECT 1 FROM {t} WHERE site_id = ? LIMIT 1", (sid,)).fetchone()
                      for t in ("proposition", "retour_experience", "sondage_option"))
        if not utilise:
            conn.execute("DELETE FROM site_culturel WHERE id = ?", (sid,))

    bilan.importes = len(retenus)
    bilan.exemples = retenus
    db.meta_set(conn, "source_datatourisme",
                f"{LICENCE} ({bilan.importes} lieux, https://www.datatourisme.fr)")
    bilan.duree_s = time.perf_counter() - debut
    return bilan


def chemin_csv() -> Path | None:
    """data/datatourisme-reg-occ.csv, dans les dossiers de données habituels."""
    for dossier in config.dossiers_donnees():
        p = dossier / NOM_FICHIER
        if p.exists():
            return p
    return None


def actif() -> bool:
    return os.environ.get("LIO_DATATOURISME", "1").strip() != "0"


def importer_si_disponible(conn: sqlite3.Connection) -> Bilan | None:
    """Appelé par les ETL : importe si le fichier existe et si LIO_DATATOURISME n'est pas à 0."""
    chemin = chemin_csv()
    if not actif() or chemin is None:
        return None
    bilan = importer(conn, chemin)
    print(f"DATAtourisme : {bilan.importes} lieux importés depuis {chemin.name} "
          f"({bilan.duree_s:.1f} s)", file=sys.stderr)
    return bilan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--csv", type=Path, default=None, help="fichier DATAtourisme (défaut : data/)")
    parser.add_argument("--db", type=Path, default=None, help="base SQLite (défaut : LIO_DB_PATH)")
    parser.add_argument("--max", type=int, default=MAX_TOTAL, dest="max_total")
    parser.add_argument("--max-par-gare", type=int, default=MAX_PAR_GARE)
    parser.add_argument("--dry-run", action="store_true", help="calcule le bilan sans écrire")
    args = parser.parse_args()
    chemin = args.csv or chemin_csv()
    if chemin is None or not Path(chemin).exists():
        sys.exit(f"Fichier introuvable : placez {NOM_FICHIER} dans data/ ou passez --csv.")
    path = args.db or config.db_path()
    if not path.exists():
        sys.exit(f"Base introuvable : {path} (lancez d'abord etl.seed_demo ou le serveur).")
    with db.connexion(path) as conn:
        bilan = importer(conn, chemin, max_total=args.max_total, max_par_gare=args.max_par_gare)
        if args.dry_run:
            conn.rollback()
    print(bilan.texte())
    print(f"{'(simulation, rien écrit) ' if args.dry_run else ''}Base : {path}")


if __name__ == "__main__":
    main()
