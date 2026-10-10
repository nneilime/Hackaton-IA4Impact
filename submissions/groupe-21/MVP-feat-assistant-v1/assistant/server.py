"""Serveur HTTP (bibliothèque standard) : interface de la maquette et API de l'assistant Caisse d'Épargne.

  GET  /               interface : front/index.html (maquette Caisse d'Épargne, versions web et mobile)
  GET  /api/health     état du service, sans aucun secret
  POST /api/chat       {conversation_id, message, preferences} -> événements NDJSON :
                       start, status (étapes réelles : recherche, lecture, calcul…), puis result ou error.
                       Les questions simples reçoivent une réponse pré-rédigée sans appel au modèle (0 jeton).
  POST /api/simulate   {produit, montant, duree_mois, …} -> simulation de crédit calculée sur la base fictive
  POST /api/feedback   avis utile / pas utile (compté, jamais journalisé avec son contenu)
  POST /api/transcribe audio du micro (corps brut audio/*) -> {text} : mode vocal des navigateurs sans reconnaissance
  POST /api/tts        {text, lang, rate} -> audio (voix neuronale Microsoft, voix locale Piper en secours)
  POST /api/reset      {conversation_id} -> efface la conversation de la mémoire du serveur

La clé d'API reste côté serveur. Aucun contenu de conversation n'est journalisé ni écrit sur disque.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import threading
import time
import traceback
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from finance import engine as finance

from . import rag_tools, scripted, voice
from .agent import Agent, AgentError, ConversationStore, _result_card
from .rag_tools import BANKS

log = logging.getLogger("assistant")

BANK = "CE"   # l'assistant couvre uniquement la Caisse d'Épargne
FRONT = Path(__file__).resolve().parents[1] / "front"
STATIC = {
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}
PAGES = {"/", "/index.html"}
_INLINE_SCRIPT = re.compile(rb"<script>(.*?)</script>", re.S)
MAX_BODY = 16_000
MAX_AUDIO = 3_000_000   # environ 1 minute de parole compressée
MAX_MESSAGE = 2_000


def csp(script_hashes: list[str]) -> str:
    scripts = " ".join(f"'sha256-{h}'" for h in script_hashes)
    return (f"default-src 'none'; script-src 'self' {scripts}; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-src 'self'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'self'")


class Page:
    """index.html et les empreintes de ses scripts intégrés (relus si le fichier change)."""

    def __init__(self, path: Path = FRONT / "index.html"):
        self.path, self._mtime, self.body, self.csp = path, None, b"", csp([])
        self._lock = threading.Lock()

    def get(self) -> tuple[bytes, str]:
        mtime = self.path.stat().st_mtime
        with self._lock:
            if mtime != self._mtime:
                body = self.path.read_bytes()
                hashes = [base64.b64encode(hashlib.sha256(m).digest()).decode() for m in _INLINE_SCRIPT.findall(body)]
                self.body, self.csp, self._mtime = body, csp(hashes), mtime
            return self.body, self.csp


class RateLimiter:
    """Fenêtre glissante par adresse : protège le crédit de l'API si le serveur est exposé sur un réseau."""

    def __init__(self, limit: int = 20, window: float = 60.0):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            if len(self._hits) > 10_000:
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return True


def make_handler(agent: Agent, store: ConversationStore, limiter: RateLimiter) -> type[BaseHTTPRequestHandler]:
    page = Page()
    speaker = voice.Speaker()
    voice_limiter = RateLimiter(limit=240)   # une réponse lue = plusieurs phrases synthétisées
    feedback_counts = {"up": 0, "down": 0}
    feedback_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "AssistantCE"
        sys_version = ""

        def log_message(self, fmt, *args):  # méthode, chemin et statut : ni adresse IP, ni contenu
            log.info(fmt, *args)

        # -------------------------------------------------------------- routes

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/api/health":
                return self._json(200, {"status": "ok", "llm_configured": agent.configured, "model": agent.model,
                                        "bank": BANKS[BANK], "finance_reference": finance.ref_month(),
                                        "scripted_answers": len(scripted.entries()),
                                        "voice": {"transcription": voice.stt_configured(),
                                                  "synthesis": speaker.available}})
            if path in PAGES:
                body, policy = page.get()
                return self._send(200, body, "text/html; charset=utf-8", cache="no-cache", policy=policy)
            entry = STATIC.get(path)
            if entry is None:
                return self._error(404, "not_found", "Page introuvable.")
            self._send(200, (FRONT / entry[0]).read_bytes(), entry[1], cache="no-cache")

        def do_POST(self):
            path = urlsplit(self.path).path
            if path == "/api/chat":
                return self._chat()
            if path == "/api/reset":
                return self._reset()
            if path == "/api/simulate":
                return self._simulate()
            if path == "/api/feedback":
                return self._feedback()
            if path == "/api/transcribe":
                return self._transcribe()
            if path == "/api/tts":
                return self._tts()
            self._error(404, "not_found", "Page introuvable.")

        def _chat(self):
            body = self._read_json()
            if body is None:
                return
            message, cid = body.get("message"), body.get("conversation_id")
            prefs = body.get("preferences") if isinstance(body.get("preferences"), dict) else {}
            if not isinstance(message, str) or not message.strip():
                return self._error(400, "empty_message", "Votre message est vide.")
            message = message.strip()
            if len(message) > MAX_MESSAGE:
                return self._error(413, "message_too_long", f"Votre message dépasse {MAX_MESSAGE} caractères : raccourcissez-le.")
            if not isinstance(cid, str) or len(cid) > 64:
                cid = None
            if not limiter.allow(self.client_address[0]):
                return self._error(429, "rate_limited", "Trop de messages en peu de temps : patientez une minute.")
            conv, reset = store.open(cid, BANK)
            if not conv.lock.acquire(blocking=False):
                return self._error(409, "busy", "Une réponse est déjà en cours dans cette conversation.")
            try:
                self._stream(conv, reset, message, bool(prefs.get("simple")))
            finally:
                conv.lock.release()

        def _stream(self, conv, reset, message, simple):
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self._security_headers()
            self.end_headers()
            gone = threading.Event()

            def emit(event: dict) -> None:
                if gone.is_set():
                    return
                try:
                    self.wfile.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
                    self.wfile.flush()
                except OSError:  # navigateur fermé ou requête abandonnée
                    gone.set()

            emit({"type": "start", "conversation_id": conv.id, "context_reset": reset})
            entry = None if simple else scripted.match(message)
            if entry is not None:   # question simple : réponse pré-rédigée, aucun jeton consommé
                reply = scripted.reply(entry)
                store.remember(conv, message, reply["blocks"][0]["text"])
                log.info("réponse pré-rédigée id=%s (0 jeton)", entry["id"])
                return emit({"type": "result", "conversation_id": conv.id, "response": reply})
            try:
                reply = agent.answer(conv, message, simple=simple, emit=emit, cancelled=gone.is_set)
                emit({"type": "result", "conversation_id": conv.id, "response": reply})
            except AgentError as e:
                emit({"type": "error", "code": e.code, "message": e.message})
            except Exception as e:  # dernier recours : jamais de détail interne dans le navigateur ni de contenu au journal
                log.error("erreur interne %s\n%s", type(e).__name__, "".join(traceback.format_tb(e.__traceback__)))
                emit({"type": "error", "code": "internal",
                      "message": "Une erreur technique est survenue. Réessayez dans quelques instants."})

        def _reset(self):
            body = self._read_json()
            if body is None:
                return
            if isinstance(body.get("conversation_id"), str):
                store.delete(body["conversation_id"])
            self._json(200, {"ok": True})

        def _simulate(self):
            """Simulation de crédit pour le parcours guidé de la maquette (formulaire), sans modèle."""
            body = self._read_json()
            if body is None:
                return
            if not limiter.allow(self.client_address[0]):
                return self._error(429, "rate_limited", "Trop de demandes en peu de temps : patientez une minute.")
            allowed = ("produit", "montant", "duree_mois", "age", "fumeur", "apport", "revenus_mensuels",
                       "charges_mensuelles", "debut")
            try:
                data = finance.simulate_loan(**{k: body[k] for k in allowed if body.get(k) not in (None, "")})
            except finance.FinanceError as e:
                return self._error(400, "invalid_simulation", str(e))
            except TypeError:
                return self._error(400, "invalid_simulation", "Indiquez au moins le produit, le montant et la durée.")
            self._json(200, {"result": _result_card(data), "data": data})

        def _feedback(self):
            body = self._read_json()
            if body is None:
                return
            value = body.get("value")
            if value in feedback_counts:
                with feedback_lock:
                    feedback_counts[value] += 1
                log.info("avis reçu (%s) : %d utiles, %d pas utiles depuis le démarrage", value,
                         feedback_counts["up"], feedback_counts["down"])
            self._json(200, {"ok": True})

        def _transcribe(self):
            """Audio du micro → texte. L'audio n'est ni conservé ni journalisé."""
            ctype = self.headers.get("Content-Type", "")
            if not ctype.startswith("audio/"):
                return self._error(415, "bad_request", "Requête invalide.")
            if not self._same_origin():
                return self._error(403, "forbidden", "Requête refusée.")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if not 0 < length <= MAX_AUDIO:
                return self._error(413, "too_large", "Enregistrement trop long : parlez moins d'une minute.")
            if not voice_limiter.allow(self.client_address[0]):
                return self._error(429, "rate_limited", "Trop de demandes en peu de temps : patientez une minute.")
            audio = self.rfile.read(length)
            lang = urlsplit(self.path).query.removeprefix("lang=")[:2] or "fr"
            ext = {"audio/ogg": "ogg", "audio/mp4": "m4a", "audio/wav": "wav", "audio/mpeg": "mp3"}.get(ctype.split(";")[0], "webm")
            try:
                text = voice.transcribe(audio, f"micro.{ext}", lang)
            except voice.VoiceError as e:
                return self._error(503, "voice_unavailable", str(e))
            self._json(200, {"text": text})

        def _tts(self):
            """Texte → audio : voix neuronale (MP3) ou, en secours, voix locale Piper (WAV)."""
            body = self._read_json()
            if body is None:
                return
            if not voice_limiter.allow(self.client_address[0]):
                return self._error(429, "rate_limited", "Trop de demandes en peu de temps : patientez une minute.")
            text = body.get("text")
            if not isinstance(text, str) or not re.search(r"\w", text):   # vide ou ponctuation seule
                return self._error(400, "empty_text", "Rien à lire.")
            try:
                rate = float(body.get("rate") or 1)
            except (TypeError, ValueError):
                rate = 1.0
            try:
                audio, mime = speaker.synthesize(text, str(body.get("lang") or "fr")[:2], rate)
            except voice.VoiceError as e:
                return self._error(503, "voice_unavailable", str(e))
            except Exception as e:  # voix introuvable, téléchargement impossible… : jamais de détail interne
                log.error("synthèse vocale en échec : %s", type(e).__name__)
                return self._error(503, "voice_unavailable", "La lecture à voix haute n'est pas disponible pour le moment.")
            self._send(200, audio, mime)

        def _same_origin(self) -> bool:
            origin = self.headers.get("Origin")
            return not origin or urlsplit(origin).netloc == self.headers.get("Host")

        # -------------------------------------------------------------- utilitaires

        def _read_json(self) -> dict | None:
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                self._error(415, "bad_request", "Requête invalide.")
                return None
            if not self._same_origin():
                self._error(403, "forbidden", "Requête refusée.")
                return None
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if not 0 <= length <= MAX_BODY:
                self._error(413, "too_large", "Requête trop volumineuse.")
                return None
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:  # JSON invalide ou encodage incorrect
                data = None
            if not isinstance(data, dict):
                self._error(400, "bad_request", "Requête invalide.")
                return None
            return data

        def _security_headers(self, policy: str | None = None):
            self.send_header("Content-Security-Policy", policy or csp([]))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "SAMEORIGIN")   # la vue mobile affiche la page dans un cadre
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")

        def _send(self, status: int, body: bytes, content_type: str, cache: str = "no-store", policy: str | None = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self._security_headers(policy)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: dict):
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _error(self, status: int, code: str, message: str):
            self._json(status, {"error": {"code": code, "message": message}})

    return Handler


def create_server(agent: Agent, host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(agent, ConversationStore(), RateLimiter()))


def run(settings) -> None:
    from .llm import ChatLLM

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)

    agent = Agent(ChatLLM.from_env(settings.model, settings.reasoning_effort))
    rag_tools.retriever()   # index chargé au démarrage : la première question ne l'attend pas
    httpd = create_server(agent, settings.host, settings.port)
    shown = "localhost" if settings.host in ("127.0.0.1", "0.0.0.0", "") else settings.host
    print(f"Assistant IA Caisse d'Épargne (prototype) : http://{shown}:{httpd.server_port}/  "
          f"[modèle {agent.llm.model} via Gemini, secours {agent.llm.fallback_model}]", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
