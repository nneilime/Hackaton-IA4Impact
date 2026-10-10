"""Retour d'expérience : 5 critères enregistrés, le critère « satisfaction » du site évolue."""
from __future__ import annotations

import sqlite3

from fastapi import HTTPException

from .. import db, schemas
from . import confiance, sites


def enregistrer(conn: sqlite3.Connection, req: schemas.RequeteRetour) -> schemas.ReponseRetour:
    ref = req.reference.strip().upper()
    d = conn.execute("SELECT * FROM dossier WHERE reference = ?", (ref,)).fetchone()
    if d is None:
        raise HTTPException(404, f"Dossier {req.reference} introuvable.")
    if d["statut"] == "ANNULE":
        raise HTTPException(409, "Ce dossier est annulé : impossible d'enregistrer un retour.")
    p = conn.execute("SELECT * FROM proposition WHERE id = ?", (d["proposition_id"],)).fetchone()
    prop = schemas.Proposition.model_validate_json(p["proposition_json"])
    site = sites.charger_site(conn, d["site_id"])
    bloquant = any(c.niveau == "rouge" for c in prop.controles)

    sat_avant = sites.satisfaction(conn, d["site_id"])
    avant = confiance.remplacer_satisfaction(prop.indice, bloquant, sat_avant)
    conn.execute(
        """INSERT INTO retour_experience (dossier_reference, site_id, satisfaction, adaptation_train,
             acces_gare_site, confiance, recommande, commentaire, est_simule, cree_le)
           VALUES (?,?,?,?,?,?,?,?,0,?)
           ON CONFLICT(dossier_reference) DO UPDATE SET satisfaction = excluded.satisfaction,
             adaptation_train = excluded.adaptation_train, acces_gare_site = excluded.acces_gare_site,
             confiance = excluded.confiance, recommande = excluded.recommande,
             commentaire = excluded.commentaire, cree_le = excluded.cree_le""",
        (ref, d["site_id"], req.satisfaction, req.adaptation_train, req.acces_gare_site,
         req.confiance, int(req.recommande), (req.commentaire or "").strip(), db.maintenant_iso()),
    )
    sat_apres = sites.satisfaction(conn, d["site_id"])
    apres = confiance.remplacer_satisfaction(prop.indice, bloquant, sat_apres)

    pts = lambda i: next(c.points for c in i.details if c.critere == confiance.SATISFACTION)  # noqa: E731
    nom = site["nom"] if site else d["site_id"]
    message = (f"Merci pour votre retour ! Le critère « satisfaction » de {nom} passe de {pts(avant)}/10 à "
               f"{pts(apres)}/10, et l'indice de confiance de votre trajet de {avant.score} à "
               f"{apres.score}/100. Les prochains enseignants en profiteront.")
    return schemas.ReponseRetour(ok=True, indice_avant=avant.score, indice_apres=apres.score, message=message)
