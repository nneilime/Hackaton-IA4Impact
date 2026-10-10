"""LLM client: Mistral (default) or OpenRouter, both OpenAI-compatible chat completions, with model fallbacks.

Key: MISTRAL_API_KEY (provider mistral) or OPENROUTER_API_KEY (provider openrouter), in the environment or in .env at
the repo root. Without a key everything still works:
explanations come from templates and refusal reasons are parsed by rules (llm_available() is False).
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.request

from dispatch.config import ROOT

_env_loaded = False


def _load_env() -> None:
    """Minimal .env reader (KEY=VALUE lines), so no extra dependency is needed."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_KEYS = {"mistral": "MISTRAL_API_KEY", "openrouter": "OPENROUTER_API_KEY"}


def _key_name() -> str:
    from dispatch.config import load_config
    return _KEYS.get(getattr(load_config().llm, "provider", "openrouter"), "OPENROUTER_API_KEY")


def llm_available() -> bool:
    _load_env()
    return bool(os.environ.get(_key_name()))


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def chat(system: str, user: str, cfg, max_tokens: int | None = None, json_mode: bool = False) -> str:
    """One chat completion: the configured provider first, then `llm.fallback_provider` if it fails and has a key."""
    _load_env()
    try:
        return _chat(cfg.llm, system, user, max_tokens or cfg.llm.max_tokens, cfg.llm, json_mode)
    except Exception:
        fb = getattr(cfg.llm, "fallback_provider", None)
        if fb is None or not os.environ.get(_KEYS.get(fb.provider, "")):
            raise
        return _chat(fb, system, user, max_tokens or cfg.llm.max_tokens, cfg.llm, json_mode)


def _chat(llm, system: str, user: str, max_tokens: int, base, json_mode: bool) -> str:
    provider = getattr(llm, "provider", "openrouter")
    key = os.environ[_KEYS.get(provider, "OPENROUTER_API_KEY")]
    models = [llm.model] + list(llm.fallback_models)
    last: Exception | None = None
    for model in (models if provider == "mistral" else models[:1]):
        body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "max_tokens": max_tokens, "temperature": base.temperature}
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        if provider == "openrouter":
            body["models"] = models                                  # OpenRouter routes the fallbacks itself
            if getattr(llm, "disable_reasoning", False):
                body["reasoning"] = {"enabled": False}
            headers |= {"HTTP-Referer": "https://github.com/manticore999/hackatoun", "X-Title": "Pilotage de crise Enedis"}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(f"{llm.base_url.rstrip('/')}/chat/completions",
                                     data=json.dumps(body).encode("utf-8"), method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=base.timeout_s, context=_ssl_context()) as r:
                data = json.loads(r.read())
            return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception as e:                                       # rate limit / unknown model: next one
            last = e
    raise last if last else RuntimeError("no model")
