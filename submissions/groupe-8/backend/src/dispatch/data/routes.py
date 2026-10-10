"""Road geometry for the map: the real route between two points (OSRM `route` service, OpenStreetMap roads),
cached on disk (data/cache/routes.json). Falls back to a straight segment if OSRM is unreachable.
Only for drawing; travel TIMES used by the engine come from data/travel.py."""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request

from dispatch.config import ROOT
from dispatch.data.travel import _ssl_context

log = logging.getLogger(__name__)
_PATH = ROOT / "data" / "cache" / "routes.json"
_lock = threading.Lock()
_cache: dict[str, dict] | None = None
_offline_until = 0.0                                             # retry OSRM 60 s after a failure


def _key(a, b) -> str:
    return f"{a[0]:.4f},{a[1]:.4f}>{b[0]:.4f},{b[1]:.4f}"


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(_PATH.read_text()) if _PATH.exists() else {}
    return _cache


def _save() -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(_cache))


def route(a: tuple[float, float], b: tuple[float, float], url: str) -> dict:
    """a, b = (lon, lat). Returns {coordinates: [[lon, lat], ...], source, duration_min, distance_km}."""
    global _offline_until
    cache = _load()
    k = _key(a, b)
    if k in cache:
        return cache[k]
    if time.time() >= _offline_until:
        try:
            q = f"{url.rstrip('/')}/route/v1/driving/{a[0]:.5f},{a[1]:.5f};{b[0]:.5f},{b[1]:.5f}?overview=full&geometries=geojson"
            with urllib.request.urlopen(q, timeout=10, context=_ssl_context()) as r:
                d = json.loads(r.read())
            rt = d["routes"][0]
            out = {"coordinates": rt["geometry"]["coordinates"], "source": "osrm",
                   "duration_min": round(rt["duration"] / 60, 1), "distance_km": round(rt["distance"] / 1000, 1)}
            with _lock:
                cache[k] = out
                _save()
            return out
        except Exception as e:                                   # network down / rate limit: straight line
            log.warning("OSRM route unavailable (%s): straight line", e)
            _offline_until = time.time() + 60
    return {"coordinates": [list(a), list(b)], "source": "straight", "duration_min": None, "distance_km": None}


def routes(pairs: list, url: str, limit: int = 40) -> list[dict]:
    return [route(tuple(a), tuple(b), url) for a, b in pairs[:limit]]
