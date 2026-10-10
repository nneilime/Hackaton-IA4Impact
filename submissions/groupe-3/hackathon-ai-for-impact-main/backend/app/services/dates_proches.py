"""Dates faisables les plus proches d'une date sans train fiable (avant ET après, ±21 jours).

Réutilise la recherche de trains et les contrôles existants (propositions.planifier) : aucune
disponibilité inventée. Jours ouvrés seulement (hors week-end), jamais dans le passé.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from fastapi import HTTPException

from .. import config, schemas
from . import comprendre, propositions, sites

FENETRE_JOURS = 21
NB_MAX = 3


FERIES_FIXES = {(1, 1), (1, 5), (8, 5), (14, 7), (15, 8), (1, 11), (11, 11), (25, 12)}


def _ouvre(jour: date) -> bool:
    """Jour de semaine hors jours fériés fixes (pas de calcul de Pâques : aucune donnée inventée)."""
    return jour.weekday() < 5 and (jour.month, jour.day) not in FERIES_FIXES


def chercher(conn: sqlite3.Connection, demande: schemas.Demande, site: sqlite3.Row,
             jour: str, aujourdhui: date | None = None, nb: int = NB_MAX) -> list[schemas.DateProche]:
    """2 à 3 propositions {date, écart, aller, retour} autour de `jour` (exclu), de la plus proche à la plus loin,
    avec au moins une avant et une après quand elles existent. Rendues triées par date."""
    aujourdhui = aujourdhui or config.aujourdhui()
    d0 = date.fromisoformat(jour)
    ctx = propositions.contexte(demande)
    avant: list[schemas.DateProche] = []
    apres: list[schemas.DateProche] = []
    for k in range(1, FENETRE_JOURS + 1):
        if len(avant) >= nb and len(apres) >= nb:
            break
        for signe, liste in ((-1, avant), (1, apres)):
            d = d0 + timedelta(days=signe * k)
            if d <= aujourdhui or not _ouvre(d) or len(liste) >= nb:
                continue
            r = propositions.planifier(conn, ctx, site, d.isoformat(), max_base=3, avec_alternatives=False)
            bons = sorted((p for p in r.propositions if p.date == d.isoformat() and p.indice.niveau != "rouge"),
                          key=lambda p: (-p.indice.score, p.aller.depart))
            if bons:
                p = bons[0]
                liste.append(schemas.DateProche(date=p.date, ecart_jours=signe * k, aller=p.aller,
                                                retour=p.retour, niveau=p.indice.niveau, score=p.indice.score))
    # le plus proche de chaque côté d'abord, puis on complète par proximité
    choisies = [x[0] for x in (avant, apres) if x]
    restes = sorted([x for x in avant + apres if x not in choisies], key=lambda x: abs(x.ecart_jours))
    choisies += restes[:max(0, nb - len(choisies))]
    return sorted(choisies, key=lambda x: x.date)


def _gare(conn: sqlite3.Connection, ref: str) -> schemas.Gare:
    row = conn.execute("SELECT * FROM gare WHERE code_uic = ?", (ref,)).fetchone() \
        or comprendre.gare_par_nom(conn, ref)
    if row is None:
        raise HTTPException(404, f"Gare inconnue : « {ref} ».")
    return schemas.Gare(code_uic=row["code_uic"], nom=row["nom"], lat=row["lat"], lon=row["lon"])


def depuis_requete(conn: sqlite3.Connection, req: schemas.DatesProchesRequete) -> schemas.DatesProchesReponse:
    try:
        date.fromisoformat(req.date)
    except ValueError:
        raise HTTPException(422, "La date doit être au format AAAA-MM-JJ.")
    site = sites.charger_site(conn, req.site_id) if req.site_id else None
    if site is None and req.gare_arrivee:
        g = _gare(conn, req.gare_arrivee)
        site = conn.execute("SELECT * FROM site_culturel WHERE gare_uic = ? ORDER BY id LIMIT 1", (g.code_uic,)).fetchone()
    if site is None:
        raise HTTPException(404, "Destination inconnue : précisez site_id ou une gare d'arrivée desservant un site.")
    demande = comprendre.completer(conn, schemas.Demande(
        date=req.date, gare_depart=_gare(conn, req.gare_depart), nb_eleves=req.effectif, nb_accompagnateurs=0,
        heure_retour_max=req.heure_retour_max, heure_depart_min=req.heure_depart_min))
    return schemas.DatesProchesReponse(date_demandee=req.date,
                                       propositions=chercher(conn, demande, site, req.date))
