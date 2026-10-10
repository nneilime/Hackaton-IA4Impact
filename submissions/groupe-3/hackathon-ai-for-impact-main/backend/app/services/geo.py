"""Géographie : table locale des communes d'Occitanie, géocodage, gare la plus proche.

Le géocodage s'appuie d'abord sur la table locale (rapide, hors ligne, déterministe). Si le lieu
n'y figure pas, on tente l'API Adresse (https://api-adresse.data.gouv.fr/search/) avec un délai de
2 s ; en cas d'échec, on reste sur le repli local.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .. import config
from .texte import normaliser

# Communes d'Occitanie (centre approximatif). Toutes sont en Occitanie (règle R8).
COMMUNES: dict[str, tuple[float, float]] = {
    "Foix": (42.9653, 1.6071), "Pamiers": (43.1167, 1.6108),
    "Tarascon-sur-Ariège": (42.8455, 1.6056), "Ax-les-Thermes": (42.7194, 1.8386),
    "Saint-Girons": (42.9850, 1.1460), "Lavelanet": (42.9311, 1.8486),
    "Mirepoix": (43.0878, 1.8742), "Saverdun": (43.2361, 1.5747), "Varilhes": (43.0461, 1.6297),
    "Toulouse": (43.6045, 1.4440), "Blagnac": (43.6372, 1.3897), "Colomiers": (43.6114, 1.3353),
    "Tournefeuille": (43.5853, 1.3447), "Muret": (43.4614, 1.3267), "Balma": (43.6111, 1.4994),
    "L'Union": (43.6575, 1.4842), "Ramonville-Saint-Agne": (43.5461, 1.4783),
    "Castanet-Tolosan": (43.5164, 1.4986), "Villefranche-de-Lauragais": (43.4006, 1.7175),
    "Saint-Gaudens": (43.1078, 0.7233), "Revel": (43.4586, 2.0044),
    "Carcassonne": (43.2130, 2.3491), "Castelnaudary": (43.3183, 1.9539),
    "Limoux": (43.0547, 2.2186), "Narbonne": (43.1844, 3.0039),
    "Lézignan-Corbières": (43.2014, 2.7578), "Béziers": (43.3442, 3.2158),
    "Agde": (43.3108, 3.4758), "Sète": (43.4028, 3.6928), "Montpellier": (43.6108, 3.8767),
    "Lunel": (43.6747, 4.1358), "Lodève": (43.7317, 3.3194), "Nîmes": (43.8367, 4.3601),
    "Alès": (44.1250, 4.0817), "Beaucaire": (43.8081, 4.6439), "Uzès": (44.0125, 4.4197),
    "Le Vigan": (43.9906, 3.6058), "Perpignan": (42.6986, 2.8956), "Prades": (42.6175, 2.4219),
    "Céret": (42.4856, 2.7475), "Argelès-sur-Mer": (42.5464, 3.0239),
    "Albi": (43.9289, 2.1464), "Castres": (43.6061, 2.2400), "Gaillac": (43.9014, 1.8969),
    "Carmaux": (44.0506, 2.1581), "Lavaur": (43.6989, 1.8192), "Graulhet": (43.7614, 1.9892),
    "Mazamet": (43.4917, 2.3736), "Rodez": (44.3506, 2.5750), "Millau": (44.0975, 3.0778),
    "Villefranche-de-Rouergue": (44.3517, 2.0342), "Decazeville": (44.5600, 2.2508),
    "Saint-Affrique": (43.9583, 2.8869), "Figeac": (44.6086, 2.0317), "Cahors": (44.4475, 1.4419),
    "Gourdon": (44.7372, 1.3833), "Souillac": (44.8972, 1.4772), "Montauban": (44.0176, 1.3550),
    "Moissac": (44.1053, 1.0853), "Castelsarrasin": (44.0400, 1.1072),
    "Caussade": (44.1606, 1.5372), "Auch": (43.6465, 0.5855), "Condom": (43.9583, 0.3722),
    "L'Isle-Jourdain": (43.6136, 1.0811), "Tarbes": (43.2328, 0.0781),
    "Lourdes": (43.0947, -0.0458), "Lannemezan": (43.1253, 0.3842),
    "Bagnères-de-Bigorre": (43.0653, 0.1492), "Mende": (44.5181, 3.5006),
    "Marvejols": (44.5531, 3.2914), "Langogne": (44.7272, 3.8550), "Florac": (44.3247, 3.5933),
}
_COMMUNES_NORM = sorted(((normaliser(c), c) for c in COMMUNES), key=lambda x: -len(x[0]))

# Emprise approximative de l'Occitanie (repli pour R8 quand le lieu vient de l'API Adresse)
BBOX_OCCITANIE = (42.33, -0.33, 45.05, 4.85)


@dataclass
class LieuGeocode:
    libelle: str
    lat: float
    lon: float
    commune: str | None
    en_occitanie: bool | None
    source: str  # "local" ou "api-adresse"


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def commune_dans_texte(texte: str) -> str | None:
    """Première commune de la table trouvée dans le texte (la plus longue l'emporte)."""
    n = f" {normaliser(texte)} "
    for norm, nom in _COMMUNES_NORM:
        if f" {norm} " in n:
            return nom
    return None


def toutes_communes_dans_texte(texte: str) -> list[tuple[int, str]]:
    n = f" {normaliser(texte)} "
    trouvees = []
    for norm, nom in _COMMUNES_NORM:
        i = n.find(f" {norm} ")
        if i >= 0 and not any(i >= j and i < j + len(normaliser(x)) for j, x in trouvees):
            trouvees.append((i, nom))
    return sorted(trouvees)


def en_occitanie(lat: float, lon: float) -> bool:
    la0, lo0, la1, lo1 = BBOX_OCCITANIE
    return la0 <= lat <= la1 and lo0 <= lon <= lo1


def _api_adresse(q: str) -> LieuGeocode | None:
    if not config.geocodage_en_ligne() or not q.strip():
        return None
    url = "https://api-adresse.data.gouv.fr/search/?" + urllib.parse.urlencode({"q": q, "limit": 1})
    try:
        with urllib.request.urlopen(url, timeout=2) as rep:
            data = json.loads(rep.read().decode("utf-8"))
    except Exception:
        return None
    feats = data.get("features") or []
    if not feats:
        return None
    f = feats[0]
    lon, lat = f["geometry"]["coordinates"]
    props = f.get("properties", {})
    if float(props.get("score", 0)) < 0.4:
        return None
    contexte = props.get("context", "")
    return LieuGeocode(
        libelle=q.strip(), lat=float(lat), lon=float(lon), commune=props.get("city"),
        en_occitanie=("Occitanie" in contexte) if contexte else en_occitanie(lat, lon),
        source="api-adresse",
    )


def geocoder(libelle: str) -> LieuGeocode | None:
    """Lieu de départ -> coordonnées. Table locale d'abord, API Adresse ensuite (2 s max)."""
    commune = commune_dans_texte(libelle)
    if commune:
        lat, lon = COMMUNES[commune]
        return LieuGeocode(libelle, lat, lon, commune, True, "local")
    return _api_adresse(libelle)


def commune_proche(lat: float, lon: float, rayon_m: float = 6000) -> str | None:
    best = min(COMMUNES.items(), key=lambda kv: distance_m(lat, lon, kv[1][0], kv[1][1]))
    return best[0] if distance_m(lat, lon, *best[1]) <= rayon_m else None


def gare_la_plus_proche(conn: sqlite3.Connection, lat: float, lon: float) -> tuple[sqlite3.Row, float] | None:
    """Gare desservie par au moins un train autorisé aux groupes, la plus proche du lieu."""
    rows = conn.execute(
        """SELECT g.* FROM gare g WHERE g.lat IS NOT NULL AND EXISTS (
             SELECT 1 FROM desserte d JOIN train t ON t.numero = d.train_numero
             WHERE d.gare_uic = g.code_uic AND t.autorise_groupe = 1)"""
    ).fetchall()
    if not rows:
        return None
    best = min(rows, key=lambda g: distance_m(lat, lon, g["lat"], g["lon"]))
    d = distance_m(lat, lon, best["lat"], best["lon"])
    if d > config.RAYON_GARE_KM * 1000:
        return None
    return best, d


def nettoyer_libelle(texte: str) -> str:
    t = re.sub(r"\s+", " ", texte or "").strip(" .,;:!?")
    return t[:1].upper() + t[1:] if t else t
