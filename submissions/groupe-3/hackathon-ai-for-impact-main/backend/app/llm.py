"""Les 3 appels au LLM (Claude) : comprendre, recommander, expliquer. Rien d'autre.

Le LLM ne calcule jamais d'horaire, de place disponible ni de score : il extrait la demande,
classe et justifie des sites DU CATALOGUE, et reformule une explication à partir de chiffres
fournis. Toute réponse est validée ; en cas d'erreur réseau, de refus ou de sortie invalide, le
code retombe sur le mode démo (règles déterministes).

Fournisseur choisi par l'environnement : GROQ_API_KEY (API compatible OpenAI, prioritaire), sinon
ANTHROPIC_API_KEY, sinon mode « demo ». Aucune clé n'est jamais écrite dans un fichier.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal, Optional, TypeVar

from pydantic import BaseModel

log = logging.getLogger("lio.llm")

MODELE = os.environ.get("LIO_LLM_MODEL", "claude-opus-5-5")
# Scène Tchouette : modèle rapide et économique, délai court (au-delà, repli démo pour ce tour).
MODELE_SCENE = os.environ.get("LIO_LLM_MODEL_SCENE", "claude-sonnet-5-5")
DELAI_SCENE_S = float(os.environ.get("LIO_LLM_DELAI_SCENE", "8"))
MAX_APPELS_PAR_TOUR = 2
T = TypeVar("T", bound=BaseModel)

_client = None


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELE_GROQ_DEFAUT = "llama-3.3-70b-versatile"
DELAI_GROQ_S = 6.0
_transport_groq = None  # injectable (tests) : httpx.BaseTransport


def fournisseur() -> str:
    """« groq », « anthropic » ou « demo » selon les clés présentes dans l'environnement."""
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "demo"


def mode() -> str:
    return "llm" if fournisseur() != "demo" else "demo"


def _appel_groq(systeme: str, contenu: str, format_sortie: type[T], max_tokens: int,
                delai: float = DELAI_GROQ_S) -> T | None:
    """Un seul essai, JSON validé par Pydantic. None sur toute erreur (journal sans contenu brut)."""
    try:
        import httpx

        schema = json.dumps(format_sortie.model_json_schema(), ensure_ascii=False)
        corps = {
            "model": os.environ.get("LLM_MODEL") or MODELE_GROQ_DEFAUT,
            "messages": [
                {"role": "system", "content": f"{systeme}\n\nRéponds uniquement par un objet JSON "
                                              f"valide conforme à ce schéma JSON :\n{schema}"},
                {"role": "user", "content": contenu},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=delai, transport=_transport_groq) as c:
            r = c.post(GROQ_URL, json=corps,
                       headers={"Authorization": f"Bearer {os.environ.get('GROQ_API_KEY', '')}"})
        r.raise_for_status()
        choix = r.json()["choices"][0]
        if choix.get("finish_reason") == "length":
            log.warning("Groq : réponse tronquée, repli démo.")
            return None
        return format_sortie.model_validate_json(choix["message"]["content"])
    except Exception as e:  # réseau, délai, HTTP, JSON ou schéma invalides
        log.warning("Groq indisponible ou réponse inutilisable (%s), repli démo.", type(e).__name__)
        return None


def _get_client():
    global _client
    if _client is None:
        import anthropic

        # Délais courts : l'interface attend, et on a toujours un repli déterministe.
        _client = anthropic.Anthropic(timeout=25.0, max_retries=1)
    return _client


def _appeler(systeme: str, contenu: str, format_sortie: type[T], max_tokens: int = 4000) -> T | None:
    """Un appel structuré (sortie JSON validée par Pydantic). None en cas d'échec ou de refus."""
    if mode() != "llm" or _tour_scene.get() is not None:
        # Pendant un tour de scène, seuls les 2 appels rapides de la scène sont permis.
        return None
    if fournisseur() == "groq":
        return _appel_groq(systeme, contenu, format_sortie, max_tokens, delai=DELAI_GROQ_S)
    try:
        import anthropic
    except ImportError:
        return None
    try:
        reponse = _get_client().beta.messages.parse(
            model=MODELE,
            max_tokens=max_tokens,
            system=systeme,
            messages=[{"role": "user", "content": contenu}],
            output_format=format_sortie,
            output_config={"effort": "low"},
            # Repli côté serveur sur le modèle recommandé si une requête est déclinée.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIConnectionError as e:  # inclut les dépassements de délai
        log.warning("LLM injoignable, repli démo : %s", e)
        return None
    except anthropic.RateLimitError as e:
        log.warning("LLM limité en débit, repli démo : %s", e)
        return None
    except anthropic.APIStatusError as e:
        log.warning("Erreur de l'API LLM (%s), repli démo : %s", e.status_code, e.message)
        return None
    except Exception as e:  # sortie non conforme au schéma, etc.
        log.warning("Réponse LLM inutilisable, repli démo : %s", e)
        return None
    if reponse.stop_reason == "refusal":
        log.warning("Requête déclinée par le LLM, repli démo.")
        return None
    return reponse.parsed_output


# --- Scène : appels rapides et comptés -----------------------------------------------------------

_tour_scene: ContextVar[dict | None] = ContextVar("tour_scene", default=None)


@contextmanager
def tour_de_scene():
    """Encadre un tour de la scène : au plus MAX_APPELS_PAR_TOUR appels, bilan discret dans les logs.

    Pendant le tour, les appels « classiques » (recommander, expliquer, extraire_demande) sont coupés :
    la scène reste sur ses règles déterministes et ne paie que comprendre + reformuler.
    """
    bilan = {"appels": 0, "ms": 0, "entree": 0, "sortie": 0, "cache_lu": 0, "cache_ecrit": 0}
    jeton = _tour_scene.set(bilan)
    try:
        yield bilan
    finally:
        _tour_scene.reset(jeton)
        if bilan["appels"]:
            log.info("Scène : %d appel(s) LLM, %d ms, jetons entrée %d (cache lu %d, écrit %d), sortie %d",
                     bilan["appels"], bilan["ms"], bilan["entree"], bilan["cache_lu"],
                     bilan["cache_ecrit"], bilan["sortie"])


def appel_scene(etiquette: str, systeme: str, contenu: str, format_sortie: type[T],
                max_tokens: int = 2000) -> T | None:
    """Appel structuré rapide pour la scène (Sonnet, effort bas, délai court, aucun nouvel essai).

    None en mode démo, au-delà du quota du tour, sur erreur réseau, délai dépassé, refus ou sortie
    inutilisable : le moteur garde alors son comportement scripté pour ce tour.
    """
    if mode() != "llm":
        return None
    bilan = _tour_scene.get()
    if bilan is not None and bilan["appels"] >= MAX_APPELS_PAR_TOUR:
        log.info("Scène : quota de %d appels atteint, « %s » ignoré.", MAX_APPELS_PAR_TOUR, etiquette)
        return None
    debut = time.monotonic()
    if fournisseur() == "groq":
        if bilan is not None:
            bilan["appels"] += 1
        try:
            return _appel_groq(systeme, contenu, format_sortie, max_tokens)
        finally:
            if bilan is not None:
                bilan["ms"] += int((time.monotonic() - debut) * 1000)
    try:
        import anthropic
    except ImportError:
        return None
    if bilan is not None:
        bilan["appels"] += 1
    try:
        reponse = _get_client().with_options(timeout=DELAI_SCENE_S, max_retries=0).beta.messages.parse(
            model=MODELE_SCENE,
            max_tokens=max_tokens,
            # Prompt système figé (aucune donnée variable) : préfixe stable, mis en cache.
            system=[{"type": "text", "text": systeme, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": contenu}],
            output_format=format_sortie,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APITimeoutError:
        log.warning("Scène/%s : délai de %.0f s dépassé, repli démo.", etiquette, DELAI_SCENE_S)
        return None
    except anthropic.APIConnectionError as e:
        log.warning("Scène/%s : LLM injoignable, repli démo : %s", etiquette, e)
        return None
    except anthropic.RateLimitError:
        log.warning("Scène/%s : LLM limité en débit, repli démo.", etiquette)
        return None
    except anthropic.APIStatusError as e:
        log.warning("Scène/%s : erreur API (%s), repli démo.", etiquette, e.status_code)
        return None
    except Exception as e:  # sortie non conforme au schéma, etc.
        log.warning("Scène/%s : réponse inutilisable, repli démo : %s", etiquette, e)
        return None
    finally:
        ms = int((time.monotonic() - debut) * 1000)
        if bilan is not None:
            bilan["ms"] += ms
    _compter_jetons(etiquette, reponse, ms, bilan)
    if reponse.stop_reason == "refusal":
        details = getattr(reponse, "stop_details", None)
        log.warning("Scène/%s : requête déclinée (%s), repli démo.", etiquette,
                    getattr(details, "category", None))
        return None
    if reponse.stop_reason == "max_tokens":
        log.warning("Scène/%s : réponse tronquée, repli démo.", etiquette)
        return None
    return getattr(reponse, "parsed_output", None)


def appel_json(etiquette: str, systeme: str, contenu: str, format_sortie: type[T],
               max_tokens: int = 800) -> T | None:
    """Un appel structuré rapide hors scène (ex. reformulation RAG) : 1 essai, délai court, None si échec."""
    if mode() != "llm":
        return None
    if fournisseur() == "groq":
        return _appel_groq(systeme, contenu, format_sortie, max_tokens)
    return appel_scene(etiquette, systeme, contenu, format_sortie, max_tokens)


def _compter_jetons(etiquette: str, reponse, ms: int, bilan: dict | None) -> None:
    u = getattr(reponse, "usage", None)
    vals = {k: int(getattr(u, k, 0) or 0) for k in
            ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
    if bilan is not None:
        bilan["entree"] += vals["input_tokens"]
        bilan["sortie"] += vals["output_tokens"]
        bilan["cache_lu"] += vals["cache_read_input_tokens"]
        bilan["cache_ecrit"] += vals["cache_creation_input_tokens"]
    log.debug("Scène/%s : %d ms, entrée %d, sortie %d, cache lu %d", etiquette, ms,
              vals["input_tokens"], vals["output_tokens"], vals["cache_read_input_tokens"])


# --- 1. Comprendre -----------------------------------------------------------------------------

class ExtractionDemande(BaseModel):
    niveau: Optional[str] = None
    theme: Optional[str] = None
    nb_eleves: Optional[int] = None
    nb_accompagnateurs: Optional[int] = None
    date: Optional[str] = None
    duree: Optional[Literal["journee", "demi-journee"]] = None
    heure_depart_min: Optional[str] = None
    heure_retour_max: Optional[str] = None
    lieu_depart: Optional[str] = None
    destination_souhaitee: Optional[str] = None


SYSTEME_COMPRENDRE = """Tu extrais les informations d'une demande de sortie scolaire en train liO \
(Occitanie), écrite en français par un enseignant. Tu ne réponds pas à l'enseignant : tu remplis \
seulement les champs.

Règles :
- Ne remplis que ce que le DERNIER message de l'enseignant dit ou modifie ; null pour tout le reste. \
Le message précédent de l'assistant sert seulement à interpréter une réponse courte (« 4 » après \
« Combien d'accompagnateurs ? »).
- N'invente rien. Pas de valeur par défaut.
- niveau : forme courte parmi CP, CE1, CE2, CM1, CM2, 6e, 5e, 4e, 3e, 2de, 1re, Tle.
- theme : le thème pédagogique en quelques mots (ex. « Moyen Âge »).
- nb_eleves et nb_accompagnateurs : nombres entiers (adultes, enseignants et parents comptent \
comme accompagnateurs).
- date : AAAA-MM-JJ. Sans année, prends la prochaine occurrence après la date du jour.
- duree : « journee » ou « demi-journee ».
- heure_depart_min et heure_retour_max : HH:MM (« retour avant 19h » donne 19:00).
- lieu_depart : l'établissement et sa commune tels qu'écrits (ex. « Collège de Foix »).
- destination_souhaitee : seulement si l'enseignant nomme un lieu à visiter."""


def extraire_demande(dernier_message: str, message_assistant: str | None, demande_actuelle: dict,
                     aujourdhui: str) -> dict | None:
    contenu = (
        f"Date du jour : {aujourdhui}\n"
        f"Demande déjà connue (JSON) : {json.dumps(demande_actuelle, ensure_ascii=False)}\n"
        f"Message précédent de l'assistant : {message_assistant or '(aucun)'}\n"
        f"Dernier message de l'enseignant : {dernier_message}"
    )
    r = _appeler(SYSTEME_COMPRENDRE, contenu, ExtractionDemande, max_tokens=3000)
    return r.model_dump() if r else None


# --- 2. Recommander ------------------------------------------------------------------------------

class SiteNote(BaseModel):
    site_id: str
    note: int
    justification: str


class Recommandation(BaseModel):
    sites: list[SiteNote]
    choix: list[str]


SYSTEME_RECOMMANDER = """Tu aides un enseignant d'Occitanie à choisir une sortie scolaire. \
Tu reçois sa demande et une liste de sites TIRÉE DE NOTRE CATALOGUE (avec thèmes, niveaux, activités \
et intérêt pédagogique). Tu ne proposes jamais de site hors de cette liste.

Pour chaque site, donne une note d'adéquation pédagogique entière de 0 à 3 (3 = cœur du programme \
pour ce niveau et ce thème, 0 = sans rapport) et une justification d'une phrase, adressée à \
l'enseignant, fondée uniquement sur les informations du catalogue. N'écris aucun horaire, aucun \
nombre de places et aucun score : ils sont calculés ailleurs.
Puis choisis au plus 3 site_id, du plus pertinent au moins pertinent, en variant les communes \
quand c'est possible."""


def recommander(demande: dict, candidats: list[dict]) -> Recommandation | None:
    contenu = (f"Demande : {json.dumps(demande, ensure_ascii=False)}\n"
               f"Sites candidats : {json.dumps(candidats, ensure_ascii=False)}")
    r = _appeler(SYSTEME_RECOMMANDER, contenu, Recommandation, max_tokens=6000)
    if r is None:
        return None
    ids = {c["site_id"] for c in candidats}
    r.sites = [s for s in r.sites if s.site_id in ids]
    r.choix = [i for i in dict.fromkeys(r.choix) if i in ids][:3]
    return r if r.choix else None


# --- 3. Expliquer --------------------------------------------------------------------------------

class Explication(BaseModel):
    proposition_id: str
    texte: str


class Explications(BaseModel):
    explications: list[Explication]


SYSTEME_EXPLIQUER = """Tu es Tchouette, la mascotte (une chouette-locomotive) du copilote des \
sorties scolaires liO. Tu reformules, pour un enseignant, l'évaluation de chaque proposition de \
trajet en 1 à 3 phrases courtes, chaleureuses, au vouvoiement.

Règles strictes :
- Utilise UNIQUEMENT les faits fournis. N'écris aucun horaire, nombre de places, durée, pourcentage \
ou score qui ne figure pas tel quel dans les faits.
- Ne présente jamais la sortie comme réservée ou confirmée : on parle de proposition, puis de demande \
de pré-réservation.
- Une proposition rouge est « pas assez fiable » : dis pourquoi ; si une alternative existe, \
annonce-la.
- Pas de liste, pas de titre, pas d'emoji."""


_HEURE = re.compile(r"(\d{1,2})\s*(?:h|:)\s*(\d{2})?")


def _nombres_autorises(faits: str) -> tuple[set[int], set[tuple[int, int]]]:
    nombres = {int(n) for n in re.findall(r"\d+", faits)}
    heures = {(int(h), int(m or 0)) for h, m in _HEURE.findall(faits)}
    return nombres | {0, 1, 2, 3}, heures


def explication_valide(texte: str, faits: str) -> bool:
    """Garde-fou : aucun nombre ni horaire absent des faits fournis."""
    if not texte or len(texte) > 600:
        return False
    nombres, heures = _nombres_autorises(faits)
    heures |= {(9, 0), (16, 0)}  # bornes de la plage de l'offre groupe
    for h, m in _HEURE.findall(texte):
        if (int(h), int(m or 0)) not in heures:
            return False
    sans_heures = _HEURE.sub(" ", texte)
    if any(int(n) not in nombres for n in re.findall(r"\d+", sans_heures)):
        return False
    # jamais « confirmé » ni « réservé » (sauf « pré-réservé ») à ce stade
    return re.search(r"confirm|(?<!pré-)\bréservée?s?\b", texte, re.IGNORECASE) is None


def expliquer(faits_par_proposition: dict[str, str]) -> dict[str, str]:
    """Reformule les explications ; ne garde que celles qui passent le garde-fou."""
    if not faits_par_proposition:
        return {}
    contenu = "\n\n".join(f"proposition_id={pid}\n{faits}" for pid, faits in faits_par_proposition.items())
    r = _appeler(SYSTEME_EXPLIQUER, contenu, Explications, max_tokens=6000)
    if r is None:
        return {}
    out = {}
    for e in r.explications:
        faits = faits_par_proposition.get(e.proposition_id)
        if faits is not None and explication_valide(e.texte.strip(), faits):
            out[e.proposition_id] = e.texte.strip()
    return out
