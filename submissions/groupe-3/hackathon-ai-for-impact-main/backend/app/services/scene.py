"""Moteur de la scène « Tchouette est l'interface » : POST /api/scene (API_CONTRACT.md, section v3).

Une machine à états SANS état serveur : l'`EtatScene` arrive dans la requête et repart dans la
réponse. Les étapes ne sautent jamais ; un événement impossible pour l'étape courante donne un 409
avec un message français. Toute la logique métier passe par les services existants (comprendre,
recommander, propositions, sondages, dossiers) : ce module n'invente ni horaire, ni place, ni lieu.

Étapes : accueil -> theme -> criteres -> destination -> trajet -> (vote ->) prereservation -> fin.

Conventions de cet état (le contrat les laisse libres) :
- étape `theme`, `rang == 1` : on attend le NOM D'UN LIEU (porte « Je sais où aller ») ; `rang == 0` :
  on attend un thème. `rang` n'a pas d'autre sens à cette étape.
- étape `trajet` : `proposition_id` est le trajet PRÉSENTÉ (stocké en base par `dossiers.stocker`) ;
  il devient le trajet retenu quand la carte `reserver` fait passer à `prereservation`.
- le thème peut rester vide après la porte « Surprenez-moi » : la recommandation se fait alors
  sans thème (niveau et richesse du site seulement).

Le crochet LLM (`scene_llm`) n'est appelé qu'en mode « llm » ; sans lui, tout fonctionne en mode démo.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from fastapi import HTTPException

from .. import config, db, llm, schemas
from . import (comprendre, confiance, dossiers, expliquer, propositions, recommander, scene_llm,
               sites, sondages, trains)
from . import scene_textes as T
from . import dates_proches as dates_mod
from . import trajet_options
from . import rag
from . import themes as themes_mod
from .texte import date_fr, duree_fr, heure_fr, normaliser

MAX_CARNET = 30
ANCRES = {"accueil": "centre", "theme": "gauche", "criteres": "gauche", "destination": "gauche",
          "trajet": "gauche", "vote": "droite", "prereservation": "bas-droite", "fin": "centre"}
ICONES_THEME = {"Moyen Âge": "chateau", "Préhistoire": "os", "Antiquité": "colonnes",
                "Espace et astronomie": "planete", "Sciences et nature": "feuille", "Arts": "palette",
                "Temps modernes": "calendrier", "Première Guerre mondiale": "groupe"}
NIVEAUX_CARTES = [("CM2", "Primaire"), ("6e", "Collège"), ("5e", "Collège"), ("4e", "Collège")]
LIBELLES_MANQUANTS = {"theme": "thème ou lieu à visiter", "niveau": "niveau de la classe",
                      "effectif": "effectif", "date": "date de la sortie", "lieu": "lieu de départ"}
SUGGESTIONS_LIEU = ["Collège de Foix", "Lycée de Montauban", "École de Narbonne"]
AIDE_DATE = "21 jours avant, de préférence"
STATUTS_LISIBLES = {"OPTION": "option posée", "PRE_RESERVATION": "pré-réservation transmise",
                    "CONTRE_PROPOSITION": "contre-proposition de SNCF", "ANNULE": "annulé",
                    "CONFIRMATION": "confirmation reçue de SNCF"}
CRITERES_ORDRE = ["niveau", "effectif", "date", "lieu"]

# --- Reconnaissance des intentions (texte libre, mode démo) ----------------------------------
_RE_RETOUR = re.compile(r"^(retour(?! (?:avant|vers|a|apres|pour))|retourner|revenir|en arriere|precedent|precedente|annuler|annule|"
                        r"reviens|reviens en arriere|je reviens)\b")
_RE_RECOMMENCER = re.compile(r"\b(recommenc\w+|a zero|nouvelle sortie|autre sortie|tout effacer|"
                             r"reinitialis\w+|nouveau projet|repartir de zero)\b")
_RE_AFFIRM = re.compile(r"^(oui|ok|okay|d accord|parfait|super|go|banco|c est bon|ca me va|ca marche|top|"
                        r"yes|volontiers|avec plaisir|excellent|genial|nickel)( \w+){0,2}$")
_RE_NEG = re.compile(r"^(non|nan|bof|pas terrible|pas convaincu|pas vraiment|pas celle ci|pas celui ci)"
                     r"( \w+){0,2}$")
_RE_CHOISIR = re.compile(r"\b(celle ci|celui ci|je la prends|on la prend|je la veux|ca me va|"
                         r"je choisis|on y va|retenons)\b")
_RE_AUTRE_DEST = re.compile(r"\b(autre idee|autre destination|autre site|autre lieu|autre proposition|"
                            r"une autre|un autre site|suivant|suivante|ailleurs|autre chose|proposez autre|"
                            r"une autre idee|montrez en une autre)\b")
_RE_POURQUOI = re.compile(r"\b(pourquoi|comment ca|explique\w*|justifi\w+|detail\w*|raisons?|d ou vient|"
                          r"sur quoi|fiable)\b")
_RE_VOTE = re.compile(r"\b(vote|voter|votent|votez|sondage|sonder|qr code|qr|faire choisir)\b")
_RE_RESERVER = re.compile(r"\b(pre reserv\w+|prereserv\w+|reserv\w+|on prend|je prends|on le prend|"
                          r"je le prends|celui la|valide\w*)\b")
_RE_AUTRE_TRAIN = re.compile(r"\b(autre train|autre horaire|autre option|autre trajet|autres? horaires|"
                             r"plus tot|plus tard|un autre|une autre|suivant|different)\b")
_RE_PORTE_THEME = re.compile(r"\b(un theme|j ai un theme|theme)\b")
_RE_PORTE_LIEU = re.compile(r"\b(je sais (deja )?ou (aller|partir)|j ai (deja )?une destination|"
                            r"destination precise|je connais (deja )?ma destination|lieu precis|"
                            r"je sais ou)\b")
_RE_SURPRISE = re.compile(r"\b(surpren\w+|surprise)\b")
_RE_RETOUR_EXP = re.compile(r"\b(retour d experience|mon avis|feedback|bilan|retour apres|evaluer)\b")
_RE_CHANGER = re.compile(
    r"\b(chang\w+|modifi\w+|corrig\w+|refaire|rectifi\w+|une autre|un autre|autre)\s+(?:\w+\s+){0,2}?"
    r"(date|jour|effectif|nombre|eleves|accompagnateurs|niveau|classe|theme|sujet|depart|"
    r"etablissement|gare)\b")

_CONVERSATION: list[tuple[str, re.Pattern, str]] = [
    ("salut", re.compile(r"^(bonjour|salut|coucou|hello|bonsoir|hey|allo)\b"), "salue"),
    ("merci", re.compile(r"\b(merci|bravo|bien joue|felicitations|chapeau)\b"), "joie"),
    ("aide", re.compile(r"\b(comment (ca|cela) (marche|fonctionne)|aide moi|aidez moi|a quoi (ca )?sert|"
                        r"c est quoi|que fais tu|que faites vous|tu sers a quoi)\b"), "parle"),
    ("identite", re.compile(r"\b(qui es tu|qui etes vous|tu es qui|vous etes qui|ton nom|ton prenom|"
                            r"comment t appelles|comment vous appelez)\b"), "parle"),
    ("ca_va", re.compile(r"\b(ca va|comment vas tu|comment allez vous|la forme)\b"), "joie"),
    ("blague", re.compile(r"\b(blague|drole|rigol\w+|humour|plaisant\w*|raconte|mdr|lol|haha|"
                          r"chouette|hibou|hulule|plume|oiseau)\b"), "joie"),
    ("retard", re.compile(r"\b(retard\w*|greve|panne|supprim\w+|en avance)\b"), "parle"),
    ("insulte", re.compile(r"\b(nul|nulle|idiot\w*|stupide|bete|debile|naze|pourri\w*|inutile)\b"),
     "reflexion"),
    ("hors_sujet", re.compile(r"\b(meteo|pluie|soleil|recette|cuisine|foot\w*|match|politique|president|"
                              r"bitcoin|crypto\w*|film|serie|musique|chanson|jeu video|python|javascript|"
                              r"code|maths?|devoirs?|horoscope|loto|voiture|avion|restaurant|pizza|"
                              r"capitale|blague de|poeme|histoire de france|celebrite)\b"), "reflexion"),
]


# --- Structures internes ---------------------------------------------------------------------

@dataclass
class Sortie:
    replique: str
    humeur: str = "parle"
    ancre: str | None = None
    cartes: list = field(default_factory=list)
    saisie: object = None
    badges: list = field(default_factory=list)
    destination: schemas.Destination | None = None
    proposition: schemas.Proposition | None = None
    detail: schemas.DetailScene | None = None
    faits: dict = field(default_factory=dict)
    dates_proches: list = field(default_factory=list)


@dataclass
class Bilan:
    """Résultat de l'intégration d'informations nouvelles dans la demande."""
    changes: list[str] = field(default_factory=list)
    erreur: str | None = None
    alerte: str | None = None
    special: Sortie | None = None      # ambiguïté ou thème hors catalogue : réponse déjà prête
    prefill: tuple[int | None, int | None] | None = None


@dataclass
class Choix:
    """Trajets présentables pour une destination à la date demandée."""
    genre: str                                    # "jour" | "autre_jour" | "bloque" | "aucun"
    options: list[schemas.Proposition]            # non rouges : d'abord la date demandée, puis les autres
    ref: schemas.Proposition | None               # proposition présentée par défaut
    rouge_jour: schemas.Proposition | None        # meilleur trajet bloqué de la date demandée


@dataclass
class Plan:
    site: sqlite3.Row
    resultat: propositions.Resultat
    dest: schemas.Destination
    choix: Choix


class Tour:
    """Contexte d'un tour de dialogue."""

    def __init__(self, conn: sqlite3.Connection, etat: schemas.EtatScene):
        self.conn = conn
        self.etat = etat
        self.tours0 = etat.tours
        self.aujourdhui = config.aujourdhui()
        self.carnet_ens: str | None = None
        self.sauter_theme = False
        self.mode = llm.mode()
        self.texte_libre = False   # le LLM n'est appelé que pour le texte libre, jamais sur un clic

    def t(self, cle: str, **kw) -> str:
        return T.pick(cle, self.tours0, **kw)


# --- Entrée ----------------------------------------------------------------------------------

def jouer(conn: sqlite3.Connection, req: schemas.RequeteScene) -> schemas.ReponseScene:
    # Un tour = au plus 2 appels LLM (comprendre puis reformuler), bilan discret dans les logs.
    with llm.tour_de_scene():
        return _jouer(conn, req)


def _jouer(conn: sqlite3.Connection, req: schemas.RequeteScene) -> schemas.ReponseScene:
    ev = req.evenement
    if ev.type == "demarrer":
        etat = _etat_neuf(conn, req.etat.tours if req.etat else 0)
        tour = Tour(conn, etat)
        return _finaliser(tour, _vue_accueil(tour, "accueil"))
    if req.etat is None:
        raise HTTPException(409, "Aucune conversation en cours : démarrez avec l'événement « demarrer ».")
    etat = req.etat.model_copy(deep=True)
    _verifier_etat(conn, etat)
    etat.demande = comprendre.completer(conn, etat.demande)
    tour = Tour(conn, etat)
    if ev.type == "texte":
        tour.texte_libre = True
        sortie = _on_texte(tour, ev.texte)
    elif ev.type == "choix":
        sortie = _on_choix(tour, ev.id)
    elif ev.type == "valeur":
        sortie = _on_valeur(tour, ev)
    elif ev.type == "retour":
        sortie = _on_retour(tour)
    elif ev.type == "vote_termine":
        sortie = _on_vote_termine(tour, ev.site_id)
    elif ev.type == "soumettre_vote":
        sortie = _on_soumettre_vote(tour, ev.ids)
    else:
        sortie = _on_prereservation_faite(tour, ev.reference)
    return _finaliser(tour, sortie)


def _etat_neuf(conn: sqlite3.Connection, tours: int) -> schemas.EtatScene:
    return schemas.EtatScene(etape="accueil", tours=tours,
                             demande=comprendre.completer(conn, schemas.Demande()))


def _verifier_etat(conn: sqlite3.Connection, etat: schemas.EtatScene) -> None:
    def refuser(msg: str):
        raise HTTPException(409, "L'état de la conversation est incohérent : " + msg
                            + " Relancez la conversation avec « demarrer ».")

    if etat.rang < 0 or etat.tours < 0:
        refuser("compteur invalide.")
    e = etat.etape
    if e in ("destination", "trajet", "vote", "prereservation"):
        if not etat.candidats:
            refuser("aucune destination proposée à cette étape.")
        if not 0 <= etat.rang < len(etat.candidats):
            refuser("la destination présentée n'est pas dans la liste.")
        for sid in etat.candidats:
            if sites.charger_site(conn, sid) is None:
                refuser(f"le site « {sid} » n'est pas dans le catalogue.")
        d = etat.demande
        if d.gare_depart is None or not d.date or not d.niveau or d.nb_eleves is None \
                or d.nb_accompagnateurs is None:
            refuser("la demande est incomplète pour cette étape.")
    if e in ("trajet", "prereservation") and not etat.site_id:
        refuser("aucune destination retenue.")
    if e == "prereservation" and not etat.proposition_id:
        refuser("aucun trajet retenu.")
    if e == "vote" and not etat.vote_code:
        refuser("aucun vote en cours.")
    if e == "fin" and not etat.dossier_reference:
        refuser("aucun dossier de pré-réservation.")
    if etat.site_id and etat.candidats and etat.site_id not in etat.candidats:
        refuser("la destination retenue n'est pas dans la liste.")


# --- Finalisation de la réponse --------------------------------------------------------------

def _finaliser(tour: Tour, s: Sortie) -> schemas.ReponseScene:
    etat = tour.etat
    replique = T.limiter(s.replique)
    if tour.carnet_ens:
        etat.carnet.append(schemas.Replique(qui="enseignant", texte=tour.carnet_ens))
    if tour.mode == "llm" and tour.texte_libre:
        replique = _reformuler(tour, replique, s.faits)
    etat.carnet.append(schemas.Replique(qui="tchouette", texte=replique))
    etat.carnet = etat.carnet[-MAX_CARNET:]
    etat.tours = tour.tours0 + 1
    cartes = s.cartes[:4]
    if sum(1 for c in cartes if c.style == "primaire") > 1:
        premiere = next(c for c in cartes if c.style == "primaire")
        cartes = [c if (c.style != "primaire" or c is premiere) else c.model_copy(update={"style": "neutre"})
                  for c in cartes]
    return schemas.ReponseScene(
        etat=etat, etape=etat.etape, replique=replique, humeur=s.humeur,
        ancre=s.ancre or ANCRES[etat.etape], cartes=cartes, saisie=s.saisie, badges=s.badges[:4],
        puces=_puces(etat), manquants=_manquants(etat), destination=s.destination,
        proposition=s.proposition, detail=s.detail, mode=tour.mode, **_extras_destination(tour, s),
        alternatives=_alternatives(tour, s), dates_proches=s.dates_proches)


_MOTS_INTERDITS = re.compile(r"\b(r[ée]serv[ée]e?s?|confirm[ée]e?s?)\b", re.IGNORECASE)


def _reformuler(tour: Tour, replique: str, faits: dict) -> str:
    """Reformulation par le LLM, acceptée seulement si elle ne change aucun fait."""
    try:
        r = scene_llm.reformuler(replique, faits, tour.etat)
    except Exception:  # un incident LLM ne doit jamais casser la scène
        return replique
    if not r or not isinstance(r, str):
        return replique
    r = " ".join(r.split())
    if T.compter(r) > T.MAX_MOTS or _MOTS_INTERDITS.search(r):
        return replique
    permis = set(re.findall(r"\d+", replique + " " + " ".join(str(v) for v in faits.values())))
    if not set(re.findall(r"\d+", r)) <= permis:
        return replique
    return r


def _puces(etat: schemas.EtatScene) -> list[schemas.PuceCritere]:
    d = etat.demande
    out = []
    if d.niveau:
        out.append(schemas.PuceCritere(cle="niveau", libelle="Classe", valeur=d.niveau))
    if d.theme:
        out.append(schemas.PuceCritere(cle="theme", libelle="Thème", valeur=d.theme))
    elif d.destination_souhaitee:
        out.append(schemas.PuceCritere(cle="destination", libelle="Lieu", valeur=d.destination_souhaitee))
    if d.nb_eleves is not None and d.nb_accompagnateurs is not None:
        out.append(schemas.PuceCritere(cle="effectif", libelle="Voyageurs",
                                       valeur=str(d.nb_eleves + d.nb_accompagnateurs)))
    if d.date:
        try:
            out.append(schemas.PuceCritere(cle="date", libelle="Date",
                                           valeur=T.date_puce(date.fromisoformat(d.date))))
        except ValueError:
            pass
    if d.gare_depart is not None:
        out.append(schemas.PuceCritere(cle="depart", libelle="Départ", valeur=d.gare_depart.nom))
    if d.heure_retour_max and d.heure_retour_max != config.HEURE_RETOUR_DEFAUT:
        out.append(schemas.PuceCritere(cle="retour", libelle="Retour avant",
                                       valeur=heure_fr(d.heure_retour_max)))
    return out


def _premier_manquant(d: schemas.Demande) -> str | None:
    if not d.niveau:
        return "niveau"
    if d.nb_eleves is None or d.nb_accompagnateurs is None:
        return "effectif"
    if not d.date:
        return "date"
    if d.lieu_depart is None or d.gare_depart is None:
        return "lieu"
    return None


def _manquants(etat: schemas.EtatScene) -> list[str]:
    if etat.etape not in ("accueil", "theme", "criteres"):
        return []
    d = etat.demande
    out = []
    if etat.etape in ("accueil", "theme") and not d.theme and not d.destination_souhaitee:
        out.append(LIBELLES_MANQUANTS["theme"])
    if not d.niveau:
        out.append(LIBELLES_MANQUANTS["niveau"])
    if d.nb_eleves is None or d.nb_accompagnateurs is None:
        out.append(LIBELLES_MANQUANTS["effectif"])
    if not d.date:
        out.append(LIBELLES_MANQUANTS["date"])
    if d.lieu_depart is None or d.gare_depart is None:
        out.append(LIBELLES_MANQUANTS["lieu"])
    return out


# --- Cartes ----------------------------------------------------------------------------------

def _carte(id_: str, titre: str, sous: str | None = None, icone: str | None = None,
           style: str | None = None) -> schemas.CarteScene:
    return schemas.CarteScene(id=id_, titre=titre, sous_titre=sous, icone=icone, style=style)


def _cartes_accueil() -> list[schemas.CarteScene]:
    return [_carte("theme", "J'ai un thème", "Je choisis le sujet de la sortie", "ampoule"),
            _carte("destination", "Je sais où aller", "J'ai déjà un lieu en tête", "pin"),
            _carte("surprise", "Surprenez-moi", "Tchouette choisit pour moi", "etincelles")]


def _slug_theme(canon: str) -> str:
    return "theme:" + normaliser(canon).replace(" ", "-")


def _themes_disponibles(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """Thèmes du vocabulaire qui ont réellement au moins un site au catalogue, les mieux couverts d'abord."""
    compte: dict[str, int] = {}
    for s in sites.tous_les_sites(conn):
        propres = {normaliser(t) for t in sites.liste(s["themes"])}
        for canon in themes_mod.SYNONYMES:
            if normaliser(canon) in propres:
                compte[canon] = compte.get(canon, 0) + 1
    return sorted(compte.items(), key=lambda kv: (-kv[1], kv[0]))


def _cartes_themes(conn: sqlite3.Connection, prioritaires: list[str] | None = None) -> list[schemas.CarteScene]:
    dispo = dict(_themes_disponibles(conn))
    ordre = [c for c in (prioritaires or []) if c in dispo]
    ordre += [c for c, _ in _themes_disponibles(conn) if c not in ordre]
    cartes = []
    for canon in ordre[:4]:
        n = dispo[canon]
        cartes.append(_carte(_slug_theme(canon), canon, f"{n} site{'s' if n > 1 else ''} au catalogue",
                             ICONES_THEME.get(canon, "ampoule")))
    return cartes


def _cartes_sites(conn: sqlite3.Connection) -> list[schemas.CarteScene]:
    """Quelques lieux emblématiques du catalogue fait main (un par commune, noms courts)."""
    vus, cartes = set(), []
    candidats = sorted((s for s in sites.tous_les_sites(conn) if not str(s["id"]).startswith("dt-")
                        and len(s["nom"].split()) <= 4), key=lambda s: (-s["richesse"], s["id"]))
    for s in candidats:
        if s["commune"] in vus:
            continue
        vus.add(s["commune"])
        cartes.append(_carte("site:" + s["id"], s["nom"], s["commune"], "pin"))
        if len(cartes) == 4:
            break
    return cartes


def _cartes_niveaux() -> list[schemas.CarteScene]:
    return [_carte("niveau:" + n, n, sous, "groupe") for n, sous in NIVEAUX_CARTES]


def _cartes_destination(etat: schemas.EtatScene) -> list[schemas.CarteScene]:
    cartes = [_carte("choisir", "Celle-ci !", "On regarde le trajet", "oui", "primaire")]
    if len(etat.candidats) > 1:
        cartes.append(_carte("autre", "Une autre idée", "Je vous en propose une autre", "etincelles", "neutre"))
    cartes.append(_carte("pourquoi", "Pourquoi ?", "Les chiffres derrière ce choix", "loupe", "neutre"))
    if len(etat.candidats) > 1:
        cartes.append(_carte("vote", "Faire voter la classe", "Les élèves choisissent", "qr", "neutre"))
    return cartes


def _cartes_trajet(choix_genre: str, nb_options: int, reservable: bool, p: schemas.Proposition | None) -> list:
    cartes = []
    if reservable:
        sous = "Une demande, SNCF doit la confirmer"
        if p is not None and choix_genre == "autre_jour":
            sous = f"Le {T.date_courte(date.fromisoformat(p.date))} (autre jour)"
        cartes.append(_carte("reserver", "Pré-réserver", sous, "train", "primaire"))
    if nb_options > 1:
        cartes.append(_carte("autre_train", "Un autre train", "Une autre option fiable", "train", "neutre"))
    cartes.append(_carte("pourquoi", "Pourquoi ?", "Le détail du calcul", "loupe", "neutre"))
    cartes.append(_carte("retour", "Retour", "Revenir à la destination", "retour", "neutre"))
    return cartes


def _titre_carte(tour: Tour, id_: str) -> str:
    fixes = {"theme": "J'ai un thème", "destination": "Je sais où aller", "surprise": "Surprenez-moi",
             "choisir": "Celle-ci !", "autre": "Une autre idée", "pourquoi": "Pourquoi ?",
             "vote": "Faire voter la classe", "reserver": "Pré-réserver", "autre_train": "Un autre train",
             "retour": "Retour", "retour_experience": "Mon retour, plus tard", "recommencer": "Nouvelle sortie"}
    if id_ in fixes:
        return fixes[id_]
    if id_.startswith("theme:"):
        return next((c for c in themes_mod.SYNONYMES if _slug_theme(c) == id_), id_.split(":", 1)[1])
    if id_.startswith("site:"):
        site = sites.charger_site(tour.conn, id_.split(":", 1)[1])
        return site["nom"] if site else id_.split(":", 1)[1]
    return id_.split(":", 1)[-1]


def _saisie_date(tour: Tour) -> schemas.SaisieDate:
    return schemas.SaisieDate(min=(tour.aujourdhui + timedelta(days=1)).isoformat(), aide=AIDE_DATE)


# --- Assemblage de répliques -----------------------------------------------------------------

def _assembler(*morceaux: tuple[str | None, bool]) -> str:
    """Joint les morceaux (texte, obligatoire) ; retire les facultatifs, du premier au dernier, si
    la réplique dépasse la limite de mots."""
    gardes = [(t, o) for t, o in morceaux if t]
    while T.compter(" ".join(t for t, _ in gardes)) > T.MAX_MOTS:
        i = next((k for k, (_, o) in enumerate(gardes) if not o), None)
        if i is None:
            break
        gardes.pop(i)
    return " ".join(t.strip() for t, _ in gardes)


# --- Vues (présentation neutre de chaque étape) ----------------------------------------------

def _vue_accueil(tour: Tour, cle: str) -> Sortie:
    tour.etat.etape = "accueil"
    return Sortie(tour.t(cle), "salue", "centre", _cartes_accueil())


def _vue_theme(tour: Tour, prefixe: str | None = None, cartes=None, cle: str | None = None) -> Sortie:
    etat = tour.etat
    mode_lieu = etat.etape == "theme" and etat.rang == 1
    if mode_lieu:
        texte = tour.t(cle or "lieu_question")
        cartes = cartes if cartes is not None else _cartes_sites(tour.conn)
    else:
        texte = tour.t(cle or "theme_question")
        cartes = cartes if cartes is not None else _cartes_themes(tour.conn)
    return Sortie(_assembler((prefixe, False), (texte, True)), "parle", None, cartes)


def _question(tour: Tour, manquant: str, ack: str | None = None, erreur: str | None = None,
              alerte: str | None = None, prefill: tuple | None = None) -> Sortie:
    d = tour.etat.demande
    cartes, saisie = [], None
    if manquant == "niveau":
        q, cartes = tour.t("q_niveau"), _cartes_niveaux()
    elif manquant == "effectif":
        if d.nb_eleves is not None and d.nb_accompagnateurs is None:
            q = tour.t("q_effectif_acc")
        elif d.nb_accompagnateurs is not None and d.nb_eleves is None:
            q = tour.t("q_effectif_eleves")
        else:
            q = tour.t("q_effectif")
        e, a = prefill if prefill else (d.nb_eleves, d.nb_accompagnateurs)
        saisie = schemas.SaisieEffectif(eleves=e, accompagnateurs=a)
    elif manquant == "date":
        q, saisie = tour.t("q_date"), _saisie_date(tour)
    else:
        q, saisie = tour.t("q_lieu"), schemas.SaisieLieu(suggestions=SUGGESTIONS_LIEU)
    if erreur:
        texte = _assembler((erreur, True), (q, False))
        humeur = "inquiete"
    else:
        texte = _assembler((ack, False), (alerte, False), (q, True))
        humeur = "parle"
    return Sortie(texte, humeur, None, cartes, saisie)


# --- Calcul des destinations et des trajets --------------------------------------------------

def _plan(tour: Tour, site_id: str) -> Plan:
    d = tour.etat.demande
    site = sites.charger_site(tour.conn, site_id)
    if site is None:
        raise HTTPException(409, f"Le site « {site_id} » n'est plus dans le catalogue.")
    r = propositions.planifier(tour.conn, propositions.contexte(d), site)
    note = sites.note_llm(site["id"], d.theme, d.niveau)
    dest = propositions.destination(tour.conn, r, note[1] if note else None)
    return Plan(site, r, dest, _meilleurs(r, d.date))


def _meilleurs(r: propositions.Resultat, jour: str) -> Choix:
    """Le meilleur trajet de la DATE DEMANDÉE ; jamais l'alternative d'un autre jour présentée comme telle."""
    def cle(p):
        return (-p.indice.score, p.aller.depart)

    props = r.propositions
    ok_jour = sorted((p for p in props if p.date == jour and p.indice.niveau != "rouge"), key=cle)
    ok_autre = sorted((p for p in props if p.date != jour and p.indice.niveau != "rouge"),
                      key=lambda p: (p.date,) + cle(p))
    rouges = sorted((p for p in props if p.date == jour and p.indice.niveau == "rouge"), key=cle)
    options = ok_jour + ok_autre
    rouge = rouges[0] if rouges else None
    if ok_jour:
        return Choix("jour", options, ok_jour[0], rouge)
    if ok_autre:
        return Choix("autre_jour", options, ok_autre[0], rouge)
    if rouge is not None:
        return Choix("bloque", [], rouge, rouge)
    return Choix("aucun", [], None, None)


def _calculer_destinations(tour: Tour) -> bool:
    etat = tour.etat
    d = etat.demande
    if d.gare_depart is None:
        raise HTTPException(409, "La gare de départ est inconnue : précisez le lieu de départ.")
    rep = recommander.recommander(tour.conn, d)
    etat.candidats = [x.site_id for x in rep.destinations]
    etat.rang = 0
    etat.site_id = None
    etat.proposition_id = None
    return bool(etat.candidats)


def _source_sncf(conn: sqlite3.Connection) -> str:
    return "sncf" if (db.meta_get(conn, "donnees", "demo") or "demo") == "sncf" else "demo"


def _regularite(conn: sqlite3.Connection, p: schemas.Proposition) -> float | None:
    numeros = list(dict.fromkeys(s.train for s in p.aller.segments + p.retour.segments))
    taux = [r["taux_regularite"] for r in confiance.fiabilites(conn, numeros, {}).values()
            if r is not None and r["taux_regularite"] is not None]
    return min(taux) if taux else None


def _badge(icone: str, texte: str, source: str) -> schemas.BadgeSource:
    return schemas.BadgeSource(icone=icone, texte=texte, source=source)


def _badges_destination(tour: Tour, plan: Plan) -> list[schemas.BadgeSource]:
    dest, conn = plan.dest, tour.conn
    src = _source_sncf(conn)
    badges = []
    if dest.temps_trajet_min:
        corr = "direct" if dest.correspondances == 0 else (
            f"{dest.correspondances} correspondance{'s' if dest.correspondances > 1 else ''}")
        badges.append(_badge("train", f"{duree_fr(dest.temps_trajet_min)} de train, {corr}", src))
    a = dest.acces_gare_site
    texte = (f"{a.minutes_groupe} min à pied" if a.mode == "pied"
             else f"Réseau urbain, environ {a.minutes_groupe} min")
    badges.append(_badge("pin", texte, "datatourisme" if dest.site_id.startswith("dt-") else "catalogue"))
    if plan.choix.ref is not None:
        reg = _regularite(conn, plan.choix.ref)
        if reg is not None:
            badges.append(_badge("chart", f"À l'heure {str(round(reg)).replace('.', ',')} %", src))
    if dest.niveau != "rouge":
        badges.append(_badge("shield", f"Indice {dest.indice_confiance}/100", "calcul"))
    doc = rag.fiche(dest.site_id, dest.nom)
    if doc is not None:
        source = "catalogue" if doc.source == "catalogue" else "datatourisme"
        libelle = "Fiche catalogue" if source == "catalogue" else "Fiche DATAtourisme"
        badges.append(_badge("database", f"{libelle} : « {doc.passage[:90].rstrip()}… »", source))
    return badges


def _badges_trajet(tour: Tour, p: schemas.Proposition) -> list[schemas.BadgeSource]:
    conn = tour.conn
    src = _source_sncf(conn)
    badges = []
    reg = _regularite(conn, p)
    if reg is not None:
        badges.append(_badge("chart", f"À l'heure {str(round(reg)).replace('.', ',')} %", src))
    dispo = min(p.jauge_aller.disponibles, p.jauge_retour.disponibles)
    badges.append(_badge("users", f"{dispo} places pour {p.jauge_aller.besoin} voyageurs", src))
    badges.append(_badge("clock", f"{p.marge_avant_visite_min} min de marge avant la visite", "calcul"))
    if p.indice.niveau != "rouge":
        autre_jour = f" ({T.date_puce(date.fromisoformat(p.date))})" if p.date != tour.etat.demande.date else ""
        badges.append(_badge("shield", f"Indice {p.indice.score}/100{autre_jour}", "calcul"))
    return badges


def _niveau_ratio(points: int, maximum: int) -> str:
    r = points / maximum if maximum else 0
    return "vert" if r >= 0.8 else ("orange" if r >= 0.5 else "rouge")


def _detail(tour: Tour, titre: str, p: schemas.Proposition, dest: schemas.Destination) -> schemas.DetailScene:
    """« Pourquoi ? » : critères de l'indice, accès gare → site, source. Rien d'inventé : tout vient du calcul."""
    L = schemas.LigneDetail
    lignes = []
    rouges = [c for c in p.controles if c.niveau == "rouge"]
    if rouges:
        lignes.append(L(libelle="Pourquoi c'est bloqué", valeur=" ".join(c.message for c in rouges),
                        niveau="rouge"))
    lignes.append(L(libelle="Date étudiée", valeur=date_fr(p.date), niveau=None))
    res = trains.resoudre_date(tour.conn, p.date)
    if res.jour_type:
        lignes.append(L(libelle="Horaires", valeur="Date hors de la grille horaire disponible : horaires "
                                                   "indicatifs d'un jour type.", niveau="orange"))
    for c in p.indice.details:
        lignes.append(L(libelle=c.critere, valeur=f"{c.points}/{c.max} · {c.explication}",
                        niveau=_niveau_ratio(c.points, c.max)))
    a = dest.acces_gare_site
    lignes.append(L(libelle="Accès gare → site", valeur=a.message, niveau=a.niveau))
    for c in p.controles:
        if c.niveau != "vert" and c.regle != "R3" and c.niveau != "rouge":
            lignes.append(L(libelle=c.libelle, valeur=c.message, niveau=c.niveau))
    if dest.site_id.startswith("dt-"):
        lignes.append(L(libelle="Fiche du site", valeur="Site « Découverte » (DATAtourisme) : horaires "
                                                        "d'ouverture et accueil à vérifier auprès du site.",
                        niveau="orange"))
    if (db.meta_get(tour.conn, "donnees", "demo") or "demo") == "sncf":
        lignes.append(L(libelle="Source des données", valeur="Fichiers SNCF : régularité, trains et "
                                                             "places.", niveau=None))
    else:
        lignes.append(L(libelle="Source des données", valeur="Données de démonstration : trains, "
                                                             "horaires et places sont simulés.",
                        niveau="orange"))
    return schemas.DetailScene(titre=titre, lignes=lignes)


def _raison_blocage(p: schemas.Proposition) -> str:
    regles = {c.regle for c in p.controles if c.niveau == "rouge"}
    for regle, texte in (("R2", "places insuffisantes"), ("R5", "retour trop tardif"),
                         ("R8", "établissement hors Occitanie"), ("R1", "train fermé aux groupes")):
        if regle in regles:
            return texte
    return "indice trop bas"


def _duree_txt(dest: schemas.Destination) -> str | None:
    return duree_fr(dest.temps_trajet_min) if dest.temps_trajet_min else None


def _vue_destination(tour: Tour, kind: str = "presente", prefixe: str | None = None,
                     detail: bool = False) -> Sortie:
    etat, d = tour.etat, tour.etat.demande
    etat.etape = "destination"
    plan = _plan(tour, etat.candidats[etat.rang])
    dest = plan.dest
    duree = _duree_txt(dest)
    kw = dict(nom=dest.nom, commune=dest.commune, gare=d.gare_depart.nom, duree=duree or "")
    if detail:
        texte = tour.t("dest_pourquoi")
        humeur = "loupe"
    else:
        if kind == "boucle":
            texte = tour.t("dest_autre_boucle", **kw)
        elif kind == "autre" and duree:
            texte = tour.t("dest_autre", **kw)
        elif kind == "mise_a_jour" and duree:
            texte = tour.t("dest_mise_a_jour", **kw)
        elif etat.rang == 0 and d.destination_souhaitee and not _correspond(d.destination_souhaitee, dest):
            texte = tour.t("dest_souhaitee_absente", souhait=d.destination_souhaitee, **kw)
        elif not duree:
            texte = tour.t("dest_presente_sans_duree", **kw)
        elif not d.theme and not d.destination_souhaitee:
            texte = tour.t("dest_surprise", **kw)
        else:
            texte = tour.t("dest_presente", **kw)
        note = None
        if dest.niveau == "rouge":
            note = tour.t("dest_note_rouge")
        elif dest.niveau == "orange":
            note = tour.t("dest_note_orange")
        elif d.theme and sites.adequation(plan.site, d)[0] < 2:
            note = tour.t("dest_note_theme")
        texte = _assembler((prefixe, False), (texte, True), (note, False))
        humeur = "pointe"
    ref = plan.choix.ref
    s = Sortie(texte, humeur, None, _cartes_destination(etat), None, _badges_destination(tour, plan), dest,
               None, _detail(tour, f"Pourquoi {dest.nom} ?", ref, dest) if (detail and ref) else None,
               {"destination": dest.nom, "commune": dest.commune, "gare": d.gare_depart.nom,
                "duree_train": duree or "", "indice": dest.indice_confiance, "niveau": dest.niveau})
    return s


def _correspond(souhait: str, dest: schemas.Destination) -> bool:
    n, cible = normaliser(souhait), normaliser(dest.nom + " " + dest.commune)
    return n in cible or normaliser(dest.nom) in n


def _calculer_et_presenter(tour: Tour, ack: str | None = None, kind: str = "presente") -> Sortie:
    etat = tour.etat
    if not _calculer_destinations(tour):
        etat.demande = comprendre.completer(
            tour.conn, etat.demande.model_copy(update={"date": None}))
        etat.etape = "criteres"
        s = _question(tour, "date")
        s.replique = _assembler((tour.t("dest_aucune"), True))
        s.humeur = "inquiete"
        return s
    etat.vote_code = None
    return _vue_destination(tour, kind=kind, prefixe=ack)


def _decrire(tour: Tour, p: schemas.Proposition, genre: str, raison: str | None, mode: str,
             d: schemas.Demande, indicatif: bool) -> tuple[str, str]:
    """(texte, humeur) pour un trajet présenté."""
    dep, ret = heure_fr(p.aller.depart), heure_fr(p.retour.arrivee)
    dispo = min(p.jauge_aller.disponibles, p.jauge_retour.disponibles)
    kw = dict(dep=dep, ret=ret, dispo=dispo, besoin=p.jauge_aller.besoin)
    suffixe = T.pick("trajet_indicatif", tour.tours0) if indicatif else ""
    if p.indice.niveau == "rouge":
        return tour.t("trajet_sans_alternative", raison=raison or _raison_blocage(p)), "inquiete"
    jour = T.date_courte(date.fromisoformat(p.date))
    if genre == "autre_jour":
        return (_assembler((tour.t("trajet_autre_jour", raison=raison or "aucun train adapté", jour=jour,
                                   dep=dep, ret=ret), True), (suffixe, False)), "inquiete")
    if p.date != d.date:
        texte = f"Autre jour : le {jour}, départ à {dep}, retour à {ret}. {dispo} places pour {p.jauge_aller.besoin}."
        return _assembler((texte, True), (suffixe, False)), "parle"
    if mode == "autre":
        base, humeur = tour.t("trajet_autre", **kw), ("joie" if p.indice.niveau == "vert" else "parle")
    elif p.indice.niveau == "vert":
        base, humeur = tour.t("trajet_vert", **kw), "joie"
    else:
        base, humeur = tour.t("trajet_orange", **kw), "parle"
    return _assembler((base, True), (suffixe, False)), humeur


def _presenter_trajet(tour: Tour, plan: Plan, p: schemas.Proposition | None, mode: str = "choisi",
                      prefixe: str | None = None, humeur: str | None = None,
                      detail: bool = False) -> Sortie:
    """Montre un trajet de la destination retenue ; le stocke en base (pour la pré-réservation)."""
    etat, d = tour.etat, tour.etat.demande
    etat.etape = "trajet"
    etat.site_id = plan.dest.site_id
    choix = plan.choix
    if mode == "choisi" and p is None and choix.genre == "aucun":
        proposees = _vue_dates_proches(tour, plan)
        if proposees is not None:
            return proposees
    if p is None:
        etat.proposition_id = None
        etat.etape = "destination"
        s = _vue_destination(tour)
        s.replique = _assembler((tour.t("trajet_aucun"), True))
        s.humeur = "inquiete"
        return s
    expliquer.expliquer(plan.resultat.propositions, d)
    dossiers.stocker(tour.conn, [p], plan.dest, d.model_copy(update={"date": p.date}))
    etat.proposition_id = p.proposition_id
    genre = choix.genre if p is choix.ref else "jour"
    raison = _raison_blocage(choix.rouge_jour) if (genre == "autre_jour" and choix.rouge_jour) else None
    indicatif = trains.resoudre_date(tour.conn, p.date).jour_type
    texte, hum = _decrire(tour, p, genre, raison, mode, d, indicatif)
    reservable = p.indice.niveau != "rouge"
    nb_options = len(choix.options)
    if detail:
        texte, hum = tour.t("trajet_pourquoi"), "loupe"
    elif prefixe:
        texte = _assembler((prefixe, True), (texte, True))
    return Sortie(
        texte, humeur or hum, None, _cartes_trajet(genre, nb_options, reservable, p),
        None, _badges_trajet(tour, p), plan.dest, p,
        _detail(tour, f"Pourquoi ce train ? ({plan.dest.nom})", p, plan.dest) if detail else None,
        {"destination": plan.dest.nom, "depart": heure_fr(p.aller.depart), "retour": heure_fr(p.retour.arrivee),
         "places": min(p.jauge_aller.disponibles, p.jauge_retour.disponibles),
         "voyageurs": p.jauge_aller.besoin, "niveau": p.indice.niveau})


def _proposition_stockee(tour: Tour) -> tuple[schemas.Proposition, schemas.Destination] | None:
    pid = tour.etat.proposition_id
    if not pid:
        return None
    row = tour.conn.execute("SELECT proposition_json, site_json FROM proposition WHERE id = ?", (pid,)).fetchone()
    if row is None:
        return None
    return (schemas.Proposition.model_validate_json(row["proposition_json"]),
            schemas.Destination.model_validate_json(row["site_json"]))


def _vue_trajet(tour: Tour, detail: bool = False) -> Sortie:
    """Retrouve le trajet déjà présenté (sinon le recalcule)."""
    etat = tour.etat
    stocke = _proposition_stockee(tour)
    plan = _plan(tour, etat.site_id)
    if stocke is None:
        return _presenter_trajet(tour, plan, plan.choix.ref, detail=detail)
    p, dest = stocke
    etat.etape = "trajet"
    reservable = p.indice.niveau != "rouge"
    genre = "jour" if reservable else "bloque"
    texte, hum = _decrire(tour, p, genre, None, "courante", etat.demande,
                          trains.resoudre_date(tour.conn, p.date).jour_type)
    if detail:
        texte, hum = tour.t("trajet_pourquoi"), "loupe"
    return Sortie(texte, hum, None, _cartes_trajet(genre, len(plan.choix.options), reservable, p), None,
                  _badges_trajet(tour, p), dest, p,
                  _detail(tour, f"Pourquoi ce train ? ({dest.nom})", p, dest) if detail else None,
                  {"destination": dest.nom, "depart": heure_fr(p.aller.depart),
                   "retour": heure_fr(p.retour.arrivee), "niveau": p.indice.niveau})


def _vue_vote(tour: Tour) -> Sortie:
    etat = tour.etat
    etat.etape = "vote"
    dest = _plan(tour, etat.candidats[etat.rang]).dest
    return Sortie(tour.t("vote_amorce"), "parle", "droite",
                  [_carte("retour", "Annuler le vote", "Revenir aux destinations", "retour", "neutre")],
                  None, [], dest)


def _vue_prereservation(tour: Tour, prefixe: str | None = None) -> Sortie:
    etat = tour.etat
    etat.etape = "prereservation"
    stocke = _proposition_stockee(tour)
    if stocke is None:
        raise HTTPException(409, "Le trajet retenu est introuvable : revenez au trajet pour le choisir à nouveau.")
    p, dest = stocke
    texte = _assembler((prefixe, False), (tour.t("prereservation"), True))
    return Sortie(texte, "parle", None,
                  [_carte("retour", "Changer de train", "Revenir au trajet", "retour", "neutre")],
                  None, _badges_trajet(tour, p)[:3], dest, p, None,
                  {"destination": dest.nom, "statut": "demande de pré-réservation"})


def _vue_fin(tour: Tour, replique: str | None = None, humeur: str = "joie") -> Sortie:
    tour.etat.etape = "fin"
    return Sortie(replique or tour.t("fin_texte"), humeur, None,
                  [_carte("retour_experience", "Mon retour, plus tard", "Après la sortie", "coeur", "neutre"),
                   _carte("recommencer", "Nouvelle sortie", "Repartir de zéro", "train", "primaire")])


def _vue(tour: Tour) -> Sortie:
    """Présentation neutre de l'étape courante (sert aux réponses de conversation)."""
    etat = tour.etat
    e = etat.etape
    if e == "accueil":
        return _vue_accueil(tour, "accueil_retour")
    if e == "theme":
        return _vue_theme(tour)
    if e == "criteres":
        return _question(tour, _premier_manquant(etat.demande) or "date")
    if e == "destination":
        return _vue_destination(tour)
    if e == "trajet":
        return _vue_trajet(tour)
    if e == "vote":
        return _vue_vote(tour)
    if e == "prereservation":
        return _vue_prereservation(tour)
    return _vue_fin(tour)


def _rappel(tour: Tour) -> str:
    etat = tour.etat
    e = etat.etape
    if e == "theme":
        return tour.t("rappel_lieu" if etat.rang == 1 else "rappel_theme")
    if e == "criteres":
        m = _premier_manquant(etat.demande)
        return tour.t({"niveau": "rappel_niveau", "effectif": "rappel_effectif", "date": "rappel_date",
                       "lieu": "rappel_lieu_depart"}.get(m, "rappel_date"))
    return tour.t("rappel_" + e)


def _repondre_libre(tour: Tour, cle: str, humeur: str) -> Sortie:
    """Plaisanterie, hors-sujet, aide… puis retour à l'étape en cours."""
    v = _vue(tour)
    return replace(v, replique=_assembler((tour.t(cle), True), (_rappel(tour), False)), humeur=humeur,
                   detail=None)


# --- Intégration de nouvelles informations ---------------------------------------------------

def _diff(avant: schemas.Demande, apres: schemas.Demande) -> list[str]:
    ch = []
    if avant.niveau != apres.niveau:
        ch.append("niveau")
    if avant.theme != apres.theme:
        ch.append("theme")
    if (avant.nb_eleves, avant.nb_accompagnateurs) != (apres.nb_eleves, apres.nb_accompagnateurs):
        ch.append("effectif")
    if avant.date != apres.date:
        ch.append("date")
    if (avant.gare_depart.code_uic if avant.gare_depart else None) != \
            (apres.gare_depart.code_uic if apres.gare_depart else None) or \
            (avant.lieu_depart.libelle if avant.lieu_depart else None) != \
            (apres.lieu_depart.libelle if apres.lieu_depart else None):
        ch.append("lieu")
    if avant.destination_souhaitee != apres.destination_souhaitee:
        ch.append("destination")
    if (avant.heure_depart_min, avant.heure_retour_max, avant.duree) != \
            (apres.heure_depart_min, apres.heure_retour_max, apres.duree):
        ch.append("horaires")
    return ch


def _theme_special(tour: Tour, texte: str, ambigus: list[str] | None, cle_hors: str = "theme_hors_catalogue") -> Sortie:
    """Thème ambigu ou hors catalogue : jamais accepté en silence ni ramené à un autre thème."""
    etat = tour.etat
    etat.etape = "theme"
    etat.rang = 0
    court = " ".join(texte.split())[:40]
    if ambigus:
        a, b = ambigus[0], ambigus[1]
        phrase = tour.t("theme_ambigu", texte=court, a=a, b=b)
        cartes = _cartes_themes(tour.conn, ambigus)
    else:
        phrase = tour.t(cle_hors, texte=court)
        cartes = _cartes_themes(tour.conn)
    return Sortie(phrase, "reflexion", None, cartes)


def _integrer(tour: Tour, ex: dict, texte: str | None = None) -> Bilan:
    """Applique les informations extraites à la demande, avec leurs garde-fous (thème, effectif, date, gare)."""
    etat, conn = tour.etat, tour.conn
    avant = etat.demande
    bilan = Bilan()
    ex = {k: v for k, v in ex.items() if v is not None}

    # Thème : uniquement un thème qui existe au catalogue, jamais un autre à la place
    if "theme" in ex:
        brut = str(ex.pop("theme"))
        ambigus = themes_mod.themes_ambigus(texte or brut)
        dispo = {c for c, _ in _themes_disponibles(conn)}
        canon = themes_mod.canonique(brut)
        if ambigus:
            bilan.special = _theme_special(tour, brut if not texte or len(texte.split()) > 6 else texte, ambigus)
        elif canon is None or canon not in dispo:
            bilan.special = _theme_special(tour, brut, None)
        else:
            ex["theme"] = canon

    # Effectif : 6 à 50 voyageurs, adultes compris
    if "nb_eleves" in ex or "nb_accompagnateurs" in ex:
        e = ex.get("nb_eleves", avant.nb_eleves)
        a = ex.get("nb_accompagnateurs", avant.nb_accompagnateurs)
        total = (e or 0) + (a or 0)
        if e is not None and e > config.MAX_VOYAGEURS or (e is not None and a is not None
                                                          and total > config.MAX_VOYAGEURS):
            bilan.erreur = tour.t("effectif_trop", n=total if a is not None and e is not None else e)
        elif e is not None and a is not None and total < config.MIN_VOYAGEURS:
            bilan.erreur = tour.t("effectif_peu", n=total)
        elif e is not None and e < 1:
            bilan.erreur = tour.t("effectif_invalide")
        if bilan.erreur:
            bilan.prefill = (e, a)
            ex.pop("nb_eleves", None)
            ex.pop("nb_accompagnateurs", None)

    # Date : à partir de demain, 21 jours avant de préférence
    if "date" in ex:
        try:
            jour = date.fromisoformat(str(ex["date"]))
        except ValueError:
            jour = None
        if jour is None:
            bilan.erreur = bilan.erreur or tour.t("date_illisible")
            ex.pop("date")
        elif jour < tour.aujourdhui:
            bilan.erreur = bilan.erreur or tour.t("date_passee", date=date_fr(jour))
            ex.pop("date")
        elif jour == tour.aujourdhui:
            bilan.erreur = bilan.erreur or tour.t("date_trop_proche")
            ex.pop("date")
        elif (jour - tour.aujourdhui).days < config.DELAI_MIN_JOURS:
            bilan.alerte = tour.t("date_court")

    apres = comprendre.completer(conn, comprendre.fusionner(avant, ex))

    # Lieu de départ : une gare liO doit être trouvée, sans jamais afficher d'identifiant technique
    if "lieu_depart" in ex and apres.gare_depart is None:
        brut = ex["lieu_depart"]
        libelle = brut["libelle"] if isinstance(brut, dict) else str(brut)
        bilan.erreur = bilan.erreur or tour.t("lieu_introuvable", lieu=libelle[:50])
        apres = comprendre.completer(conn, apres.model_copy(
            update={"lieu_depart": avant.lieu_depart, "gare_depart": avant.gare_depart}))

    etat.demande = apres
    bilan.changes = _diff(avant, apres)
    return bilan


def _ack(tour: Tour, changes: list[str]) -> str | None:
    d = tour.etat.demande
    principaux = [c for c in changes if c in ("niveau", "theme", "effectif", "date", "lieu", "destination")]
    if len(principaux) >= 2:
        return tour.t("ack_plusieurs")
    if not principaux:
        if "horaires" in changes and d.heure_retour_max:
            return f"Retour avant {heure_fr(d.heure_retour_max)}, noté."
        return None
    c = principaux[0]
    if c == "niveau":
        return tour.t("ack_niveau", niveau=d.niveau)
    if c == "theme":
        return tour.t("theme_ok", theme=d.theme)
    if c == "effectif":
        return tour.t("ack_effectif", total=(d.nb_eleves or 0) + (d.nb_accompagnateurs or 0))
    if c == "date":
        return tour.t("ack_date", date=date_fr(d.date))
    if c == "lieu" and d.gare_depart:
        return tour.t("ack_lieu", gare=d.gare_depart.nom)
    if c == "destination":
        return tour.t("lieu_ok", lieu=d.destination_souhaitee)
    return None


def _router(tour: Tour, bilan: Bilan | None = None, ack: str | None = None,
            kind: str = "presente") -> Sortie:
    """Prochaine étape selon ce que l'on sait : thème, un critère à la fois, ou la destination."""
    etat, d = tour.etat, tour.etat.demande
    if bilan and bilan.special is not None:
        return bilan.special
    erreur = bilan.erreur if bilan else None
    alerte = bilan.alerte if bilan else None
    if etat.etape in ("accueil", "theme") and not d.theme and not d.destination_souhaitee \
            and not tour.sauter_theme:
        etat.etape = "theme"
        etat.rang = 0
        return _vue_theme(tour, prefixe=erreur or ack)
    manquant = _premier_manquant(d)
    if manquant:
        etat.etape = "criteres"
        etat.rang = 0
        etat.candidats, etat.site_id, etat.proposition_id, etat.vote_code = [], None, None, None
        return _question(tour, manquant, ack, erreur, alerte, bilan.prefill if bilan else None)
    if erreur:  # demande complète, mais la correction proposée est refusée : on reste où l'on est
        if etat.etape in ("accueil", "theme", "criteres"):
            return _calculer_et_presenter(tour, erreur, kind)
        s = _vue(tour)
        return replace(s, replique=_assembler((erreur, True), (_rappel(tour), False)), humeur="inquiete",
                       detail=None)
    return _calculer_et_presenter(tour, _assembler((ack, False), (alerte, False)) or None, kind)


# --- Événements ------------------------------------------------------------------------------

def _on_choix(tour: Tour, id_: str) -> Sortie:
    etat, e = tour.etat, tour.etat.etape
    tour.carnet_ens = _titre_carte(tour, id_)
    nouveau = _on_choix_trajet_modifiable(tour, id_)
    if nouveau is not None:
        return nouveau

    def inconnu():
        raise HTTPException(409, f"La carte « {id_} » n'existe pas à l'étape « {e} ».")

    if e == "accueil":
        if id_ == "theme":
            etat.etape, etat.rang = "theme", 0
            return _vue_theme(tour)
        if id_ == "destination":
            etat.etape, etat.rang = "theme", 1
            return _vue_theme(tour)
        if id_ == "surprise":
            tour.sauter_theme = True
            return _router(tour, None, tour.t("theme_surprise"))
        inconnu()
    if e == "theme":
        if etat.rang == 0 and id_.startswith("theme:"):
            canon = next((c for c, _ in _themes_disponibles(tour.conn) if _slug_theme(c) == id_), None)
            if canon is None:
                raise HTTPException(409, f"Le thème « {id_.split(':', 1)[1]} » n'existe pas au catalogue.")
            bilan = _integrer(tour, {"theme": canon})
            return _router(tour, bilan, _ack(tour, bilan.changes))
        if etat.rang == 1 and id_.startswith("site:"):
            site = sites.charger_site(tour.conn, id_.split(":", 1)[1])
            if site is None:
                raise HTTPException(409, "Ce lieu n'existe pas au catalogue.")
            bilan = _integrer(tour, {"destination_souhaitee": site["nom"]})
            return _router(tour, bilan, _ack(tour, bilan.changes))
        inconnu()
    if e == "criteres":
        if id_.startswith("niveau:") and _premier_manquant(etat.demande) == "niveau":
            niveau = id_.split(":", 1)[1]
            if niveau not in {n for n, _ in NIVEAUX_CARTES}:
                inconnu()
            bilan = _integrer(tour, {"niveau": niveau})
            return _router(tour, bilan, _ack(tour, bilan.changes))
        inconnu()
    if e == "destination":
        if id_ == "choisir":
            etat.site_id = etat.candidats[etat.rang]
            plan = _plan(tour, etat.site_id)
            return _presenter_trajet(tour, plan, plan.choix.ref)
        if id_ == "autre":
            return _autre_destination(tour)
        if id_ == "pourquoi":
            return _vue_destination(tour, detail=True)
        if id_ == "vote":
            return _creer_vote(tour)
        inconnu()
    if e == "trajet":
        if id_ == "reserver":
            return _reserver(tour, strict=True)
        if id_ == "autre_train":
            return _autre_train(tour)
        if id_ == "pourquoi":
            return _vue_trajet(tour, detail=True)
        if id_ == "retour":
            return _on_retour(tour)
        inconnu()
    if e in ("vote", "prereservation"):
        if id_ == "retour":
            return _on_retour(tour)
        inconnu()
    if e == "fin":
        if id_ == "recommencer":
            return _recommencer(tour)
        if id_ == "retour_experience":
            return _vue_fin(tour, tour.t("fin_retour_exp"))
        inconnu()
    inconnu()


def _recommencer(tour: Tour) -> Sortie:
    tour.etat = _etat_neuf(tour.conn, tour.tours0)
    return _vue_accueil(tour, "recommencer")


def _autre_destination(tour: Tour) -> Sortie:
    etat = tour.etat
    n = len(etat.candidats)
    if n <= 1:
        s = _vue_destination(tour)
        return replace(s, replique=_assembler((tour.t("dest_aucune_autre"), True)), humeur="reflexion")
    boucle = etat.rang == n - 1
    etat.rang = 0 if boucle else etat.rang + 1
    return _vue_destination(tour, kind="boucle" if boucle else "autre")


def _autre_train(tour: Tour) -> Sortie:
    etat = tour.etat
    stocke = _proposition_stockee(tour)
    plan = _plan(tour, etat.site_id)
    options = plan.choix.options
    if len(options) < 2 or stocke is None:
        s = _vue_trajet(tour)
        return replace(s, replique=_assembler((tour.t("trajet_aucun_autre"), True)), humeur="parle")
    actuel = stocke[0]
    cle_actuelle = (actuel.date, tuple(x.train for x in actuel.aller.segments),
                    tuple(x.train for x in actuel.retour.segments))
    cles = [(p.date, tuple(x.train for x in p.aller.segments), tuple(x.train for x in p.retour.segments))
            for p in options]
    i = cles.index(cle_actuelle) if cle_actuelle in cles else -1
    suivant = options[(i + 1) % len(options)]
    return _presenter_trajet(tour, plan, suivant, mode="autre")


def _reserver(tour: Tour, strict: bool) -> Sortie:
    etat = tour.etat
    stocke = _proposition_stockee(tour)
    if stocke is None:
        raise HTTPException(409, "Aucun trajet n'est présenté : demandez d'abord un trajet.")
    p, _ = stocke
    if p.indice.niveau == "rouge":
        if strict:
            raise HTTPException(409, "Ce trajet n'est pas assez fiable pour être pré-réservé : "
                                     + _raison_blocage(p) + ". Choisissez un autre trajet.")
        return replace(_vue_trajet(tour), replique=tour.t("trajet_reserver_bloque"), humeur="inquiete")
    if p.date < tour.aujourdhui.isoformat():
        raise HTTPException(409, f"Le {date_fr(p.date)} est déjà passé : relancez la recherche avec une date à venir.")
    prefixe = None
    if p.date != etat.demande.date:
        etat.demande = etat.demande.model_copy(update={"date": p.date})
        prefixe = tour.t("prereservation_date", jour=T.date_courte(date.fromisoformat(p.date))).strip()
    return _vue_prereservation(tour, prefixe)


def _creer_vote(tour: Tour) -> Sortie:
    etat = tour.etat
    if len(etat.candidats) < 2:
        s = _vue_destination(tour)
        return replace(s, replique=tour.t("vote_un_seul"), humeur="reflexion")
    destinations = [_plan(tour, sid).dest for sid in etat.candidats]
    sondage = sondages.creer(tour.conn, schemas.RequeteSondage(demande=etat.demande, destinations=destinations))
    etat.vote_code = sondage.code
    etat.etape = "vote"
    return Sortie(tour.t("vote_amorce"), "parle", "droite",
                  [_carte("retour", "Annuler le vote", "Revenir aux destinations", "retour", "neutre")],
                  None, [], destinations[etat.rang], None, None,
                  {"vote": sondage.code, "options": len(sondage.options)})


def _on_vote_termine(tour: Tour, site_id: str) -> Sortie:
    etat = tour.etat
    if etat.etape != "vote":
        raise HTTPException(409, "Aucun vote n'est en cours : l'événement « vote_termine » est impossible à "
                                 f"l'étape « {etat.etape} ».")
    if site_id not in etat.candidats:
        raise HTTPException(409, "Cette destination ne faisait pas partie du vote.")
    sondages.fermer(tour.conn, etat.vote_code)  # sans effet si le front l'a déjà fait
    tour.carnet_ens = "Résultat du vote de la classe"
    etat.rang = etat.candidats.index(site_id)
    etat.site_id = site_id
    plan = _plan(tour, site_id)
    p = plan.choix.ref
    s = _presenter_trajet(tour, plan, p, mode="vote")
    if p is None:
        return s
    nom = plan.dest.nom
    if p.indice.niveau == "rouge":
        s.replique = tour.t("vote_termine_bloque", nom=nom, raison=_raison_blocage(p))
        s.humeur = "inquiete"
    elif plan.choix.genre == "autre_jour":
        raison = _raison_blocage(plan.choix.rouge_jour) if plan.choix.rouge_jour else "aucun train adapté"
        s.replique = tour.t("vote_termine_autre_jour", nom=nom, raison=raison,
                            jour=T.date_courte(date.fromisoformat(p.date)))
        s.humeur = "celebre"
    else:
        suite = f"Départ à {heure_fr(p.aller.depart)}, retour à {heure_fr(p.retour.arrivee)}."
        s.replique = tour.t("vote_termine", nom=nom, suite=suite)
        s.humeur = "celebre"
    return s


def _on_prereservation_faite(tour: Tour, reference: str) -> Sortie:
    etat = tour.etat
    if etat.etape != "prereservation":
        raise HTTPException(409, "Aucune pré-réservation n'est attendue : l'événement « prereservation_faite » "
                                 f"est impossible à l'étape « {etat.etape} ».")
    try:
        dossier = dossiers.lire(tour.conn, reference)
    except HTTPException:
        raise HTTPException(409, f"Je ne trouve aucun dossier de pré-réservation « {reference} ».")
    if dossier.proposition.proposition_id != etat.proposition_id:
        raise HTTPException(409, "Ce dossier ne correspond pas au trajet retenu dans la conversation.")
    tour.carnet_ens = "Demande de pré-réservation envoyée"
    etat.dossier_reference = dossier.reference
    if dossier.statut == "PRE_RESERVATION":
        texte = tour.t("fin", ref=dossier.reference)
    else:
        texte = tour.t("fin_autre_statut", ref=dossier.reference,
                       statut=STATUTS_LISIBLES.get(dossier.statut, dossier.statut.lower()))
    s = _vue_fin(tour, texte, "joie")
    s.faits = {"dossier": dossier.reference, "statut": dossier.statut}
    return s


def _on_valeur(tour: Tour, ev: schemas.EvValeur) -> Sortie:
    etat = tour.etat
    if etat.etape != "criteres":
        raise HTTPException(409, f"La saisie « {ev.champ} » n'est pas attendue à l'étape « {etat.etape} ».")
    v = ev.valeur
    ex: dict = {}
    if ev.champ == "effectif":
        def entier(*cles):
            for c in cles:
                if c in v:
                    try:
                        n = int(v[c])
                    except (TypeError, ValueError):
                        raise HTTPException(422, "L'effectif doit être donné en nombres entiers "
                                                 "(« eleves » et « accompagnateurs »).")
                    return n
            return None
        e, a = entier("eleves", "nb_eleves"), entier("accompagnateurs", "nb_accompagnateurs")
        if e is None and a is None:
            raise HTTPException(422, "Il manque le nombre d'élèves ou d'accompagnateurs (« eleves », « accompagnateurs »).")
        if e is not None:
            ex["nb_eleves"] = e
        if a is not None:
            ex["nb_accompagnateurs"] = a
        tour.carnet_ens = " et ".join(x for x in (f"{e} élèves" if e is not None else "",
                                                  f"{a} accompagnateurs" if a is not None else "") if x)
    elif ev.champ == "date":
        brut = str(v.get("date", v.get("valeur", ""))).strip()
        try:
            date.fromisoformat(brut)
        except ValueError:
            raise HTTPException(422, "La date doit être au format AAAA-MM-JJ (par exemple 2026-11-12).")
        ex["date"] = brut
        tour.carnet_ens = date_fr(brut)
    else:
        libelle = " ".join(str(v.get("libelle", v.get("lieu", v.get("valeur", "")))).split())
        if len(libelle) < 2:
            raise HTTPException(422, "Indiquez le nom de l'établissement ou de la commune de départ.")
        ex["lieu_depart"] = {"libelle": libelle[:120], "commune": None}
        tour.carnet_ens = libelle[:120]
    bilan = _integrer(tour, ex)
    return _router(tour, bilan, _ack(tour, bilan.changes))


def _effacer(conn: sqlite3.Connection, d: schemas.Demande, champ: str) -> schemas.Demande:
    maj = {"niveau": {"niveau": None}, "effectif": {"nb_eleves": None, "nb_accompagnateurs": None},
           "date": {"date": None}, "lieu": {"lieu_depart": None, "gare_depart": None},
           "theme": {"theme": None}, "destination": {"destination_souhaitee": None}}[champ]
    return comprendre.completer(conn, d.model_copy(update=maj))


def _on_retour(tour: Tour) -> Sortie:
    etat, e = tour.etat, tour.etat.etape
    tour.carnet_ens = "Retour"
    if e == "accueil":
        return _vue_accueil(tour, "accueil_retour")
    if e == "theme":
        etat.rang = 0
        return _vue_accueil(tour, "accueil_retour")
    if e == "criteres":
        d = etat.demande
        remplis = {"niveau": bool(d.niveau), "effectif": d.nb_eleves is not None or d.nb_accompagnateurs is not None,
                   "date": bool(d.date), "lieu": d.lieu_depart is not None}
        for champ in reversed(CRITERES_ORDRE):
            if remplis[champ]:
                etat.demande = _effacer(tour.conn, d, champ)
                return _question(tour, champ)
        if d.destination_souhaitee:
            etat.demande = _effacer(tour.conn, d, "destination")
            etat.etape, etat.rang = "theme", 1
            return _vue_theme(tour)
        if d.theme:
            etat.demande = _effacer(tour.conn, d, "theme")
            etat.etape, etat.rang = "theme", 0
            return _vue_theme(tour)
        return _vue_accueil(tour, "accueil_retour")
    if e == "destination":
        etat.demande = _effacer(tour.conn, etat.demande, "lieu")
        etat.etape = "criteres"
        etat.candidats, etat.rang, etat.site_id, etat.proposition_id, etat.vote_code = [], 0, None, None, None
        return _question(tour, "lieu")
    if e == "trajet":
        etat.site_id, etat.proposition_id = None, None
        return _vue_destination(tour)
    if e == "vote":
        try:
            sondages.fermer(tour.conn, etat.vote_code)
        except HTTPException:
            pass
        etat.vote_code = None
        s = _vue_destination(tour)
        return replace(s, replique=_assembler((tour.t("vote_annule"), True)), humeur="parle")
    if e == "prereservation":
        etat.etape = "trajet"
        return _vue_trajet(tour)
    raise HTTPException(409, "La demande est transmise : on ne peut plus revenir en arrière. "
                             "Choisissez « Nouvelle sortie » pour recommencer.")


# --- Texte libre -----------------------------------------------------------------------------

def _catalogue(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return [(s["nom"], s["commune"]) for s in sites.tous_les_sites(conn)]


def _champ_attendu(tour: Tour) -> str | None:
    etat = tour.etat
    if etat.etape == "theme":
        return "destination_souhaitee" if etat.rang == 1 else "theme"
    if etat.etape == "criteres":
        m = _premier_manquant(etat.demande)
        if m == "niveau":
            return "niveau"
        if m == "effectif":
            return "nb_accompagnateurs" if etat.demande.nb_eleves is not None else "nb_eleves"
        if m == "lieu":
            return "lieu_depart"
    return None


def _intention_carte(tour: Tour, norm: str) -> str | None:
    """Carte que le texte libre désigne, si elle existe à l'étape courante."""
    e = tour.etat.etape
    mots = norm.split()
    court = len(mots) <= 10
    if e == "accueil":
        if _RE_PORTE_LIEU.search(norm):
            return "destination"
        if _RE_SURPRISE.search(norm) or comprendre.INCERTAIN.search(norm):
            return "surprise"
        if court and _RE_PORTE_THEME.search(norm):
            return "theme"
    elif e == "destination":
        if _RE_POURQUOI.search(norm):
            return "pourquoi"
        if _RE_VOTE.search(norm):
            return "vote"
        if _RE_NEG.match(norm) or (court and _RE_AUTRE_DEST.search(norm)):
            return "autre"
        if _RE_AFFIRM.match(norm) or (court and _RE_CHOISIR.search(norm)):
            return "choisir"
    elif e == "trajet":
        if _RE_POURQUOI.search(norm):
            return "pourquoi"
        if court and _RE_AUTRE_DEST.search(norm) and "train" not in norm:
            return "retour"
        if court and (_RE_AUTRE_TRAIN.search(norm) or _RE_NEG.match(norm)):
            return "autre_train"
        if _RE_AFFIRM.match(norm) or (court and _RE_RESERVER.search(norm)):
            return "reserver"
        if _RE_VOTE.search(norm):
            return "vote"
    elif e == "fin":
        if _RE_RETOUR_EXP.search(norm):
            return "retour_experience"
    return None


def _on_texte(tour: Tour, texte: str) -> Sortie:
    etat, e = tour.etat, tour.etat.etape
    texte = " ".join(texte.split())
    tour.carnet_ens = texte[:300] or None
    norm = normaliser(texte)
    if not norm:
        return _repondre_libre(tour, "pas_compris", "reflexion")
    court = len(norm.split()) <= 4

    # 1. Commandes globales (messages courts) : reconnues par les règles, sans appel LLM
    if court and _RE_RETOUR.match(norm):
        return _on_retour_texte(tour)
    if _RE_RECOMMENCER.search(norm) and len(norm.split()) <= 6:
        return _recommencer(tour)

    # Le LLM (mode « llm » seulement) ne fait que comprendre : il n'invente rien
    indice_llm: dict = {}
    if tour.mode == "llm":
        try:
            indice_llm = scene_llm.comprendre_texte(texte, etat) or {}
        except Exception:
            indice_llm = {}
    if indice_llm.get("intention") == "retour" and e in ("theme", "criteres", "destination"):
        return _on_retour_texte(tour)

    # 2. Carte désignée par le LLM
    choix = indice_llm.get("choix")
    if isinstance(choix, str) and _carte_valide(tour, choix):
        return _on_choix(tour, choix)

    # 3. Informations nouvelles (aux étapes où le projet est modifiable)
    modifiable = e in ("accueil", "theme", "criteres", "destination", "trajet")
    if modifiable:
        ex = comprendre.extraire(texte, tour.aujourdhui, None, _catalogue(tour.conn),
                                 comprendre.commune_de_depart(etat.demande))
        if isinstance(indice_llm.get("extrait"), dict):
            ex.update({k: v for k, v in indice_llm["extrait"].items() if v is not None})
        if e == "theme" and etat.rang == 1:
            ex.pop("theme", None)  # on attend un lieu, pas un thème
        if ex:
            avant = etat.demande
            bilan = _integrer(tour, ex, texte)
            if bilan.special is not None or bilan.erreur or bilan.changes:
                kind = "mise_a_jour" if e in ("destination", "trajet") else "presente"
                if e in ("destination", "trajet") and bilan.changes:
                    etat.vote_code = None
                return _router(tour, bilan, _ack(tour, bilan.changes), kind)
            etat.demande = avant
        demande_changer = _RE_CHANGER.search(norm)
        if demande_changer and e in ("criteres", "destination", "trajet"):
            s = _on_changer(tour, demande_changer.group(2))
            if s is not None:
                return s

    # 4. Cartes désignées par le texte (« une autre idée », « pourquoi ce train ? »…)
    carte = _intention_carte(tour, norm)
    if carte:
        return _appliquer_carte_texte(tour, carte)

    # 5. Conversation : bonjour, merci, humour, hors-sujet…
    if e in ("accueil", "theme", "criteres") and _RE_POURQUOI.search(norm):
        return _repondre_libre(tour, "pourquoi_info", "parle")
    intention = indice_llm.get("intention")
    for cle, motif, humeur in _CONVERSATION:
        if (intention == cle or motif.search(norm)) and not (cle == "salut" and len(norm.split()) > 4):
            if cle == "hors_sujet" and e in ("theme", "criteres") and _lieu_plausible(tour, norm):
                break
            return _repondre_libre(tour, cle, humeur)

    # 6. Réponse courte à la question posée (niveau seul, effectif seul, lieu, thème…)
    if modifiable:
        s = _reponse_courte(tour, texte, norm)
        if s is not None:
            return s

    # 7. Incompréhension
    if e == "destination":
        return replace(_vue(tour), replique=tour.t("incomprise_destination"), humeur="reflexion", detail=None)
    if e == "trajet":
        return replace(_vue(tour), replique=tour.t("incomprise_trajet"), humeur="reflexion", detail=None)
    if e == "vote":
        return _repondre_libre(tour, "vote_en_cours", "reflexion")
    if e == "prereservation":
        return _repondre_libre(tour, "modif_bloquee", "reflexion")
    if e == "fin":
        return _vue_fin(tour, tour.t("fin_texte"), "joie")
    return replace(_vue(tour), replique=_assembler((tour.t("pas_compris"), False), (_rappel(tour), True)),
                   humeur="reflexion", detail=None)


def _lieu_plausible(tour: Tour, norm: str) -> bool:
    return tour.etat.etape == "criteres" and _premier_manquant(tour.etat.demande) == "lieu" \
        and bool(comprendre.geo.commune_dans_texte(norm))


def _carte_valide(tour: Tour, id_: str) -> bool:
    e = tour.etat.etape
    valides = {"accueil": {"theme", "destination", "surprise"},
               "destination": {"choisir", "autre", "pourquoi", "vote"},
               "trajet": {"reserver", "autre_train", "pourquoi", "retour"},
               "vote": {"retour"}, "prereservation": {"retour"},
               "fin": {"retour_experience", "recommencer"}}.get(e, set())
    return id_ in valides


def _appliquer_carte_texte(tour: Tour, carte: str) -> Sortie:
    """Une carte désignée en texte libre : même effet que le clic, sans 409 si elle n'est pas offerte."""
    e = tour.etat.etape
    if carte == "surprise" and e == "accueil":
        tour.sauter_theme = True
        return _router(tour, None, tour.t("theme_surprise"))
    if carte == "vote" and e == "trajet":
        return replace(_vue_trajet(tour), replique="Le vote se lance depuis les destinations : revenez-y avec « Retour ».",
                       humeur="parle", detail=None)
    if carte == "reserver":
        return _reserver(tour, strict=False)
    if _carte_valide(tour, carte):
        return _on_choix(tour, carte)
    return _repondre_libre(tour, "indisponible", "reflexion")


def _on_retour_texte(tour: Tour) -> Sortie:
    if tour.etat.etape == "fin":
        return _repondre_libre(tour, "indisponible", "reflexion")
    return _on_retour(tour)


def _on_changer(tour: Tour, mot: str) -> Sortie | None:
    """« Changer la date » : on efface le critère et on le redemande."""
    champ = {"date": "date", "jour": "date", "effectif": "effectif", "nombre": "effectif",
             "eleves": "effectif", "accompagnateurs": "effectif", "niveau": "niveau", "classe": "niveau",
             "theme": "theme", "sujet": "theme", "depart": "lieu",
             "etablissement": "lieu", "gare": "lieu"}.get(mot)
    if champ is None:
        return None
    etat = tour.etat
    if champ == "theme":
        etat.demande = _effacer(tour.conn, etat.demande, "theme")
        etat.demande = _effacer(tour.conn, etat.demande, "destination")
        etat.etape, etat.rang = "theme", 0
        etat.candidats, etat.site_id, etat.proposition_id, etat.vote_code = [], None, None, None
        return _vue_theme(tour)
    etat.demande = _effacer(tour.conn, etat.demande, champ)
    etat.etape = "criteres"
    etat.candidats, etat.rang, etat.site_id, etat.proposition_id, etat.vote_code = [], 0, None, None, None
    return _question(tour, champ)


def _reponse_courte(tour: Tour, texte: str, norm: str) -> Sortie | None:
    """Réponse brève à la question posée : niveau, effectif, lieu, thème ou lieu à visiter."""
    etat = tour.etat
    attendu = _champ_attendu(tour)
    if attendu is None:
        return None
    if etat.etape == "theme":
        if comprendre.INCERTAIN.search(norm):
            tour.sauter_theme = True
            return _router(tour, None, tour.t("theme_surprise"))
        if etat.rang == 1:
            ex = comprendre.extraire(texte, tour.aujourdhui, "destination_souhaitee", _catalogue(tour.conn),
                                     comprendre.commune_de_depart(etat.demande))
            if ex.get("destination_souhaitee"):
                bilan = _integrer(tour, {"destination_souhaitee": ex["destination_souhaitee"]})
                return _router(tour, bilan, _ack(tour, bilan.changes))
            return Sortie(tour.t("lieu_hors_catalogue", texte=" ".join(texte.split())[:40]), "reflexion",
                          None, _cartes_sites(tour.conn))
        if len(norm.split()) <= 6:
            return _theme_special(tour, texte, themes_mod.themes_ambigus(texte) or None)
        return None
    ex = comprendre.extraire(texte, tour.aujourdhui, attendu, _catalogue(tour.conn),
                             comprendre.commune_de_depart(etat.demande))
    if attendu == "lieu_depart" and ("lieu_depart" not in ex or _question_ou_phrase(texte, norm)):
        return None
    if attendu != "lieu_depart":
        ex = {k: v for k, v in ex.items() if k in ("niveau", "nb_eleves", "nb_accompagnateurs")}
    if not ex:
        return None
    bilan = _integrer(tour, ex, texte)
    if not (bilan.changes or bilan.erreur or bilan.special):
        return None
    return _router(tour, bilan, _ack(tour, bilan.changes))


_RE_INTERROGATIF = re.compile(r"^(pourquoi|comment|quand|combien|que|qu|quoi|est ce|c est|peux|pouvez|veux|"
                              r"voulez|je|tu|vous|on|il|elle|nous|ca|cela|ce|quel|quelle|qui|ou est)\b")


def _question_ou_phrase(texte: str, norm: str) -> bool:
    """Vrai si le texte ressemble à une question ou à une phrase, pas à un nom de lieu."""
    if "?" in texte or _RE_INTERROGATIF.match(norm):
        return not comprendre.geo.commune_dans_texte(norm) or "?" in texte
    return len(norm.split()) > 8


# --- Sélection multiple de destinations, vote sur les candidates et carte -------------------
# (bloc ajouté : multi-sélection + vote ; le reste de la machine à états est inchangé)

def _on_soumettre_vote(tour: Tour, ids: list[str]) -> Sortie:
    """1 destination cochée : choix direct. 2 à 4 : sondage de classe limité à ces candidates."""
    etat = tour.etat
    if etat.etape != "destination":
        raise HTTPException(409, "On ne peut soumettre des destinations au vote qu'à l'étape « destination » "
                                 f"(étape actuelle : « {etat.etape} »).")
    uniques = list(dict.fromkeys(ids))
    if not 1 <= len(uniques) <= 4:
        raise HTTPException(409, "Choisissez entre 1 et 4 destinations.")
    hors = [i for i in uniques if i not in etat.candidats]
    if hors:
        raise HTTPException(409, "Cette destination ne fait pas partie des candidates proposées.")
    noms = []
    for sid in uniques:
        site = sites.charger_site(tour.conn, sid)
        noms.append(site["nom"] if site else sid)
    tour.carnet_ens = "Destinations soumises : " + ", ".join(noms)
    if len(uniques) == 1:
        etat.rang = etat.candidats.index(uniques[0])
        etat.site_id = uniques[0]
        plan = _plan(tour, etat.site_id)
        return _presenter_trajet(tour, plan, plan.choix.ref)
    destinations = [_plan(tour, sid).dest for sid in uniques]
    sondage = sondages.creer(tour.conn, schemas.RequeteSondage(demande=etat.demande, destinations=destinations))
    etat.vote_code = sondage.code
    etat.rang = etat.candidats.index(uniques[0])
    etat.etape = "vote"
    return Sortie(f"Voici le vote : {len(uniques)} destinations en lice. Les élèves scannent, ou vous saisissez "
                  "les votes à la main.", "parle", "droite",
                  [_carte("retour", "Annuler le vote", "Revenir aux destinations", "retour", "neutre")],
                  None, [], destinations[0], None, None,
                  {"vote": sondage.code, "options": len(sondage.options)})


def _zoom_pour(points: list[tuple[float, float]]) -> int:
    import math
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    etendue = max(max(lats) - min(lats), (max(lons) - min(lons)) * math.cos(math.radians(sum(lats) / len(lats))), 0.01)
    return max(4, min(13, int(math.log2(360 / (etendue * 1.5)))))


def _carte_destinations(tour: Tour, actif: str | None, dests: list[schemas.Destination]) -> schemas.CarteGeo | None:
    """Carte : gare de départ, candidates numérotées, destination active, gare d'arrivée, marche gare -> site."""
    d = tour.etat.demande
    pts: list[schemas.PointCarte] = []
    traces: list[list[list[float]]] = []
    if d.gare_depart is not None and d.gare_depart.lat and d.gare_depart.lon:
        pts.append(schemas.PointCarte(lat=d.gare_depart.lat, lon=d.gare_depart.lon,
                                      libelle=f"Départ : {d.gare_depart.nom}", type="depart"))
    for i, dest in enumerate(dests):
        site = sites.charger_site(tour.conn, dest.site_id)
        if site is None or not site["lat"] or not site["lon"]:
            continue
        est_actif = dest.site_id == actif
        marche = dest.acces_gare_site
        lib = dest.nom
        if est_actif:
            lib += f" · {marche.minutes_groupe} min {'à pied' if marche.mode == 'pied' else 'en transport urbain'}"
        pts.append(schemas.PointCarte(lat=site["lat"], lon=site["lon"], libelle=lib,
                                      type="destination" if est_actif else "candidate",
                                      numero=i + 1, actif=est_actif))
        if est_actif and dest.gare.lat and dest.gare.lon:
            pts.append(schemas.PointCarte(lat=dest.gare.lat, lon=dest.gare.lon,
                                          libelle=f"Arrivée : {dest.gare.nom}", type="arrivee"))
            traces.append([[dest.gare.lat, dest.gare.lon], [site["lat"], site["lon"]]])
    if len(pts) < 2:
        return None
    coords = [(p.lat, p.lon) for p in pts]
    centre = [sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords)]
    return schemas.CarteGeo(centre=centre, zoom=_zoom_pour(coords), points=pts, traces=traces)


def _extras_destination(tour: Tour, s: Sortie) -> dict:
    """Champs optionnels de la réponse : candidates à cocher (étape destination) et carte (destination, vote)."""
    etat = tour.etat
    if etat.etape not in ("destination", "vote") or not etat.candidats:
        return {}
    try:
        dests = [_plan(tour, sid).dest for sid in etat.candidats]
        actif = s.destination.site_id if s.destination else None
        carte = _carte_destinations(tour, actif, dests)
    except HTTPException:
        return {}
    return {"choix_destinations": dests if etat.etape == "destination" else [], "carte": carte}


# --- Trajet modifiable, dates proches (ajout) -------------------------------------------------

JOURS_CAP = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _libelle_date(iso: str, ecart: int) -> str:
    d = date.fromisoformat(iso)
    return f"{JOURS_CAP[d.weekday()]} {T.date_puce(d)} ({ecart:+d} j)".replace("-", "−")


def _dates_proches(tour: Tour, plan: Plan) -> list[schemas.DateProche]:
    return dates_mod.chercher(tour.conn, tour.etat.demande, plan.site, tour.etat.demande.date, tour.aujourdhui)


def _vue_dates_proches(tour: Tour, plan: Plan) -> Sortie | None:
    """Aucun trajet fiable à la date demandée : Tchouette propose les dates faisables les plus proches."""
    etat = tour.etat
    props = _dates_proches(tour, plan)
    if not props:
        return None
    etat.etape = "trajet"
    etat.site_id = plan.dest.site_id
    etat.proposition_id = None
    jour = date_fr(etat.demande.date, False).rsplit(" ", 1)[0]
    cartes = [_carte(f"choisir_date:{x.date}", _libelle_date(x.date, x.ecart_jours),
                     f"Départ {heure_fr(x.aller.depart)}, retour {heure_fr(x.retour.arrivee)}", "calendrier",
                     "primaire" if i == 0 else "neutre") for i, x in enumerate(props)]
    cartes.append(_carte("retour_etape", "Étape précédente", "Revenir à la destination", "retour", "neutre"))
    return Sortie(f"Pas de train fiable le {jour}, voici les dates les plus proches.", "inquiete", None,
                  cartes[:4], None, [], plan.dest, None, None,
                  {"destination": plan.dest.nom}, props)


def _alternatives(tour: Tour, s: Sortie) -> schemas.AlternativesTrajet | None:
    etat = tour.etat
    if etat.etape != "trajet" or s.proposition is None or not etat.site_id:
        return None
    site = sites.charger_site(tour.conn, etat.site_id)
    if site is None:
        return None
    return trajet_options.vers_schema(trajet_options.calculer(tour.conn, etat.demande, site, s.proposition))


def _on_choix_trajet_modifiable(tour: Tour, id_: str) -> Sortie | None:
    """Actions nouvelles de l'étape trajet : changer_aller:<id>, changer_retour:<id>, retour_etape,
    choisir_date:<AAAA-MM-JJ>. Renvoie None pour toute autre carte."""
    etat = tour.etat
    sens = "aller" if id_.startswith("changer_aller:") else "retour" if id_.startswith("changer_retour:") else None
    if id_ != "retour_etape" and sens is None and not id_.startswith("choisir_date:"):
        return None
    if etat.etape != "trajet":
        raise HTTPException(409, f"La carte « {id_} » n'existe pas à l'étape « {etat.etape} ».")
    if id_ == "retour_etape":
        tour.carnet_ens = "Revenir à l'étape précédente"
        return _on_retour(tour)
    if id_.startswith("choisir_date:"):
        iso = id_.split(":", 1)[1]
        plan = _plan(tour, etat.site_id)
        choisie = next((x for x in _dates_proches(tour, plan) if x.date == iso), None)
        if choisie is None:
            raise HTTPException(409, "Cette date ne fait pas partie des dates proposées : "
                                     "choisissez l'une des cartes affichées.")
        tour.carnet_ens = _libelle_date(iso, choisie.ecart_jours)
        etat.demande = etat.demande.model_copy(update={"date": iso})
        plan = _plan(tour, etat.site_id)
        s = _presenter_trajet(tour, plan, plan.choix.ref)
        return replace(s, replique=_assembler(
            (f"Je relance avec le {T.date_courte(date.fromisoformat(iso))}.", False), (s.replique, True)))
    stocke = _proposition_stockee(tour)
    site = sites.charger_site(tour.conn, etat.site_id) if etat.site_id else None
    if stocke is None or site is None:
        raise HTTPException(409, "Aucun trajet n'est présenté : choisissez d'abord une destination.")
    ident = id_.split(":", 1)[1]
    nouvelle = trajet_options.appliquer(tour.conn, etat.demande, site, stocke[0], sens, ident)
    if nouvelle is None:
        raise HTTPException(409, f"Cet horaire {'d' + chr(39) + 'aller' if sens == 'aller' else 'de retour'} n'est pas faisable pour votre groupe : "
                                 "choisissez l'un des horaires proposés.")
    dossiers.stocker(tour.conn, [nouvelle], stocke[1], etat.demande.model_copy(update={"date": nouvelle.date}))
    etat.proposition_id = nouvelle.proposition_id
    tour.carnet_ens = "Autre horaire d'aller" if sens == "aller" else "Autre horaire de retour"
    s = _vue_trajet(tour)
    quoi = (f"aller à {heure_fr(nouvelle.aller.depart)}" if sens == "aller"
            else f"retour à {heure_fr(nouvelle.retour.depart)}")
    return replace(s, replique=_assembler((f"C'est noté : {quoi}.", False), (s.replique, True)))
