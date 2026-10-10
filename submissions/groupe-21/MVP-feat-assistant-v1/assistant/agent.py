"""Conversation et boucle d'outils avec le modèle : recherche FAQ, base de données fictive, réponse contrôlée.

Garanties tenues par le serveur, quel que soit le comportement du modèle :
- la banque est la Caisse d'Épargne ; ce n'est jamais un paramètre du modèle ;
- read_source n'accepte qu'un source_id renvoyé par search_faq dans cette conversation ;
- une réponse de fond (« answer ») doit reposer sur une fiche de la base de connaissances lue avec succès, ou sur un résultat
  des outils de la base (finance/), et ses nombres doivent figurer dans ces pages ou résultats ;
- les liens affichés viennent des métadonnées du lecteur, jamais du texte du modèle ;
- un message n'entre dans l'historique qu'une fois traité avec succès (pas d'historique partiel).

Les réponses suivent le contrat de la maquette front/index.html : {blocks, meta}.
"""
from __future__ import annotations

import json
import logging
import re
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from types import SimpleNamespace
from urllib.parse import urlsplit

from finance import engine as finance

from . import guard, prompt, rag_tools
from .llm import AgentError

log = logging.getLogger("assistant")

MAX_MODEL_CALLS = 8      # appels au modèle pour un message
MAX_SEARCHES = 4         # recherches pour un message
MAX_READS = 4            # lectures pour un message
MAX_FINANCE = 5          # appels aux outils de la base pour un message
FINANCE_KEPT = 6         # résultats de la base gardés comme preuves dans la conversation
MAX_CORRECTIONS = 2      # réponses finales refusées par le contrôle serveur avant le message de repli
MAX_TURNS = 40           # messages par conversation
MAX_SOURCES_SHOWN = 4
CONVERSATION_TTL = 30 * 60

SLOW_NOTICE = 20         # secondes sans réponse avant de prévenir le client que la recherche continue
SLOW_LABELS = ("Je continue de rechercher, veuillez patienter…",
               "Je recherche toujours, veuillez patienter…")

CONTROL_PREFIX = "[Contrôle automatique du serveur, ce n'est pas un message de l'utilisateur] "
MEDIA_NOTE = ("La page officielle contient aussi des vidéos ou des illustrations que l'assistant ne lit pas : "
              "consultez-la pour les voir.")

_LIST_MARKER = re.compile(r"^\s*\d+\.\s", re.M)
_NUMBER = re.compile(r"\d+(?:[,.]\d+)?")
_THOUSANDS = re.compile(r"(?<=\d)[   ](?=\d{3}(?!\d))")
_NUMERIC_CLAIM = re.compile(
    r"\d+(?:[,.]\d+)?\s*(?:h\b|heures?|jours?|semaines?|mois|ans?\b|minutes?|€|euros?|%|chiffres)", re.I)
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_URL = re.compile(r"\b(?:https?://|www\.)[^\s<>()\"']+", re.I)
_SOURCE_LINE = re.compile(r"^[ \t]*\**[ \t]*sources?[ \t]*\**[ \t]*:.*$", re.I | re.M)


@dataclass
class Conversation:
    bank: str
    id: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    history: list = field(default_factory=list)     # tours terminés : {"full": [...], "brief": [...]}
    candidates: dict = field(default_factory=dict)  # source_id -> candidat renvoyé par search_faq
    reads: dict = field(default_factory=dict)       # source_id -> dernier résultat de read_source
    evidence: dict = field(default_factory=dict)    # source_id -> contenu lu transmis au modèle
    finance: list = field(default_factory=list)     # derniers résultats de la base transmis au modèle (texte)
    user_texts: list = field(default_factory=list)
    turns: int = 0
    last_active: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def model_history(self) -> list[dict]:
        """Tours précédents résumés (question, réponse affichée, pages citées) : la page se relit si besoin."""
        return [m for turn in self.history for m in turn["brief"]]


class ConversationStore:
    """Conversations gardées en mémoire uniquement, effacées après inactivité : rien n'est écrit sur disque."""

    def __init__(self, ttl: float = CONVERSATION_TTL, max_size: int = 500):
        self._items: dict[str, Conversation] = {}
        self._lock = threading.Lock()
        self.ttl, self.max_size = ttl, max_size

    def open(self, conversation_id: str | None, bank: str) -> tuple[Conversation, str | None]:
        """Conversation à utiliser, et raison d'une remise à zéro du contexte ("expired", "bank_changed")."""
        now = time.monotonic()
        with self._lock:
            self._sweep(now)
            conv = self._items.get(conversation_id) if conversation_id else None
            reason = None
            if conversation_id and conv is None:
                reason = "expired"
            elif conv is not None and conv.bank != bank:
                # Changement de banque : nouveau contexte documentaire, rien n'est réutilisé.
                del self._items[conv.id]
                conv, reason = None, "bank_changed"
            if conv is None:
                conv = Conversation(bank=bank)
                self._items[conv.id] = conv
            conv.last_active = now
            return conv, reason

    def remember(self, conv: Conversation, user_text: str, answer_text: str) -> None:
        """Garde un échange servi sans modèle (réponse pré-rédigée) pour que le modèle ait le contexte ensuite."""
        user, bot = {"role": "user", "content": user_text}, {"role": "assistant", "content": answer_text}
        conv.history.append({"full": [user, bot], "brief": [user, bot]})
        conv.user_texts.append(user_text)
        conv.turns += 1

    def delete(self, conversation_id: str) -> None:
        with self._lock:
            self._items.pop(conversation_id, None)

    def __len__(self) -> int:
        return len(self._items)

    def _sweep(self, now: float) -> None:
        for cid in [cid for cid, c in self._items.items() if now - c.last_active > self.ttl and not c.lock.locked()]:
            del self._items[cid]
        while len(self._items) >= self.max_size:
            del self._items[min(self._items.values(), key=lambda c: c.last_active).id]


class _Turn:
    """Un message en cours de traitement ; fusionné dans la conversation seulement s'il aboutit."""

    def __init__(self, conv: Conversation, text: str):
        self.conv, self.user_text = conv, text
        self.messages: list[dict] = []
        self.candidates: dict = {}
        self.reads: dict = {}
        self.evidence: dict = {}
        self.finance: list[dict] = []   # {"tool", "args", "data", "text"} des appels réussis à la base
        self.model_calls = self.searches = self.read_count = self.finance_count = self.corrections = 0
        self.tokens_in = self.tokens_out = 0
        self.started = time.monotonic()

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    def finance_texts(self) -> list[str]:
        return [f["text"] for f in self.finance] + self.conv.finance

    def candidate(self, sid: str) -> dict | None:
        return self.candidates.get(sid) or self.conv.candidates.get(sid)

    def read(self, sid: str) -> dict | None:
        return self.reads[sid] if sid in self.reads else self.conv.reads.get(sid)

    def evidence_text(self, sid: str) -> str:
        return self.evidence.get(sid) or self.conv.evidence.get(sid, "")

    def commit(self, summary: str) -> None:
        c = self.conv
        # L'appel final à « repondre » devient le texte affiché : historique valide et lisible au tour suivant.
        self.messages[-1] = {"role": "assistant", "content": summary}
        c.history.append({"full": self.messages, "brief": [self.messages[0], self.messages[-1]]})
        c.candidates.update(self.candidates)
        c.reads.update(self.reads)
        c.evidence.update(self.evidence)
        c.finance = (c.finance + [f["text"] for f in self.finance])[-FINANCE_KEPT:]
        c.user_texts.append(self.user_text)
        c.turns += 1


class Agent:
    def __init__(self, llm):
        self.llm = llm

    @property
    def configured(self) -> bool:
        return self.llm.configured

    @property
    def model(self) -> str:
        return self.llm.model

    def answer(self, conv: Conversation, text: str, *, simple: bool = False, emit=None, cancelled=None) -> dict:
        """Traite un message et renvoie la réponse affichable {blocks, meta}. Lève AgentError si impossible.

        Si la réponse tarde (SLOW_NOTICE secondes), le client est prévenu que la recherche continue, puis à nouveau
        à chaque intervalle : l'utilisateur, et son lecteur d'écran, ne restent jamais sans nouvelles."""
        raw, lock, stop = emit or (lambda event: None), threading.Lock(), threading.Event()

        def safe_emit(event: dict) -> None:   # le minuteur et la boucle écrivent dans le même flux
            with lock:
                if not stop.is_set():
                    raw(event)

        def notify_slow() -> None:
            n = 0
            while not stop.wait(SLOW_NOTICE):
                safe_emit(_status("slow", SLOW_LABELS[min(n, len(SLOW_LABELS) - 1)]))
                n += 1

        threading.Thread(target=notify_slow, daemon=True).start()
        try:
            return self._answer(conv, text, simple=simple, emit=safe_emit, cancelled=cancelled)
        finally:
            with lock:
                stop.set()

    def _answer(self, conv: Conversation, text: str, *, simple: bool, emit, cancelled) -> dict:
        emit = emit or (lambda event: None)
        cancelled = cancelled or (lambda: False)
        if guard.contains_secret(text):
            log.info("message bloqué par le garde-fou (donnée sensible), non transmis")
            return _reply("guard", [{"type": "warning", "text": guard.WARNING}], conv.bank)
        if conv.turns >= MAX_TURNS:
            raise AgentError("conversation_too_long",
                             "Cette conversation est longue : commencez une nouvelle conversation pour continuer.")
        if not self.configured:
            raise AgentError("llm_not_configured",
                             "Le service d'IA n'est pas configuré sur ce serveur : aucune réponse ne peut être générée.")

        turn = _Turn(conv, text)
        turn.messages.append({"role": "user", "content": f"{text}\n\n{prompt.SIMPLE_LANGUAGE_NOTE}" if simple else text})
        emit(_status("understand", "Analyse de votre question…"))
        preloaded = _preload(turn, text)   # fiches FAQ lues d'avance : le modèle peut répondre en un seul appel
        on_wait = lambda s: emit(_status("wait", f"Le service d'IA limite le débit : reprise dans {s} s…"))

        while turn.model_calls < MAX_MODEL_CALLS:
            if cancelled():
                raise AgentError("cancelled", "Demande interrompue.")
            turn.model_calls += 1
            system = {"role": "system", "content": prompt.system_prompt(conv.bank) + preloaded}
            message, finish, usage = self.llm.chat([system] + conv.model_history() + turn.messages, prompt.TOOLS, on_wait)
            if isinstance(usage, tuple):   # (jetons en entrée, jetons en sortie)
                turn.tokens_in += usage[0]
                turn.tokens_out += usage[1]
            else:
                turn.tokens_in += usage
            if finish == "length":
                raise AgentError("incomplete", "La réponse n'a pas pu être terminée. Reformulez ou simplifiez votre question.")
            calls = list(message.tool_calls or [])
            if not calls:   # appel d'outil écrit en texte (JSON) : on reconnaît l'outil visé d'après ses paramètres
                inferred = _inferred_call(message.content, turn.model_calls)
                if inferred is not None:
                    log.info("appel d'outil écrit en texte, reconnu : %s", inferred.function.name)
                    calls, message = [inferred], SimpleNamespace(content="", tool_calls=[inferred])
            entry = {"role": "assistant", "content": message.content or ""}
            if calls:
                entry["tool_calls"] = [_tool_call_entry(c) for c in calls]
            turn.messages.append(entry)

            finals = [c for c in calls if c.function.name == prompt.FINAL_TOOL]
            others = [c for c in calls if c.function.name != prompt.FINAL_TOOL]
            if others:
                turn.messages.extend(self._run_tools(turn, others, emit))
                fast = _fast_reply(turn, others)
                if fast is not None:   # calcul seul : réponse rédigée par le serveur, sans second appel au modèle
                    reply, data = fast
                    turn.messages.append({"role": "assistant", "content": ""})
                    turn.commit(_summary(turn, reply, data))
                    return self._done(turn, reply, committed=True)
                turn.messages.extend(_tool_message(c.id, "Ignoré : appelle repondre seul, après avoir reçu les "
                                                         "résultats des autres outils.") for c in finals)
                emit(_status("analyse", "Analyse des résultats…"))
                continue

            # Réponse finale : appel à repondre, ou objet JSON écrit en texte (même contrôle dans les deux cas).
            data = _arguments(finals[0]) if finals else _json_object(message.content)
            if data is not None:
                problem = _problem(turn, data)
            elif finals:
                problem = "arguments de repondre illisibles : renvoie kind, text, options et source_ids."
            else:
                problem = "aucun outil appelé : utilise search_faq ou read_source, puis repondre pour la réponse finale."
            if problem is None:
                reply = _reply_from(turn, data)
                turn.commit(_summary(turn, reply, data))
                return self._done(turn, reply, committed=True)
            log.info("réponse finale refusée par le contrôle serveur (%s)", problem[:70])
            if turn.corrections >= MAX_CORRECTIONS:
                break
            turn.corrections += 1
            emit(_status("check", "Vérification de la réponse…"))
            if finals:
                turn.messages.append(_tool_message(finals[0].id, "Refusé par le contrôle du serveur : " + problem))
                turn.messages.extend(_tool_message(c.id, "Ignoré : un seul appel à repondre.") for c in finals[1:])
            else:
                turn.messages.append({"role": "user", "content": CONTROL_PREFIX + problem})
        # Pas de réponse conforme : message honnête, et le tour n'est pas conservé.
        return self._done(turn, _fallback(turn), committed=False)

    def _run_tools(self, turn: _Turn, calls: list, emit) -> list[dict]:
        """Contrôle chaque appel d'outil, exécute ceux qui sont autorisés, puis renvoie tous les résultats."""
        bank = turn.conv.bank
        planned = []  # (appel, tâche à exécuter ou None, message de refus, argument)
        for call in calls:
            args = _arguments(call) or {}
            name = call.function.name
            if name == "search_faq":
                query = args.get("query")
                if not isinstance(query, str) or not query.strip() or len(query) > 300:
                    planned.append((call, None, "Refusé : requête vide ou trop longue.", None))
                elif turn.searches >= MAX_SEARCHES:
                    planned.append((call, None, "Refusé : limite de recherches atteinte pour ce message. Réponds avec "
                                                "les informations disponibles, ou avec kind \"not_found\".", None))
                else:
                    query = query.strip()
                    turn.searches += 1
                    emit(_status("search", f"Recherche dans la FAQ {rag_tools.BANKS[bank]} : « {query[:80]} »"))
                    planned.append((call, lambda q=query: rag_tools.search(q, bank), None, query))
            elif name == "read_source":
                sid = args.get("source_id")
                cand = turn.candidate(sid) if isinstance(sid, str) else None
                if not isinstance(sid, str) or not rag_tools.SOURCE_ID.match(sid):
                    planned.append((call, None, "Refusé : identifiant invalide. Utilise un source_id exact renvoyé par "
                                                "search_faq, jamais une URL.", None))
                elif cand is None:
                    planned.append((call, None, "Refusé : ce source_id ne provient d'aucun résultat de search_faq dans "
                                                "cette conversation. Utilise d'abord search_faq.", None))
                elif cand.get("bank_code") != bank:
                    planned.append((call, None, "Refusé : cette source n'appartient pas à la banque sélectionnée.", None))
                elif turn.read_count >= MAX_READS:
                    planned.append((call, None, "Refusé : limite de lectures atteinte pour ce message. Réponds avec les "
                                                "pages déjà lues.", None))
                else:
                    turn.read_count += 1
                    emit(_status("read", f"Lecture de la fiche : « {cand['question'][:110]} »"))
                    planned.append((call, lambda s=sid: rag_tools.read(s, bank), None, sid))
            elif name in FINANCE_CALLS:
                if turn.finance_count >= MAX_FINANCE:
                    planned.append((call, None, "Refusé : limite de calculs atteinte pour ce message. Réponds avec "
                                                "les résultats déjà obtenus.", None))
                else:
                    turn.finance_count += 1
                    emit(_status("compute", FINANCE_LABELS[name]))
                    planned.append((call, lambda n=name, a=args: FINANCE_CALLS[n](a), None, args))
            else:
                planned.append((call, None, f"Refusé : outil inconnu « {name} ».", None))

        tasks = [task for _, task, _, _ in planned if task]
        outcomes = {}
        if tasks:
            with ThreadPoolExecutor(max_workers=min(4, len(tasks))) as pool:
                futures = [(task, pool.submit(task)) for task in tasks]
                for task, future in futures:
                    try:
                        outcomes[id(task)] = (future.result(), None)
                    except finance.FinanceError as e:  # paramètres hors grille : expliqués au modèle
                        outcomes[id(task)] = (None, e)
                    except Exception as e:  # un outil défaillant ne doit pas interrompre la conversation
                        log.warning("outil en échec : %s", type(e).__name__)
                        outcomes[id(task)] = (None, e)

        messages = []
        for call, task, refusal, arg in planned:
            if task is None:
                messages.append(_tool_message(call.id, refusal))
                continue
            value, error = outcomes[id(task)]
            if isinstance(error, finance.FinanceError):
                messages.append(_tool_message(call.id, f"Paramètres refusés par la base : {error} Corrige-les, ou "
                                                       "demande la précision à l'utilisateur (kind \"clarification\")."))
            elif error is not None:
                messages.append(_tool_message(call.id, "Erreur technique de l'outil : réessaie une fois, ou réponds sans "
                                                       "cette source (kind \"unverified\")."))
            elif call.function.name in FINANCE_CALLS:
                text = finance.to_text(value)
                turn.finance.append({"tool": call.function.name, "args": arg, "data": value, "text": text})
                messages.append(_tool_message(call.id, f"<base_prototype outil=\"{call.function.name}\">\n{text}\n</base_prototype>"))
            elif call.function.name == "search_faq":
                found = [r for r in value if r.get("bank_code") == bank]
                turn.candidates.update({r["source_id"]: r for r in found})
                messages.append(_tool_message(call.id, rag_tools.format_search(arg, bank, found)))
            else:
                turn.reads[arg] = value
                text, failed = rag_tools.format_read(arg, bank, value)
                if not failed:
                    turn.evidence[arg] = text
                messages.append(_tool_message(call.id, text))
        return messages

    def _done(self, turn: _Turn, reply: dict, committed: bool) -> dict:
        # Journal d'exploitation sans contenu de conversation.
        log.info("réponse kind=%s banque=%s appels_modèle=%d recherches=%d lectures=%d calculs=%d corrections=%d "
                 "jetons=%d historique=%s durée=%.1fs", reply["meta"]["kind"], turn.conv.bank, turn.model_calls,
                 turn.searches, turn.read_count, turn.finance_count, turn.corrections, turn.tokens,
                 "conservé" if committed else "non conservé", time.monotonic() - turn.started)
        used = getattr(self.llm, "last_model", None) or self.llm.model
        fallback = used == getattr(self.llm, "fallback_model", None)
        reply["meta"].update(model="fallback" if fallback else "gemini", model_name=used, latency_ms=int((time.monotonic() - turn.started) * 1000),
                             usage={"input_tokens": turn.tokens_in, "output_tokens": turn.tokens_out})
        return reply


# ---------------------------------------------------------------------- outils de la base (finance/)

def _pick(args: dict, *names: str) -> dict:
    return {k: args[k] for k in names if args.get(k) not in (None, "")}


FINANCE_CALLS = {
    "simuler_credit": lambda a: finance.simulate_loan(**_pick(a, "produit", "montant", "duree_mois", "age", "fumeur", "apport",
                                                               "revenus_mensuels", "charges_mensuelles", "debut")),
    "capacite_emprunt": lambda a: finance.borrowing_capacity(**_pick(a, "revenus_mensuels", "charges_mensuelles",
                                                                     "duree_mois", "produit", "apport", "age")),
    "prevoir_taux": lambda a: finance.forecast(**_pick(a, "serie", "horizon_mois")),
    "simuler_epargne": lambda a: finance.project_savings(**_pick(a, "produit", "versement_initial", "versement_mensuel",
                                                                 "duree_annees")),
    "catalogue": lambda a: finance.catalogue(**_pick(a, "sujet", "filtre")),
}
FINANCE_LABELS = {
    "simuler_credit": "Calcul de la simulation de crédit…",
    "capacite_emprunt": "Calcul de votre capacité d'emprunt…",
    "prevoir_taux": "Lecture de l'historique et des prévisions de taux…",
    "simuler_epargne": "Projection de votre épargne…",
    "catalogue": "Consultation des produits et tarifs…",
}
FINANCE_SOURCE = "Base de données du prototype ({}) : données fictives, estimation indicative"
GENERAL_SOURCE = ("Information générale de l'assistant, hors documents de la Caisse d'Épargne : "
                  "à faire confirmer par un conseiller")
_FINANCE_NAMES = {"simuler_credit": "simulation de crédit", "capacite_emprunt": "capacité d'emprunt",
                  "prevoir_taux": "prévisions de taux", "simuler_epargne": "projection d'épargne",
                  "catalogue": "catalogue et tarifs"}


# ---------------------------------------------------------------------- réponse rapide

PRELOAD = 3                       # fiches FAQ lues avant le premier appel au modèle (0 = désactivé)
FAST_FINANCE = True               # calcul seul : réponse rédigée par le serveur, sans second appel
FAST_TOOLS = {"simuler_credit", "capacite_emprunt", "simuler_epargne", "prevoir_taux"}


def _preload(turn: _Turn, text: str) -> str:
    """Recherche FAQ faite par le serveur (quelques millisecondes) : les meilleures fiches sont lues et jointes aux
    consignes. Elles comptent comme lues : le modèle peut les citer directement, sans search_faq ni read_source."""
    bank = turn.conv.bank
    try:
        hits = rag_tools.search(text[:300], bank)[:PRELOAD] if PRELOAD else []
    except Exception as e:   # l'index ne doit jamais empêcher de répondre
        log.warning("présélection FAQ impossible : %s", type(e).__name__)
        return ""
    blocks = []
    for h in hits:
        sid = h["source_id"]
        result = rag_tools.read(sid, bank)
        evidence, failed = rag_tools.format_read(sid, bank, result)
        if failed:
            continue
        turn.candidates[sid], turn.reads[sid], turn.evidence[sid] = h, result, evidence
        blocks.append(evidence)
    if not blocks:
        return ""
    return ("\n\nFiches FAQ présélectionnées par le serveur pour le dernier message (déjà lues, citables par leur "
            "source_id ; elles peuvent être hors sujet) :\n" + "\n\n".join(blocks))


def _fast_reply(turn: _Turn, calls: list) -> tuple[dict, dict] | None:
    """Un seul calcul demandé d'emblée et réussi : la réponse reprend la carte de résultat, chiffres exacts compris."""
    if not FAST_FINANCE or turn.model_calls != 1 or len(calls) != 1 or calls[0].function.name not in FAST_TOOLS or len(turn.finance) != 1:
        return None
    card = _result_card(turn.finance[0]["data"])
    if not card:
        return None
    lines = [f"{card['title']} : **{card['big']}** {card['sub']}."]
    lines += [f"- {label} : **{value}**" for label, value in card["rows"][:5]]
    lines.append("\nC'est une estimation sur des données fictives : un conseiller peut vous faire une proposition réelle.")
    data = {"kind": "answer", "text": "\n".join(lines), "options": [], "source_ids": []}
    return _reply_from(turn, data), data


# ---------------------------------------------------------------------- contrôles et réponse

def _problem(turn: _Turn, data: dict | None) -> str | None:
    """Motif de refus de la réponse finale, ou None si elle respecte les règles."""
    if not isinstance(data, dict) or data.get("kind") not in prompt.KINDS \
            or not isinstance(data.get("text"), str) or not data["text"].strip():
        return "réponse illisible : appelle repondre avec kind, text, options et source_ids."
    kind, text, ids = data["kind"], data["text"], _ids(data)
    if kind == "general":   # connaissances générales, affichées comme telles avec un avertissement
        return None
    verified = [sid for sid in ids if rag_tools.is_verified(turn.read(sid))]
    computed = turn.finance_texts()
    if kind == "answer" and not verified and not computed:
        return ("ta réponse est de type \"answer\" mais ne repose ni sur une page lue avec succès par read_source "
                f"(source_ids reçus : {', '.join(ids) or 'aucun'}), ni sur un outil de la base. Lis la page "
                "pertinente ou utilise l'outil de calcul adapté ; si la FAQ et la base ne couvrent pas la question, renvoie la "
                "même réponse avec kind \"general\" (information générale, sans tarif ni procédure propre à la banque).")
    if kind == "clarification" or (kind != "answer" and not _NUMERIC_CLAIM.search(text)):
        return None
    if kind != "answer" and not verified and not computed:
        return ("ton message donne des délais, montants ou conditions chiffrées sans page lue ni calcul de la base : "
                "retire-les, utilise l'outil qui les établit (kind \"answer\"), ou, s'il s'agit de règles générales, réponds "
                "avec kind \"general\".")
    evidence = " ".join([turn.evidence_text(sid) for sid in verified] + computed + turn.conv.user_texts + [turn.user_text])
    missing = _unsupported_numbers(text, evidence)
    if missing:
        return (f"ces nombres de ta réponse n'apparaissent ni dans les pages citées ni dans les résultats de la base : "
                f"{', '.join(missing)}. Ne calcule rien toi-même : reprends les chiffres exacts des outils, ou appelle "
                "l'outil pour obtenir ceux qui manquent.")
    return None


def _numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in _NUMBER.findall(_THOUSANDS.sub("", text))}


def _unsupported_numbers(text: str, evidence: str) -> list[str]:
    known = set()
    for n in _numbers(evidence):   # un chiffre arrondi (1 094,24 → 1 094 ou 1 094,2) reste reconnu
        known.add(n)
        if "." in n:
            value = float(n)
            known.update({str(round(value)), f"{value:.1f}", f"{value:.1f}".rstrip("0").rstrip(".")})
    return sorted(n for n in _numbers(_LIST_MARKER.sub("", text)) if n not in known)


def _reply_from(turn: _Turn, data: dict) -> dict:
    bank, kind = turn.conv.bank, data["kind"]
    blocks = [{"type": "text", "text": _clean_text(data["text"], bank)}]
    if kind == "general":
        blocks.append({"type": "chips", "items": [{"label": "Parler à un conseiller", "action": {"type": "handoff"}}]})
    if kind == "clarification":
        options = _options(data)
        if options:
            blocks.append({"type": "choices", "key": "llm", "items": [{"label": o, "value": o} for o in options]})
        return _reply(kind, blocks, bank)
    card = _result_card(turn.finance[-1]["data"]) if kind == "answer" and turn.finance else None
    if card:
        blocks.append(card)
    sources = _sources(turn, _ids(data))
    if turn.finance:
        used = ", ".join(dict.fromkeys(_FINANCE_NAMES[f["tool"]] for f in turn.finance))
        sources.append({"title": FINANCE_SOURCE.format(used), "status": "hypothese"})
    if kind == "general":
        sources.append({"title": GENERAL_SOURCE, "status": "hypothese"})
    if sources:
        blocks.append({"type": "sources", "items": sources})
    if any(s.get("has_media") for s in sources):
        blocks.append({"type": "text", "text": MEDIA_NOTE})
    return _reply(kind, blocks, bank)


def _result_card(r: dict) -> dict | None:
    """Carte « résultat » de la maquette pour le dernier calcul de la base."""
    eur, pct, kind = finance.eur, finance.pct, r.get("type")
    if kind == "simulation_credit":
        rows = [["Montant", eur(r["montant"])], ["Durée", f"{r['duree_mois']} mois ({finance.years_label(r['duree_annees'])})"],
                ["Taux nominal", pct(r["taux_nominal"])], ["TAEG", pct(r["taeg"])],
                ["Mensualité hors assurance", eur(r["mensualite"], 2)], ["Coût total du crédit", eur(r["cout_total"])]]
        if r["debut_futur"] and len(r["scenarios"]) == 3:
            sc = r["scenarios"]
            rows.insert(3, [f"Taux prévu en {finance.month_label(r['debut'])} (bas / central / haut)",
                            " / ".join(pct(sc[k]["taux_nominal"]) for k in ("bas", "central", "haut"))])
        if "taux_endettement" in r:
            rows.append(["Taux d'endettement", pct(r["taux_endettement"], 1)])
        return {"type": "result", "title": f"Estimation : {r['produit_nom']}", "big": f"≈ {eur(r['mensualite_avec_assurance'])}",
                "sub": "par mois, assurance comprise", "rows": rows,
                "legal": r["mention_legale"] or "C'est une estimation sur des données fictives, pas une offre : un conseiller peut vous faire une vraie proposition."}
    if kind == "capacite_emprunt" and r.get("capital_max"):
        rows = [["Revenus mensuels", eur(r["revenus_mensuels"])], ["Charges mensuelles", eur(r["charges_mensuelles"])],
                ["Mensualité maximale (35 %)", eur(r["mensualite_max"])], ["Durée", f"{r['duree_mois']} mois"],
                ["Taux nominal utilisé", pct(r["taux_nominal"])]]
        if "budget_achat_ancien" in r:
            rows += [["Budget d'achat dans l'ancien", eur(r["budget_achat_ancien"])], ["Budget d'achat dans le neuf", eur(r["budget_achat_neuf"])]]
        return {"type": "result", "title": "Votre capacité d'emprunt", "big": f"≈ {eur(r['capital_max'])}",
                "sub": "empruntables", "rows": rows, "legal": finance.DISCLAIMER}
    if kind == "projection_epargne":
        sc = r["scenarios"]
        rows = [["Versement initial", eur(r["versement_initial"])], ["Versement mensuel", eur(r["versement_mensuel"])],
                ["Total versé", eur(sc["central"]["total_verse"])], ["Gains (scénario central)", eur(sc["central"]["gains"])],
                ["Scénario bas / haut", f"{eur(sc['bas']['capital_final'])} / {eur(sc['haut']['capital_final'])}"]]
        if r["taux_actuel"] is not None:
            rows.insert(0, ["Taux actuel", pct(r["taux_actuel"])])
        return {"type": "result", "title": f"Projection : {r['produit_nom']}", "big": f"≈ {eur(sc['central']['capital_final'])}",
                "sub": f"dans {finance.years_label(r['duree_annees'])}", "rows": rows, "legal": finance.DISCLAIMER}
    if kind == "prevision_taux" and r["previsions"]:
        last = r["previsions"][-1]
        return {"type": "result", "title": r["libelle"], "big": pct(last["central"]),
                "sub": f"prévu en {finance.month_label(last['mois'])} (scénario central)",
                "rows": [[f"Aujourd'hui ({finance.month_label(r['mois_reference'])})", pct(r["valeur_actuelle"])],
                         ["Scénario bas", pct(last["bas"])], ["Scénario haut", pct(last["haut"])]],
                "legal": "Prévision incertaine sur des données fictives : ce n'est ni une promesse ni une offre."}
    return None


def _summary(turn: _Turn, reply: dict, data: dict) -> str:
    """Ce que le modèle retrouvera de ce tour dans l'historique : texte affiché, choix, pages et calculs."""
    parts = [reply["blocks"][0]["text"]]
    if data["kind"] == "clarification" and _options(data):
        parts.append("[Choix proposés : " + " ; ".join(_options(data)) + "]")
    cited = [sid for sid in _ids(data) if turn.read(sid) is not None]
    if cited:
        parts.append("[Pages citées : " + " ; ".join(cited) + "]")
    if turn.finance:
        parts.append("[Calculs de la base : " + " ; ".join(
            f"{f['tool']}({json.dumps(f['args'], ensure_ascii=False)})" for f in turn.finance) + "]")
    return "\n\n".join(parts)


def _fallback(turn: _Turn) -> dict:
    sources = _sources(turn, list(turn.reads))
    text = ("Je n'ai pas pu établir de réponse vérifiée : je préfère ne pas vous répondre sur le fond. "
            + ("Vous pouvez consulter directement la page ci-dessous, reformuler votre question ou vous adresser à "
               "votre conseiller." if sources else
               "Vous pouvez reformuler votre question ou vous adresser à votre conseiller."))
    blocks = [{"type": "text", "text": text}] + ([{"type": "sources", "items": sources}] if sources else [])
    blocks.append({"type": "chips", "items": [{"label": "Parler à un conseiller", "action": {"type": "handoff"}}]})
    return _reply("unverified", blocks, turn.conv.bank)


def _sources(turn: _Turn, ids: list[str]) -> list[dict]:
    """Pages FAQ citées (format de la maquette), seulement si elles ont été lues dans la conversation."""
    out = []
    for sid in ids:
        result = turn.read(sid)
        if result is None:
            continue
        d = rag_tools.source_display(sid, turn.conv.bank, result, turn.candidate(sid))
        if d:
            title = f"FAQ Caisse d'Épargne : {d['title']}" + (f" (mise à jour le {d['updated']})" if d["updated"] else "" if d["verified"] else " (fiche non vérifiée)")
            out.append({"title": title, "url": d["url"], "status": "constat" if d["verified"] else "exemple",
                        "has_media": d["has_media"]})
    return out[:MAX_SOURCES_SHOWN]


def _clean_text(text: str, bank: str) -> str:
    """Le texte du modèle ne porte aucun lien : les URL étrangères à la FAQ de la banque sont retirées."""
    host = rag_tools.HOSTS[bank]

    def url(m: re.Match) -> str:
        raw = m.group(0)
        netloc = urlsplit(raw if "://" in raw else "https://" + raw).netloc.lower()
        return raw if netloc == host else "[lien retiré]"

    text = _MD_LINK.sub(r"\1", text)
    text = _URL.sub(url, text)
    text = _SOURCE_LINE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()[:6000]


def _options(data: dict) -> list[str]:
    options = data.get("options") if isinstance(data.get("options"), list) else []
    return [o.strip()[:120] for o in options if isinstance(o, str) and o.strip()][:4]


def _ids(data: dict) -> list[str]:
    ids = data.get("source_ids") if isinstance(data.get("source_ids"), list) else []
    return list(dict.fromkeys(i for i in ids if isinstance(i, str) and rag_tools.SOURCE_ID.match(i)))


# Paramètres caractéristiques de chaque outil, pour un appel écrit en texte par le modèle.
_TOOL_SIGNATURES = [
    (prompt.FINAL_TOOL, {"kind"}), ("read_source", {"source_id"}), ("search_faq", {"query"}),
    ("simuler_credit", {"produit", "montant", "duree_mois"}), ("simuler_epargne", {"produit", "duree_annees"}),
    ("capacite_emprunt", {"revenus_mensuels"}), ("prevoir_taux", {"serie"}), ("catalogue", {"sujet"}),
]


def _inferred_call(content: str | None, n: int):
    data = _json_object(content)
    if not data:
        return None
    for name, keys in _TOOL_SIGNATURES:
        if keys <= data.keys():
            if name == prompt.FINAL_TOOL:
                return None   # réponse finale écrite en texte : contrôlée telle quelle plus bas
            return SimpleNamespace(id=f"texte{n}", type="function",
                                   function=SimpleNamespace(name=name, arguments=json.dumps(data, ensure_ascii=False)))
    return None


def _arguments(call) -> dict | None:
    return _json_object(call.function.arguments or "{}")


def _json_object(text: str | None) -> dict | None:
    try:
        data = json.loads(text or "")
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _tool_call_entry(call) -> dict:
    """Appel d'outil renvoyé tel quel au modèle au tour suivant. Gemini 3 exige la signature de raisonnement
    (extra_content.google.thought_signature) reçue avec l'appel : sans elle, l'API refuse la requête (400)."""
    entry = {"id": call.id, "type": "function", "function": {"name": call.function.name, "arguments": call.function.arguments}}
    extra = getattr(call, "extra_content", None) or (getattr(call, "model_extra", None) or {}).get("extra_content")
    if extra:
        entry["extra_content"] = extra
    return entry


def _tool_message(tool_call_id: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


def _status(step: str, label: str) -> dict:
    return {"type": "status", "step": step, "label": label}


def _reply(kind: str, blocks: list[dict], bank: str) -> dict:
    return {"blocks": blocks, "meta": {"kind": kind, "bank": bank, "intent": "ia"}}
