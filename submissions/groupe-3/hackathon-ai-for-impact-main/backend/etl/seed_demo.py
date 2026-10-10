"""Sème le jeu de DÉMONSTRATION dans SQLite (utilisé quand les fichiers SNCF sont absents).

Usage : python -m etl.seed_demo [--reset]
Tout ce qui est simulé est marqué (est_simule = 1) et `GET /api/sante` répond donnees = "demo".
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from app import config, db
from . import commun, import_datatourisme, reseau_demo as R

# Décalages mensuels de somme nulle : la moyenne des mois reste la valeur cible.
_ONDULATION = [1.2, -0.8, 0.5, -1.0, 0.3, -0.4, 0.6, -0.2, -0.2]


def _fiabilite_cible(numero: str) -> tuple[float, float, float]:
    if numero in R.FIABILITE_FIXEE:
        return R.FIABILITE_FIXEE[numero]
    rng = random.Random(int(numero))
    return (round(rng.uniform(86.0, 97.5), 1), round(rng.uniform(0.2, 3.8), 1),
            round(rng.uniform(82.0, 99.0), 1))


def _circule(jours: str, d: date) -> bool:
    semaine = d.isoweekday() <= 5
    return jours == R.T or (jours == R.S and semaine) or (jours == R.WE and not semaine)


def semer(path: Path | None = None) -> None:
    path = path or config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with db.connexion(path) as conn:
        db.creer_schema(conn)

        for cle, (uic, nom, lat, lon, commune) in R.GARES.items():
            conn.execute(
                "INSERT INTO gare (code_uic, nom, lat, lon, commune, est_simule) VALUES (?,?,?,?,?,1)",
                (uic, nom, lat, lon, commune),
            )

        debut, fin = date.fromisoformat(R.DEBUT_GRILLE), date.fromisoformat(R.FIN_GRILLE)
        dates = [debut + timedelta(days=i) for i in range((fin - debut).days + 1)]
        lignes_desserte = []
        for numero, ligne, dep, heure, term, autorise, jours in R.TRAINS:
            axe, _ = R.LIGNES[ligne]
            arrets = R.arrets_du_train(ligne, dep, heure, term)
            conn.execute(
                """INSERT INTO train (numero, axe, origine, destination, autorise_groupe,
                     capacite_groupe, est_simule) VALUES (?,?,?,?,?,?,1)""",
                (numero, axe, R.GARES[dep][1], R.GARES[term][1], autorise, config.CAPACITE_GROUPE),
            )
            for d in dates:
                if not _circule(jours, d):
                    continue
                for ordre, (g, arr, dp) in enumerate(arrets, start=1):
                    lignes_desserte.append(
                        (numero, d.isoformat(), d.isoweekday(), ordre, R.GARES[g][0], arr, dp))
            # Indicateurs mensuels simulés
            reg, sup, emp = _fiabilite_cible(numero)
            rng = random.Random(int(numero) * 7)
            nb_jours = 21 if jours == R.S else (30 if jours == R.T else 9)
            for i, mois in enumerate(R.MOIS_INDICATEURS):
                o = _ONDULATION[i]
                r_m = max(0.0, min(100.0, reg + o * 1.5))
                s_m = max(0.0, sup + o * 0.4)
                e_m = max(0.0, min(100.0, emp + o * 1.2))
                circ = nb_jours
                supp = round(circ * s_m / 100)
                conn.execute(
                    """INSERT INTO indicateur_mensuel (train_numero, mois, circulations_theoriques,
                         circulations_realisees, frequentation, nb_retards, taux_regularite,
                         nb_suppressions, taux_suppression, taux_respect_emport, nb_incidents,
                         nb_trains_impactes, nb_ventes, minutes_perdues, est_simule)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                    (numero, mois, circ, circ - supp, round(rng.uniform(80, 900)),
                     round(circ * (100 - r_m) / 100), round(r_m, 2), supp, round(s_m, 2),
                     round(e_m, 2), rng.randint(0, 3), rng.randint(0, 4),
                     round(rng.uniform(50, 600)), round(rng.uniform(5, 120), 1)),
                )
        conn.executemany(
            """INSERT INTO desserte (train_numero, date_circulation, jour_semaine, ordre, gare_uic,
                 heure_arrivee, heure_depart, est_simule) VALUES (?,?,?,?,?,?,?,1)""",
            lignes_desserte,
        )
        commun.calculer_fiabilite(conn)

        ignores = commun.inserer_sites(conn, est_simule=0)
        if ignores:
            print("Sites sans gare dans le réseau de démo :", ignores, file=sys.stderr)
        commun.inserer_retours_simules(conn)

        for train, jour, places in R.POSITIONNEMENTS_SIMULES:
            conn.execute(
                """INSERT INTO positionnement (train_numero, date_sortie, nb_places,
                     dossier_reference, est_simule) VALUES (?,?,?,NULL,1)""",
                (train, jour, places),
            )

        # Lieux DATAtourisme en complément du catalogue fait main (si le fichier est là et que
        # LIO_DATATOURISME n'est pas à 0).
        import_datatourisme.importer_si_disponible(conn)

        db.meta_set(conn, "donnees", "demo")
        db.meta_set(conn, "construite_le", db.maintenant_iso())
        db.meta_set(conn, "sequence_dossier", "0")
        db.meta_set(conn, "source", "jeu de démonstration (etl/seed_demo.py)")
    print(f"Base de démonstration créée : {path} ({len(lignes_desserte)} arrêts, "
          f"{len(R.TRAINS)} trains, {len(R.GARES)} gares)", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="recrée la base même si elle existe")
    args = parser.parse_args()
    path = config.db_path()
    if path.exists() and not args.reset:
        print(f"{path} existe déjà : relancez avec --reset pour la recréer.", file=sys.stderr)
        return
    semer(path)


if __name__ == "__main__":
    main()
