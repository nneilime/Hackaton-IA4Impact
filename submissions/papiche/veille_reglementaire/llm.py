# SPDX-License-Identifier: AGPL-3.0-or-later
"""Adaptateur LLM : délègue à question.py (Astroport.ONE/IA) s'il est présent, sinon Ollama direct.

Le fournisseur est interchangeable par configuration (VEILLE_MODEL, OLLAMA_HOST) : aucune clé requise.
Chaque appel est mis en cache (hash du prompt) pour qu'un rejeu soit instantané et reproductible.
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
from . import config

_question = None
_tried = False
DIRECT = False          # benchmark : client Ollama direct (question.py ne remonte pas les compteurs de tokens)
BYPASS_CACHE = False    # benchmark : mesurer le vrai calcul, jamais une réponse en cache
COUNTERS = {"calls": 0, "prompt_tokens": 0, "gen_tokens": 0, "prefill_s": 0.0, "decode_s": 0.0, "load_s": 0.0, "total_s": 0.0}


def _load_question_py():
    """Importe question.py sans effet de bord (son execv n'est actif qu'en exécution directe)."""
    global _question, _tried
    if _tried:
        return _question
    _tried = True
    d = Path(config.QUESTION_PY_DIR)
    if (d / "question.py").is_file():
        sys.path.insert(0, str(d))
        try:
            import question  # type: ignore
            _question = question
        except Exception as e:  # dépendances absentes, etc. -> repli propre
            print(f"[llm] question.py indisponible ({e}); repli Ollama direct", file=sys.stderr)
    return _question


def backend() -> str:
    return "question.py" if _load_question_py() else "ollama"


def _key(model: str, system: str, user: str) -> str:
    return hashlib.sha256(f"{model}\x00{system}\x00{user}".encode()).hexdigest()


def chat_json(system: str, user: str, *, model: str | None = None, temperature: float = 0.0,
              num_ctx: int = 4096, num_predict: int = 700) -> dict:
    """Retourne {"text": str|None, "cached": bool, "backend": str, "model": str}."""
    model = model or config.MODEL
    path = config.CACHE / f"{_key(model, system, user)}.json"
    if path.is_file() and not BYPASS_CACHE:
        d = json.loads(path.read_text())
        d["cached"] = True
        return d
    q = None if DIRECT else _load_question_py()
    text, stats = None, None
    if q is not None:
        text = q.get_ollama_answer(user, model, system, temperature=temperature, num_ctx=num_ctx,
                                   num_predict=num_predict, format_json=True)
    else:
        import ollama
        client = ollama.Client(host=config.OLLAMA_HOST)
        r = client.chat(model=model, format="json",
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                        options={"temperature": temperature, "num_ctx": num_ctx, "num_predict": num_predict})
        text = r["message"]["content"]
        ns = 1e9
        stats = {"prompt_tokens": r.get("prompt_eval_count") or 0, "gen_tokens": r.get("eval_count") or 0,
                 "prefill_s": (r.get("prompt_eval_duration") or 0) / ns, "decode_s": (r.get("eval_duration") or 0) / ns,
                 "load_s": (r.get("load_duration") or 0) / ns, "total_s": (r.get("total_duration") or 0) / ns}
        COUNTERS["calls"] += 1
        for k, v in stats.items():
            COUNTERS[k] += v
    out = {"text": text, "cached": False, "backend": "ollama" if q is None else backend(), "model": model, "stats": stats}
    if text is not None and not BYPASS_CACHE:
        path.write_text(json.dumps(out, ensure_ascii=False))
    return out


def embed(text: str) -> list[float]:
    import ollama
    return ollama.Client(host=config.OLLAMA_HOST).embeddings(model=config.EMBED_MODEL, prompt=text)["embedding"]
