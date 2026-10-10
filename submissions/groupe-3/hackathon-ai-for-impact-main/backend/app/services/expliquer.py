"""Expliquer chaque proposition en langage clair, à partir des chiffres calculés par le code.

Mode démo : phrases construites par gabarits. Mode LLM : un seul appel reformule toutes les
propositions ; chaque texte passe un garde-fou (aucun horaire ni nombre absent des faits), sinon
on garde le gabarit.
"""
from __future__ import annotations

from .. import llm, schemas
from .texte import date_fr, duree_fr, heure_fr

VIGILANCE = {
    "R3": "accès au site par le réseau urbain",
    "R4": "marge courte avant la visite",
    "R6": "horaires hors de la plage 9h-16h de l'offre groupe (étude au cas par cas)",
    "R7": "demande à moins de 21 jours du départ",
    "R8": "localisation de l'établissement à confirmer",
    "R9": "un autre groupe est déjà positionné sur un des trains (validation au cas par cas)",
}


def _resume(p: schemas.Proposition, gare_depart: str, heure_retour_max: str) -> str:
    a, r = p.aller, p.retour
    trajet = ("Trajet direct" if a.correspondances == 0
              else f"Trajet avec une correspondance à {a.segments[0].gare_arrivee}")
    dispo = min(p.jauge_aller.disponibles, p.jauge_retour.disponibles)
    return (f"{trajet} : départ de {gare_depart} à {heure_fr(a.depart)}, arrivée à "
            f"{heure_fr(a.arrivee)} ({duree_fr(a.duree_min)}), avec {p.marge_avant_visite_min} min de "
            f"marge avant la visite. Retour à {gare_depart} à {heure_fr(r.arrivee)}, avant "
            f"{heure_fr(heure_retour_max)}. {dispo} places disponibles pour vos "
            f"{p.jauge_aller.besoin} voyageurs.")


def gabarit(p: schemas.Proposition, props: list[schemas.Proposition], gare_depart: str,
            heure_retour_max: str) -> str:
    score = p.indice.score
    if p.indice.niveau == "rouge":
        rouges = [c.message for c in p.controles if c.niveau == "rouge"]
        if rouges:
            txt = "Pas assez fiable. " + " ".join(rouges)
            if any(c.regle == "R2" and c.niveau == "rouge" for c in p.controles) and \
                    max(p.jauge_aller.groupes_positionnes, p.jauge_retour.groupes_positionnes) > 0:
                txt += " Un autre groupe a déjà posé une option sur ce train."
        else:
            faibles = sorted(p.indice.details, key=lambda d: d.points / d.max)[:2]
            txt = (f"Pas assez fiable (indice {score}/100) : "
                   + " ; ".join(d.explication.rstrip(".") for d in faibles) + ".")
        if any(q.remplace == p.proposition_id for q in props):
            txt += " Je vous propose une alternative juste en dessous."
        else:
            txt += " Je n'ai pas trouvé d'alternative sûre : essayez une autre date ou une autre destination."
        return txt

    debut = ""
    if p.est_alternative and p.remplace:
        rouge = next((q for q in props if q.proposition_id == p.remplace), None)
        if rouge and rouge.date != p.date:
            debut = (f"Alternative : le {date_fr(rouge.date)} ne convient pas, mais le même trajet "
                     f"est possible le {date_fr(p.date)}. ")
        elif rouge and p.aller.depart > rouge.aller.depart:
            debut = (f"Alternative au train de {heure_fr(rouge.aller.depart)} : le train suivant "
                     f"({p.aller.segments[0].train}, départ à {heure_fr(p.aller.depart)}) a assez de places. ")
        elif rouge:
            debut = (f"Alternative à la proposition de {heure_fr(rouge.aller.depart)} : même train à "
                     f"l'aller, retour par le train {p.retour.segments[0].train} de "
                     f"{heure_fr(p.retour.depart)}. ")
    vigilance = [VIGILANCE[c.regle] for c in p.controles if c.niveau == "orange" and c.regle in VIGILANCE]
    if p.indice.niveau == "vert":
        ton = f"Fiable ({score}/100). "
    else:
        ton = f"Faisable, avec des points de vigilance ({score}/100). "
    txt = debut + ton + _resume(p, gare_depart, heure_retour_max)
    if vigilance:
        txt += " À surveiller : " + " ; ".join(vigilance) + "."
    return txt


def _faits(p: schemas.Proposition, gabarit_txt: str) -> str:
    lignes = [
        f"niveau={p.indice.niveau} score={p.indice.score}/100 date={p.date}",
        f"aller: {', '.join(f'train {s.train} {s.gare_depart} {s.depart} -> {s.gare_arrivee} {s.arrivee}' for s in p.aller.segments)}",
        f"retour: {', '.join(f'train {s.train} {s.gare_depart} {s.depart} -> {s.gare_arrivee} {s.arrivee}' for s in p.retour.segments)}",
        f"places: besoin {p.jauge_aller.besoin}, disponibles aller {p.jauge_aller.disponibles}, "
        f"retour {p.jauge_retour.disponibles}",
        f"marge avant visite: {p.marge_avant_visite_min} min",
        "contrôles non verts: " + " | ".join(f"{c.regle} {c.niveau}: {c.message}"
                                             for c in p.controles if c.niveau != "vert"),
        "alternative de la proposition: " + (p.remplace or "non"),
        f"texte de référence: {gabarit_txt}",
    ]
    return "\n".join(lignes)


def expliquer(props: list[schemas.Proposition], demande: schemas.Demande) -> None:
    """Remplit `explication_ia` de chaque proposition (sur place)."""
    gare = demande.gare_depart.nom if demande.gare_depart else "la gare de départ"
    hmax = demande.heure_retour_max or "18:00"
    gabarits = {p.proposition_id: gabarit(p, props, gare, hmax) for p in props}
    reformulees = {}
    if llm.mode() == "llm" and props:
        reformulees = llm.expliquer({p.proposition_id: _faits(p, gabarits[p.proposition_id]) for p in props})
    for p in props:
        p.explication_ia = reformulees.get(p.proposition_id) or gabarits[p.proposition_id]
