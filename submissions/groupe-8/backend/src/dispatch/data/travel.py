"""Travel-time models (config `travel.mode`):

  straight   distance x detour / speed (one speed everywhere)
  simulated  realistic offline model (default): each end of a trip is urban (Toulouse), mountain (Pyrénées,
             south of `mountain.lat_below`) or plain, with its own speed and road-detour factor; plus a fixed
             start-up overhead and a global storm factor. Deterministic, no network.
  osrm       real road times from an OSRM server (OpenStreetMap), cached on disk; falls back to `simulated`
             for any pair it cannot get. Flood closures still come from operator rules (zone_inaccessible,
             travel_factor) on top of any mode.
"""
from __future__ import annotations

import json
import logging
import ssl
import urllib.request
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Works on scalars or numpy arrays (broadcasting)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def _zone_params(lat, lon, cfg):
    """(local speed, main-road speed, detour) arrays for each point: urban (Toulouse), mountain, or plain."""
    z = cfg.travel.zones
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    shape = np.broadcast(lat, lon).shape
    local = np.full(shape, float(z.plain.local_kmh)); main = np.full(shape, float(z.plain.main_kmh))
    det = np.full(shape, float(z.plain.detour))
    for name, mask in (("mountain", lat < z.mountain.lat_below),
                       ("urban", haversine_km(lat, lon, z.urban.centre[0], z.urban.centre[1]) < z.urban.radius_km)):
        zz = getattr(z, name)
        local = np.where(mask, zz.local_kmh, local); main = np.where(mask, zz.main_kmh, main)
        det = np.where(mask, zz.detour, det)
    return local, main, det


def travel_hours(lat1, lon1, lat2, lon2, cfg):
    """Travel time in hours. `straight`: one speed. `simulated`: the first/last `local_km` of road at each end's
    local speed, the rest on main roads (harmonic mean of both ends), plus a start-up overhead and storm factor."""
    d = haversine_km(lat1, lon1, lat2, lon2)
    t = cfg.travel
    if getattr(t, "mode", "straight") == "straight":
        return d * t.detour_factor / t.speed_kmh
    l1, m1, d1 = _zone_params(lat1, lon1, cfg)
    l2, m2, d2 = _zone_params(lat2, lon2, cfg)
    road = d * (d1 + d2) / 2
    local = np.minimum(road, t.local_km)
    hours = local / 2 / l1 + local / 2 / l2 + (road - local) * (1 / m1 + 1 / m2) / 2
    hours = np.where(d > 0.05, hours + t.overhead_min / 60, 0.0)
    return hours * t.storm_factor


def travel_matrix(origins: np.ndarray, destinations: np.ndarray, cfg) -> np.ndarray:
    """origins (n, 2) and destinations (m, 2) as [lat, lon] -> (n, m) matrix of hours."""
    base = travel_hours(origins[:, None, 0], origins[:, None, 1], destinations[None, :, 0], destinations[None, :, 1], cfg)
    if getattr(cfg.travel, "mode", "") != "osrm":
        return base
    return OsrmCache.get(cfg).matrix(origins, destinations, fallback=base) * cfg.travel.storm_factor


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


class OsrmCache:
    """Pairwise road durations from an OSRM `table` service, cached in data/cache/osrm.json (rounded coords)."""
    _instance = None

    def __init__(self, url: str, path: Path, max_coords: int = 90):
        self.url, self.path, self.max_coords = url.rstrip("/"), path, max_coords
        self.cache: dict[str, float] = json.loads(path.read_text()) if path.exists() else {}
        self.offline = False

    @classmethod
    def get(cls, cfg) -> "OsrmCache":
        if cls._instance is None:
            from dispatch.config import ROOT
            cls._instance = cls(cfg.travel.osrm_url, ROOT / "data" / "cache" / "osrm.json")
        return cls._instance

    @staticmethod
    def _key(a, b) -> str:
        return f"{a[0]:.4f},{a[1]:.4f}>{b[0]:.4f},{b[1]:.4f}"

    def _fetch(self, src: list, dst: list) -> None:
        pts = src + dst
        coords = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in pts)
        url = (f"{self.url}/table/v1/driving/{coords}?sources={';'.join(map(str, range(len(src))))}"
               f"&destinations={';'.join(map(str, range(len(src), len(pts))))}&annotations=duration")
        with urllib.request.urlopen(url, timeout=20, context=_ssl_context()) as r:
            data = json.loads(r.read())
        for i, a in enumerate(src):
            for j, b in enumerate(dst):
                v = data["durations"][i][j]
                if v is not None:
                    self.cache[self._key(a, b)] = v / 3600

    def matrix(self, origins: np.ndarray, destinations: np.ndarray, fallback: np.ndarray) -> np.ndarray:
        o = [tuple(map(float, x)) for x in origins]; d = [tuple(map(float, x)) for x in destinations]
        missing = sorted({(i, j) for i in range(len(o)) for j in range(len(d)) if self._key(o[i], d[j]) not in self.cache})
        if missing and not self.offline:
            half = self.max_coords // 2
            src_ids = sorted({i for i, _ in missing}); dst_ids = sorted({j for _, j in missing})
            try:
                for a in range(0, len(src_ids), half):
                    for b in range(0, len(dst_ids), half):
                        self._fetch([o[i] for i in src_ids[a:a + half]], [d[j] for j in dst_ids[b:b + half]])
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps(self.cache))
            except Exception as e:                      # network down / rate-limited: use the simulated model
                log.warning("OSRM unavailable (%s): falling back to the simulated travel model", e)
                self.offline = True
        out = fallback.copy()
        for i in range(len(o)):
            for j in range(len(d)):
                v = self.cache.get(self._key(o[i], d[j]))
                if v is not None:
                    out[i, j] = v
        return out
