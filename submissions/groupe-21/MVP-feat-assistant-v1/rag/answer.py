"""Réponse générée par un LLM (Gemini, point d'accès compatible OpenAI) à partir du contexte RAG.

    .venv/bin/python -m rag "j'ai perdu ma carte" --bank CE --ask

Clé lue dans la variable d'environnement GEMINI_API_KEY ou dans le fichier .env à la racine.
"""
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
MODEL = os.environ.get("ASSISTANT_MODEL", "gemini-3.8-flash")
BANKS = {"CE": "Caisse d'Épargne", "BP": "Banque Populaire"}


def _api_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip() == "GEMINI_API_KEY":
                return v.strip().strip("\"'")
    raise RuntimeError("GEMINI_API_KEY manquante (variable d'environnement ou fichier .env)")


def _system_prompt(bank):
    text = (Path(__file__).parent / "prompt_systeme.md").read_text()
    prompt = text.split("---", 1)[1].strip()
    return prompt.replace("{banque}", BANKS.get(bank, "Caisse d'Épargne ou de la Banque Populaire"))


def answer(retriever, question, bank=None, k=3):
    ctx = retriever.context(question, bank=bank, k=k)
    body = {
        "model": MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": _system_prompt(bank)},
            {"role": "user", "content": f"{ctx['context']}\n\nQuestion du client : {question}"},
        ],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json",
                 "User-Agent": "faq-rag/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)["choices"][0]["message"]["content"]
