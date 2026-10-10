"""Recommander 3 destinations, tirées UNIQUEMENT du catalogue.

Filtre par le code (thème, niveau, accessibilité en train, hors commune de départ), puis classement :
par le LLM en mode « llm » (note 0-3 et justification), par règles en mode démo. Les indices de
confiance sont toujours calculés par le code.
"""
from __future__ import annotations

import sqlite3

from .. import db, llm, schemas
from . import comprendre, propositions, sites
from .texte import normaliser

MAX_CANDIDATS = 10


def _decouverte(site) -> bool:
    """Site importé de DATAtourisme (id préfixé « dt- ») : classé après le catalogue fait main."""
    return str(site["id"]).startswith("dt-")


def _souhaites(demande: schemas.Demande, tous: list[sqlite3.Row]) -> tuple[list[str], bool]:
    """Sites correspondant à la destination souhaitée (site précis d'abord, puis sa commune)."""
    if not demande.destination_souhaitee:
        return [], False
    cible = normaliser(demande.destination_souhaitee)
    exacts = [s["id"] for s in tous if normaliser(s["nom"]) == cible or s["id"] == demande.destination_souhaitee]
    partiels = [s["id"] for s in tous if s["id"] not in exacts and
                (cible in normaliser(s["nom"]) or normaliser(s["nom"]) in cible)]
    commune = [s["id"] for s in tous if s["id"] not in exacts + partiels and
               normaliser(s["commune"] or "") == cible]
    ids = exacts + partiels + commune
    return ids, bool(ids)


def recommander(conn: sqlite3.Connection, demande: schemas.Demande) -> schemas.ReponseDestinations:
    ctx = propositions.contexte(demande)
    commune_dep = comprendre.commune_de_depart(demande)
    tous = sites.tous_les_sites(conn)
    exclus = [s for s in tous if s["gare_uic"] == ctx.gare_uic or
              (commune_dep and normaliser(s["commune"] or "") == normaliser(commune_dep))]
    ids_exclus = {s["id"] for s in exclus}
    possibles = [s for s in tous if s["id"] not in ids_exclus]
    souhaites, trouve = _souhaites(demande, possibles)
    souhait_local = not trouve and _souhaites(demande, exclus)[1]

    notes = {s["id"]: sites.adequation(s, demande) for s in possibles}
    seuil = 2 if demande.theme else 1
    pre = sorted(possibles, key=lambda s: (s["id"] not in souhaites, -notes[s["id"]][0], _decouverte(s),
                                         -s["richesse"]))
    candidats = [s for s in pre if s["id"] in souhaites or notes[s["id"]][0] >= seuil]
    if len(candidats) < 3:
        candidats += [s for s in pre if s not in candidats][: 3 - len(candidats)]

    # Mode LLM : le modèle note et classe les sites du catalogue (jamais d'autres)
    choix_llm: list[str] = []
    justifications: dict[str, str] = {}
    if llm.mode() == "llm":
        pool = [s for s in pre if s["id"] in souhaites or notes[s["id"]][0] >= 1][:20] or pre[:20]
        r = llm.recommander(
            {"niveau": demande.niveau, "theme": demande.theme,
             "destination_souhaitee": demande.destination_souhaitee, "duree": demande.duree},
            [{"site_id": s["id"], "nom": s["nom"], "commune": s["commune"],
              "themes": sites.liste(s["themes"]), "niveaux": sites.liste(s["niveaux"]),
              "activites": sites.liste(s["activites"]),
              "interet_pedagogique": s["interet_pedagogique"]} for s in pool],
        )
        if r:
            for n in r.sites:
                sites.memoriser_note_llm(n.site_id, demande.theme, demande.niveau, n.note, n.justification)
                justifications[n.site_id] = n.justification
            choix_llm = r.choix
            par_id = {s["id"]: s for s in pool}
            candidats = [par_id[i] for i in dict.fromkeys(souhaites + choix_llm) if i in par_id] + \
                [s for s in candidats if s["id"] not in choix_llm and s["id"] not in souhaites]

    resultats, sans_train = [], []
    for s in candidats[:MAX_CANDIDATS]:
        r = propositions.planifier(conn, ctx, s)
        if not r.propositions:
            # Aucun aller-retour liO autorisé aux groupes ce jour-là : on ne l'affiche pas avec un 0/100,
            # on le signale seulement dans le message s'il collait au projet.
            if s["id"] in souhaites or notes[s["id"]][0] >= seuil:
                sans_train.append(s)
            continue
        resultats.append(r)

    rang = {"vert": 0, "orange": 1, "rouge": 2}

    def cle(r: propositions.Resultat):
        sid = r.site["id"]
        return (
            souhaites.index(sid) if sid in souhaites else len(souhaites),
            choix_llm.index(sid) if sid in choix_llm else len(choix_llm),
            -sites.adequation(r.site, demande)[0],
            _decouverte(r.site),
            r.niveau == "rouge",
            -r.site["richesse"],
            -r.indice,
            rang[r.niveau],
            r.temps_trajet_min or 9999,
        )

    resultats.sort(key=cle)
    retenus, communes = [], set()
    for r in resultats:  # une destination par commune d'abord, pour varier
        if r.site["id"] in souhaites or r.site["commune"] not in communes:
            retenus.append(r)
            communes.add(r.site["commune"])
        if len(retenus) == 3:
            break
    for r in resultats:
        if len(retenus) == 3:
            break
        if r not in retenus:
            retenus.append(r)

    destinations = [propositions.destination(conn, r, justifications.get(r.site["id"])) for r in retenus]
    return schemas.ReponseDestinations(destinations=destinations,
                                       message=_message(demande, ctx, destinations, exclus, trouve or souhait_local, retenus,
                                                        sans_train))


def _message(demande, ctx, destinations, exclus, trouve, retenus, sans_train=()) -> str:
    parts = []
    if demande.destination_souhaitee and not trouve:
        parts.append(f"Je n'ai pas « {demande.destination_souhaitee} » dans notre catalogue : voici les "
                     f"destinations les plus proches de votre projet.")
    if not destinations:
        parts.append("Je n'ai trouvé aucun site du catalogue accessible en train liO autorisé aux groupes "
                     "pour cette demande. Essayez un autre thème ou une autre date.")
    else:
        sujet = f"« {demande.theme} »" if demande.theme else "votre projet"
        niveau = f" ({demande.niveau})" if demande.niveau else ""
        n = len(destinations)
        parts.append(f"Voici {n} destination{'s' if n > 1 else ''} de notre catalogue pour {sujet}{niveau}, "
                     f"au départ de la gare de {ctx.gare_nom}.")
    if demande.destination_souhaitee and trouve and not any(
            normaliser(demande.destination_souhaitee) in normaliser(d.nom + " " + d.commune) for d in destinations):
        parts.append(f"« {demande.destination_souhaitee} » est dans votre commune : pas besoin de train !")
    if exclus and demande.theme:
        pertinents = [s for s in exclus if sites.adequation(s, demande)[0] >= 2]
        if pertinents:
            noms = ", ".join(s["nom"] for s in pertinents[:2])
            parts.append(f"J'ai écarté {noms} : {'il est' if len(pertinents) == 1 else 'ils sont'} dans "
                         f"votre commune, pas besoin de train !")
    retenus_ids = {r.site["id"] for r in retenus}
    ecartes = [s for s in sans_train if s["id"] not in retenus_ids]
    if ecartes:
        noms = ", ".join(s["nom"] for s in ecartes[:2])
        parts.append(f"J'ai écarté {noms} : aucun aller-retour en train liO autorisé aux groupes "
                     f"ne tient dans vos horaires ce jour-là.")
    if retenus and retenus[0].date_info.jour_type:
        parts.append(retenus[0].date_info.message)
    if db.nature_donnees() == "demo":
        parts.append("Données de démonstration : trains, horaires et places sont simulés.")
    return " ".join(parts)
