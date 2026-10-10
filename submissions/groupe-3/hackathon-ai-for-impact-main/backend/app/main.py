"""API FastAPI du copilote des sorties scolaires liO. Contrat : API_CONTRACT.md (racine du repo).

Lancement (depuis backend/) : uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config, db, llm, schemas
from .services import (chat, comprendre, dossiers, expliquer, propositions, recommander, retours,
                       sites, trains)
from .services.texte import date_fr, heure_fr
from .services import dates_proches, scene, sondages

log = logging.getLogger("lio")


@asynccontextmanager
async def lifespan(_: FastAPI):
    donnees = db.initialiser()
    trains.vider_caches()
    log.info("Base prête (données : %s, mode : %s)", donnees, llm.mode())
    yield


app = FastAPI(title="Copilote des sorties scolaires liO", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Erreurs : toujours { "detail": "message lisible en français" } ---------------------------

def _message_validation(erreurs: list[dict]) -> str:
    if not erreurs:
        return "Requête invalide."
    e = erreurs[0]
    champ = ".".join(str(x) for x in e.get("loc", ()) if x not in ("body", "query", "path"))
    t = e.get("type", "")
    ctx = e.get("ctx") or {}
    if t == "missing":
        return f"Champ obligatoire manquant : « {champ} »."
    if t == "json_invalid":
        return "Le corps de la requête n'est pas un JSON valide."
    if t in ("greater_than_equal", "less_than_equal", "greater_than", "less_than"):
        return f"Le champ « {champ} » doit être une note de 1 à 5."
    if t == "extra_forbidden":
        return f"Champ inconnu : « {champ} »."
    if t == "union_tag_invalid" or t == "union_tag_not_found":
        return f"Type d'événement inconnu ou manquant pour « {champ} »."
    if t == "literal_error":
        return f"Valeur non autorisée pour « {champ} » (valeurs possibles : {ctx.get('expected', '?')})."
    if t.startswith("int"):
        return f"Le champ « {champ} » doit être un nombre entier."
    if t.startswith("bool"):
        return f"Le champ « {champ} » doit valoir vrai ou faux."
    return f"Valeur invalide pour le champ « {champ} »."


@app.exception_handler(RequestValidationError)
async def _validation(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": _message_validation(exc.errors())})


@app.exception_handler(Exception)
async def _erreur(_: Request, exc: Exception):
    log.exception("Erreur interne")
    return JSONResponse(status_code=500, content={
        "detail": "Le copilote a rencontré une erreur inattendue. Réessayez dans un instant."})


def connexion() -> Iterator[sqlite3.Connection]:
    with db.connexion() as conn:
        yield conn


LIBELLES_CHAMPS = {
    "niveau": "niveau de la classe", "theme": "thème", "nb_eleves": "nombre d'élèves",
    "nb_accompagnateurs": "nombre d'accompagnateurs", "date": "date de la sortie",
    "lieu_depart": "lieu de départ", "gare_depart": "gare de départ",
}


def _demande_exploitable(conn: sqlite3.Connection, d: schemas.Demande) -> schemas.Demande:
    d = comprendre.completer(conn, d)
    requis = [c for c in ("nb_eleves", "nb_accompagnateurs", "date", "gare_depart")
              if getattr(d, c) is None]
    if d.gare_depart is None and "gare_depart" in requis and d.lieu_depart is None:
        requis[requis.index("gare_depart")] = "lieu_depart"
    if requis:
        raise HTTPException(422, "Il manque des informations pour chercher des trains : "
                                 + ", ".join(LIBELLES_CHAMPS[c] for c in requis) + ".")
    try:
        sortie = date.fromisoformat(d.date)
    except ValueError:
        raise HTTPException(422, "La date de la sortie est illisible : indiquez-la sous la forme AAAA-MM-JJ.")
    if sortie < config.aujourdhui():  # audit n°17 : une date passée n'est jamais acceptée
        raise HTTPException(422, f"Le {date_fr(sortie)} est déjà passé : choisissez une date à venir.")
    return d


# --- Routes -----------------------------------------------------------------------------------

class SanteDetaillee(schemas.Sante):
    """Sante + provenance des données (champs additifs, ignorés par les clients existants)."""
    source: str = ""            # libellé d'affichage : "SNCF 2026" ou "Démonstration"
    hypotheses: list[str] = []  # hypothèses actives (ex. semaine type pour novembre 2026)


@app.get("/api/sante", response_model=SanteDetaillee)
def sante() -> SanteDetaillee:
    donnees, source, hyp = db.nature_donnees(), "Démonstration", []
    try:
        with db.connexion() as conn:
            source = db.meta_get(conn, "source_libelle") or source
            if donnees == "sncf":
                from etl import import_sncf
                hyp = import_sncf.hypotheses(conn)
    except Exception:  # base absente ou ancienne : /api/sante ne doit jamais échouer
        pass
    return SanteDetaillee(ok=True, mode=llm.mode(), donnees=donnees, source=source, hypotheses=hyp)


@app.post("/api/chat", response_model=schemas.ReponseChat)
def route_chat(req: schemas.RequeteChat, conn: sqlite3.Connection = Depends(connexion)):
    return chat.repondre(conn, req)


@app.post("/api/demande/valider", response_model=schemas.Demande)
def valider(req: schemas.RequeteDemande, conn: sqlite3.Connection = Depends(connexion)):
    return comprendre.completer(conn, req.demande)


@app.post("/api/destinations", response_model=schemas.ReponseDestinations)
def route_destinations(req: schemas.RequeteDemande, conn: sqlite3.Connection = Depends(connexion)):
    d = _demande_exploitable(conn, req.demande)
    return recommander.recommander(conn, d)


@app.post("/api/trajets", response_model=schemas.ReponseTrajets)
def route_trajets(req: schemas.RequeteTrajets, conn: sqlite3.Connection = Depends(connexion)):
    d = _demande_exploitable(conn, req.demande)
    site = sites.charger_site(conn, req.site_id)
    if site is None:
        raise HTTPException(404, f"Site « {req.site_id} » introuvable dans le catalogue.")
    ctx = propositions.contexte(d)
    if site["gare_uic"] == ctx.gare_uic:
        r = propositions.Resultat(site, sites.acces(site), trains.resoudre_date(conn, d.date), [], {},
                                  0, 0, 0, "vert")
        return schemas.ReponseTrajets(
            site=propositions.destination(conn, r), propositions=[],
            message=f"{site['nom']} est desservi par votre gare de départ : pas besoin de train !")
    r = propositions.planifier(conn, ctx, site)
    expliquer.expliquer(r.propositions, d)
    note = sites.note_llm(site["id"], d.theme, d.niveau)
    destination = propositions.destination(conn, r, note[1] if note else None)
    dossiers.stocker(conn, r.propositions, destination, d)
    return schemas.ReponseTrajets(site=destination, propositions=r.propositions,
                                  message=_message_trajets(r, d))


def _message_trajets(r: propositions.Resultat, d: schemas.Demande) -> str:
    parts = []
    props = r.propositions
    if not props:
        parts.append(f"Aucun train liO autorisé aux groupes ne permet cet aller-retour vers {r.site['nom']} "
                     f"le {date_fr(d.date)} (départ à partir de {heure_fr(d.heure_depart_min)}, retour "
                     f"avant {heure_fr(d.heure_retour_max)}). Essayez une autre date ou une autre destination.")
    else:
        n, n_alt = len(props), len([p for p in props if p.est_alternative])
        dont = f" (dont {n_alt} alternative{'s' if n_alt > 1 else ''})" if n_alt else ""
        parts.append(f"{n} proposition{'s' if n > 1 else ''}{dont} pour {r.site['nom']} le {date_fr(d.date)}, "
                     f"triée{'s' if n > 1 else ''} par indice de confiance.")
        if any(p.indice.niveau == "rouge" for p in props):
            if any(p.est_alternative for p in props):
                parts.append("Une proposition n'est pas assez fiable : je vous montre son alternative juste après.")
            else:
                parts.append("Une proposition n'est pas assez fiable et je n'ai pas trouvé d'alternative sûre.")
    if r.date_info.jour_type:
        parts.append(r.date_info.message)
    if db.nature_donnees() == "demo":
        parts.append("Données de démonstration : trains, horaires et places sont simulés.")
    return " ".join(parts)


@app.post("/api/pre-reservations", response_model=schemas.Dossier)
def pre_reserver(req: schemas.RequetePreReservation, conn: sqlite3.Connection = Depends(connexion)):
    return dossiers.pre_reserver(conn, req)


@app.get("/api/pre-reservations/{reference}", response_model=schemas.Dossier)
def lire_dossier(reference: str, conn: sqlite3.Connection = Depends(connexion)):
    return dossiers.lire(conn, reference)


@app.post("/api/pre-reservations/{reference}/simuler-reponse", response_model=schemas.Dossier)
def simuler(reference: str, req: schemas.RequeteSimulation, conn: sqlite3.Connection = Depends(connexion)):
    return dossiers.simuler_reponse(conn, reference, req.decision)


@app.post("/api/retours", response_model=schemas.ReponseRetour)
def route_retours(req: schemas.RequeteRetour, conn: sqlite3.Connection = Depends(connexion)):
    return retours.enregistrer(conn, req)


# --- Vote en classe (v2) ----------------------------------------------------------------------

@app.post("/api/sondages", response_model=schemas.Sondage)
def creer_sondage(req: schemas.RequeteSondage, conn: sqlite3.Connection = Depends(connexion)):
    return sondages.creer(conn, req)


@app.get("/api/sondages/{code}", response_model=schemas.Sondage)
def lire_sondage(code: str, conn: sqlite3.Connection = Depends(connexion)):
    return sondages.lire(conn, code)


@app.post("/api/sondages/{code}/votes", response_model=schemas.Sondage)
def voter_sondage(code: str, req: schemas.RequeteVote, conn: sqlite3.Connection = Depends(connexion)):
    return sondages.voter(conn, code, req)


@app.post("/api/sondages/{code}/votes-manuels", response_model=schemas.Sondage)
def votes_manuels_sondage(code: str, req: schemas.RequeteVotesManuels,
                          conn: sqlite3.Connection = Depends(connexion)):
    return sondages.votes_manuels(conn, code, req)


@app.post("/api/sondages/{code}/fermer", response_model=schemas.Sondage)
def fermer_sondage(code: str, conn: sqlite3.Connection = Depends(connexion)):
    return sondages.fermer(conn, code)


@app.get("/api/reseau", response_model=schemas.Reseau)
def reseau() -> schemas.Reseau:
    return schemas.Reseau(ip_locale=sondages.ip_locale())


# --- Scène « Tchouette est l'interface » (v3) -------------------------------------------------

@app.post("/api/dates-proches", response_model=schemas.DatesProchesReponse)
def route_dates_proches(req: schemas.DatesProchesRequete, conn: sqlite3.Connection = Depends(connexion)):
    return dates_proches.depuis_requete(conn, req)


@app.post("/api/scene", response_model=schemas.ReponseScene)
def route_scene(req: schemas.RequeteScene, conn: sqlite3.Connection = Depends(connexion)):
    return scene.jouer(conn, req)
