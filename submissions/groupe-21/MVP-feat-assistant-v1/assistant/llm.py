"""Accès au modèle de langage : Gemini (API Google, point d'accès compatible OpenAI, SDK officiel `openai`).

La clé (GEMINI_API_KEY) reste côté serveur. Les nouvelles tentatives sont gérées ici plutôt que par le SDK, pour
annoncer à l'utilisateur une attente due à la limite de débit. Si le modèle principal est saturé (503) ou que son
quota est épuisé, un modèle de secours (ASSISTANT_FALLBACK_MODEL, par défaut gemini-3.1-flash-lite) prend le relais.
"""
from __future__ import annotations

import logging
import math
import os
import re
import time
from types import SimpleNamespace

import openai

log = logging.getLogger("assistant")

MAX_RATE_WAIT = 45   # attente maximale acceptée pour une limite de débit, en secondes
_RESET = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?$")


class AgentError(Exception):
    """Erreur présentée à l'utilisateur : message simple, sans détail interne."""

    def __init__(self, code: str, message: str):
        super().__init__(code)
        self.code, self.message = code, message


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class ChatLLM:
    """Adaptateur d'une API de chat compatible OpenAI, avec appels d'outils obligatoires."""
    provider = "gemini"

    def __init__(self, client, model: str, reasoning_effort: str = "medium",
                 max_completion_tokens: int = 1500, fallback_model: str | None = None, sdk=openai):
        # client=None : aucune clé disponible, le service démarre et l'interface l'indique.
        self.client, self.model, self.sdk = client, model, sdk
        self.reasoning_effort, self.max_completion_tokens = reasoning_effort, max_completion_tokens
        self.fallback_model = fallback_model if fallback_model and fallback_model != model else None
        self.last_model = model
        self._primary_blocked_until = 0.0

    @classmethod
    def from_env(cls, model: str, reasoning_effort: str) -> "ChatLLM":
        """Client Gemini si GEMINI_API_KEY est défini (sinon le service démarre et l'interface l'indique)."""
        key = os.environ.get("GEMINI_API_KEY")
        # Délai par appel : au-delà, le modèle de secours est essayé plutôt que de laisser l'utilisateur attendre.
        timeout = float(os.environ.get("ASSISTANT_CALL_TIMEOUT", "20"))
        client = openai.OpenAI(api_key=key, base_url=GEMINI_URL, timeout=timeout, max_retries=0) if key else None
        return cls(client, model, reasoning_effort,
                   fallback_model=os.environ.get("ASSISTANT_FALLBACK_MODEL", "gemini-3.1-flash-lite").strip() or None)

    @property
    def configured(self) -> bool:
        return bool(getattr(self.client, "api_key", None))

    def chat(self, messages: list[dict], tools: list[dict], on_wait=None):
        """Un appel au modèle, qui doit utiliser un outil. Renvoie (message, finish_reason, (jetons en entrée, en sortie))."""
        use_fallback = self.fallback_model is not None and time.monotonic() < self._primary_blocked_until
        params = dict(model=self.fallback_model if use_fallback else self.model, messages=messages, tools=tools,
                      tool_choice="required", max_completion_tokens=self.max_completion_tokens)
        if self.reasoning_effort:
            params["reasoning_effort"] = self.reasoning_effort
        for attempt in range(4):
            try:
                response = self.client.chat.completions.create(**params)
                self.last_model = params["model"]
                choice = response.choices[0]
                usage = response.usage
                return choice.message, choice.finish_reason, (getattr(usage, "prompt_tokens", 0) or 0,
                                                              getattr(usage, "completion_tokens", 0) or 0)
            except self.sdk.RateLimitError as e:
                wait = _retry_after(e)
                if (wait is None or wait > MAX_RATE_WAIT) and self.fallback_model and params["model"] != self.fallback_model:
                    # Quota du modèle principal épuisé pour longtemps : bascule sur le modèle de secours.
                    self._primary_blocked_until = time.monotonic() + (wait or 600)
                    log.warning("quota du modèle principal épuisé : bascule sur le modèle de secours pendant %d s", wait or 600)
                    params["model"] = self.fallback_model
                    continue
                if attempt == 3 or wait is None or wait > MAX_RATE_WAIT:
                    raise _error(e, "llm_busy", "Le service d'IA a atteint sa limite d'utilisation pour le moment. "
                                                "Réessayez dans quelques minutes.")
                log.info("limite de débit du modèle : attente de %d s", wait)
                if on_wait:
                    on_wait(wait)
                time.sleep(wait)
            except (self.sdk.AuthenticationError, self.sdk.PermissionDeniedError, self.sdk.NotFoundError) as e:
                raise _error(e, "llm_config", "Le service d'IA est mal configuré sur ce serveur (clé ou modèle refusé).")
            except self.sdk.BadRequestError as e:
                if _code(e) == "tool_use_failed":
                    # Le modèle a écrit du texte au lieu d'appeler un outil. Si c'est un objet JSON (souvent la
                    # réponse finale), on le rend à l'agent, qui le soumet aux mêmes contrôles qu'un appel à repondre.
                    generation = _failed_generation(e)
                    if generation.lstrip().startswith("{") and (attempt >= 1 or '"kind"' in generation):
                        # Réponse finale, ou appel d'outil écrit en texte après une nouvelle tentative : l'agent
                        # le contrôle (réponse) ou reconnaît l'outil visé d'après ses paramètres.
                        log.info("génération hors appel d'outil récupérée pour contrôle")
                        return SimpleNamespace(content=generation, tool_calls=None), "stop", (0, 0)
                    if attempt < 2:  # appel d'outil mal formé : souvent réussi au tirage suivant
                        log.info("appel d'outil mal formé par le modèle : nouvelle tentative")
                        continue
                if _code(e) == "context_length_exceeded":
                    raise _error(e, "conversation_too_long", "Cette conversation est trop longue : commencez-en une nouvelle.")
                log.warning("requête refusée par le fournisseur : %s", str(_error_body(e).get("message") or "")[:160])
                raise _error(e, "llm_request", "Une erreur technique empêche de traiter ce message. Réessayez ou reformulez.")
            except self.sdk.APIStatusError as e:
                if e.status_code == 413:  # demande plus grande que la limite de jetons par minute
                    raise _error(e, "conversation_too_long",
                                 "Cette conversation est trop longue pour le service d'IA : commencez-en une nouvelle.")
                if e.status_code >= 500 and attempt < 1:
                    time.sleep(1.5)
                    continue
                if e.status_code >= 500 and self.fallback_model and params["model"] != self.fallback_model:
                    # Modèle principal saturé : le secours répond, le principal est réessayé dans 2 minutes.
                    self._primary_blocked_until = time.monotonic() + 120
                    log.warning("modèle principal saturé (statut %s) : bascule sur le modèle de secours", e.status_code)
                    params["model"] = self.fallback_model
                    continue
                raise _error(e, "llm_unavailable", "Le service d'IA est momentanément indisponible. Réessayez dans quelques instants.")
            except self.sdk.APIConnectionError as e:  # y compris le dépassement de délai
                if isinstance(e, self.sdk.APITimeoutError) and self.fallback_model and params["model"] != self.fallback_model:
                    self._primary_blocked_until = time.monotonic() + 120
                    log.warning("modèle principal trop lent (délai dépassé) : bascule sur le modèle de secours")
                    params["model"] = self.fallback_model
                    continue
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise _error(e, "llm_unavailable", "Le service d'IA ne répond pas pour le moment. Réessayez dans quelques instants.")
        raise AgentError("llm_unavailable", "Le service d'IA ne répond pas pour le moment. Réessayez dans quelques instants.")


def _retry_after(e) -> int | None:
    headers = getattr(getattr(e, "response", None), "headers", None) or {}
    value = headers.get("retry-after")
    try:
        return max(1, math.ceil(float(value)))
    except (TypeError, ValueError):
        pass
    m = _RESET.match(headers.get("x-ratelimit-reset-tokens") or "")
    if m and any(m.groups()):
        h, mn, s = (float(x) if x else 0.0 for x in m.groups())
        return max(1, math.ceil(h * 3600 + mn * 60 + s))
    return None


def _error_body(e) -> dict:
    body = getattr(e, "body", None)
    if isinstance(body, list) and body:   # Gemini enveloppe l'erreur dans une liste
        body = body[0]
    error = body.get("error", body) if isinstance(body, dict) else None
    return error if isinstance(error, dict) else {}


def _code(e) -> str | None:
    return _error_body(e).get("code")


def _failed_generation(e) -> str:
    generation = _error_body(e).get("failed_generation")
    return generation if isinstance(generation, str) else ""


def _error(e: Exception, code: str, message: str) -> AgentError:
    # Ni contenu ni secret dans le journal : type d'erreur, statut HTTP et code d'erreur du fournisseur.
    log.warning("appel au modèle en échec : %s (statut %s, code %s)", type(e).__name__,
                getattr(e, "status_code", "-"), _code(e) if isinstance(e, openai.APIStatusError) else "-")
    return AgentError(code, message)

