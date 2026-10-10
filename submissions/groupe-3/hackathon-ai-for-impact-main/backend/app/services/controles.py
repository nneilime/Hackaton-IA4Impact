"""Contrôles R1 à R10 et jauge de pré-réservation (code déterministe, sans LLM).

La jauge n'est pas stockée : places disponibles = capacité − somme des places sous option
(table positionnement) pour ce train et cette date. L'identité des autres groupes n'est jamais lue.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from .. import config, schemas
from .sites import Acces
from .texte import arrondi, capitaliser, heure_fr
from .trains import Itineraire

LIBELLES = {
    "R1": "Train liO autorisé aux groupes",
    "R2": "Taille du groupe et places disponibles",
    "R3": "Accès gare → site",
    "R4": "Marge avant la visite",
    "R5": "Retour avant l'heure prévue",
    "R6": "Plage horaire de l'offre groupe (9h-16h)",
    "R7": "Demande au moins 21 jours avant",
    "R8": "Établissement en Occitanie",
    "R9": "Autre groupe déjà positionné",
    "R10": "Capacité d'accueil du site",
}
BLOQUANTES = {"R1", "R2", "R5", "R8"}


@dataclass
class EtatTrain:
    numero: str
    capacite: int
    sous_option: int
    groupes: int

    @property
    def disponibles(self) -> int:
        return max(0, self.capacite - self.sous_option)


def etat_train(conn: sqlite3.Connection, numero: str, jour: str, cache: dict) -> EtatTrain:
    k = (numero, jour)
    if k not in cache:
        cap = conn.execute("SELECT capacite_groupe FROM train WHERE numero = ?", (numero,)).fetchone()
        r = conn.execute(
            """SELECT COALESCE(SUM(nb_places), 0), COUNT(*) FROM positionnement
               WHERE train_numero = ? AND date_sortie = ?""",
            (numero, jour),
        ).fetchone()
        cache[k] = EtatTrain(numero, cap[0] if cap else config.CAPACITE_GROUPE, r[0], r[1])
    return cache[k]


def niveau_jauge(disponibles: int, besoin: int, groupes: int) -> str:
    if disponibles < besoin:
        return "rouge"
    if disponibles < besoin * 1.1 or groupes > 0:
        return "orange"
    return "vert"


def jauge_trajet(conn: sqlite3.Connection, it: Itineraire, jour: str, besoin: int,
                 cache: dict) -> tuple[schemas.Jauge, EtatTrain]:
    """Jauge du trajet = celle du train le plus contraint (le moins de places disponibles)."""
    etats = [etat_train(conn, s.train, jour, cache) for s in it.segments]
    pire = min(etats, key=lambda e: (e.disponibles, -e.groupes))
    groupes = max(e.groupes for e in etats)
    return schemas.Jauge(
        capacite=pire.capacite, sous_option=pire.sous_option, disponibles=pire.disponibles,
        groupes_positionnes=groupes, besoin=besoin,
        niveau=niveau_jauge(pire.disponibles, besoin, groupes),
    ), pire


@dataclass
class Faits:
    """Tout ce dont les contrôles et l'indice ont besoin pour une proposition."""
    jour: str
    aller: Itineraire
    retour: Itineraire
    noms: dict[str, str]
    besoin: int
    jauge_aller: schemas.Jauge
    jauge_retour: schemas.Jauge
    etat_aller: EtatTrain
    etat_retour: EtatTrain
    acces: Acces
    arrivee_site: int
    debut_visite: int
    marge: int
    marche_etablissement: int
    heure_retour_max: int
    lieu_lat: float | None
    lieu_lon: float | None
    capacite_site: int | None
    gare_depart_nom: str
    aujourdhui: date = field(default_factory=config.aujourdhui)

    @property
    def retour_effectif(self) -> int:
        return self.retour.arr + self.marche_etablissement


def _c(regle: str, niveau: str, message: str) -> schemas.Controle:
    return schemas.Controle(regle=regle, libelle=LIBELLES[regle], niveau=niveau, message=message)


def hors_plage(it: Itineraire) -> list[str]:
    ecarts = []
    for s in it.segments:
        if s.dep < config.PLAGE_DEBUT or s.dep > config.PLAGE_FIN:
            ecarts.append(f"départ à {heure_fr(s.dep)}")
        if s.arr > config.PLAGE_FIN or s.arr < config.PLAGE_DEBUT:
            ecarts.append(f"arrivée à {heure_fr(s.arr)}")
    return ecarts


def evaluer(f: Faits) -> tuple[list[schemas.Controle], set[str]]:
    """Retourne les 10 contrôles et l'ensemble des règles bloquantes non respectées."""
    out: list[schemas.Controle] = []
    echecs: set[str] = set()
    trains = list(dict.fromkeys(f.aller.trains + f.retour.trains))

    # R1 — seuls les trains autorisés sont chargés par la recherche
    out.append(_c("R1", "vert", f"Train{'s' if len(trains) > 1 else ''} {', '.join(trains)} "
                                f"autorisé{'s' if len(trains) > 1 else ''} aux groupes."))

    # R2 — 6 à 50 voyageurs, dans la limite des places restantes
    if not (config.MIN_VOYAGEURS <= f.besoin <= config.MAX_VOYAGEURS):
        out.append(_c("R2", "rouge", f"Le groupe compte {f.besoin} voyageurs : l'offre groupe accepte "
                                     f"de {config.MIN_VOYAGEURS} à {config.MAX_VOYAGEURS} voyageurs, "
                                     f"accompagnateurs compris."))
        echecs.add("R2")
    else:
        manques = []
        for sens, it, e in (("aller", f.aller, f.etat_aller), ("retour", f.retour, f.etat_retour)):
            if e.disponibles < f.besoin:
                dep = next(s.dep for s in it.segments if s.train == e.numero)
                manques.append(f"{e.disponibles} places disponibles sur le train {e.numero} de "
                               f"{heure_fr(dep)} ({sens}) pour {f.besoin} voyageurs")
        if manques:
            out.append(_c("R2", "rouge", "Places insuffisantes : " + " ; ".join(manques) + "."))
            echecs.add("R2")
        else:
            d = min(f.etat_aller.disponibles, f.etat_retour.disponibles)
            out.append(_c("R2", "vert", f"{f.besoin} voyageurs, au moins {d} places disponibles sur "
                                        f"chaque train."))

    # R3 — accès gare -> site (vigilance)
    out.append(_c("R3", "vert" if f.acces.a_pied_ok else "orange", f.acces.message))

    # R4 — arrivée au moins 30 min avant la visite (vigilance)
    txt = (f"Arrivée sur le site vers {heure_fr(f.arrivee_site)}, visite à {heure_fr(f.debut_visite)} "
           f"(créneau indicatif) : {f.marge} min de marge")
    if f.marge >= config.MARGE_VISITE_MIN:
        out.append(_c("R4", "vert", txt + "."))
    else:
        out.append(_c("R4", "orange", txt + f" seulement ({config.MARGE_VISITE_MIN} min conseillées)."))

    # R5 — retour au point de départ avant l'heure maximale (bloquant)
    gare = f.gare_depart_nom
    pied = (f", puis environ {f.marche_etablissement} min à pied jusqu'à l'établissement"
            if f.marche_etablissement else "")
    if f.retour_effectif <= f.heure_retour_max:
        out.append(_c("R5", "vert", f"Retour en gare de {gare} à {heure_fr(f.retour.arr)}{pied}, "
                                    f"avant {heure_fr(f.heure_retour_max)}."))
    else:
        out.append(_c("R5", "rouge", f"Retour en gare de {gare} à {heure_fr(f.retour.arr)}{pied} : "
                                     f"après l'heure maximale de {heure_fr(f.heure_retour_max)}."))
        echecs.add("R5")

    # R6 — plage 9h-16h de l'offre groupe (vigilance)
    ecarts = hors_plage(f.aller) + hors_plage(f.retour)
    if ecarts:
        out.append(_c("R6", "orange", f"{capitaliser(', '.join(ecarts))} : hors de la plage 9h-16h de "
                                      f"l'offre groupe, étude au cas par cas par SNCF."))
    else:
        out.append(_c("R6", "vert", "Tous les trains circulent entre 9h et 16h, dans la plage de "
                                    "l'offre groupe."))

    # R7 — J-21 (vigilance)
    delai = (date.fromisoformat(f.jour) - f.aujourdhui).days
    if delai >= config.DELAI_MIN_JOURS:
        out.append(_c("R7", "vert", f"Demande faite {delai} jours avant la sortie "
                                    f"({config.DELAI_MIN_JOURS} jours minimum)."))
    elif delai >= 0:
        out.append(_c("R7", "orange", f"Sortie dans {delai} jours : moins de {config.DELAI_MIN_JOURS} "
                                      f"jours, la demande sera étudiée au cas par cas."))
    else:
        out.append(_c("R7", "orange", "La date de sortie est déjà passée : choisissez une date à venir."))

    # R8 — établissement en Occitanie (bloquant)
    from .geo import en_occitanie
    if f.lieu_lat is None or f.lieu_lon is None:
        out.append(_c("R8", "orange", "Localisation de l'établissement à confirmer (offre réservée "
                                      "aux établissements d'Occitanie)."))
    elif en_occitanie(f.lieu_lat, f.lieu_lon):
        out.append(_c("R8", "vert", "Établissement situé en Occitanie."))
    else:
        out.append(_c("R8", "rouge", "Établissement hors d'Occitanie : l'offre groupe liO est "
                                     "réservée aux établissements d'Occitanie."))
        echecs.add("R8")

    # R9 — autre groupe positionné (vigilance), jamais d'identité
    positionnes = [e for e in (f.etat_aller, f.etat_retour) if e.groupes > 0]
    if positionnes:
        noms = ", ".join(dict.fromkeys(e.numero for e in positionnes))
        out.append(_c("R9", "orange", f"Un autre groupe est déjà positionné sur le train {noms} : "
                                      f"validation au cas par cas par SNCF."))
    else:
        out.append(_c("R9", "vert", "Aucun autre groupe positionné sur ces trains à cette date."))

    # R10 — capacité d'accueil du site (vigilance, « à vérifier » si inconnue)
    if f.capacite_site is None:
        out.append(_c("R10", "orange", "Capacité d'accueil du site non renseignée : à vérifier lors "
                                       "de la réservation de la visite."))
    elif f.besoin <= f.capacite_site:
        out.append(_c("R10", "vert", f"Le site accueille jusqu'à {f.capacite_site} personnes."))
    else:
        out.append(_c("R10", "orange", f"Le site accueille {f.capacite_site} personnes : prévoir "
                                       f"des sous-groupes."))
    return out, echecs


def marche_etablissement(distance_m: float | None) -> int:
    """Temps de groupe entre la gare de départ et l'établissement (si à distance de marche)."""
    if distance_m is None or distance_m > 2000:
        return 0
    individuel = distance_m / config.VITESSE_MARCHE_M_MIN
    return arrondi(individuel * config.COEF_MARCHE_GROUPE + config.REGROUPEMENT_MIN)
