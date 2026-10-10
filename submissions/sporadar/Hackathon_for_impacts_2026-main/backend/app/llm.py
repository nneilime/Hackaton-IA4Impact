"""Client IA interchangeable (SDK `openai`, compatible avec tout fournisseur qui parle le même protocole).

Configuration uniquement par le fichier .env (jamais dans le code) :
    AI_BASE_URL   adresse du fournisseur (vide = OpenAI)
    AI_API_KEY    clé (vide = PAS d'IA : l'agent passe en mode dégradé par mots-clés)
    AI_MODEL      nom du modèle
    AI_PROVIDER   nom affiché dans la réponse (facultatif)
    AI_FALLBACK_MODEL  modèle de secours, essayé si le modèle principal échoue encore (facultatif)

Règle d'or : ce module ne plante JAMAIS. Clé absente, réseau coupé, quota dépassé, réponse
illisible... `complete()` renvoie alors None et l'agent continue sans IA.
"""
import logging
import os
import threading
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

log = logging.getLogger("lpc.llm")

TIMEOUT_SECONDS = 15          # délai d'un appel unique
QUESTION_BUDGET_SECONDS = 20  # temps total (appels + attentes) accordé à l'IA pour UNE question
RETRY_WAITS = (2, 5)          # attentes (s) avant les 2 nouvelles tentatives, si le fournisseur n'impose rien
CACHE_SIZE = 256
# Valeurs d'exemple de .env.example : elles ne comptent pas comme une vraie configuration
PLACEHOLDERS = {"", "replace_me", "changeme", "change-me", "none", "null"}

_state = threading.local()    # échéance de la question en cours + dernier modèle réellement utilisé
_cache = {}                   # (system, question normalisée, json_mode) -> (texte, modèle) ; durée de vie = le processus
_cache_lock = threading.Lock()


def _env(name):
    return os.environ.get(name, "").strip()


def _set(value):
    return value.lower() not in PLACEHOLDERS


def is_configured():
    """True si une clé ET un modèle sont renseignés. Sinon : mode dégradé (mots-clés + gabarits)."""
    return _set(_env("AI_API_KEY")) and _set(_env("AI_MODEL"))


def generator_info():
    """{provider, model} à renvoyer dans `generator` : le modèle RÉELLEMENT utilisé (principal ou de secours)."""
    provider = _env("AI_PROVIDER")
    if not _set(provider):
        host = urlparse(_env("AI_BASE_URL")).hostname
        provider = host or "openai"
    return {"provider": provider, "model": getattr(_state, "model", None) or _env("AI_MODEL")}


def start_question():
    """Démarre le chronomètre d'une question : toutes les attentes et tentatives restent dans QUESTION_BUDGET_SECONDS."""
    _state.deadline = time.monotonic() + QUESTION_BUDGET_SECONDS
    _state.model = None


@lru_cache(maxsize=4)
def _client(api_key, base_url):
    from openai import OpenAI   # import tardif : le prototype démarre même si le SDK manque
    # max_retries=0 : les nouvelles tentatives sont gérées ici (attente contrôlée, budget de temps)
    return OpenAI(api_key=api_key, base_url=base_url or None, timeout=TIMEOUT_SECONDS, max_retries=0)


def _retry_after(error):
    """Attente demandée par le fournisseur (en-tête retry-after, en secondes), ou None."""
    try:
        return float(error.response.headers.get("retry-after"))
    except (AttributeError, TypeError, ValueError):
        return None


def _is_retryable(error):
    """Limite de débit (429) ou erreur serveur (5xx) : cela vaut la peine de réessayer."""
    status = getattr(error, "status_code", None)
    return type(error).__name__ == "RateLimitError" or status == 429 or (isinstance(status, int) and status >= 500)


def _models():
    """Modèle principal puis, s'il existe, modèle de secours."""
    fallback = _env("AI_FALLBACK_MODEL")
    return [_env("AI_MODEL")] + ([fallback] if _set(fallback) and fallback != _env("AI_MODEL") else [])


def _call_model(model, system, user, json_mode):
    """Un modèle, jusqu'à 1 + len(RETRY_WAITS) essais. Renvoie le texte, ou None si ce modèle échoue."""
    args = {"model": model, "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        args["response_format"] = {"type": "json_object"}
    try:
        client = _client(_env("AI_API_KEY"), _env("AI_BASE_URL"))
    except Exception as error:   # noqa: BLE001 - SDK absent ou configuration invalide : mode keyword, jamais de 500
        log.warning("Client IA indisponible (%s) : repli sur le mode keyword.", type(error).__name__)
        return None
    for attempt in range(len(RETRY_WAITS) + 1):
        remaining = _state.deadline - time.monotonic()
        if remaining <= 0:
            return None
        try:
            response = client.chat.completions.create(timeout=min(TIMEOUT_SECONDS, remaining), **args)
            return (response.choices[0].message.content or "").strip() or None
        except Exception as error:   # noqa: BLE001 - volontairement large : jamais de plantage
            # On ne journalise que le type d'erreur (le message peut contenir des détails de requête)
            log.warning("Appel IA en échec (%s, modèle %s, essai %d).", type(error).__name__, model, attempt + 1)
            if not _is_retryable(error) or attempt == len(RETRY_WAITS):
                return None
            wait = _retry_after(error)
            wait = RETRY_WAITS[attempt] if wait is None else wait
            if wait >= _state.deadline - time.monotonic():
                return None   # attendre dépasserait le budget : mieux vaut passer au modèle suivant
            time.sleep(wait)
    return None


def complete(system, user, json_mode=False):
    """Un appel au modèle (temperature 0). Renvoie le texte, ou None si IA absente ou en échec.

    json_mode=True demande une sortie JSON (le mot « JSON » doit alors figurer dans le prompt).
    Réessaie sur limite de débit / erreur 5xx, puis tente AI_FALLBACK_MODEL ; les réussites sont mises en cache.
    """
    if not is_configured():
        return None
    key = (system, " ".join(user.lower().split()), json_mode)
    with _cache_lock:
        hit = _cache.get(key)
    if hit:
        _state.model = hit[1]
        return hit[0]
    if getattr(_state, "deadline", None) is None:
        start_question()   # appel hors /ask : on applique quand même le budget de temps
    for model in _models():
        text = _call_model(model, system, user, json_mode)
        if text:
            _state.model = model
            with _cache_lock:
                if len(_cache) >= CACHE_SIZE:
                    _cache.pop(next(iter(_cache)))
                _cache[key] = (text, model)
            return text
    return None
