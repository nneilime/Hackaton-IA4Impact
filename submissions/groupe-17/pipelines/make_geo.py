"""Positions GÉOGRAPHIQUES FICTIVES (le jeu de données n'en contient pas : « métropole toulousaine »).
Chaque résidence est placée dans un secteur de l'agglomération ; bâtiments et logements sont dispersés autour.
À remplacer par de vraies coordonnées si In'li en fournit."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
import pandas as pd
from batia.config import RAW
from batia.io import save_table

CENTRES = {  # (lat, lon, secteur fictif)
    "RES-A": (43.6360, 1.3900, "Nord-Ouest"),
    "RES-B": (43.6540, 1.4850, "Nord-Est"),
    "RES-C": (43.5370, 1.3450, "Sud-Ouest"),
    "RES-D": (43.5480, 1.4760, "Sud-Est"),
    "RES-E": (43.6110, 1.3340, "Ouest"),
    "RES-F": (43.6110, 1.4990, "Est"),
    "RES-G": (43.6045, 1.4440, "Centre"),
    "RES-H": (43.5860, 1.4230, "Sud"),
}


def main():
    rng = np.random.default_rng(7)
    bat = pd.read_csv(RAW / "02_batiments.csv")
    log = pd.read_csv(RAW / "03_logements.csv")[
        [
            "logement_id",
            "batiment_id",
            "residence_id",
            "etage",
            "typologie",
            "surface_habitable_m2",
        ]
    ]
    rows = []
    for rid, g in bat.groupby("residence_id"):
        lat0, lon0, secteur = CENTRES[rid]
        n = len(g)
        for i, (_, r) in enumerate(g.iterrows()):
            ang = 2 * np.pi * i / n
            rows.append(
                {
                    "batiment_id": r.batiment_id,
                    "residence_id": rid,
                    "secteur_fictif": secteur,
                    "lat": lat0 + 0.0013 * np.sin(ang) + rng.normal(0, 0.0002),
                    "lon": lon0 + 0.0018 * np.cos(ang) + rng.normal(0, 0.0003),
                    "nb_niveaux": r.nb_niveaux,
                    "nb_logements": r.nb_logements,
                    "ascenseur": r.ascenseur,
                }
            )
    gb = pd.DataFrame(rows)
    gl = log.merge(gb[["batiment_id", "lat", "lon"]], on="batiment_id")
    gl["lat"] = gl.lat + rng.normal(0, 0.00012, len(gl)) + gl.etage * 0.00001
    gl["lon"] = gl.lon + rng.normal(0, 0.00018, len(gl))
    save_table(gb, "geo_batiments")
    save_table(gl, "geo_logements")
    print(
        "OK",
        len(gb),
        "bâtiments,",
        len(gl),
        "logements géolocalisés (positions fictives)",
    )


if __name__ == "__main__":
    main()
