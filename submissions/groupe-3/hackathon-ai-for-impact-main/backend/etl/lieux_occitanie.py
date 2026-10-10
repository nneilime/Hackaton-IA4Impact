"""Base JSON des lieux d'intérêt pédagogique d'Occitanie : OSM (Overpass) -> géocodage inverse -> LLM.

Pipeline en 4 étapes, toutes reprenables :
1. Extraction OSM, une requête Overpass par département (13). Rotation de miroirs, backoff
   exponentiel sur 429/504, réponses brutes en cache disque. Une requête trop lourde est découpée
   par famille de tags.
2. Nettoyage : lieux sans nom, hors sujet (parkings, distributeurs...) et doublons (même objet OSM
   vu par deux départements, ou deux objets à moins de 50 m de même type ou de nom proche).
3. Géocodage inverse par lots CSV (Géoplateforme IGN, repli sur api-adresse.data.gouv.fr) :
   commune, département et adresse. Résultats en cache disque.
4. Enrichissement LLM par lots de 10, sur une API compatible OpenAI (OpenAI, Groq, Ollama) en mode
   `json_object`. Les disciplines et niveaux sont filtrés contre les listes fermées : aucune valeur
   hors référentiel n'est conservée. Checkpoint JSONL après chaque lot : une reprise ne réinterroge
   jamais le LLM pour un lieu déjà enrichi.

Usage (depuis backend/) :
    OPENAI_API_KEY=sk-... .venv/bin/python -m etl.lieux_occitanie
    OPENAI_API_KEY=sk-... .venv/bin/python -m etl.lieux_occitanie --departements 46 --limite 30
    GROQ_API_KEY=gsk_... .venv/bin/python -m etl.lieux_occitanie --fournisseur groq
    .venv/bin/python -m etl.lieux_occitanie --fournisseur ollama --modele qwen2.5:7b
    .venv/bin/python -m etl.lieux_occitanie --sans-llm          # OSM + géocodage seulement

Variables d'environnement : LLM_FOURNISSEUR, LLM_BASE_URL, LLM_MODELE, LLM_API_KEY (prioritaire sur
OPENAI_API_KEY / GROQ_API_KEY), OVERPASS_URLS (miroirs séparés par des virgules).

Sorties dans data/lieux_occitanie/ (racine du repo, non versionné) :
    lieux_occitanie.json      la base finale (lieux enrichis et validés uniquement)
    lieux_non_enrichis.json   lieux extraits mais pas (encore) classés, avec la raison
    lieux_bruts.json          lieux nettoyés et géocodés, avant LLM
    rapport.json              compteurs du dernier passage
    checkpoint_llm.jsonl      progression du LLM (une ligne par lieu enrichi)
    cache/                    réponses Overpass brutes et géocodage
    pipeline.log
Relancer la même commande reprend là où le script s'était arrêté. Codes de sortie : 0 complet,
1 erreur fatale, 2 incomplet (département ou LLM en échec), 130 interrompu.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import io
import json
import logging
import math
import os
import random
import re
import signal
import threading
import time
import unicodedata
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

log = logging.getLogger("lieux_occitanie")

REPO_DIR = Path(__file__).resolve().parents[2]
SORTIE_DEFAUT = REPO_DIR / "data" / "lieux_occitanie"
USER_AGENT = "lio-hackathon-ai-for-impact/1.0 (backend/etl/lieux_occitanie.py)"

# --- Référentiels ----------------------------------------------------------------------------------

DEPARTEMENTS = {
    "09": "Ariège", "11": "Aude", "12": "Aveyron", "30": "Gard", "31": "Haute-Garonne",
    "32": "Gers", "34": "Hérault", "46": "Lot", "48": "Lozère", "65": "Hautes-Pyrénées",
    "66": "Pyrénées-Orientales", "81": "Tarn", "82": "Tarn-et-Garonne",
}

DISCIPLINES = (
    "SVT / Sciences de la Vie et de la Terre",
    "Histoire-Géographie / EMC",
    "Physique-Chimie",
    "Technologie / Ingénierie",
    "Arts Plastiques / Histoire des Arts",
    "Éducation Musicale",
    "Français / Littérature",
    "Philosophie",
    "Langues Vivantes",
    "EPS / Activités Physiques et Plein Air",
    "Enseignement Scientifique",
)
NIVEAUX = (
    "Maternelle (Cycle 1)",
    "Élémentaire / CP-CE2 (Cycle 2)",
    "Élémentaire / CM1-CM2 (Cycle 3)",
    "Collège / 6e (Cycle 3)",
    "Collège / 5e-3e (Cycle 4)",
    "Lycée Général & Technologique",
    "Lycée Professionnel",
)
(SVT, HIST_GEO, PHYS_CHIM, TECHNO, ARTS, MUSIQUE, FRANCAIS, PHILO, LANGUES, EPS,
 ENS_SCI) = DISCIPLINES
MATERNELLE, CYCLE_2, CM1_CM2, SIXIEME, CYCLE_4, LYCEE_GT, LYCEE_PRO = NIVEAUX

# Filet de sécurité : formulations courantes ramenées à la valeur exacte du référentiel. Le LLM
# reçoit les listes exactes ; ces alias ne servent que s'il abrège ou reformule.
ALIAS_DISCIPLINES = {
    "histoire": [HIST_GEO], "geographie": [HIST_GEO], "education civique": [HIST_GEO],
    "enseignement moral et civique": [HIST_GEO], "sciences de la vie": [SVT], "biologie": [SVT],
    "geologie": [SVT], "physique": [PHYS_CHIM], "chimie": [PHYS_CHIM],
    "sciences physiques": [PHYS_CHIM], "sciences de l ingenieur": [TECHNO], "arts": [ARTS],
    "histoire de l art": [ARTS], "musique": [MUSIQUE], "lettres": [FRANCAIS],
    "langues": [LANGUES], "langue vivante": [LANGUES], "anglais": [LANGUES],
    "espagnol": [LANGUES], "occitan": [LANGUES], "catalan": [LANGUES],
    "education physique et sportive": [EPS], "sport": [EPS], "activites physiques": [EPS],
}
ALIAS_NIVEAUX = {
    "maternelle": [MATERNELLE], "cycle 1": [MATERNELLE],
    "cp": [CYCLE_2], "ce1": [CYCLE_2], "ce2": [CYCLE_2], "cycle 2": [CYCLE_2],
    "cm1": [CM1_CM2], "cm2": [CM1_CM2], "cycle 3": [CM1_CM2, SIXIEME],
    "elementaire": [CYCLE_2, CM1_CM2], "college": [SIXIEME, CYCLE_4],
    "6e": [SIXIEME], "6eme": [SIXIEME], "sixieme": [SIXIEME],
    "5e": [CYCLE_4], "4e": [CYCLE_4], "3e": [CYCLE_4], "cycle 4": [CYCLE_4],
    "lycee": [LYCEE_GT], "lycee general": [LYCEE_GT], "lycee technologique": [LYCEE_GT],
    "seconde": [LYCEE_GT], "premiere": [LYCEE_GT], "terminale": [LYCEE_GT],
    "lycee pro": [LYCEE_PRO], "bac pro": [LYCEE_PRO], "cap": [LYCEE_PRO],
}

# --- Filtres OSM -----------------------------------------------------------------------------------

# L'ordre fixe aussi la priorité de type_site : le tag le plus précis gagne (natural=cave_entrance
# avant tourism=attraction, historic=castle avant tourism=museum) ; « attraction » vient en dernier.
FILTRES_OSM: dict[str, tuple[str, ...]] = {
    "natural": ("cave_entrance", "peak", "reserve"),
    "historic": ("castle", "monument", "archaeological_site", "ruins"),
    "tourism": ("museum", "zoo", "aquarium", "viewpoint", "attraction"),
    # natural=reserve n'est presque jamais utilisé dans OSM : les réserves naturelles y sont
    # cartographiées en leisure=nature_reserve.
    "leisure": ("nature_reserve",),
}
LIBELLES_TYPE = {
    "cave_entrance": "Entrée de cavité naturelle (grotte, gouffre)",
    "peak": "Sommet",
    "reserve": "Réserve naturelle",
    "nature_reserve": "Réserve naturelle",
    "castle": "Château",
    "monument": "Monument",
    "archaeological_site": "Site archéologique",
    "ruins": "Ruines",
    "museum": "Musée",
    "zoo": "Parc zoologique",
    "aquarium": "Aquarium",
    "viewpoint": "Point de vue",
    "attraction": "Site touristique",
}
# Détails factuels repris des tags OSM dans description_brute.
DETAILS_TAGS = (
    ("ele", "altitude : {} m"),
    ("historic:civilization", "civilisation : {}"),
    ("archaeological_site", "type de site archéologique : {}"),
    ("site_type", "type de site : {}"),
    ("castle_type", "type de château : {}"),
    ("museum", "thème du musée : {}"),
    ("start_date", "date : {}"),
    ("inscription", "inscription : « {} »"),
    ("operator", "gestionnaire : {}"),
)
AMENITES_HORS_SUJET = frozenset({
    "parking", "parking_space", "parking_entrance", "bicycle_parking", "motorcycle_parking",
    "atm", "bank", "vending_machine", "toilets", "fuel", "charging_station", "car_wash",
    "bench", "waste_basket", "waste_disposal", "recycling", "telephone", "post_box",
    "bus_station", "taxi", "restaurant", "fast_food", "cafe", "bar", "pub",
})
CLES_HORS_SUJET = ("shop", "parking", "public_transport")
NOM_HORS_SUJET = re.compile(
    r"\b(parking|stationnement|toilettes?|wc|sanitaires?|distributeurs?|dab|poubelles?|"
    r"arret de bus|aire de (pique nique|jeux|camping cars?|services|repos))\b"
)

MIROIRS_OVERPASS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
GEOCODEURS_INVERSES = (
    "https://data.geopf.fr/geocodage/reverse/csv",
    "https://api-adresse.data.gouv.fr/reverse/csv/",
)

DISTANCE_DOUBLON_M = 50
DISTANCE_ADRESSE_MAX_M = 250      # au-delà, l'adresse la plus proche ne décrit plus le lieu
TAILLE_LOT_GEOCODAGE = 1000
STATUTS_TEMPORAIRES = frozenset({408, 409, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 529})
MAX_TENTATIVES_HTTP_LLM = 6
MAX_ESSAIS_LLM = 3                # essais par lieu avant de le déclarer en échec pour ce passage
SEUIL_LOTS_EN_ECHEC = 5           # lots consécutifs sans aucun succès : le LLM est arrêté

FOURNISSEURS = {
    "openai": {"base_url": "https://api.openai.com/v1", "modele": "gpt-4o-mini",
               "cle_env": "OPENAI_API_KEY", "rpm": 300},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "modele": "llama-3.3-70b-versatile",
             "cle_env": "GROQ_API_KEY", "rpm": 25},
    "ollama": {"base_url": "http://localhost:11434/v1", "modele": "qwen2.5:7b",
               "cle_env": None, "rpm": 0},
}
CHAMPS_LLM = ("disciplines_scolaires", "niveaux_scolaires", "mots_cles_pedagogiques",
              "resume_pedagogique")


class ErreurReseau(Exception):
    """Service injoignable après toutes les tentatives : on réessaiera au prochain passage."""


class ErreurFatale(Exception):
    """Erreur non récupérable (clé refusée, modèle introuvable, quota épuisé...)."""


class ReponseInvalide(Exception):
    def __init__(self, message: str, tronquee: bool = False):
        super().__init__(message)
        self.tronquee = tronquee


# --- Utilitaires -----------------------------------------------------------------------------------

def maintenant_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normaliser_texte(s: str) -> str:
    """Minuscules, sans accents ni ponctuation : « Histoire-Géographie » -> « histoire geographie »."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def empreinte(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]


def ecrire_json(chemin: Path, donnees: Any) -> None:
    """Écriture atomique : un arrêt brutal ne laisse jamais un fichier à moitié écrit."""
    tmp = chemin.with_name(chemin.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, chemin)


def lire_json(chemin: Path, defaut: Any) -> Any:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return defaut
    except (OSError, ValueError) as e:
        log.warning("Fichier illisible ignoré (%s) : %s", chemin.name, e)
        return defaut


def retry_after(reponse: httpx.Response) -> float | None:
    try:
        return max(0.0, float(reponse.headers["retry-after"]))
    except (KeyError, ValueError):
        return None


def delai(tentative: int, base: float, plafond: float, impose: float | None = None) -> float:
    """Backoff exponentiel avec gigue ; un Retry-After du serveur est respecté (5 min au plus)."""
    if impose is not None:
        return min(impose, 300.0)
    return min(plafond, base * 2 ** tentative) * random.uniform(0.8, 1.2)


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


def _json_ou_none(reponse: httpx.Response) -> Any:
    try:
        return reponse.json()
    except ValueError:
        return None


# --- 1. Extraction Overpass ------------------------------------------------------------------------

def requete_overpass(dep: str, filtres: dict[str, tuple[str, ...]], timeout_s: int) -> str:
    selections = "\n".join(
        f'  nwr["{cle}"~"^({"|".join(valeurs)})$"]["name"](area.d);' for cle, valeurs in filtres.items()
    )
    return (
        f"[out:json][timeout:{timeout_s}];\n"
        f'area["ref:INSEE"="{dep}"]["boundary"="administrative"]["admin_level"="6"]->.d;\n'
        f"(\n{selections}\n);\nout center tags qt;"
    )


class Overpass:
    """Client Overpass : miroirs en rotation, backoff exponentiel, réponses brutes en cache disque."""

    def __init__(self, http: httpx.Client, miroirs: list[str], dossier_cache: Path, rafraichir: bool,
                 tentatives: int = 6, timeout_s: int = 300):
        self.http, self.miroirs, self.dossier = http, miroirs, dossier_cache
        self.rafraichir, self.tentatives, self.timeout_s = rafraichir, tentatives, timeout_s
        self._actif = 0              # indice du dernier miroir qui a répondu
        self._dernier_appel = 0.0

    def departement(self, dep: str) -> list[dict]:
        complete = requete_overpass(dep, FILTRES_OSM, self.timeout_s)
        parties = {cle: requete_overpass(dep, {cle: v}, self.timeout_s) for cle, v in FILTRES_OSM.items()}
        elements = self._lire_cache(f"overpass_{dep}", complete)
        if elements is not None:
            return elements
        en_cache = {cle: self._lire_cache(f"overpass_{dep}_{cle}", q) for cle, q in parties.items()}
        if all(e is not None for e in en_cache.values()):
            return [el for e in en_cache.values() for el in e]
        try:
            return self._telecharger(f"overpass_{dep}", complete)
        except ErreurReseau as e:
            log.warning("Département %s : requête complète en échec (%s), découpage par famille de tags.",
                        dep, e)
        elements = []
        for cle, requete in parties.items():
            partie = en_cache[cle]
            elements += partie if partie is not None else self._telecharger(f"overpass_{dep}_{cle}", requete)
        return elements

    def _lire_cache(self, nom: str, requete: str) -> list[dict] | None:
        if self.rafraichir:
            return None
        cache = lire_json(self.dossier / f"{nom}.json", None)
        reponse = cache.get("reponse") if isinstance(cache, dict) else None
        if (isinstance(reponse, dict) and isinstance(reponse.get("elements"), list)
                and cache.get("empreinte") == empreinte(requete)):
            return reponse["elements"]
        return None

    def _telecharger(self, nom: str, requete: str) -> list[dict]:
        reponse, miroir = self._executer(requete)
        ecrire_json(self.dossier / f"{nom}.json", {
            "empreinte": empreinte(requete), "extrait_le": maintenant_iso(), "miroir": miroir,
            "requete": requete, "reponse": reponse,
        })
        return reponse["elements"]

    def _executer(self, requete: str) -> tuple[dict, str]:
        derniere_erreur = "aucune tentative"
        for tentative in range(self.tentatives):
            miroir = self.miroirs[(self._actif + tentative) % len(self.miroirs)]
            impose = None
            # Politesse envers les serveurs publics : 2 s au moins entre deux requêtes.
            time.sleep(max(0.0, self._dernier_appel + 2.0 - time.monotonic()))
            self._dernier_appel = time.monotonic()
            try:
                r = self.http.post(miroir, data={"data": requete},
                                   timeout=httpx.Timeout(self.timeout_s + 30.0, connect=15.0))
            except httpx.HTTPError as e:
                derniere_erreur = type(e).__name__
            else:
                if r.status_code == 200:
                    donnees = _json_ou_none(r)
                    remarque = str(donnees.get("remark", "")) if isinstance(donnees, dict) else ""
                    # Délai ou mémoire dépassés : Overpass répond 200 avec une « remark » et une
                    # réponse partielle, qu'il ne faut surtout pas mettre en cache.
                    if (isinstance(donnees, dict) and isinstance(donnees.get("elements"), list)
                            and "error" not in remarque.lower()):
                        self._actif = (self._actif + tentative) % len(self.miroirs)
                        return donnees, miroir
                    derniere_erreur = f"réponse partielle ou illisible ({remarque[:150] or 'JSON invalide'})"
                else:
                    derniere_erreur = f"HTTP {r.status_code}"
                    impose = retry_after(r)
            log.warning("Overpass %s : %s (essai %d/%d).", httpx.URL(miroir).host, derniere_erreur,
                        tentative + 1, self.tentatives)
            if tentative + 1 < self.tentatives:
                time.sleep(delai(tentative, base=4.0, plafond=60.0, impose=impose))
        raise ErreurReseau(derniere_erreur)


# --- 2. Nettoyage ----------------------------------------------------------------------------------

@dataclass
class Lieu:
    type_osm: str
    id_osm: int
    nom: str
    lat: float
    lon: float
    tags: dict[str, str]
    type_site: str
    deps: set[str] = field(default_factory=set)   # départements dont la requête a remonté l'objet
    departement: str = ""                          # code retenu
    commune: str = ""
    adresse: str = ""
    description_brute: str = ""

    @property
    def cle(self) -> str:
        return f"{self.type_osm}/{self.id_osm}"


def choisir_type_site(tags: dict[str, str]) -> str | None:
    for cle, valeurs in FILTRES_OSM.items():
        if tags.get(cle) in valeurs:
            return tags[cle]
    return None


def est_hors_sujet(tags: dict[str, str], nom: str) -> bool:
    if tags.get("amenity") in AMENITES_HORS_SUJET or any(c in tags for c in CLES_HORS_SUJET):
        return True
    return NOM_HORS_SUJET.search(normaliser_texte(nom)) is not None


def noms_proches(a: str, b: str) -> bool:
    na, nb = normaliser_texte(a), normaliser_texte(b)
    if na == nb or (min(len(na), len(nb)) >= 5 and (na in nb or nb in na)):
        return True
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.85


def richesse(lieu: Lieu) -> int:
    t = lieu.tags
    return (len(t) + 5 * ("addr:street" in t or "addr:place" in t)
            + 5 * bool(t.get("description") or t.get("description:fr"))
            + 2 * (lieu.type_site != "attraction"))


def nettoyer(elements_par_dep: dict[str, list[dict]], stats: Counter) -> list[Lieu]:
    par_cle: dict[str, Lieu] = {}
    for dep, elements in elements_par_dep.items():
        for el in elements:
            stats["osm_elements_bruts"] += 1
            tags = el.get("tags") or {}
            nom = " ".join((tags.get("name:fr") or tags.get("name") or "").split())
            if not nom:
                stats["exclus_sans_nom"] += 1
                continue
            centre = el.get("center") or {}
            lat, lon = el.get("lat", centre.get("lat")), el.get("lon", centre.get("lon"))
            type_site = choisir_type_site(tags)
            if lat is None or lon is None or type_site is None or el.get("type") not in ("node", "way", "relation"):
                stats["exclus_incomplets"] += 1
                continue
            if est_hors_sujet(tags, nom):
                stats["exclus_hors_sujet"] += 1
                continue
            cle = f"{el['type']}/{el['id']}"
            if cle in par_cle:              # objet à cheval sur deux départements
                par_cle[cle].deps.add(dep)
                stats["doublons_osm"] += 1
                continue
            par_cle[cle] = Lieu(type_osm=el["type"], id_osm=int(el["id"]), nom=nom, lat=float(lat),
                                lon=float(lon), tags=dict(tags), type_site=type_site, deps={dep})
    return dedoublonner_geo(list(par_cle.values()), stats)


def dedoublonner_geo(lieux: list[Lieu], stats: Counter) -> list[Lieu]:
    """Fusionne les objets à moins de 50 m de même type ou de nom proche (ex. nœud + contour du
    même gouffre). Le plus riche en tags est gardé et complété par les tags de l'autre."""
    pas = 0.001   # ~111 m en latitude, ~72 m en longitude : les 9 cases voisines couvrent 50 m
    grille: dict[tuple[int, int], list[Lieu]] = {}
    gardes: list[Lieu] = []
    for lieu in sorted(lieux, key=lambda l: (-richesse(l), l.cle)):
        gx, gy = math.floor(lieu.lat / pas), math.floor(lieu.lon / pas)
        doublon = next((
            g for dx in (-1, 0, 1) for dy in (-1, 0, 1) for g in grille.get((gx + dx, gy + dy), ())
            if distance_m(g.lat, g.lon, lieu.lat, lieu.lon) < DISTANCE_DOUBLON_M
            and (g.type_site == lieu.type_site or noms_proches(g.nom, lieu.nom))
        ), None)
        if doublon is not None:
            for k, v in lieu.tags.items():
                doublon.tags.setdefault(k, v)
            doublon.deps |= lieu.deps
            stats["doublons_geo"] += 1
            continue
        grille.setdefault((gx, gy), []).append(lieu)
        gardes.append(lieu)
    return gardes


# --- 3. Géocodage inverse --------------------------------------------------------------------------

class GeocodeurInverse:
    """Géocodage inverse par lots CSV, avec cache disque par lieu (clé OSM + coordonnées)."""

    def __init__(self, http: httpx.Client, chemin_cache: Path, urls: tuple[str, ...] = GEOCODEURS_INVERSES,
                 tentatives: int = 5):
        self.http, self.chemin, self.urls, self.tentatives = http, chemin_cache, urls, tentatives
        self.cache: dict[str, dict] = lire_json(chemin_cache, {})

    def resoudre(self, lieux: list[Lieu]) -> dict[str, dict]:
        a_faire = [l for l in lieux if not self._en_cache(l)]
        log.info("Géocodage inverse : %d lieux en cache, %d à résoudre.", len(lieux) - len(a_faire), len(a_faire))
        for i in range(0, len(a_faire), TAILLE_LOT_GEOCODAGE):
            lot = a_faire[i:i + TAILLE_LOT_GEOCODAGE]
            try:
                self.cache.update(self._lot(lot))
            except ErreurReseau as e:
                log.warning("Géocodage indisponible (%s) : repli sur les adresses OSM pour %d lieux.",
                            e, len(a_faire) - i)
                break
            ecrire_json(self.chemin, self.cache)
            log.info("Géocodage : %d/%d.", min(i + TAILLE_LOT_GEOCODAGE, len(a_faire)), len(a_faire))
        return {l.cle: self.cache[l.cle] for l in lieux if self._en_cache(l)}

    def _en_cache(self, lieu: Lieu) -> bool:
        e = self.cache.get(lieu.cle)
        return (isinstance(e, dict) and abs(e.get("lat", 999) - lieu.lat) < 5e-4
                and abs(e.get("lon", 999) - lieu.lon) < 5e-4)

    def _lot(self, lot: list[Lieu]) -> dict[str, dict]:
        tampon = io.StringIO()
        ecrivain = csv.writer(tampon)
        ecrivain.writerow(["cle", "lat", "lon"])
        ecrivain.writerows([l.cle, f"{l.lat:.7f}", f"{l.lon:.7f}"] for l in lot)
        contenu = tampon.getvalue().encode("utf-8")
        derniere_erreur = "aucune tentative"
        for tentative in range(self.tentatives):
            url = self.urls[tentative % len(self.urls)]
            impose = None
            try:
                r = self.http.post(url, files={"data": ("lieux.csv", contenu, "text/csv")},
                                   timeout=httpx.Timeout(180.0, connect=15.0))
            except httpx.HTTPError as e:
                derniere_erreur = f"{httpx.URL(url).host} : {type(e).__name__}"
            else:
                if r.status_code == 200:
                    lignes = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", "replace"))))
                    if lignes and "result_citycode" in lignes[0]:
                        return self._interpreter(lot, lignes)
                    derniere_erreur = f"{httpx.URL(url).host} : CSV inattendu"
                else:
                    derniere_erreur = f"{httpx.URL(url).host} : HTTP {r.status_code}"
                    impose = retry_after(r)
            log.warning("Géocodage %s (essai %d/%d).", derniere_erreur, tentative + 1, self.tentatives)
            if tentative + 1 < self.tentatives:
                time.sleep(delai(tentative, base=2.0, plafond=30.0, impose=impose))
        raise ErreurReseau(derniere_erreur)

    @staticmethod
    def _interpreter(lot: list[Lieu], lignes: list[dict]) -> dict[str, dict]:
        if "cle" in lignes[0]:
            par_cle = {row.get("cle"): row for row in lignes}
        elif len(lignes) == len(lot):     # colonne perdue : les lignes reviennent dans l'ordre
            par_cle = {l.cle: row for l, row in zip(lot, lignes)}
        else:
            log.warning("Géocodage : réponse impossible à rapprocher du lot, lot ignoré.")
            return {}
        resultats = {}
        for l in lot:
            row = par_cle.get(l.cle)
            if row is None:
                continue
            trouve = row.get("result_status", "ok") == "ok" and bool(row.get("result_citycode"))
            try:
                distance = float(row.get("result_distance") or "inf")
            except ValueError:
                distance = float("inf")
            resultats[l.cle] = {
                "lat": l.lat, "lon": l.lon, "trouve": trouve,
                "nom": row.get("result_name") or "", "type": row.get("result_type") or "",
                "code_postal": row.get("result_postcode") or "", "commune": row.get("result_city") or "",
                "code_insee": row.get("result_citycode") or "",
                "distance_m": distance if math.isfinite(distance) else None,
            }
        return resultats


def adresse_osm(tags: dict[str, str]) -> str | None:
    voie, ville, cp = tags.get("addr:street") or tags.get("addr:place"), tags.get("addr:city"), tags.get("addr:postcode")
    if not voie or not (ville or cp):
        return None
    numero = tags.get("addr:housenumber")
    return f"{numero + ' ' if numero else ''}{voie}, {' '.join(x for x in (cp, ville) if x)}"


def localiser(lieu: Lieu, geo: dict | None) -> None:
    """Département, commune et adresse. La requête Overpass fait foi pour le département ; la
    commune du géocodeur n'est retenue que si elle est dans un de ces départements."""
    tags = lieu.tags
    geo_ok = bool(geo and geo.get("trouve") and geo["code_insee"][:2] in lieu.deps)
    lieu.departement = geo["code_insee"][:2] if geo_ok else min(lieu.deps)
    lieu.commune = (geo["commune"] if geo_ok else "") or tags.get("addr:city", "")
    ville = " ".join(x for x in (tags.get("addr:postcode") or (geo["code_postal"] if geo_ok else ""),
                                 lieu.commune) if x)
    adresse = adresse_osm(tags)
    proche = geo_ok and geo["distance_m"] is not None and geo["distance_m"] <= DISTANCE_ADRESSE_MAX_M
    if not adresse and proche and geo["nom"] and geo["type"] != "municipality":
        adresse = f"{geo['nom']}, {ville}" if ville else geo["nom"]
    lieu.adresse = adresse or ville


def decrire(lieu: Lieu) -> str:
    """Description factuelle tirée d'OSM uniquement : type, description OSM, puis détails des tags."""
    t = lieu.tags
    phrases = [LIBELLES_TYPE.get(lieu.type_site, lieu.type_site)]
    texte_osm = " ".join((t.get("description:fr") or t.get("description") or "").split())
    if texte_osm:
        phrases.append(texte_osm.rstrip(". "))
    details = [gabarit.format(t[cle].strip()) for cle, gabarit in DETAILS_TAGS if t.get(cle, "").strip()]
    if "ref:mhs" in t or t.get("heritage:operator") == "mhs":
        details.append("protégé au titre des monuments historiques")
    if details:
        phrases.append("; ".join(details))
    phrases = [p[0].upper() + p[1:] for p in phrases if p]
    return (". ".join(phrases) + ".")[:1000]


# --- 4. Enrichissement LLM -------------------------------------------------------------------------

class Referentiel:
    """Liste fermée : ramène une valeur du LLM à une valeur exacte du référentiel, ou l'écarte."""

    def __init__(self, valeurs: tuple[str, ...], alias: dict[str, list[str]]):
        self.valeurs = valeurs
        self.index: dict[str, list[str]] = {}
        for v in valeurs:
            sans_parentheses = re.sub(r"\(.*?\)", " ", v)
            for variante in {v, sans_parentheses, *v.split("/"), *sans_parentheses.split("/")}:
                cibles = self.index.setdefault(normaliser_texte(variante), [])
                if v not in cibles:
                    cibles.append(v)
        for a, cibles in alias.items():
            self.index[normaliser_texte(a)] = list(cibles)
        self.index.pop("", None)

    def filtrer(self, brut: Any) -> tuple[list[str], list[str]]:
        """(valeurs retenues dans l'ordre du référentiel, valeurs écartées)."""
        if isinstance(brut, str):
            brut = [brut]
        if not isinstance(brut, list):
            return [], ([] if brut is None else [repr(brut)[:80]])
        retenues: set[str] = set()
        ecartees = []
        for b in brut:
            cibles = self.index.get(normaliser_texte(b)) if isinstance(b, str) else None
            if cibles:
                retenues.update(cibles)
            else:
                ecartees.append(str(b)[:80])
        return [v for v in self.valeurs if v in retenues], ecartees


REF_DISCIPLINES = Referentiel(DISCIPLINES, ALIAS_DISCIPLINES)
REF_NIVEAUX = Referentiel(NIVEAUX, ALIAS_NIVEAUX)


def nettoyer_mots_cles(brut: Any) -> list[str]:
    if isinstance(brut, str):
        brut = re.split(r"[,;]", brut)
    if not isinstance(brut, list):
        return []
    mots: list[str] = []
    for m in brut:
        if isinstance(m, str):
            m = " ".join(m.split()).strip(" .;,-#").lower()
            if 2 <= len(m) <= 60 and m not in mots:
                mots.append(m)
    return mots[:10]


def valider_enrichissement(brut: Any, ecartees: list[str] | None = None) -> tuple[dict | None, str]:
    """Post-traitement strict d'une réponse du LLM (ou d'une ligne de checkpoint).

    Les disciplines et niveaux hors référentiel sont supprimés ; s'il n'en reste aucun, le lieu
    est rejeté. Renvoie (enrichissement validé ou None, raison du rejet)."""
    if not isinstance(brut, dict):
        return None, "objet JSON attendu"
    disciplines, hors_ref_d = REF_DISCIPLINES.filtrer(brut.get("disciplines_scolaires"))
    niveaux, hors_ref_n = REF_NIVEAUX.filtrer(brut.get("niveaux_scolaires"))
    if ecartees is not None:
        ecartees += hors_ref_d + hors_ref_n
    mots = nettoyer_mots_cles(brut.get("mots_cles_pedagogiques"))
    resume = " ".join(str(brut.get("resume_pedagogique") or "").split())
    if len(resume) > 700:
        coupe = resume[:700]
        resume = coupe[:coupe.rfind(". ") + 1] or coupe
    if not disciplines:
        return None, "aucune discipline du référentiel"
    if not niveaux:
        return None, "aucun niveau du référentiel"
    if len(mots) < 3:
        return None, "moins de 3 mots-clés"
    if len(resume) < 40:
        return None, "résumé pédagogique absent ou trop court"
    return {"disciplines_scolaires": disciplines, "niveaux_scolaires": niveaux,
            "mots_cles_pedagogiques": mots, "resume_pedagogique": resume}, ""


SYSTEME_LLM = f"""Tu es conseiller pédagogique de l'Éducation nationale française et tu prépares des \
sorties scolaires en Occitanie. Pour chaque lieu fourni, évalue ce qu'une classe peut y apprendre.

Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, de la forme :
{{"lieux": [{{"ref": "L1", "disciplines_scolaires": ["..."], "niveaux_scolaires": ["..."], \
"mots_cles_pedagogiques": ["..."], "resume_pedagogique": "..."}}]}}

Règles strictes :
- Exactement un objet par lieu, avec la même valeur de "ref" que dans la demande.
- "disciplines_scolaires" : 1 à 4 valeurs, recopiées caractère pour caractère depuis cette liste \
fermée : {json.dumps(DISCIPLINES, ensure_ascii=False)}
- "niveaux_scolaires" : 1 à 7 valeurs, recopiées caractère pour caractère depuis cette liste \
fermée : {json.dumps(NIVEAUX, ensure_ascii=False)}
- Toute valeur absente de ces listes sera supprimée : n'en invente pas, ne les abrège pas.
- Ne retiens que les niveaux pour lesquels la sortie est réaliste (âge, sécurité, accessibilité : \
un sommet de haute montagne ne convient pas à une classe de maternelle).
- "mots_cles_pedagogiques" : 4 à 8 notions des programmes scolaires, en français et en minuscules.
- "resume_pedagogique" : 1 ou 2 phrases (300 caractères au plus) sur ce que les élèves peuvent y \
étudier. N'invente aucun fait (date, chiffre, nom propre) absent des informations fournies ; reste \
général si elles sont minces."""


def extraire_json(contenu: str | None) -> Any:
    texte = re.sub(r"^```(?:json)?\s*|\s*```$", "", (contenu or "").strip())
    try:
        return json.loads(texte)
    except ValueError:
        debut, fin = texte.find("{"), texte.rfind("}")
        if debut < 0 or fin <= debut:
            raise ReponseInvalide("aucun objet JSON dans la réponse") from None
        try:
            return json.loads(texte[debut:fin + 1])
        except ValueError as e:
            raise ReponseInvalide(f"JSON invalide : {e}") from None


def associer_refs(donnees: Any, refs: dict[str, Lieu]) -> dict[str, Any]:
    """Retrouve l'objet renvoyé pour chaque ref, en tolérant les variantes de forme courantes."""
    liste = None
    if isinstance(donnees, list):
        liste = donnees
    elif isinstance(donnees, dict):
        if isinstance(donnees.get("lieux"), list):
            liste = donnees["lieux"]
        elif donnees and all(k in refs for k in donnees):          # {"L1": {...}, "L2": {...}}
            return {k: v for k, v in donnees.items() if isinstance(v, dict)}
        elif len(refs) == 1 and "disciplines_scolaires" in donnees:  # un seul lieu, objet nu
            return {next(iter(refs)): donnees}
        else:
            listes = [v for v in donnees.values() if isinstance(v, list)]
            liste = listes[0] if len(listes) == 1 else None
    if liste is None:
        raise ReponseInvalide("liste « lieux » absente de la réponse")
    items = {str(i.get("ref", "")).strip(): i for i in liste if isinstance(i, dict)}
    if len(refs) == 1 and len(liste) == 1 and isinstance(liste[0], dict) and not (items.keys() & refs.keys()):
        return {next(iter(refs)): liste[0]}
    return {ref: items[ref] for ref in refs if ref in items}


@dataclass
class ConfigLLM:
    fournisseur: str
    base_url: str
    modele: str
    cle_api: str | None
    rpm: int
    timeout_s: float
    workers: int
    taille_lot: int
    limite: int | None


def config_llm(args: argparse.Namespace) -> ConfigLLM:
    nom = args.fournisseur or os.environ.get("LLM_FOURNISSEUR", "openai")
    if nom not in FOURNISSEURS:
        raise ErreurFatale(f"Fournisseur LLM inconnu : {nom} (choix : {', '.join(FOURNISSEURS)}).")
    p = FOURNISSEURS[nom]
    base_url = (args.base_url or os.environ.get("LLM_BASE_URL") or p["base_url"]).rstrip("/")
    cle = os.environ.get("LLM_API_KEY") or (os.environ.get(p["cle_env"]) if p["cle_env"] else None)
    if p["cle_env"] and not cle and base_url == p["base_url"]:
        raise ErreurFatale(f"Clé API absente : définissez {p['cle_env']} (ou LLM_API_KEY), "
                           "ou lancez avec --sans-llm.")
    return ConfigLLM(
        fournisseur=nom, base_url=base_url,
        modele=args.modele or os.environ.get("LLM_MODELE") or p["modele"], cle_api=cle,
        rpm=p["rpm"] if args.rpm is None else args.rpm, timeout_s=args.timeout_llm,
        workers=max(1, args.workers), taille_lot=max(1, args.lot), limite=args.limite,
    )


class Limiteur:
    """Espace les requêtes pour rester sous un nombre de requêtes par minute (0 = sans limite)."""

    def __init__(self, rpm: int):
        self.intervalle = 60.0 / rpm if rpm > 0 else 0.0
        self._prochain = 0.0
        self._verrou = threading.Lock()

    def attendre(self) -> None:
        if not self.intervalle:
            return
        with self._verrou:
            maintenant = time.monotonic()
            attente = self._prochain - maintenant
            self._prochain = max(maintenant, self._prochain) + self.intervalle
        if attente > 0:
            time.sleep(attente)


class ClientLLM:
    """API chat/completions compatible OpenAI (OpenAI, Groq, Ollama), sortie en mode json_object."""

    def __init__(self, http: httpx.Client, cfg: ConfigLLM):
        self.http, self.cfg = http, cfg
        self.url = f"{cfg.base_url}/chat/completions"
        self.entetes = {"Authorization": f"Bearer {cfg.cle_api}"} if cfg.cle_api else {}
        self.limiteur = Limiteur(cfg.rpm)
        self.arret = threading.Event()
        self.valeurs_ecartees: Counter = Counter()
        self._verrou = threading.Lock()

    def classer(self, lot: list[Lieu]) -> tuple[dict[str, dict], dict[str, str]]:
        """Enrichit un lot. Les lieux invalides sont redemandés seuls ou en sous-lots (2 essais de
        plus au maximum). Renvoie (enrichissements validés, raisons d'échec), par clé OSM."""
        resultats: dict[str, dict] = {}
        echecs: dict[str, str] = {}
        file = deque([(lot, 0)])
        while file:
            sous_lot, essais = file.popleft()
            refs = {f"L{i}": l for i, l in enumerate(sous_lot, 1)}
            tronquee = False
            try:
                items = associer_refs(self._appeler(refs), refs)
                ok, ko = self._valider(items, refs)
            except ReponseInvalide as e:
                ok, ko, tronquee = {}, {l.cle: str(e) for l in sous_lot}, e.tronquee
            except ErreurReseau:
                if not resultats:
                    raise
                return resultats, echecs     # le reste du lot sera repris au prochain passage
            resultats.update(ok)
            restants = [l for l in sous_lot if l.cle in ko]
            if not restants:
                continue
            if essais + 1 >= MAX_ESSAIS_LLM:
                echecs.update({l.cle: ko[l.cle] for l in restants})
            elif len(restants) > 1 and (tronquee or essais >= 1):
                milieu = len(restants) // 2
                file.extend([(restants[:milieu], essais + 1), (restants[milieu:], essais + 1)])
            else:
                file.append((restants, essais + 1))
        return resultats, echecs

    def _valider(self, items: dict[str, Any], refs: dict[str, Lieu]) -> tuple[dict, dict]:
        ok, ko, ecartees = {}, {}, []
        for ref, lieu in refs.items():
            if ref not in items:
                ko[lieu.cle] = "absent de la réponse du LLM"
                continue
            enrichissement, raison = valider_enrichissement(items[ref], ecartees)
            if enrichissement:
                ok[lieu.cle] = {**enrichissement, "modele": self.cfg.modele, "enrichi_le": maintenant_iso()}
            else:
                ko[lieu.cle] = raison
        if ecartees:
            log.debug("Valeurs hors référentiel supprimées : %s", ecartees)
            with self._verrou:
                self.valeurs_ecartees.update(ecartees)
        return ok, ko

    def _appeler(self, refs: dict[str, Lieu]) -> Any:
        lieux = [{
            "ref": ref, "nom": l.nom, "type": LIBELLES_TYPE.get(l.type_site, l.type_site),
            "commune": l.commune or "inconnue", "departement": DEPARTEMENTS.get(l.departement, ""),
            "description": l.description_brute,
        } for ref, l in refs.items()]
        corps = {
            "model": self.cfg.modele,
            "temperature": 0.2,
            "max_tokens": 350 * len(refs) + 300,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEME_LLM},
                {"role": "user", "content": "Lieux à classer (JSON) :\n"
                                            + json.dumps(lieux, ensure_ascii=False, indent=1)},
            ],
        }
        donnees = self._post(corps)
        try:
            choix = donnees["choices"][0]
            contenu = choix["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ReponseInvalide("réponse sans contenu") from None
        if choix.get("finish_reason") == "length":
            raise ReponseInvalide("réponse tronquée (max_tokens atteint)", tronquee=True)
        return extraire_json(contenu)

    def _post(self, corps: dict) -> Any:
        derniere_erreur = "aucune tentative"
        for tentative in range(MAX_TENTATIVES_HTTP_LLM):
            if self.arret.is_set():
                raise ErreurReseau("arrêt demandé")
            self.limiteur.attendre()
            impose = None
            try:
                r = self.http.post(self.url, json=corps, headers=self.entetes,
                                   timeout=httpx.Timeout(self.cfg.timeout_s, connect=15.0))
            except httpx.HTTPError as e:
                derniere_erreur = type(e).__name__
            else:
                if r.status_code == 200:
                    donnees = _json_ou_none(r)
                    if donnees is None:
                        raise ReponseInvalide("réponse HTTP non JSON")
                    return donnees
                extrait = r.text[:300]
                if r.status_code in (401, 403):
                    raise ErreurFatale(f"clé API refusée par {self.cfg.fournisseur} (HTTP {r.status_code}) : {extrait}")
                if r.status_code == 404:
                    raise ErreurFatale(f"modèle « {self.cfg.modele} » ou URL {self.url} introuvable "
                                       f"(avec Ollama : ollama pull {self.cfg.modele}) : {extrait}")
                if r.status_code == 429 and "insufficient_quota" in extrait:
                    raise ErreurFatale(f"quota épuisé chez {self.cfg.fournisseur} : {extrait}")
                if r.status_code not in STATUTS_TEMPORAIRES:
                    # 400 inclus : Groq le renvoie quand le JSON généré est invalide, un nouvel essai
                    # suffit souvent.
                    raise ReponseInvalide(f"HTTP {r.status_code} : {extrait}")
                derniere_erreur = f"HTTP {r.status_code}"
                impose = retry_after(r)
            attente = delai(tentative, base=2.0, plafond=60.0, impose=impose)
            log.debug("LLM : %s, nouvel essai dans %.0f s.", derniere_erreur, attente)
            self.arret.wait(attente)
        raise ErreurReseau(derniere_erreur)


class Checkpoint:
    """Progression du LLM en JSONL : une ligne par lieu enrichi, ajoutée et synchronisée sur disque
    après chaque lot. Une ligne tronquée par un arrêt brutal est simplement ignorée."""

    def __init__(self, chemin: Path):
        self.chemin = chemin
        self.resultats: dict[str, dict] = {}
        self.echecs: dict[str, str] = {}
        if not chemin.exists():
            return
        brut = chemin.read_bytes()
        if brut and not brut.endswith(b"\n"):
            with chemin.open("ab") as f:   # isole une éventuelle dernière ligne tronquée
                f.write(b"\n")
        invalides = 0
        for ligne in brut.decode("utf-8", "replace").splitlines():
            if not ligne.strip():
                continue
            try:
                entree = json.loads(ligne)
            except ValueError:
                invalides += 1
                continue
            # Revalidation contre le référentiel courant : une ligne devenue invalide sera refaite.
            enrichissement, _ = valider_enrichissement(entree)
            if enrichissement is None or not isinstance(entree.get("cle"), str):
                invalides += 1
                continue
            self.resultats[entree["cle"]] = {**entree, **enrichissement}
        if invalides:
            log.warning("Checkpoint : %d ligne(s) invalide(s) ignorée(s), ces lieux seront refaits.", invalides)

    def ajouter(self, resultats: dict[str, dict]) -> None:
        if not resultats:
            return
        with self.chemin.open("a", encoding="utf-8") as f:
            for cle, enrichissement in resultats.items():
                f.write(json.dumps({"cle": cle, **enrichissement}, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self.resultats.update(resultats)
        for cle in resultats:
            self.echecs.pop(cle, None)


def enrichir(lieux: list[Lieu], checkpoint: Checkpoint, client: ClientLLM, cfg: ConfigLLM,
             stats: Counter) -> bool:
    """Envoie au LLM les lieux absents du checkpoint, par lots. Renvoie True si tous les lieux
    soumis pendant ce passage ont été enrichis."""
    a_faire = [l for l in lieux if l.cle not in checkpoint.resultats]
    if cfg.limite is not None:
        a_faire = a_faire[:cfg.limite]
    lots = [a_faire[i:i + cfg.taille_lot] for i in range(0, len(a_faire), cfg.taille_lot)]
    log.info("LLM %s (%s) : %d lieux déjà enrichis (checkpoint), %d à traiter en %d lots.",
             cfg.fournisseur, cfg.modele, len(checkpoint.resultats), len(a_faire), len(lots))
    if not lots:
        return True

    def tache(lot: list[Lieu]):
        return None if client.arret.is_set() else client.classer(lot)

    lots_sans_succes = lots_injoignables = 0
    disjoncte = False
    executeur = ThreadPoolExecutor(max_workers=cfg.workers)
    try:
        futurs = [executeur.submit(tache, lot) for lot in lots]
        for n, futur in enumerate(as_completed(futurs), 1):
            try:
                resultat = futur.result()
            except ErreurReseau as e:
                log.warning("Lot %d/%d : LLM injoignable (%s), ces lieux seront repris au prochain passage.",
                            n, len(lots), e)
                resultat = ({}, {})
                lots_injoignables += 1
            if resultat is None:     # arrêt demandé avant le démarrage du lot
                continue
            ok, ko = resultat
            checkpoint.ajouter(ok)
            checkpoint.echecs.update(ko)
            stats["llm_enrichis_ce_passage"] += len(ok)
            stats["llm_echecs_ce_passage"] += len(ko)
            log.info("Lot %d/%d : %d enrichis, %d en échec. Total : %d/%d.", n, len(lots), len(ok),
                     len(ko), len(checkpoint.resultats), len(lieux))
            for cle, raison in ko.items():
                log.debug("  %s : %s", cle, raison)
            lots_sans_succes = 0 if ok else lots_sans_succes + 1
            if lots_sans_succes >= SEUIL_LOTS_EN_ECHEC and not client.arret.is_set():
                log.error("%d lots consécutifs sans aucun succès : arrêt de l'étape LLM. "
                          "Vérifiez le service puis relancez, la progression est conservée.", lots_sans_succes)
                disjoncte = True
                client.arret.set()
    except BaseException:
        # Ctrl+C ou erreur fatale : plus aucun nouvel appel, on n'attend pas les appels en vol.
        client.arret.set()
        executeur.shutdown(wait=False, cancel_futures=True)
        raise
    client.arret.set()
    executeur.shutdown(wait=True, cancel_futures=True)
    return not disjoncte and not lots_injoignables and not stats["llm_echecs_ce_passage"]


# --- 5. Export -------------------------------------------------------------------------------------

class LieuExport(BaseModel):
    """Schéma cible d'un lieu. type_osm s'ajoute à id_osm : un nœud et un chemin OSM peuvent porter
    le même identifiant numérique."""
    model_config = ConfigDict(extra="forbid")

    id_osm: int
    type_osm: Literal["node", "way", "relation"]
    nom: str = Field(min_length=1)
    adresse: str
    commune: str
    departement: Literal[tuple(DEPARTEMENTS.values())]  # type: ignore[valid-type]
    latitude: float = Field(ge=42.2, le=45.2)
    longitude: float = Field(ge=-0.5, le=5.0)
    type_site: str
    description_brute: str
    disciplines_scolaires: list[Literal[DISCIPLINES]] = Field(min_length=1)  # type: ignore[valid-type]
    niveaux_scolaires: list[Literal[NIVEAUX]] = Field(min_length=1)  # type: ignore[valid-type]
    mots_cles_pedagogiques: list[str] = Field(min_length=3)
    resume_pedagogique: str = Field(min_length=40, max_length=700)


def ligne_brute(l: Lieu) -> dict:
    return {
        "cle": l.cle, "id_osm": l.id_osm, "type_osm": l.type_osm, "nom": l.nom, "adresse": l.adresse,
        "commune": l.commune, "departement": DEPARTEMENTS[l.departement], "latitude": round(l.lat, 6),
        "longitude": round(l.lon, 6), "type_site": l.type_site, "description_brute": l.description_brute,
        "tags_osm": l.tags,
    }


def exporter(lieux: list[Lieu], checkpoint: Checkpoint, sortie: Path, stats: Counter) -> list[dict]:
    base, non_enrichis = [], []
    for l in lieux:
        enrichissement = checkpoint.resultats.get(l.cle)
        if enrichissement is None:
            non_enrichis.append({"cle": l.cle, "nom": l.nom, "commune": l.commune, "type_site": l.type_site,
                                 "raison": checkpoint.echecs.get(l.cle, "pas encore enrichi")})
            continue
        try:
            base.append(LieuExport(
                id_osm=l.id_osm, type_osm=l.type_osm, nom=l.nom, adresse=l.adresse, commune=l.commune,
                departement=DEPARTEMENTS[l.departement], latitude=round(l.lat, 6),
                longitude=round(l.lon, 6), type_site=l.type_site, description_brute=l.description_brute,
                **{k: enrichissement[k] for k in CHAMPS_LLM},
            ).model_dump())
        except ValidationError as e:
            erreur = e.errors()[0]
            non_enrichis.append({"cle": l.cle, "nom": l.nom, "commune": l.commune, "type_site": l.type_site,
                                 "raison": f"schéma : {'.'.join(map(str, erreur['loc']))} {erreur['msg']}"})
    base.sort(key=lambda d: (d["departement"], d["commune"], d["nom"]))
    ecrire_json(sortie / "lieux_occitanie.json", base)
    ecrire_json(sortie / "lieux_non_enrichis.json", non_enrichis)
    stats["lieux_exportes"] = len(base)
    stats["lieux_non_enrichis"] = len(non_enrichis)
    log.info("Export : %d lieux dans %s, %d non enrichis.", len(base), sortie / "lieux_occitanie.json",
             len(non_enrichis))
    return base


# --- Orchestration ---------------------------------------------------------------------------------

def departements(texte: str) -> list[str]:
    deps = [d.strip().zfill(2) for d in texte.split(",") if d.strip()]
    inconnus = [d for d in deps if d not in DEPARTEMENTS]
    if inconnus or not deps:
        raise argparse.ArgumentTypeError(
            f"départements hors Occitanie : {', '.join(inconnus) or '(aucun)'} (choix : {', '.join(DEPARTEMENTS)})")
    return list(dict.fromkeys(deps))


def analyser_arguments(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Base JSON des lieux d'intérêt pédagogique d'Occitanie "
                                            "(OSM -> géocodage inverse -> LLM).")
    p.add_argument("--departements", type=departements, default=list(DEPARTEMENTS),
                   help="codes séparés par des virgules (défaut : les 13)")
    p.add_argument("--sortie", type=Path, default=SORTIE_DEFAUT, help=f"dossier de sortie (défaut : {SORTIE_DEFAUT})")
    p.add_argument("--fournisseur", choices=list(FOURNISSEURS), help="défaut : LLM_FOURNISSEUR ou openai")
    p.add_argument("--modele", help="modèle LLM (défaut selon le fournisseur, ou LLM_MODELE)")
    p.add_argument("--base-url", help="URL d'une API compatible OpenAI (défaut selon le fournisseur)")
    p.add_argument("--lot", type=int, default=10, help="lieux par appel LLM et par checkpoint (défaut : 10)")
    p.add_argument("--workers", type=int, default=2, help="appels LLM en parallèle (défaut : 2)")
    p.add_argument("--rpm", type=int, help="requêtes LLM par minute au plus (défaut selon le fournisseur, 0 = libre)")
    p.add_argument("--limite", type=int, help="nombre maximal de lieux envoyés au LLM pendant ce passage")
    p.add_argument("--timeout-llm", type=float, default=180.0, help="délai d'un appel LLM en secondes")
    p.add_argument("--sans-llm", action="store_true", help="s'arrêter après l'extraction et le géocodage")
    p.add_argument("--sans-geocodage", action="store_true", help="adresses tirées des seuls tags OSM")
    p.add_argument("--rafraichir-osm", action="store_true", help="ignorer le cache Overpass")
    p.add_argument("-v", "--verbeux", action="store_true")
    return p.parse_args(argv)


def configurer_logs(sortie: Path, verbeux: bool) -> None:
    log.handlers.clear()
    log.setLevel(logging.DEBUG if verbeux else logging.INFO)
    log.propagate = False
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
    fichier = logging.FileHandler(sortie / "pipeline.log", encoding="utf-8")
    fichier.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    log.addHandler(console)
    log.addHandler(fichier)


def _sur_sigterm(signum, frame):
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    args = analyser_arguments(argv)
    sortie: Path = args.sortie
    (sortie / "cache").mkdir(parents=True, exist_ok=True)
    configurer_logs(sortie, args.verbeux)
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, _sur_sigterm)   # kill / arrêt d'un conteneur : même reprise que Ctrl+C
    debut = time.monotonic()

    try:
        cfg = None if args.sans_llm else config_llm(args)
    except ErreurFatale as e:
        log.error("%s", e)
        return 1

    miroirs = [u.strip() for u in os.environ.get("OVERPASS_URLS", "").split(",") if u.strip()] or list(MIROIRS_OVERPASS)
    stats: Counter = Counter()
    deps_en_echec: list[str] = []
    lieux: list[Lieu] = []
    pret_a_exporter = interrompu = fatal = False
    llm_complet = True
    checkpoint = Checkpoint(sortie / "checkpoint_llm.jsonl")
    client: ClientLLM | None = None

    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as http:
        try:
            overpass = Overpass(http, miroirs, sortie / "cache", args.rafraichir_osm)
            elements: dict[str, list[dict]] = {}
            for dep in args.departements:
                try:
                    elements[dep] = overpass.departement(dep)
                    log.info("OSM %s (%s) : %d éléments.", dep, DEPARTEMENTS[dep], len(elements[dep]))
                    if not elements[dep]:
                        log.warning("Aucun élément pour le département %s : zone introuvable ?", dep)
                except ErreurReseau as e:
                    deps_en_echec.append(dep)
                    log.error("OSM %s (%s) : échec définitif (%s). Relancez plus tard, les autres "
                              "départements sont conservés.", dep, DEPARTEMENTS[dep], e)

            lieux = nettoyer(elements, stats)
            log.info("Nettoyage : %d lieux retenus (%d sans nom, %d hors sujet, %d doublons OSM, "
                     "%d doublons à moins de %d m).", len(lieux), stats["exclus_sans_nom"],
                     stats["exclus_hors_sujet"], stats["doublons_osm"], stats["doublons_geo"], DISTANCE_DOUBLON_M)

            geo = {} if args.sans_geocodage else GeocodeurInverse(http, sortie / "cache" / "geocodage.json").resoudre(lieux)
            for lieu in lieux:
                localiser(lieu, geo.get(lieu.cle))
                lieu.description_brute = decrire(lieu)
            stats["lieux_sans_commune"] = sum(1 for l in lieux if not l.commune)
            ecrire_json(sortie / "lieux_bruts.json", [ligne_brute(l) for l in lieux])
            pret_a_exporter = True

            if cfg is not None:
                client = ClientLLM(http, cfg)
                llm_complet = enrichir(lieux, checkpoint, client, cfg, stats)
        except KeyboardInterrupt:
            interrompu = True
            log.warning("Interruption : progression sauvegardée, relancez la même commande pour reprendre.")
        except ErreurFatale as e:
            fatal = True
            log.error("Arrêt : %s", e)

        if pret_a_exporter:
            base = exporter(lieux, checkpoint, sortie, stats)
            ecrire_json(sortie / "rapport.json", {
                "genere_le": maintenant_iso(),
                "duree_s": round(time.monotonic() - debut),
                "departements_demandes": args.departements,
                "departements_en_echec": deps_en_echec,
                "llm": {"fournisseur": cfg.fournisseur, "modele": cfg.modele} if cfg else None,
                "compteurs": dict(stats),
                "lieux_par_departement": dict(Counter(d["departement"] for d in base).most_common()),
                "lieux_par_type_site": dict(Counter(d["type_site"] for d in base).most_common()),
                "disciplines": dict(Counter(x for d in base for x in d["disciplines_scolaires"]).most_common()),
                "niveaux": dict(Counter(x for d in base for x in d["niveaux_scolaires"]).most_common()),
                "valeurs_hors_referentiel_supprimees": dict(client.valeurs_ecartees.most_common(30)) if client else {},
            })

    if interrompu:
        return 130
    if fatal:
        return 1
    return 2 if deps_en_echec or not llm_complet else 0


if __name__ == "__main__":
    raise SystemExit(main())
