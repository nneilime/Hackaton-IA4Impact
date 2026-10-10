"""The simulated world: alerts of a past crisis, then the field teams' reports for every validated trip."""
from __future__ import annotations

import heapq
import json
import math
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def call(self, path: str, body=None, method: str | None = None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(f"{self.base}{path}", data=data, method=method or ("POST" if body is not None else "GET"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())


@dataclass
class Alert:
    at_h: float                     # hours after the start of the crisis
    id: str
    poste_id: str
    est_duration_h: float
    cause: str


@dataclass(order=True)
class FieldReport:
    at_h: float
    seq: int
    event: dict = field(compare=False)


class Field:
    """Sends the alerts on time and answers every dispatch with 'team on site' then 'repair done'.

    travel_noise / duration_noise: lognormal sigma on the engine's travel estimate and on the repair estimate
    (0 = the field does exactly what was estimated)."""

    def __init__(self, api: Api, alerts: list[Alert], travel_noise: float = 0.0, duration_noise: float = 0.0,
                 seed: int = 0, log=print):
        self.api, self.log = api, log
        self.alerts = sorted(alerts, key=lambda a: a.at_h)
        self.travel_noise, self.duration_noise = travel_noise, duration_noise
        self.rng = random.Random(seed)
        self.reports: list[FieldReport] = []
        self.sent = 0
        self.last_dispatch = 0
        self.restored = 0
        self._seq = 0
        self.speed = 1.0
        self._wall0 = time.time()
        self._h0 = 0.0

    # ---- clock: the backend's; estimated locally between two reads
    def sync_clock(self) -> None:
        c = self.api.call("/live/clock")
        self.speed, self._wall0, self._h0 = c["speed"], time.time(), c["nowHours"]

    def now_h(self) -> float:
        return self._h0 + self.speed * (time.time() - self._wall0) / 3600

    def _noisy(self, x: float, sigma: float) -> float:
        return x if not sigma else x * math.exp(self.rng.gauss(-sigma * sigma / 2, sigma))

    def _report(self, at_h: float, event: dict) -> None:
        self._seq += 1
        heapq.heappush(self.reports, FieldReport(at_h, self._seq, event))

    # ---- one step of the world
    def step(self) -> None:
        now = self.now_h()
        due = []
        while self.sent < len(self.alerts) and self.alerts[self.sent].at_h <= now:
            a = self.alerts[self.sent]
            due.append({"type": "incident_reported", "id": a.id, "poste_id": a.poste_id,
                        "est_duration_h": a.est_duration_h, "cause": a.cause})
            self.sent += 1
        if due:
            self.api.call("/live/events", due)
            self.log(f"[{self._clock(now)}] {len(due)} alerte(s) envoyée(s) ({self.sent}/{len(self.alerts)})")
        for d in self.api.call(f"/live/dispatches?after={self.last_dispatch}"):
            self.last_dispatch = d["seq"]
            arrive = d["depart_h"] + self._noisy(d["travel_h"], self.travel_noise)
            done = arrive + self._noisy(d["repair_h"], self.duration_noise)
            self._report(arrive, {"type": "team_on_site", "team": d["team"], "incident": d["incident"]})
            self._report(done, {"type": "repair_done", "team": d["team"], "incident": d["incident"]})
            self.log(f"[{self._clock(now)}] départ {d['team']} -> {d['incident']} (sur place vers {self._clock(arrive)})")
        while self.reports and self.reports[0].at_h <= now:
            r = heapq.heappop(self.reports)
            self.api.call("/live/events", r.event)
            if r.event["type"] == "repair_done":
                self.restored += 1
                self.log(f"[{self._clock(now)}] réparé : {r.event['incident']} ({self.restored}/{len(self.alerts)})")

    def finished(self) -> bool:
        return self.sent == len(self.alerts) and not self.reports and self.restored >= len(self.alerts)

    def _clock(self, h: float) -> str:
        return f"H0+{int(h)}h{int((h % 1) * 60):02d}"

    def run(self, poll_s: float = 0.5) -> None:
        self.sync_clock()
        last_sync = time.time()
        while not self.finished():
            try:
                self.step()
            except urllib.error.URLError as e:
                self.log(f"API injoignable ({e}), nouvel essai…")
                time.sleep(2)
                continue
            if time.time() - last_sync > 30:
                self.sync_clock()
                last_sync = time.time()
            time.sleep(poll_s)
        self.log("Crise terminée : toutes les pannes sont réparées.")
