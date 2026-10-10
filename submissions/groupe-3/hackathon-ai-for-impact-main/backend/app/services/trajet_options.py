"""Trajet modifiable : horaires alternatifs (aller / retour) calculés par le serveur.

Chaque option est une vraie circulation de la grille, évaluée par les mêmes contrôles (R1-R10) et le même
indice de confiance que la proposition de départ. Le client n'envoie qu'un identifiant de circulation,
qui doit appartenir à cette liste : rien n'est inventé ni accepté tel quel.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .. import schemas
from . import propositions, sites, trains
from .propositions import Candidat
from .texte import fmt_hm

NB_OPTIONS_MAX = 5
NB_EVALUEES_MAX = 8


@dataclass
class _Option:
    id: str
    sens: str
    candidat: Candidat
    actuel: bool


def identifiant(it: trains.Itineraire) -> str:
    return "+".join(it.trains)


def _evaluer(conn, ctx, site, acces, base: Candidat, aller, retour) -> Candidat | None:
    c = Candidat(base.jour, base.grille, aller, retour, base.retours,
                 aller.arr + acces.minutes, base.debut_visite, base.marge)
    if aller is not base.aller:
        cr = propositions.creneau_visite(site, c.arrivee_site)
        if cr is None:
            return None
        c.debut_visite, c.marge = cr
    propositions.evaluer(conn, ctx, site, acces, c)
    return c


def _retenir(options: list[_Option], actuel_dep: int, sens: str) -> list[_Option]:
    """Au plus 5 options non bloquantes, les plus proches de l'horaire actuel, triées par heure."""
    ok = [o for o in options if o.candidat.niveau != "rouge" or o.actuel]
    cle = (lambda o: o.candidat.aller.dep) if sens == "aller" else (lambda o: o.candidat.retour.dep)
    ok.sort(key=lambda o: (not o.actuel, abs(cle(o) - actuel_dep)))
    return sorted(ok[:NB_OPTIONS_MAX], key=cle)


def calculer(conn: sqlite3.Connection, demande: schemas.Demande, site: sqlite3.Row,
             p: schemas.Proposition) -> dict[str, list[_Option]]:
    ctx = propositions.contexte(demande)
    acces = sites.acces(site)
    tous, _, _ = propositions.candidats_du_jour(conn, ctx, site, acces, p.date)
    ta = tuple(s.train for s in p.aller.segments)
    tr = tuple(s.train for s in p.retour.segments)
    cur = next((c for c in tous if c.aller.trains == ta), None)
    if cur is None:
        return {"aller": [], "retour": []}
    ret_cur = next((r for r in cur.retours if r.trains == tr), cur.retour)
    base = _evaluer(conn, ctx, site, acces, cur, cur.aller, ret_cur)

    allers: list[_Option] = []
    proches = sorted(tous, key=lambda c: abs(c.aller.dep - cur.aller.dep))[:NB_EVALUEES_MAX]
    for c in proches:
        retour = next((r for r in c.retours if r.trains == ret_cur.trains), c.retour)
        cand = base if c.aller.trains == ta else _evaluer(conn, ctx, site, acces, c, c.aller, retour)
        if cand is not None:
            allers.append(_Option(identifiant(c.aller), "aller", cand, c.aller.trains == ta))
    retours: list[_Option] = []
    for r in sorted(cur.retours, key=lambda r: abs(r.dep - ret_cur.dep))[:NB_EVALUEES_MAX]:
        cand = base if r.trains == ret_cur.trains else _evaluer(conn, ctx, site, acces, cur, cur.aller, r)
        if cand is not None:
            retours.append(_Option(identifiant(r), "retour", cand, r.trains == ret_cur.trains))
    return {"aller": _retenir(allers, cur.aller.dep, "aller"),
            "retour": _retenir(retours, ret_cur.dep, "retour")}


def vers_schema(opts: dict[str, list[_Option]]) -> schemas.AlternativesTrajet:
    def conv(o: _Option) -> schemas.OptionHoraire:
        c, f = o.candidat, o.candidat.faits
        it = c.aller if o.sens == "aller" else c.retour
        jauge = f.jauge_aller if o.sens == "aller" else f.jauge_retour
        return schemas.OptionHoraire(
            id=o.id, depart=fmt_hm(it.dep), arrivee=fmt_hm(it.arr), duree_min=it.duree,
            correspondances=it.correspondances, places_disponibles=jauge.disponibles, besoin=jauge.besoin,
            niveau=c.niveau, score=c.score, actuel=o.actuel)
    return schemas.AlternativesTrajet(aller=[conv(o) for o in opts["aller"]],
                                      retour=[conv(o) for o in opts["retour"]])


def appliquer(conn: sqlite3.Connection, demande: schemas.Demande, site: sqlite3.Row,
              p: schemas.Proposition, sens: str, ident: str) -> schemas.Proposition | None:
    """Nouvelle proposition si `ident` est une circulation faisable du `sens` demandé, sinon None."""
    opts = calculer(conn, demande, site, p)
    o = next((x for x in opts[sens] if x.id == ident), None)
    if o is None or o.candidat.niveau == "rouge":
        return None
    return propositions.vers_proposition(o.candidat, site["id"])
