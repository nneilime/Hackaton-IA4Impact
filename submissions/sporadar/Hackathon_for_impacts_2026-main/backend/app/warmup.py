"""Préchauffage : calcule en arrière-plan les réponses des requêtes de démo (docs/demo_cases.md).

Pourquoi : certaines réponses (surtout /opportunities, 8 à 15 s à froid) sont gardées en mémoire par `services.cached`.
Sans préchauffage, la première personne qui pose une question de démo attend ; avec lui, elle trouve le résultat prêt.

Comment :
- au démarrage de l'API (voir `lifespan` dans main.py), un thread lit toutes les requêtes `GET /...` écrites entre
  accents graves dans docs/demo_cases.md (celles qui contiennent <id> sont ignorées : il faut un vrai identifiant) ;
- il les envoie à l'application elle-même, en mémoire (pas de réseau, pas de dépendance en plus), exactement comme
  le ferait un client : les routes, la validation et les caches sont donc les vrais ;
- il recommence avant l'expiration des caches (WARMUP_REFRESH_SECONDS), pour que la démo reste rapide.

Lecture seule sur la base. Désactiver : variable d'environnement WARMUP=0. Le préchauffage ne bloque jamais le
démarrage et une erreur n'arrête jamais l'API (elle est seulement écrite dans les logs).
"""
import asyncio
import os
import re
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

from . import services

DEMO_FILE = Path(__file__).resolve().parents[2] / "docs" / "demo_cases.md"
# Doit rester plus court que la durée de vie des caches de opportunities.py (OPP_CACHE_SECONDS)
WARMUP_REFRESH_SECONDS = 1500
REFRESH_MAX_AGE = 60     # pendant un rafraîchissement, une valeur plus vieille que cela est recalculée


def demo_requests(path=DEMO_FILE):
    """Chemins `/route?paramètres` trouvés dans le fichier de démo, sans doublon, dans l'ordre. Fichier absent -> []."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    found = []
    for match in re.finditer(r"`GET (/[^`\s][^`]*)`", text):
        url = match.group(1).strip()
        if "<" in url or url in found:
            continue
        route, _, query = url.partition("?")
        # Les exemples contiennent des espaces et des parenthèses : on les encode proprement
        found.append(route + ("?" + urlencode(parse_qsl(query, keep_blank_values=True)) if query else ""))
    return found


async def _get(app, url):
    """Envoie un GET à l'application en mémoire et renvoie le code HTTP."""
    route, _, query = url.partition("?")
    headers = [(b"host", b"localhost")]
    key = os.environ.get("API_KEY", "").strip()
    if key:
        headers.append((b"x-api-key", key.encode()))
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "http",
             "path": route, "raw_path": route.encode(), "root_path": "", "query_string": query.encode(),
             "headers": headers, "server": ("localhost", 80), "client": ("127.0.0.1", 0)}
    status = {"code": None}
    sent_body = {"done": False}

    async def receive():
        if not sent_body["done"]:
            sent_body["done"] = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]

    await app(scope, receive, send)
    return status["code"]


def warm_once(app, urls, refresh):
    """Une passe sur toutes les requêtes. `refresh` : recalculer les valeurs déjà gardées en mémoire si elles vieillissent."""
    services.REFRESH_MAX_AGE = REFRESH_MAX_AGE if refresh else None
    try:
        for url in urls:
            started = time.time()
            try:
                code = asyncio.run(_get(app, url))
            except Exception as exc:    # une requête qui échoue ne doit pas arrêter les autres
                code = f"erreur {type(exc).__name__}"
            print(f"[warmup] GET {url} -> {code} en {time.time() - started:.1f} s", file=sys.stderr, flush=True)
    finally:
        services.REFRESH_MAX_AGE = None


def _loop(app, urls):
    refresh = False
    while True:
        warm_once(app, urls, refresh)
        refresh = True
        time.sleep(WARMUP_REFRESH_SECONDS)


def start(app):
    """Démarre le thread de préchauffage (daemon : il ne retient pas l'arrêt de l'API). Renvoie le thread ou None."""
    if os.environ.get("WARMUP", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    urls = demo_requests()
    if not urls:
        print("[warmup] aucune requête de démo trouvée (docs/demo_cases.md absent ?) : rien à préchauffer", file=sys.stderr, flush=True)
        return None
    thread = threading.Thread(target=_loop, args=(app, urls), name="warmup", daemon=True)
    thread.start()
    return thread
