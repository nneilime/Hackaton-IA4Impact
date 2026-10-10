"""Conversation avec Tchouette, la chouette-locomotive : remplit la Demande au fil des messages.

Ton : chaleureux, vouvoiement, phrases courtes, un clin d'œil ferroviaire de temps en temps, jamais
de fausse promesse. Une seule question de relance à la fois. Les réponses sont construites par le
code (y compris en mode LLM, où le modèle sert seulement à extraire les champs).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta

from .. import config, llm, schemas
from . import comprendre, sites
from .texte import date_fr, heure_fr, normaliser

ORDRE = ["niveau", "theme", "nb_eleves", "nb_accompagnateurs", "date", "lieu_depart", "gare_depart"]

QUESTIONS = {
    "niveau": "Avec quelle classe partez-vous ? Indiquez-moi le niveau (CM2, 5e, seconde…).",
    "theme": "Sur quel thème souhaitez-vous travailler avec vos élèves ?",
    "nb_eleves": "Combien d'élèves partent ?",
    "nb_accompagnateurs": "Combien d'accompagnateurs encadrent le groupe ? Adultes compris, un train "
                          "liO accueille jusqu'à 50 voyageurs.",
    "date": "Quelle date envisagez-vous ? L'offre groupe demande de s'y prendre au moins 21 jours avant.",
    "lieu_depart": "D'où partez-vous ? Le nom de votre établissement et sa commune suffisent : je trouve "
                   "la gare la plus proche.",
    "gare_depart": "Je ne trouve pas de gare liO près de ce lieu. Dans quelle commune d'Occitanie se "
                   "trouve votre établissement ?",
}

SUGGESTIONS = {
    "niveau": ["CM2", "6e", "5e", "Seconde"],
    "theme": ["Moyen Âge", "Antiquité", "Espace et astronomie", "Arts"],
    "nb_eleves": ["24 élèves", "30 élèves", "42 élèves"],
    "nb_accompagnateurs": ["2 accompagnateurs", "3 accompagnateurs", "4 accompagnateurs"],
    "lieu_depart": ["Collège de Foix", "Lycée de Montauban", "École de Narbonne"],
    "gare_depart": ["Toulouse", "Foix", "Montpellier"],
}

AIDE = ("Je vous aide en trois étapes : je comprends votre projet, je vous propose des destinations "
        "de notre catalogue accessibles en train liO, puis je vérifie les trains, les places et les règles "
        "de l'offre groupe avant votre demande de pré-réservation. Rien n'est réservé sans l'accord de la SNCF.")
QUESTION_DESTINATION = "Parfait ! Quel lieu souhaitez-vous visiter ?"
_RE_AIDE = re.compile(r"\b(comment (ca|cela) (marche|fonctionne)|aide moi|aidez moi|qui etes vous|qui es tu|"
                      r"c est quoi)\b")
_RE_SAIT_OU = re.compile(r"\b(je sais (deja )?ou aller|j ai (deja )?une destination|destination precise|"
                         r"je connais (deja )?ma destination)\b")

_MODIFIER = [(r"\b(modifier|changer) (la )?date\b", "date"),
             (r"\b(modifier|changer) (l )?effectif\b|\b(modifier|changer) le nombre d eleves\b", "nb_eleves"),
             (r"\b(modifier|changer) (le )?nombre d accompagnateurs\b", "nb_accompagnateurs"),
             (r"\b(modifier|changer) (le )?(theme|sujet)\b", "theme"),
             (r"\b(modifier|changer) (le )?(lieu|point) de depart\b|\bchanger d etablissement\b", "lieu_depart")]

ACCUEIL = ("Bonjour, je suis Tchouette, votre copilote de sortie en train liO ! Décrivez-moi votre "
           "projet : la classe, le thème, le nombre d'élèves et d'accompagnateurs, la date et "
           "l'établissement de départ. Je m'occupe des trains.")


def _dates_suggerees(aujourdhui: date) -> list[str]:
    d = aujourdhui + timedelta(days=config.DELAI_MIN_JOURS)
    while d.isoweekday() != 4:  # jeudis, à partir de J+21
        d += timedelta(days=1)
    return [date_fr(d + timedelta(weeks=k)).capitalize() for k in range(3)]


def _premier_manquant(d: schemas.Demande) -> str | None:
    for c in ORDRE:
        if c in d.champs_manquants:
            return c
    return None


def _compris(extrait: dict, d: schemas.Demande) -> str:
    morceaux = []
    if "niveau" in extrait:
        morceaux.append(f"classe de {d.niveau}")
    if "theme" in extrait and d.theme:
        morceaux.append(f"thème « {d.theme} »")
    if "nb_eleves" in extrait or "nb_accompagnateurs" in extrait:
        e, a = d.nb_eleves, d.nb_accompagnateurs
        if e is not None and a is not None:
            morceaux.append(f"{e} élèves et {a} accompagnateur{'s' if a > 1 else ''}")
        elif e is not None:
            morceaux.append(f"{e} élèves")
        elif a is not None:
            morceaux.append(f"{a} accompagnateur{'s' if a > 1 else ''}")
    if "date" in extrait and d.date:
        morceaux.append(f"sortie le {date_fr(d.date)}")
    if "duree" in extrait and d.duree:
        morceaux.append("à la journée" if d.duree == "journee" else "à la demi-journée")
    if "heure_retour_max" in extrait and d.heure_retour_max:
        morceaux.append(f"retour avant {heure_fr(d.heure_retour_max)}")
    if "lieu_depart" in extrait and d.lieu_depart:
        morceaux.append(f"départ : {d.lieu_depart.libelle}")
    if "destination_souhaitee" in extrait and d.destination_souhaitee:
        morceaux.append(f"destination : {d.destination_souhaitee}")
    return ", ".join(morceaux)


def _gare_trouvee(d: schemas.Demande) -> str:
    g = d.gare_depart
    if not g:
        return ""
    if g.distance_m:
        dist = f"{g.distance_m / 1000:.1f} km".replace(".", ",") if g.distance_m >= 1000 else f"{int(round(g.distance_m, -1))} m"
        return f"Votre gare de départ : {g.nom}, à environ {dist} de l'établissement."
    return f"Votre gare de départ : {g.nom}."


def _alertes(d: schemas.Demande, aujourdhui: date) -> list[str]:
    out = []
    if d.nb_eleves is not None and d.nb_accompagnateurs is not None:
        total = d.nb_eleves + d.nb_accompagnateurs
        if total > config.MAX_VOYAGEURS:
            out.append(f"Attention : {total} voyageurs, c'est plus que les 50 places d'un train liO pour "
                       f"un groupe. Pouvez-vous partir en deux groupes ?")
        elif total < config.MIN_VOYAGEURS:
            out.append(f"L'offre groupe commence à {config.MIN_VOYAGEURS} voyageurs, accompagnateurs compris.")
    if d.date:
        delai = (date.fromisoformat(d.date) - aujourdhui).days
        if 0 <= delai < config.DELAI_MIN_JOURS:
            out.append(f"La sortie est dans {delai} jours : moins de 21 jours, la SNCF étudiera la demande "
                       f"au cas par cas.")
    return out


def repondre(conn: sqlite3.Connection, req: schemas.RequeteChat) -> schemas.ReponseChat:
    aujourdhui = config.aujourdhui()
    mode = llm.mode()
    utilisateur = [m for m in req.messages if m.role == "user" and m.content.strip()]
    demande = comprendre.completer(conn, req.demande or schemas.Demande())

    if not utilisateur:
        return schemas.ReponseChat(
            reponse=ACCUEIL, demande=demande, complete=not demande.champs_manquants,
            suggestions=["Sortie Moyen Âge avec ma classe de 5e", "Je sais déjà où aller",
                         "Comment ça marche ?"],
            mode=mode)

    catalogue = [(s["nom"], s["commune"]) for s in sites.tous_les_sites(conn)]
    # Sans demande fournie, on relit toute la conversation ; sinon seulement le dernier message.
    a_lire = utilisateur if req.demande is None else utilisateur[-1:]
    extrait_total: dict = {}
    champ_attendu = None
    dernier_assistant = next((m.content for m in reversed(req.messages) if m.role == "assistant"), "")
    if req.demande is not None and dernier_assistant:
        # le champ dont la question vient d'être posée, sinon le premier champ manquant
        champ_attendu = next((c for c, q in QUESTIONS.items() if q in dernier_assistant),
                             _premier_manquant(demande))
    if dernier_assistant.startswith(QUESTION_DESTINATION):
        champ_attendu = "destination_souhaitee"
    for m in a_lire:
        commune = comprendre.commune_de_depart(demande)
        ex = comprendre.extraire(m.content, aujourdhui, champ_attendu, catalogue, commune)
        if mode == "llm" and m is utilisateur[-1]:
            idx = max(i for i, x in enumerate(req.messages) if x is m)
            precedent = next((x.content for x in reversed(req.messages[:idx]) if x.role == "assistant"), None)
            ex_llm = llm.extraire_demande(m.content, precedent,
                                          demande.model_dump(exclude={"champs_manquants"}),
                                          aujourdhui.isoformat())
            if ex_llm:
                for k, v in ex_llm.items():
                    if v is None:
                        continue
                    if k == "lieu_depart":
                        if "lieu_depart" not in ex or comprendre.normaliser(v) != comprendre.normaliser(ex["lieu_depart"]["libelle"]):
                            ex["lieu_depart"] = {"libelle": v, "commune": None}
                    else:
                        ex[k] = v
        demande = comprendre.completer(conn, comprendre.fusionner(demande, ex))
        extrait_total.update(ex)
        champ_attendu = _premier_manquant(demande)

    # Une date passée n'est pas retenue
    refus_date = None
    if demande.date and date.fromisoformat(demande.date) < aujourdhui:
        refus_date = f"Le {date_fr(demande.date)} est déjà passé : choisissez une date à venir."
        demande = comprendre.completer(conn, demande.model_copy(update={"date": None}))

    manquant = _premier_manquant(demande)
    complete = not demande.champs_manquants
    phrases: list[str] = []
    compris = _compris(extrait_total, demande)
    dernier = normaliser(utilisateur[-1].content)
    if not compris and _RE_SAIT_OU.search(dernier):
        return schemas.ReponseChat(
            reponse=QUESTION_DESTINATION + " Un site ou une ville d'Occitanie : je vérifie qu'il est dans "
                                           "notre catalogue et accessible en train liO.",
            demande=demande, complete=complete,
            suggestions=["Cité de Carcassonne", "Cité de l'espace", "Arènes de Nîmes"], mode=mode)
    if not compris:
        for motif, champ in _MODIFIER:
            if re.search(motif, dernier):
                return schemas.ReponseChat(
                    reponse="Bien sûr. " + QUESTIONS[champ], demande=demande, complete=complete,
                    suggestions=_dates_suggerees(aujourdhui) if champ == "date" else SUGGESTIONS[champ],
                    mode=mode)
    if compris:
        phrases.append(f"C'est noté : {compris}.")
    elif _RE_AIDE.search(dernier):
        phrases.append(AIDE)
    elif comprendre.INCERTAIN.search(dernier) and manquant == "theme":
        phrases.append("Pas de souci, je vais vous aider : choisissez un grand thème parmi ces idées, je "
                       "trouverai des sites adaptés à votre classe.")
    elif len(utilisateur) > 1 and not complete:
        phrases.append("Pardon, je n'ai pas bien saisi.")
    if "lieu_depart" in extrait_total and demande.gare_depart:
        phrases.append(_gare_trouvee(demande))
    if refus_date:
        phrases.append(refus_date)
    phrases += _alertes(demande, aujourdhui)

    if not complete and manquant:
        phrases.append(QUESTIONS[manquant])
        suggestions = _dates_suggerees(aujourdhui) if manquant == "date" else SUGGESTIONS[manquant]
    elif not compris and not refus_date:
        cible = (f"les trains pour « {demande.destination_souhaitee} »" if demande.destination_souhaitee
                 else "les destinations")
        phrases.append(f"Tout est prêt, en voiture ! Je vous montre {cible}.")
        suggestions = (["Voir les trains", "Modifier la date"] if demande.destination_souhaitee
                       else ["Voir les destinations", "Modifier la date"])
    else:
        recap = (f"Je récapitule : {demande.niveau}, "
                 + (f"« {demande.theme} », " if demande.theme else "")
                 + f"{demande.nb_eleves} élèves et {demande.nb_accompagnateurs} accompagnateurs, "
                 f"le {date_fr(demande.date)}, "
                 + ("à la journée" if demande.duree == "journee" else "à la demi-journée")
                 + f", départ à partir de {heure_fr(demande.heure_depart_min)} et retour avant "
                 f"{heure_fr(demande.heure_retour_max)}, depuis la gare de {demande.gare_depart.nom}.")
        phrases.append(recap)
        if demande.destination_souhaitee:
            phrases.append(f"Je regarde les trains pour « {demande.destination_souhaitee} » ? "
                           f"Prochain arrêt : les horaires !")
            suggestions = ["Voir les trains", "Voir d'autres destinations", "Modifier la date"]
        else:
            phrases.append("Je vous propose trois destinations du catalogue ? Prochain arrêt : les idées de sortie !")
            suggestions = ["Voir les destinations", "Modifier la date", "Changer l'effectif"]

    return schemas.ReponseChat(reponse=" ".join(p for p in phrases if p), demande=demande,
                               complete=complete, suggestions=suggestions[:4], mode=mode)
