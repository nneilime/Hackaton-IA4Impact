"""Dossiers : propositions mémorisées, pré-réservation, suivi et réponse simulée de la SNCF.

On ne réserve jamais : on pose une OPTION (places bloquées dans la jauge), puis on transmet la
demande (PRE_RESERVATION). Seule la réponse simulée du chargé de clientèle mène à CONFIRMATION.
"""
from __future__ import annotations

import json
import re
import sqlite3

from fastapi import HTTPException

from .. import config, db, schemas
from . import comprendre, propositions, sites
from .texte import date_fr, heure_fr


def stocker(conn: sqlite3.Connection, props: list[schemas.Proposition], site: schemas.Destination,
            demande: schemas.Demande) -> None:
    demande_json = demande.model_dump_json()
    for p in props:
        conn.execute(
            """INSERT INTO proposition (id, demande_id, site_id, date_sortie, train_aller, train_retour,
                 score, niveau, details_json, explication_ia, est_alternative, remplace,
                 proposition_json, site_json, demande_json, cree_le)
               VALUES (?,NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p.proposition_id, p.site_id, p.date, ",".join(s.train for s in p.aller.segments),
             ",".join(s.train for s in p.retour.segments), p.indice.score, p.indice.niveau,
             json.dumps([d.model_dump() for d in p.indice.details], ensure_ascii=False),
             p.explication_ia, int(p.est_alternative), p.remplace, p.model_dump_json(),
             site.model_dump_json(), demande_json, db.maintenant_iso()),
        )


def _reference(conn: sqlite3.Connection) -> str:
    seq = int(db.meta_get(conn, "sequence_dossier", "0") or 0) + 1
    db.meta_set(conn, "sequence_dossier", str(seq))
    return f"LIO-{config.aujourdhui().year}-{seq:06d}"


def _etape(conn, reference: str, statut: str, message: str) -> None:
    conn.execute("INSERT INTO dossier_historique (reference, statut, date, message) VALUES (?,?,?,?)",
                 (reference, statut, db.maintenant_iso(), message))


def _trains(p: schemas.Proposition) -> list[str]:
    return list(dict.fromkeys(s.train for s in p.aller.segments + p.retour.segments))


def lire(conn: sqlite3.Connection, reference: str) -> schemas.Dossier:
    d = conn.execute("SELECT * FROM dossier WHERE reference = ?", (reference.strip().upper(),)).fetchone()
    if d is None:
        raise HTTPException(404, f"Dossier {reference} introuvable.")
    p = conn.execute("SELECT * FROM proposition WHERE id = ?", (d["proposition_id"],)).fetchone()
    hist = conn.execute("SELECT * FROM dossier_historique WHERE reference = ? ORDER BY id",
                        (d["reference"],)).fetchall()
    return schemas.Dossier(
        reference=d["reference"], statut=d["statut"], message=d["message"], email=d["email"],
        demande=schemas.Demande.model_validate_json(d["demande_json"]),
        site=schemas.Destination.model_validate_json(p["site_json"]),
        proposition=schemas.Proposition.model_validate_json(p["proposition_json"]),
        historique=[schemas.EtapeDossier(statut=h["statut"], date=h["date"], message=h["message"])
                    for h in hist],
        cree_le=d["cree_le"],
    )


def pre_reserver(conn: sqlite3.Connection, req: schemas.RequetePreReservation) -> schemas.Dossier:
    email = (req.email or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "Adresse e-mail invalide : elle sert à suivre votre dossier.")
    row = conn.execute("SELECT * FROM proposition WHERE id = ?", (req.proposition_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Proposition introuvable : relancez la recherche de trajets.")
    existant = conn.execute("SELECT reference FROM dossier WHERE proposition_id = ?",
                            (req.proposition_id,)).fetchone()
    if existant:
        return lire(conn, existant["reference"])  # même demande envoyée deux fois : même dossier

    p = schemas.Proposition.model_validate_json(row["proposition_json"])
    if p.date < config.aujourdhui().isoformat():  # audit n°17
        raise HTTPException(409, f"La date de cette proposition ({date_fr(p.date)}) est déjà passée : "
                                 f"relancez la recherche avec une date à venir.")
    rouges = [c for c in p.controles if c.niveau == "rouge"]
    if rouges:
        raise HTTPException(409, "Cette proposition n'est pas assez fiable (" + rouges[0].message.rstrip(".")
                                 + ") : choisissez l'alternative proposée.")
    besoin = p.jauge_aller.besoin
    # Les places ont pu changer depuis la recherche : on revérifie la jauge avant de poser l'option.
    for t in _trains(p):
        sous_option = conn.execute(
            "SELECT COALESCE(SUM(nb_places), 0) FROM positionnement WHERE train_numero = ? AND date_sortie = ?",
            (t, p.date)).fetchone()[0]
        cap = conn.execute("SELECT capacite_groupe FROM train WHERE numero = ?", (t,)).fetchone()
        dispo = max(0, (cap[0] if cap else config.CAPACITE_GROUPE) - sous_option)
        if dispo < besoin:
            raise HTTPException(409, f"Les places ont changé depuis la recherche : il reste {dispo} places "
                                     f"sur le train {t} pour {besoin} voyageurs. Relancez la recherche pour "
                                     f"obtenir une alternative.")

    demande = req.demande or schemas.Demande.model_validate_json(row["demande_json"])
    demande = comprendre.completer(conn, demande)
    reference = _reference(conn)
    maintenant = db.maintenant_iso()
    conn.execute(
        """INSERT INTO demande (niveau, theme, nb_eleves, nb_accompagnateurs, date_sortie,
             heure_depart_min, heure_retour_max, lieu_depart, lieu_lat, lieu_lon, gare_depart_uic,
             email, demande_json, cree_le) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (demande.niveau, demande.theme, demande.nb_eleves, demande.nb_accompagnateurs, demande.date,
         demande.heure_depart_min, demande.heure_retour_max,
         demande.lieu_depart.libelle if demande.lieu_depart else None,
         demande.lieu_depart.lat if demande.lieu_depart else None,
         demande.lieu_depart.lon if demande.lieu_depart else None,
         demande.gare_depart.code_uic if demande.gare_depart else None, email,
         demande.model_dump_json(), maintenant))
    conn.execute(
        """INSERT INTO dossier (reference, proposition_id, statut, message, nb_voyageurs, email,
             site_id, demande_json, cree_le, maj_le) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (reference, p.proposition_id, "OPTION", "Option posée", besoin, email, p.site_id,
         demande.model_dump_json(), maintenant, maintenant))
    for t in _trains(p):
        conn.execute(
            """INSERT INTO positionnement (train_numero, date_sortie, nb_places, dossier_reference,
                 est_simule) VALUES (?,?,?,?,0)""", (t, p.date, besoin, reference))
    trains_txt = ", ".join(f"{s.train} ({heure_fr(s.depart)})" for s in p.aller.segments + p.retour.segments)
    _etape(conn, reference, "OPTION",
           f"Option posée : {besoin} places bloquées provisoirement le {date_fr(p.date)} sur les trains "
           f"{trains_txt}.")
    _etape(conn, reference, "PRE_RESERVATION", config.MESSAGE_PRE_RESERVATION)
    conn.execute("UPDATE dossier SET statut = 'PRE_RESERVATION', message = ?, maj_le = ? WHERE reference = ?",
                 (config.MESSAGE_PRE_RESERVATION, db.maintenant_iso(), reference))
    return lire(conn, reference)


def simuler_reponse(conn: sqlite3.Connection, reference: str, decision: str) -> schemas.Dossier:
    dossier = lire(conn, reference)
    if dossier.statut != "PRE_RESERVATION":
        raise HTTPException(409, f"Ce dossier a déjà reçu une réponse (statut {dossier.statut}).")
    if decision == "confirmer":
        statut = "CONFIRMATION"
        message = ("Pré-réservation confirmée par le chargé de clientèle SNCF (réponse simulée pour la "
                   "démonstration). Bon voyage avec liO !")
    else:
        statut = "CONTRE_PROPOSITION"
        message = ("Le chargé de clientèle SNCF propose un autre horaire (réponse simulée pour la "
                   "démonstration) : " + _contre_proposition(conn, dossier) +
                   " Relancez une recherche pour comparer, votre option reste posée en attendant.")
    _etape(conn, dossier.reference, statut, message)
    conn.execute("UPDATE dossier SET statut = ?, message = ?, maj_le = ? WHERE reference = ?",
                 (statut, message, db.maintenant_iso(), dossier.reference))
    return lire(conn, dossier.reference)


def _contre_proposition(conn: sqlite3.Connection, dossier: schemas.Dossier) -> str:
    """Autre aller-retour non rouge pour le même site (calculé par le code, pas inventé)."""
    site = sites.charger_site(conn, dossier.site.site_id)
    actuel = tuple(s.train for s in dossier.proposition.aller.segments)
    if site is not None and dossier.demande.gare_depart is not None:
        demande = dossier.demande.model_copy(update={"date": dossier.proposition.date})
        ctx = propositions.contexte(demande)
        acces = sites.acces(site)
        cands, _, _ = propositions.candidats_du_jour(conn, ctx, site, acces, dossier.proposition.date)
        for c in cands:
            if c.aller.trains == actuel:
                continue
            propositions.evaluer(conn, ctx, site, acces, c)
            if c.niveau != "rouge":
                return (f"le train {c.aller.segments[0].train} de {heure_fr(c.aller.dep)} à l'aller et le "
                        f"train {c.retour.segments[0].train} de {heure_fr(c.retour.dep)} au retour, le "
                        f"{date_fr(c.jour)}.")
    return "une autre date, à convenir avec vous par e-mail."
