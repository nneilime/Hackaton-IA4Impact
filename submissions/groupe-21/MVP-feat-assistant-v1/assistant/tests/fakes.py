"""Doublures de test : modèle scripté et fiches SIMULÉES (aucun appel réseau, aucun jeton).

Ces tests vérifient l'orchestration et les garde-fous du serveur. Les fiches réelles de la base sont vérifiées
dans test_live_rag.py, et le comportement du vrai modèle par python -m assistant.scenarios.
"""
import copy
import json
from types import SimpleNamespace

from assistant import rag_tools


def tool_call(name, cid="c1", **args):
    return SimpleNamespace(id=cid, type="function",
                           function=SimpleNamespace(name=name, arguments=json.dumps(args, ensure_ascii=False)))


def calls(*tool_calls):
    return SimpleNamespace(content="", tool_calls=list(tool_calls))


def search(query, cid="s1"):
    return calls(tool_call("search_faq", cid, query=query))


def read(source_id, cid="r1"):
    return calls(tool_call("read_source", cid, source_id=source_id))


def final(kind, text, source_ids=(), options=(), cid="f1"):
    return calls(tool_call("repondre", cid, kind=kind, text=text, options=list(options), source_ids=list(source_ids)))


def text_reply(content):
    return SimpleNamespace(content=content, tool_calls=None)


class FakeLLM:
    """Modèle scripté : chaque étape est un message, une fonction(messages) -> message, ou une exception."""
    configured = True
    model = "modele-simule"

    def __init__(self, *steps):
        self.steps, self.calls = list(steps), []

    def chat(self, messages, tools, on_wait=None):
        self.calls.append(copy.deepcopy(messages))
        if not self.steps:
            raise AssertionError("le modèle simulé n'a plus d'étape prévue")
        step = self.steps.pop(0)
        if callable(step):
            step = step(messages)
        if isinstance(step, Exception):
            raise step
        return step, "stop", 100

    def tool_messages(self, call_index=-1):
        """Messages « tool » vus par le modèle lors d'un appel donné."""
        return [m for m in self.calls[call_index] if m.get("role") == "tool"]


def record(source_id):
    return rag_tools.retriever().get(source_id)


def read_ok(source_id, markdown, videos=(), url=None):
    rec = record(source_id)
    return {"status": "ok", "source_id": source_id, "bank_code": rec["bank_code"], "question": rec["question"],
            "category": rec["category"], "subcategory": rec["subcategory"], "audience": None,
            "answer_markdown": markdown, "url": url or rec["url"], "date_modified": "2026-09-11T08:00:00+00:00",
            "videos": list(videos), "links": []}


def read_error(source_id):
    rec = record(source_id)
    return {"status": "error", "source_id": source_id, "bank_code": rec["bank_code"], "error": "fiche introuvable"}


def read_empty(source_id):
    return read_ok(source_id, "   ")


RETRAIT_CE = "CE-4971777fe1e3"
RETRAIT_BP = "BP-4a24fc307273"
BENEFICIAIRE_CE = "CE-29a1b94e179e"

RETRAIT_CE_MD = (
    "La fonctionnalité retrait SMS vous permet de retirer de l’argent sans votre carte.\n\n"
    "1. Cliquez sur **Cartes** puis sur **Retrait SMS**.\n"
    "2. Vous recevrez par SMS un code de retrait unique à 9 chiffres\n\n"
    "**A noter :** vous disposez d’un délai de 24 heures pour effectuer votre retrait avec ce code.")
BENEFICIAIRE_MD = (
    "- Aucun délai d’attente avec Sécur’Pass (code à 4 chiffres).\n"
    "- Délai d’attente de 72 heures avec le code reçu par SMS à 8 chiffres.")
