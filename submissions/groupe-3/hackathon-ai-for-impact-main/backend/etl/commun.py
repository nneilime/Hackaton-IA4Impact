"""Briques communes aux deux ETL (démo et vrais fichiers SNCF)."""
from __future__ import annotations

import json
import sqlite3

from app import config
from app.db import maintenant_iso
from app.services.texte import arrondi, normaliser  # noqa: F401 (réexportés)
from . import catalogue


def minutes_groupe(minutes_individuelles: int) -> int:
    """Temps de marche d'un groupe : individuel × 1,3 + 5 min de regroupement."""
    return arrondi(minutes_individuelles * config.COEF_MARCHE_GROUPE + config.REGROUPEMENT_MIN)


def inserer_sites(conn: sqlite3.Connection, est_simule: int = 0) -> list[str]:
    """Insère le catalogue en rattachant chaque site à une gare présente en base (par le nom).

    Retourne la liste des sites ignorés faute de gare correspondante.
    """
    gares = {normaliser(r["nom"]): r["code_uic"] for r in conn.execute("SELECT code_uic, nom FROM gare")}
    ignores = []
    for s in catalogue.SITES:
        uic = next((gares[normaliser(n)] for n in s["gares"] if normaliser(n) in gares), None)
        if uic is None:
            ignores.append(s["id"])
            continue
        conn.execute(
            """INSERT INTO site_culturel (id, nom, commune, lat, lon, gare_uic, minutes_pied,
                 minutes_pied_groupe, acces_urbain, minutes_urbain, correspondances_urbain, themes,
                 niveaux, activites, interet_pedagogique, richesse, heure_ouverture,
                 heure_fermeture, duree_visite_min, horaires, capacite_accueil, source_url,
                 est_simule)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                s["id"], s["nom"], s["commune"], s["lat"], s["lon"], uic, s["minutes_pied"],
                minutes_groupe(s["minutes_pied"]), s.get("acces_urbain"), s.get("minutes_urbain"),
                s.get("correspondances_urbain"), ";".join(s["themes"]), ";".join(s["niveaux"]),
                json.dumps(s["activites"], ensure_ascii=False), s["interet_pedagogique"],
                s.get("richesse", 2), s["heure_ouverture"], s["heure_fermeture"],
                s["duree_visite_min"],
                f"{s['heure_ouverture']}-{s['heure_fermeture']} (indicatif, à vérifier)",
                s.get("capacite_accueil"), s["source_url"], est_simule,
            ),
        )
    return ignores


def inserer_retours_simules(conn: sqlite3.Connection) -> None:
    existants = {r[0] for r in conn.execute("SELECT id FROM site_culturel")}
    for r in catalogue.RETOURS_SIMULES:
        if r["site_id"] not in existants:
            continue
        conn.execute(
            """INSERT INTO retour_experience (dossier_reference, site_id, satisfaction,
                 adaptation_train, acces_gare_site, confiance, recommande, commentaire,
                 est_simule, cree_le) VALUES (NULL,?,?,?,?,?,?,?,1,?)""",
            (r["site_id"], r["satisfaction"], r["adaptation_train"], r["acces_gare_site"],
             r["confiance"], r["recommande"], r["commentaire"], maintenant_iso()),
        )


def calculer_fiabilite(conn: sqlite3.Connection) -> None:
    """Table fiabilite_train : moyennes des indicateurs mensuels (mois sans circulation exclus)."""
    conn.execute("DELETE FROM fiabilite_train")
    conn.execute(
        """INSERT INTO fiabilite_train (train_numero, taux_regularite, taux_suppression,
             taux_respect_emport, frequentation_moy, minutes_perdues_moy, nb_mois, est_simule)
           SELECT train_numero, AVG(taux_regularite), AVG(taux_suppression),
                  AVG(taux_respect_emport), AVG(frequentation), AVG(minutes_perdues), COUNT(*),
                  MAX(est_simule)
           FROM indicateur_mensuel
           WHERE COALESCE(circulations_theoriques, 1) > 0
           GROUP BY train_numero"""
    )
