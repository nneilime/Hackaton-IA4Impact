"""Métriques géographiques du top 58 : gare/arrêt liO le plus proche, distance, temps de marche.

Usage : python -m etl.enrichir_top58   (depuis backend/)  ->  data/top58_metriques.json (ignoré par git)

Sources : fréquentation 2021 du fichier top-des-sites-touristiques-2021 ; arrêts du GTFS liO
(stops.txt seulement) ; distance par calcul haversine (vol d'oiseau). Aucune valeur inventée.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402

SRC_FREQ = "fréquentation 2021 : fichier top-des-sites-touristiques-2021"
SRC_GTFS = "GTFS liO stops.txt"
SRC_CALC = "calcul haversine"
SRC_MARCHE = (f"calcul : distance haversine × {config.MARCHE_COEF_DETOUR} (détour) / "
              f"{config.MARCHE_VITESSE_KMH} km/h (hypothèse, groupe scolaire)")
RAYON_TERRE_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * RAYON_TERRE_KM * math.asin(math.sqrt(a))


def marche_minutes(distance_km: float) -> int:
    return round(distance_km * config.MARCHE_COEF_DETOUR / config.MARCHE_VITESSE_KMH * 60)


def charger_arrets(chemin: Path) -> list[dict]:
    arrets = []
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                arrets.append({"id": r["stop_id"], "nom": r["stop_name"],
                               "lat": float(r["stop_lat"]), "lon": float(r["stop_lon"])})
            except (ValueError, KeyError):
                continue
    return arrets


def plus_proche(lat: float, lon: float, arrets: list[dict]) -> tuple[dict, float] | None:
    """Arrêt dont le nom contient « gare » en priorité (gare SNCF/routière), sinon n'importe quel arrêt."""
    gares = [a for a in arrets if "gare" in a["nom"].lower()] or arrets
    if not gares:
        return None
    best = min(gares, key=lambda a: haversine_km(lat, lon, a["lat"], a["lon"]))
    return best, haversine_km(lat, lon, best["lat"], best["lon"])


def construire(sites: list[dict], arrets: list[dict]) -> list[dict]:
    out = []
    for s in sites:
        e = {"site": s["site"], "commune": s.get("commune"),
             "total_visites": s.get("total_visites"),
             "sources": {"total_visites": SRC_FREQ}}
        if s.get("total_visites") is None:
            e["total_visites_note"] = "non publié"
        lat, lon = s.get("latitude"), s.get("longitude")
        res = plus_proche(lat, lon, arrets) if lat is not None and lon is not None else None
        if res:
            a, d = res
            e.update({"gare_proche": a["nom"], "gare_proche_id": a["id"],
                      "distance_gare_km": round(d, 2), "marche_min": marche_minutes(d)})
            e["sources"].update({"gare_proche": SRC_GTFS, "distance_gare_km": SRC_CALC,
                                 "marche_min": SRC_MARCHE})
        out.append(e)
    return out


def main() -> Path:
    sites = json.loads(config.RAG_TOP58_JSON.read_text(encoding="utf-8"))
    arrets = charger_arrets(config.GTFS_STOPS_TXT)
    metriques = construire(sites, arrets)
    sortie = config.RAG_TOP58_METRIQUES
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps({"hypotheses": {"vitesse_kmh": config.MARCHE_VITESSE_KMH,
                                                 "coef_detour": config.MARCHE_COEF_DETOUR},
                                  "sites": metriques}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(metriques)} sites -> {sortie}")
    return sortie


if __name__ == "__main__":
    main()
