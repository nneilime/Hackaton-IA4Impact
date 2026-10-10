"""Crochet LLM de la scène : deux fonctions isolées, que le moteur appelle seulement en mode « llm ».

Modèle : Claude Sonnet 5.5 (`llm.MODELE_SCENE`), effort bas, délai court, sorties structurées.
En mode démo (pas de clé), en cas d'erreur réseau, de délai dépassé, de refus ou de doute, elles
renvoient None et le moteur (scene.py) garde ses règles et ses textes scriptés pour ce tour.

Contrat :

- `comprendre_texte(texte, etat)` -> dict | None. Clés facultatives :
    "choix"     : id d'une carte valable à l'étape courante (ex. "autre", "pourquoi", "reserver") ;
    "extrait"   : champs de la demande, mêmes clés que `comprendre.extraire` (niveau, theme, nb_eleves,
                  nb_accompagnateurs, date, duree, heure_depart_min, heure_retour_max,
                  lieu_depart={"libelle", "commune"}, destination_souhaitee) ;
    "intention" : une clé de conversation du moteur (`scene._CONVERSATION` : salut, merci, aide,
                  identite, ca_va, blague, retard, insulte, hors_sujet) ou "retour".
  Le LLM ne fait que comprendre : tout champ dont la valeur n'apparaît pas dans le texte (nombre,
  heure, lieu) est écarté ici, avant même les garde-fous du moteur.
- `reformuler(replique, faits, etat)` -> str | None. Reformule la réplique scriptée avec le ton de
  Tchouette, sans aucun chiffre, nom propre ni fait absent de la réplique et des `faits`. Le moteur
  refuse en plus toute reformulation de plus de 25 mots ou disant « réservé » / « confirmé ».

Frugalité : au plus 2 appels par tour (comprendre puis reformuler), uniquement pour le texte libre
(le moteur n'appelle pas ces crochets sur un clic de carte).
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel

from .. import config, llm, schemas
from .comprendre import _chiffrer
from .texte import normaliser

# --- Intentions : liste FERMÉE, alignée sur les cartes et les clés de conversation du moteur ------

Intention = Literal[
    "donne_infos",          # l'enseignant donne ou corrige des informations de la demande
    "porte_theme",          # accueil : « j'ai un thème »            -> carte theme
    "porte_destination",    # accueil : « je sais où aller »         -> carte destination
    "surprise",             # accueil : « surprenez-moi »            -> carte surprise
    "choisir_destination",  # destination : « celle-ci »             -> carte choisir
    "autre_idee",           # destination : « une autre idée »       -> carte autre (au trajet : retour)
    "pourquoi",             # destination / trajet : « pourquoi ? »  -> carte pourquoi
    "faire_voter",          # destination : « faire voter la classe » -> carte vote
    "pre_reserver",         # trajet : « on le prend »               -> carte reserver
    "autre_train",          # trajet : « un autre horaire »          -> carte autre_train
    "retour",               # revenir à l'étape précédente
    "retour_experience",    # fin : donner son avis                  -> carte retour_experience
    "recommencer",          # fin : nouvelle sortie                  -> carte recommencer
    "salut", "merci", "aide", "identite", "ca_va",
    "plaisanterie",         # -> clé « blague » du moteur
    "retard", "insulte", "hors_sujet",
    "inconnu",
]

# (intention, étape) -> id de carte du moteur (`scene._carte_valide`)
_CARTES: dict[tuple[str, str], str] = {
    ("porte_theme", "accueil"): "theme",
    ("porte_destination", "accueil"): "destination",
    ("surprise", "accueil"): "surprise",
    ("choisir_destination", "destination"): "choisir",
    ("autre_idee", "destination"): "autre",
    ("pourquoi", "destination"): "pourquoi",
    ("faire_voter", "destination"): "vote",
    ("pre_reserver", "trajet"): "reserver",
    ("autre_train", "trajet"): "autre_train",
    ("pourquoi", "trajet"): "pourquoi",
    ("retour", "trajet"): "retour",
    ("autre_idee", "trajet"): "retour",      # une autre destination : on revient aux destinations
    ("retour", "vote"): "retour",
    ("retour", "prereservation"): "retour",
    ("retour_experience", "fin"): "retour_experience",
    ("recommencer", "fin"): "recommencer",
}
_CONVERSATION = {"salut": "salut", "merci": "merci", "aide": "aide", "identite": "identite",
                 "ca_va": "ca_va", "plaisanterie": "blague", "retard": "retard", "insulte": "insulte",
                 "hors_sujet": "hors_sujet"}
_ETAPES_RETOUR_TEXTE = {"theme", "criteres", "destination"}

NIVEAUX = ("CP", "CE1", "CE2", "CM1", "CM2", "6e", "5e", "4e", "3e", "2de", "1re", "Tle")


class ComprehensionScene(BaseModel):
    """Sortie structurée de `comprendre_texte` (tous les champs présents, null si absent)."""
    intention: Intention
    niveau: Optional[Literal["CP", "CE1", "CE2", "CM1", "CM2", "6e", "5e", "4e", "3e", "2de", "1re", "Tle"]]
    theme: Optional[str]
    nb_eleves: Optional[int]
    nb_accompagnateurs: Optional[int]
    date: Optional[str]
    duree: Optional[Literal["journee", "demi-journee"]]
    heure_depart_min: Optional[str]
    heure_retour_max: Optional[str]
    lieu_depart: Optional[str]
    commune_depart: Optional[str]
    destination_souhaitee: Optional[str]


class Reformulation(BaseModel):
    """Sortie structurée de `reformuler` : null si le modèle préfère garder le script."""
    texte: Optional[str]


SYSTEME_COMPRENDRE = """Tu es l'oreille de Tchouette, la chouette-locomotive qui aide les enseignants \
d'Occitanie à organiser une sortie scolaire en train liO. Ton rôle est strict : COMPRENDRE le dernier \
message de l'enseignant (écrit ou dicté), jamais décider ni répondre. Un moteur à règles fait le reste.

Tu reçois la date du jour, l'étape de la conversation, ce qui est déjà connu de la demande et la \
dernière réplique de Tchouette. Tu renvoies :

1. intention : UNE valeur de la liste fermée.
- donne_infos : l'enseignant donne ou corrige une information de sa sortie (classe, thème, effectif, \
date, durée, horaires, lieu de départ, lieu à visiter), y compris une réponse courte à la question posée.
- porte_theme : il veut partir d'un thème pédagogique (étape accueil).
- porte_destination : il sait déjà où aller (étape accueil).
- surprise : il n'a pas d'idée et veut une suggestion (étape accueil).
- choisir_destination : il retient la destination présentée.
- autre_idee : il veut voir une autre destination.
- pourquoi : il demande une justification (pourquoi ce lieu, ce train, est-ce fiable).
- faire_voter : il veut faire voter ou choisir sa classe.
- pre_reserver : il retient le trajet présenté et veut envoyer la demande de pré-réservation.
- autre_train : il veut un autre horaire ou un autre trajet.
- retour : il veut revenir à l'étape précédente ou annuler la dernière action.
- retour_experience : il veut donner son avis après la sortie.
- recommencer : il veut préparer une nouvelle sortie depuis le début.
- salut, merci, aide (comment ça marche), identite (qui es-tu), ca_va, plaisanterie (il plaisante, \
taquine ou fait de l'humour), retard (retards, grèves, pannes), insulte, hors_sujet (sans rapport avec \
la sortie).
- inconnu : tu n'es pas sûr.

2. Les champs de la demande, seulement s'ils sont dits dans CE message ; null pour tout le reste.
- niveau : CP, CE1, CE2, CM1, CM2, 6e, 5e, 4e, 3e, 2de, 1re ou Tle.
- theme : le thème pédagogique en quelques mots (ex. « Moyen Âge », « Préhistoire »).
- nb_eleves, nb_accompagnateurs : entiers ; enseignants et parents sont des accompagnateurs. Une \
réponse nue (« 4 ») vaut pour la question que Tchouette vient de poser.
- date : AAAA-MM-JJ ; sans année, la prochaine occurrence après la date du jour.
- duree : journee ou demi-journee.
- heure_depart_min, heure_retour_max : HH:MM, seulement si une heure est dite (« retour avant 19h » \
donne 19:00 ; « le matin » ne donne aucune heure).
- lieu_depart : l'établissement tel qu'écrit (ex. « Collège de Foix ») ; commune_depart : sa commune \
si elle est écrite.
- destination_souhaitee : seulement si l'enseignant nomme lui-même un lieu à visiter, tel qu'écrit.

Règles : n'invente jamais un lieu, une heure, un nombre ni une place. Pas de valeur par défaut. Une \
plaisanterie ou un hors-sujet ne contient aucun champ. Si tu n'es pas sûr, laisse les champs à null \
et choisis inconnu."""


SYSTEME_REFORMULER = """Tu es Tchouette, la chouette-locomotive qui accompagne les enseignants \
d'Occitanie dans l'organisation d'une sortie scolaire en train liO. Tu reçois une réplique écrite \
d'avance, les faits qu'elle s'appuie dessus et le dernier message de l'enseignant. Tu la rends plus \
vivante et chaleureuse, sans en changer le sens.

Règles strictes :
- 25 mots au plus, vouvoiement, pas d'emoji, pas de liste.
- Garde la question ou l'invitation finale de la réplique.
- N'ajoute AUCUN chiffre, horaire, date, nombre, nom de lieu, nom propre ni fait absent de la \
réplique et des faits. Ne change aucun chiffre.
- N'écris jamais « réservé » ni « confirmé » : on parle de proposition ou de demande de \
pré-réservation.
- Si l'enseignant plaisante, ajoute une pointe d'humour ferroviaire légère ; sinon reste simple.
- En cas de doute, renvoie texte = null : la réplique d'origine sera gardée."""


# --- Comprendre --------------------------------------------------------------------------------

def comprendre_texte(texte: str, etat: schemas.EtatScene) -> dict | None:
    if llm.mode() != "llm" or not texte or not texte.strip():
        return None
    derniere = next((r.texte for r in reversed(etat.carnet) if r.qui == "tchouette"), None)
    connu = {k: v for k, v in etat.demande.model_dump(
        include={"niveau", "theme", "nb_eleves", "nb_accompagnateurs", "date", "duree",
                 "heure_depart_min", "heure_retour_max", "destination_souhaitee"}).items() if v is not None}
    if etat.demande.lieu_depart is not None:
        connu["lieu_depart"] = etat.demande.lieu_depart.libelle
    contenu = (
        f"Date du jour : {config.aujourdhui().isoformat()}\n"
        f"Étape : {etat.etape}\n"
        f"Demande déjà connue : {json.dumps(connu, ensure_ascii=False, sort_keys=True)}\n"
        f"Dernière réplique de Tchouette : {derniere or '(aucune)'}\n"
        f"Message de l'enseignant : {texte.strip()[:600]}"
    )
    r = llm.appel_scene("comprendre", SYSTEME_COMPRENDRE, contenu, ComprehensionScene, max_tokens=2000)
    if r is None:
        return None
    return traduire(r, texte, etat)


def traduire(r: ComprehensionScene, texte: str, etat: schemas.EtatScene) -> dict:
    """Sortie du modèle -> indice pour le moteur, en écartant tout ce qui n'est pas dans le texte."""
    out: dict = {}
    e = etat.etape
    carte = _CARTES.get((r.intention, e))
    if carte:
        out["choix"] = carte
    elif r.intention in _CONVERSATION:
        out["intention"] = _CONVERSATION[r.intention]
        return out  # une plaisanterie ou un hors-sujet ne modifie jamais la demande
    elif r.intention == "retour" and e in _ETAPES_RETOUR_TEXTE:
        out["intention"] = "retour"
    extrait = _extrait_verifie(r, texte)
    if extrait:
        out["extrait"] = extrait
    return out


def _extrait_verifie(r: ComprehensionScene, texte: str) -> dict:
    norm = normaliser(texte)
    chiffre = _chiffrer(norm)
    nombres = {int(n) for n in re.findall(r"\d+", chiffre)}
    ex: dict = {}
    if r.niveau in NIVEAUX:
        ex["niveau"] = r.niveau
    if r.theme and 2 <= len(r.theme.strip()) <= 60:
        ex["theme"] = r.theme.strip()
    for cle in ("nb_eleves", "nb_accompagnateurs"):
        v = getattr(r, cle)
        # un nombre doit figurer dans le message (sauf 1 à 3 : « ma collègue et moi »)
        if isinstance(v, int) and 0 < v <= 200 and (v in nombres or v <= 3):
            ex[cle] = v
    if r.date:
        try:
            ex["date"] = date.fromisoformat(r.date).isoformat()
        except ValueError:
            pass
    if r.duree:
        ex["duree"] = r.duree
    for cle in ("heure_depart_min", "heure_retour_max"):
        v = getattr(r, cle)
        m = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", v or "")
        if m and int(m.group(1)) in nombres:  # l'heure doit être dite, jamais déduite de « le matin »
            ex[cle] = f"{int(m.group(1)):02d}:{m.group(2)}"
    if r.lieu_depart and _dans_texte(r.lieu_depart, norm):
        commune = r.commune_depart if r.commune_depart and _dans_texte(r.commune_depart, norm) else None
        ex["lieu_depart"] = {"libelle": r.lieu_depart.strip(), "commune": commune}
    if r.destination_souhaitee and _dans_texte(r.destination_souhaitee, norm):
        ex["destination_souhaitee"] = r.destination_souhaitee.strip()
    return ex


_MOTS_VIDES = {"de", "du", "des", "la", "le", "les", "l", "d", "a", "au", "aux", "en", "et", "sur"}


def _dans_texte(valeur: str, norm_texte: str) -> bool:
    """Chaque mot significatif de `valeur` figure dans le texte (aucun lieu inventé)."""
    mots = [m for m in normaliser(valeur).split() if m not in _MOTS_VIDES]
    texte = set(norm_texte.split())
    return bool(mots) and all(m in texte for m in mots)


# --- Reformuler --------------------------------------------------------------------------------

_INTERDITS = re.compile(r"r[ée]serv[ée]e?s?\b|confirm", re.IGNORECASE)
_NOMS_COMMUNS_TCHOUETTE = {"tchouette", "lio", "sncf", "occitanie", "vous", "votre", "vos", "je", "nous"}


def reformuler(replique: str, faits: dict, etat: schemas.EtatScene) -> str | None:
    if llm.mode() != "llm" or not replique:
        return None
    dernier_ens = next((r.texte for r in reversed(etat.carnet) if r.qui == "enseignant"), None)
    contenu = (
        f"Étape : {etat.etape}\n"
        f"Réplique écrite d'avance : {replique}\n"
        f"Faits : {json.dumps(faits, ensure_ascii=False, sort_keys=True, default=str)}\n"
        f"Dernier message de l'enseignant : {dernier_ens or '(aucun)'}"
    )
    r = llm.appel_scene("reformuler", SYSTEME_REFORMULER, contenu, Reformulation, max_tokens=1000)
    if r is None or not r.texte:
        return None
    texte = " ".join(r.texte.split())
    return texte if reformulation_valide(texte, replique, faits) else None


def reformulation_valide(texte: str, replique: str, faits: dict) -> bool:
    """Garde-fou local, plus strict que celui du moteur : ni chiffre, ni nom propre, ni mot interdit."""
    if not texte or len(texte.split()) > 25 or _INTERDITS.search(texte):
        return False
    source = replique + " " + " ".join(str(v) for v in faits.values())
    source_norm = normaliser(source)
    permis = set(re.findall(r"\d+", _chiffrer(source_norm)))
    if not set(re.findall(r"\d+", _chiffrer(normaliser(texte)))) <= permis:
        return False  # nombre ajouté, en chiffres ou en lettres
    mots_source = set(source_norm.split())
    for m in re.finditer(r"[A-ZÀ-Ý][\w'’-]*", texte):
        avant = texte[:m.start()].rstrip()
        if not avant or avant[-1] in ".!?…:«\"":
            continue  # majuscule de début de phrase
        mot = normaliser(m.group(0))
        if mot and not all(p in mots_source or p in _NOMS_COMMUNS_TCHOUETTE for p in mot.split()):
            return False  # nom propre absent de la réplique et des faits
    return True
