"""Indice Confiance Voyageur Scolaire (cahier des charges §5), calculé par le code, jamais par l'IA.

Les critères liés au train prennent le moins bon de tous les trains du trajet (aller et retour).
Seuils : 80 et plus vert « Fiable » ; 60 à 79 orange ; moins de 60, ou une règle bloquante non
respectée, rouge « Pas assez fiable ».
"""
from __future__ import annotations

import sqlite3

from .. import config, schemas
from .controles import Faits
from .texte import arrondi, capitaliser, pourcent_fr

CAPACITE = "Capacité et confort"
REGULARITE = "Régularité"
SUPPRESSION = "Risque de suppression"
HORAIRES = "Faisabilité des horaires"
ACCES = "Accès gare → site"
ADEQUATION = "Adéquation pédagogique"
SATISFACTION = "Satisfaction et coup de cœur"
CRITERES = [CAPACITE, REGULARITE, SUPPRESSION, HORAIRES, ACCES, ADEQUATION, SATISFACTION]


def niveau_score(score: int, bloquant: bool = False) -> str:
    if bloquant or score < 60:
        return "rouge"
    return "vert" if score >= 80 else "orange"


def fiabilites(conn: sqlite3.Connection, numeros: list[str], cache: dict) -> dict[str, sqlite3.Row | None]:
    out = {}
    for n in numeros:
        k = ("fiab", n)
        if k not in cache:
            cache[k] = conn.execute("SELECT * FROM fiabilite_train WHERE train_numero = ?", (n,)).fetchone()
        out[n] = cache[k]
    return out


def points_satisfaction(moyenne: float | None, nb: int, coeurs: int, simules: int) -> tuple[int, str]:
    if not nb or moyenne is None:
        return 5, "Neutre : pas encore de retours sur ce site."
    pts = arrondi(moyenne * 2)
    txt = f"{str(round(moyenne, 1)).replace('.', ',')}/5 en moyenne sur {nb} retour{'s' if nb > 1 else ''}"
    if coeurs:
        txt += f", {coeurs} coup{'s' if coeurs > 1 else ''} de cœur"
    if simules:
        txt += f" (dont {simules} simulé{'s' if simules > 1 else ''} pour la démo)"
    return min(10, pts), txt + "."


def _indice(details: list[schemas.CritereIndice], bloquant: bool) -> schemas.Indice:
    """Somme des critères. Un trajet bloqué par une règle bloquante est rouge ET son score est
    plafonné sous le seuil orange : jamais de « 84 » flatteur sur un trajet refusé (audit n°5)."""
    score = sum(d.points for d in details)
    niveau = niveau_score(score, bloquant)
    if niveau == "rouge":
        score = min(score, 59)
    return schemas.Indice(score=score, niveau=niveau, details=details)


def calculer(conn: sqlite3.Connection, f: Faits, echecs: set[str], adequation: tuple[int, str],
             satisfaction: tuple[float | None, int, int, int], cache: dict) -> schemas.Indice:
    details: list[schemas.CritereIndice] = []
    numeros = list(dict.fromkeys(f.aller.trains + f.retour.trains))
    fiab = fiabilites(conn, numeros, cache)
    connus = {n: r for n, r in fiab.items() if r is not None}

    # Capacité et confort (20)
    dispo = min(f.etat_aller.disponibles, f.etat_retour.disponibles)
    if dispo >= f.besoin * 1.1:
        base, etat = 12, "marge confortable"
    elif dispo >= f.besoin:
        base, etat = 6, "couvert tout juste"
    else:
        base, etat = 0, "insuffisant"
    emports = {n: r["taux_respect_emport"] for n, r in connus.items() if r["taux_respect_emport"] is not None}
    if emports:
        n_emp = min(emports, key=emports.get)
        e = emports[n_emp]
        pts_emp = 8 * max(0.0, min(100.0, e)) / 100
        txt_emp = f"respect de l'emport {pourcent_fr(e)} (train {n_emp})"
    else:
        pts_emp, txt_emp = 4, "respect de l'emport inconnu"
    details.append(schemas.CritereIndice(
        critere=CAPACITE, points=arrondi(base + pts_emp), max=20,
        explication=f"{f.besoin} places nécessaires, {dispo} disponibles ({etat}) ; {txt_emp}."))

    # Régularité (15) : 0 à 70 %, 15 à 95 % ou plus (médiane réelle par train : 86 %)
    regs = {n: r["taux_regularite"] for n, r in connus.items() if r["taux_regularite"] is not None}
    if regs:
        n_reg = min(regs, key=regs.get)
        reg = regs[n_reg]
        pts = max(0.0, min(15.0, (reg - 70) / 25 * 15))
        nb_mois = connus[n_reg]["nb_mois"]
        details.append(schemas.CritereIndice(
            critere=REGULARITE, points=arrondi(pts), max=15,
            explication=f"{pourcent_fr(reg)} des circulations à l'heure (train {n_reg}, le moins "
                        f"régulier du trajet, moyenne sur {nb_mois} mois)."))
    else:
        details.append(schemas.CritereIndice(critere=REGULARITE, points=7, max=15,
                                             explication="Historique de régularité indisponible."))

    # Risque de suppression (10) : 10 × (1 − taux / 15 %), minimum 0 (médiane réelle par train : 6 %)
    sups = {n: r["taux_suppression"] for n, r in connus.items() if r["taux_suppression"] is not None}
    if sups:
        n_sup = max(sups, key=sups.get)
        s = sups[n_sup]
        details.append(schemas.CritereIndice(
            critere=SUPPRESSION, points=arrondi(max(0.0, 10 * (1 - s / 15))), max=10,
            explication=f"{pourcent_fr(s, 1)} de circulations supprimées (train {n_sup})."))
    else:
        details.append(schemas.CritereIndice(critere=SUPPRESSION, points=5, max=10,
                                             explication="Historique des suppressions indisponible."))

    # Faisabilité des horaires (15) : R4, R5, R6
    from .controles import hors_plage
    from .texte import heure_fr
    pts, parts = 0, []
    if f.marge >= config.MARGE_VISITE_MIN:
        pts += 5
        parts.append(f"{f.marge} min de marge avant la visite")
    else:
        parts.append(f"⚠️ {f.marge} min de marge seulement avant la visite")
    if f.retour_effectif <= f.heure_retour_max:
        pts += 5
        parts.append(f"retour à {heure_fr(f.retour.arr)}, avant {heure_fr(f.heure_retour_max)}")
    else:
        parts.append(f"⚠️ retour à {heure_fr(f.retour.arr)}, après {heure_fr(f.heure_retour_max)}")
    ecarts = hors_plage(f.aller) + hors_plage(f.retour)
    if not ecarts:
        pts += 5
        parts.append("trajets dans la plage 9h-16h")
    else:
        parts.append(f"⚠️ {ecarts[0]}, hors plage de l'offre groupe")
    details.append(schemas.CritereIndice(critere=HORAIRES, points=pts, max=15,
                                         explication=capitaliser(", ".join(parts) + ".")))

    # Accès gare -> site (15)
    a = f.acces
    if a.points == 15:
        txt = f"{a.minutes} min à pied pour le groupe."
    elif a.points == 10:
        txt = f"Réseau urbain compatible, environ {a.minutes} min."
    else:
        txt = f"{a.minutes} min à pied pour le groupe, sans réseau urbain adapté : au-delà des critères."
    details.append(schemas.CritereIndice(critere=ACCES, points=a.points, max=15, explication=txt))

    # Adéquation pédagogique (15) : note 0-3 × 5
    note, txt = adequation
    details.append(schemas.CritereIndice(critere=ADEQUATION, points=note * 5, max=15, explication=txt))

    # Satisfaction et coup de cœur (10)
    pts_sat, txt_sat = points_satisfaction(*satisfaction)
    details.append(schemas.CritereIndice(critere=SATISFACTION, points=pts_sat, max=10, explication=txt_sat))

    return _indice(details, bool(echecs))


def remplacer_satisfaction(indice: schemas.Indice, bloquant: bool,
                           satisfaction: tuple[float | None, int, int, int]) -> schemas.Indice:
    """Recalcule l'indice d'une proposition existante avec une nouvelle satisfaction du site."""
    pts, txt = points_satisfaction(*satisfaction)
    details = [d.model_copy(update={"points": pts, "explication": txt}) if d.critere == SATISFACTION else d
               for d in indice.details]
    return _indice(details, bloquant)
