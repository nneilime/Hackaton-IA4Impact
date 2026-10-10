# SPDX-License-Identifier: AGPL-3.0-or-later
"""Client HTTP sobre et respectueux pour interroger les sources officielles.

Objectif : faire le moins de requêtes possible, de façon honnête, pour ne jamais surcharger une source.
- Un User-Agent qui dit qui nous sommes (aucun déguisement en navigateur).
- Jeux de données ouverts téléchargés EN BLOC (quelques requêtes), jamais produit par produit.
- Requêtes conditionnelles (ETag / Last-Modified) : si la source n'a pas changé, rien n'est retéléchargé (réponse 304).
- Pause minimale entre deux requêtes vers le même serveur, et reprise polie quand un serveur demande d'attendre (429, 503).
- Journal de CHAQUE requête sortante (hôte, adresse, statut, octets) : le nombre de requêtes se vérifie, il ne se promet pas.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import config

USER_AGENT = "VeilleReglementairePPP/1.0 (hackathon; collecte respectueuse de données ouvertes)"
MIN_SECONDS_BETWEEN_REQUESTS_TO_SAME_HOST = 2.0
MAX_TRIES = 4
RETRYABLE_STATUS = (429, 503)
REQUEST_LOG = config.RAW / "_requests.jsonl"

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
_last_request_time_by_host: dict[str, float] = {}


# ── Journal des requêtes ─────────────────────────────────────────────────────

def log_request(url: str, status: int, size_bytes: int, seconds: float) -> None:
    config.RAW.mkdir(parents=True, exist_ok=True)
    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "host": urlparse(url).netloc,
             "url": url, "status": status, "bytes": size_bytes, "seconds": round(seconds, 2)}
    with REQUEST_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_request_log(since: str | None = None) -> list[dict]:
    if not REQUEST_LOG.exists():
        return []
    entries = [json.loads(line) for line in REQUEST_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [e for e in entries if since is None or e["at"] >= since]


def summarize_requests(entries: list[dict]) -> dict:
    """Par serveur : nombre de requêtes, octets reçus, réponses « inchangé » (304)."""
    per_host: dict[str, dict] = defaultdict(lambda: {"requests": 0, "megabytes": 0.0, "not_modified": 0})
    for entry in entries:
        host = per_host[entry["host"]]
        host["requests"] += 1
        host["megabytes"] += entry["bytes"] / 1e6
        host["not_modified"] += entry["status"] == 304
    for host in per_host.values():
        host["megabytes"] = round(host["megabytes"], 1)
    return {"total_requests": len(entries), "total_megabytes": round(sum(e["bytes"] for e in entries) / 1e6, 1),
            "not_modified": sum(e["status"] == 304 for e in entries), "per_host": dict(per_host)}


# ── Requêtes ─────────────────────────────────────────────────────────────────

def wait_turn(host: str) -> None:
    """Respecte une pause minimale entre deux requêtes vers le même serveur."""
    elapsed = time.time() - _last_request_time_by_host.get(host, 0)
    if elapsed < MIN_SECONDS_BETWEEN_REQUESTS_TO_SAME_HOST:
        time.sleep(MIN_SECONDS_BETWEEN_REQUESTS_TO_SAME_HOST - elapsed)


def seconds_to_wait(response: requests.Response, attempt: int) -> float:
    """Le serveur dit combien attendre (Retry-After) ; sinon on double l'attente à chaque essai."""
    retry_after = response.headers.get("Retry-After", "")
    return float(retry_after) if retry_after.isdigit() else 5.0 * 2 ** attempt


def send_request(url: str, headers: dict | None = None, stream: bool = False) -> requests.Response:
    host = urlparse(url).netloc
    for attempt in range(MAX_TRIES):
        wait_turn(host)
        started = time.time()
        response = _session.get(url, headers=headers or {}, stream=stream, timeout=120)
        _last_request_time_by_host[host] = time.time()
        body_will_be_streamed = stream and response.status_code == 200
        if not body_will_be_streamed:              # un corps diffusé est journalisé par `download`, avec sa vraie taille
            log_request(url, response.status_code, 0 if stream else len(response.content), time.time() - started)
        if response.status_code not in RETRYABLE_STATUS:
            response.started_at = started
            return response
        time.sleep(seconds_to_wait(response, attempt))
    response.raise_for_status()
    return response


def get_json(url: str) -> dict:
    response = send_request(url)
    response.raise_for_status()
    return response.json()


def download(url: str, destination: Path) -> dict:
    """Télécharge `url` vers `destination` seulement si la source a changé depuis la dernière fois.

    Retourne {"changed": bool, "bytes": int}. Les validateurs (ETag, Last-Modified) sont gardés à côté du fichier.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    validators_file = destination.with_name(destination.name + ".validators.json")
    headers = {}
    if destination.exists() and validators_file.exists():
        saved = json.loads(validators_file.read_text())
        if saved.get("etag"):
            headers["If-None-Match"] = saved["etag"]
        if saved.get("last_modified"):
            headers["If-Modified-Since"] = saved["last_modified"]

    response = send_request(url, headers, stream=True)
    if response.status_code == 304:
        return {"changed": False, "bytes": 0}
    response.raise_for_status()

    partial_file = destination.with_name(destination.name + ".part")      # écriture atomique
    with partial_file.open("wb") as file:
        for chunk in response.iter_content(1 << 20):
            file.write(chunk)
    partial_file.rename(destination)
    log_request(url, response.status_code, destination.stat().st_size, time.time() - response.started_at)
    validators_file.write_text(json.dumps({"etag": response.headers.get("ETag"),
                                           "last_modified": response.headers.get("Last-Modified")}))
    return {"changed": True, "bytes": destination.stat().st_size}
