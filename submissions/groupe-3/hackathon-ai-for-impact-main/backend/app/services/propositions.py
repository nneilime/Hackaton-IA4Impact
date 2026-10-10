"""Construction des propositions aller-retour pour un site : trains -> contrôles -> indice.

Une proposition rouge est suivie d'une alternative qui repasse par les mêmes contrôles :
train suivant (ou autre retour), sinon autre date dans les 7 jours.
"""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from .. import config, schemas
from . import confiance, controles, sites, trains
from .sites import Acces
from .texte import hm
from .trains import DateResolue, Grille, Itineraire

RANG = {"vert": 0, "orange": 1, "rouge": 2}


@dataclass
class Contexte:
    demande: schemas.Demande
    gare_uic: str
    gare_nom: str
    besoin: int
    heure_depart_min: int
    heure_retour_max: int
    duree: str
    marche_etab: int
    lieu_lat: float | None
    lieu_lon: float | None
    cache: dict = field(default_factory=dict)


def contexte(demande: schemas.Demande) -> Contexte:
    g = demande.gare_depart
    lieu = demande.lieu_depart
    return Contexte(
        demande=demande,
        gare_uic=g.code_uic,
        gare_nom=g.nom,
        besoin=(demande.nb_eleves or 0) + (demande.nb_accompagnateurs or 0),
        heure_depart_min=hm(demande.heure_depart_min or config.HEURE_DEPART_DEFAUT),
        heure_retour_max=hm(demande.heure_retour_max or config.HEURE_RETOUR_DEFAUT),
        duree=demande.duree or config.DUREE_DEFAUT,
        marche_etab=controles.marche_etablissement(g.distance_m),
        lieu_lat=lieu.lat if lieu else None,
        lieu_lon=lieu.lon if lieu else None,
    )


@dataclass
class Candidat:
    jour: str
    grille: Grille
    aller: Itineraire
    retour: Itineraire
    retours: list[Itineraire]
    arrivee_site: int
    debut_visite: int
    marge: int
    faits: controles.Faits | None = None
    controles: list[schemas.Controle] = field(default_factory=list)
    echecs: set[str] = field(default_factory=set)
    indice: schemas.Indice | None = None

    @property
    def cle(self) -> tuple:
        return (self.jour, self.aller.trains, self.retour.trains)

    @property
    def niveau(self) -> str:
        return self.indice.niveau if self.indice else "rouge"

    @property
    def score(self) -> int:
        return self.indice.score if self.indice else 0

    @property
    def cause(self) -> str:
        """Où chercher une alternative : sur l'aller, sur le retour, ou ailleurs."""
        if self.faits and "R2" in self.echecs:
            if self.faits.etat_aller.disponibles < self.faits.besoin:
                return "aller"
            if self.faits.etat_retour.disponibles < self.faits.besoin:
                return "retour"
        return "autre"

    @property
    def recuperable(self) -> bool:
        if "R8" in self.echecs:
            return False
        if self.faits and not (config.MIN_VOYAGEURS <= self.faits.besoin <= config.MAX_VOYAGEURS):
            return False
        return True


def creneau_visite(site: sqlite3.Row, arrivee_site: int) -> tuple[int, int] | None:
    """Premier créneau indicatif (tous les 1/4 h) laissant 30 min de marge, sinon le premier
    créneau atteignable (marge < 30 min, vigilance R4). None si on arrive trop tard."""
    ouv = hm(site["heure_ouverture"]) or 9 * 60
    ferm = hm(site["heure_fermeture"]) or 18 * 60
    dernier = ferm - (site["duree_visite_min"] or 90)
    creneaux = range(ouv, dernier + 1, config.PAS_CRENEAU_MIN)
    for s in creneaux:
        if s >= arrivee_site + config.MARGE_VISITE_MIN:
            return s, s - arrivee_site
    for s in creneaux:
        if s >= arrivee_site:
            return s, s - arrivee_site
    return None


def duree_sur_place(site: sqlite3.Row, duree: str) -> int:
    visite = site["duree_visite_min"] or 90
    return visite + (config.PAUSE_DEJEUNER_MIN if duree == "journee" else 0)


def candidats_du_jour(conn: sqlite3.Connection, ctx: Contexte, site: sqlite3.Row, acces: Acces,
                      jour: str) -> tuple[list[Candidat], DateResolue, Grille]:
    res = trains.resoudre_date(conn, jour)
    grille = trains.charger_grille(conn, res.ref_date)
    out = []
    for aller in trains.itineraires(grille, ctx.gare_uic, site["gare_uic"], ctx.heure_depart_min):
        arrivee_site = aller.arr + acces.minutes
        c = creneau_visite(site, arrivee_site)
        if c is None:
            continue
        debut, marge = c
        pret = debut + duree_sur_place(site, ctx.duree) + acces.minutes
        retours = [r for r in trains.itineraires(grille, site["gare_uic"], ctx.gare_uic, pret)
                   if r.arr + ctx.marche_etab <= ctx.heure_retour_max]
        if not retours:
            continue
        out.append(Candidat(jour, grille, aller, retours[0], retours, arrivee_site, debut, marge))
    return out, res, grille


def evaluer(conn: sqlite3.Connection, ctx: Contexte, site: sqlite3.Row, acces: Acces,
            c: Candidat) -> Candidat:
    ja, ea = controles.jauge_trajet(conn, c.aller, c.jour, ctx.besoin, ctx.cache)
    jr, er = controles.jauge_trajet(conn, c.retour, c.jour, ctx.besoin, ctx.cache)
    f = controles.Faits(
        jour=c.jour, aller=c.aller, retour=c.retour, noms=c.grille.noms, besoin=ctx.besoin,
        jauge_aller=ja, jauge_retour=jr, etat_aller=ea, etat_retour=er, acces=acces,
        arrivee_site=c.arrivee_site, debut_visite=c.debut_visite, marge=c.marge,
        marche_etablissement=ctx.marche_etab, heure_retour_max=ctx.heure_retour_max,
        lieu_lat=ctx.lieu_lat, lieu_lon=ctx.lieu_lon, capacite_site=site["capacite_accueil"],
        gare_depart_nom=ctx.gare_nom,
    )
    c.faits = f
    c.controles, c.echecs = controles.evaluer(f)
    k_ad = ("adequation", site["id"])
    if k_ad not in ctx.cache:
        ctx.cache[k_ad] = sites.adequation(site, ctx.demande)
    k_sat = ("satisfaction", site["id"])
    if k_sat not in ctx.cache:
        ctx.cache[k_sat] = sites.satisfaction(conn, site["id"])
    c.indice = confiance.calculer(conn, f, c.echecs, ctx.cache[k_ad], ctx.cache[k_sat], ctx.cache)
    return c


def vers_proposition(c: Candidat, site_id: str, est_alternative: bool = False,
                     remplace: str | None = None) -> schemas.Proposition:
    f = c.faits
    return schemas.Proposition(
        proposition_id="P-" + uuid.uuid4().hex[:10].upper(),
        site_id=site_id,
        date=c.jour,
        aller=trains.vers_trajet(c.aller, c.grille),
        retour=trains.vers_trajet(c.retour, c.grille),
        jauge_aller=f.jauge_aller,
        jauge_retour=f.jauge_retour,
        marge_avant_visite_min=c.marge,
        controles=c.controles,
        indice=c.indice,
        explication_ia="",
        est_alternative=est_alternative,
        remplace=remplace,
    )


@dataclass
class Resultat:
    site: sqlite3.Row
    acces: Acces
    date_info: DateResolue
    propositions: list[schemas.Proposition]
    candidats: dict[str, Candidat]
    temps_trajet_min: int | None
    correspondances: int
    indice: int
    niveau: str
    alternative_autre_date: dict[str, str] = field(default_factory=dict)


def _chercher_alternative(conn, ctx, site, acces, rouge: Candidat, tous: list[Candidat],
                          deja: set[tuple]) -> Candidat | None:
    def ok(c: Candidat) -> bool:
        if c.cle in deja:
            return False
        evaluer(conn, ctx, site, acces, c)
        return c.niveau != "rouge"

    def trains_suivants():
        for c in tous:
            if c.aller.dep > rouge.aller.dep and ok(c):
                return c
        return None

    def autres_retours():
        for r in rouge.retours:
            if r.trains == rouge.retour.trains:
                continue
            c = Candidat(rouge.jour, rouge.grille, rouge.aller, r, rouge.retours, rouge.arrivee_site,
                         rouge.debut_visite, rouge.marge)
            if ok(c):
                return c
        return None

    strategies = [autres_retours, trains_suivants] if rouge.cause == "retour" else [trains_suivants, autres_retours]
    for s in strategies:
        alt = s()
        if alt:
            return alt
    # Autre date, dans les 7 jours qui suivent
    d0 = date.fromisoformat(rouge.jour)
    for k in range(1, config.JOURS_ALTERNATIVE + 1):
        jour = (d0 + timedelta(days=k)).isoformat()
        cands, _, _ = candidats_du_jour(conn, ctx, site, acces, jour)
        # on privilégie les mêmes horaires que la proposition rouge
        cands.sort(key=lambda c: (c.aller.trains != rouge.aller.trains, c.aller.dep))
        for c in cands:
            if ok(c):
                return c
    return None


def planifier(conn: sqlite3.Connection, ctx: Contexte, site: sqlite3.Row, jour: str | None = None,
              max_base: int = config.MAX_PROPOSITIONS, avec_alternatives: bool = True) -> Resultat:
    jour = jour or ctx.demande.date
    acces = sites.acces(site)
    tous, date_info, grille = candidats_du_jour(conn, ctx, site, acces, jour)

    # Meilleur temps de trajet (indépendant des horaires de visite)
    allers = trains.itineraires(grille, ctx.gare_uic, site["gare_uic"], ctx.heure_depart_min) \
        or trains.itineraires(grille, ctx.gare_uic, site["gare_uic"], 0)
    meilleur = min(allers, key=lambda it: (it.duree, it.correspondances), default=None)

    base = tous[:max_base]
    for c in base:
        evaluer(conn, ctx, site, acces, c)

    groupes: list[list[tuple[Candidat, bool]]] = []
    deja = {c.cle for c in base if c.niveau == "rouge"}
    alternatives: dict[int, Candidat] = {}
    if avec_alternatives:
        for i, c in enumerate(base):
            if c.niveau == "rouge" and c.recuperable:
                alt = _chercher_alternative(conn, ctx, site, acces, c, tous, deja)
                if alt:
                    alternatives[i] = alt
                    deja.add(alt.cle)
    cles_alt = {a.cle for a in alternatives.values()}
    for i, c in enumerate(base):
        if c.niveau != "rouge" and c.cle in cles_alt:
            continue  # déjà montrée comme alternative d'une proposition rouge
        g = [(c, False)]
        if i in alternatives:
            g.append((alternatives[i], True))
        groupes.append(g)

    def cle_groupe(g):
        non_rouges = [c.score for c, _ in g if c.niveau != "rouge"]
        return (1, max(non_rouges)) if non_rouges else (0, max(c.score for c, _ in g))

    groupes.sort(key=cle_groupe, reverse=True)

    props: list[schemas.Proposition] = []
    cands: dict[str, Candidat] = {}
    autre_date: dict[str, str] = {}
    for g in groupes:
        rouge_id = None
        for c, est_alt in g:
            p = vers_proposition(c, site["id"], est_alt, rouge_id if est_alt else None)
            if not est_alt:
                rouge_id = p.proposition_id
            elif c.jour != jour:
                autre_date[p.proposition_id] = c.jour
            props.append(p)
            cands[p.proposition_id] = c

    if props:
        # L'indice d'une destination est celui du meilleur trajet de la DATE DEMANDÉE : l'alternative
        # d'un autre jour ne le relève jamais (audit n°2). Si tous les trajets du jour sont bloqués,
        # la destination est rouge ce jour-là, même si un autre jour fonctionne.
        sur_jour = [p for p in props if p.date == jour] or props
        non_rouges = [p for p in sur_jour if p.indice.niveau != "rouge"]
        best = max(non_rouges or sur_jour, key=lambda p: p.indice.score)
        indice, niveau = best.indice.score, best.indice.niveau
    else:
        indice, niveau = 0, "rouge"
    return Resultat(site, acces, date_info, props, cands,
                    meilleur.duree if meilleur else None,
                    meilleur.correspondances if meilleur else 0, indice, niveau, autre_date)


def destination(conn: sqlite3.Connection, r: Resultat, interet: str | None = None) -> schemas.Destination:
    s = r.site
    return schemas.Destination(
        site_id=s["id"], nom=s["nom"], commune=s["commune"] or "",
        gare=sites.gare_du_site(conn, s),
        interet_pedagogique=interet or s["interet_pedagogique"] or "",
        activites=sites.liste(s["activites"]), themes=sites.liste(s["themes"]),
        niveaux=sites.liste(s["niveaux"]),
        temps_trajet_min=r.temps_trajet_min, correspondances=r.correspondances,
        acces_gare_site=r.acces.schema(), indice_confiance=r.indice, niveau=r.niveau,
    )
