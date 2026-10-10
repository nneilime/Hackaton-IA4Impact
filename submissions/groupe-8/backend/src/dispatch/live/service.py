"""LiveCrisis: one crisis managed in real time.

  clock     H0 = the moment the crisis is opened (real time, Europe/Paris). `speed` > 1 runs the clock faster from
            there (demo); at 1 it is the wall clock.
  events    incident_reported, team_on_site, repair_done, team_unavailable. They only mark the plan as stale: the
            ticker re-plans once per tick, so a burst of alerts costs one re-plan.
  decisions nothing is dispatched until the manager validates the plan (or a line of it). Each dispatch is published
            (`dispatches`) for the field, which then reports arrival and end of repair.
  history   snapshots of the front-end contract, one every `history_minutes` of crisis time and one after each
            decision: the timeline and the journal of the dashboard.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime

from dispatch.adapters import contract as C
from dispatch.copilot.translate import reason_to_modifiers
from dispatch.data.loaders import load_postes
from dispatch.engine.modifiers import Force, TeamUnavailable
from dispatch.engine.shifts import EPS
from dispatch.engine.types import Incident
from dispatch.session import LiveSession

EVENT_TYPES = ("incident_reported", "team_on_site", "repair_done", "team_unavailable")


class LiveClock:
    def __init__(self, speed: float = 1.0, start: datetime | None = None):
        self.speed = speed
        self.wall0 = time.time()
        self.t0 = start or datetime.now(C.PARIS).replace(tzinfo=None, microsecond=0)   # naive Paris time, like the CSVs

    def now_h(self) -> float:
        return self.speed * (time.time() - self.wall0) / 3600

    def info(self) -> dict:
        return {"start": C.iso(self.t0, 0), "nowHours": round(self.now_h(), 5), "speed": self.speed,
                "serverTime": datetime.now(C.PARIS).isoformat()}


class LiveCrisis:
    def __init__(self, cfg, log=None, speed: float = 1.0, label: str = ""):
        self.cfg, self.log, self.label = cfg, log, label
        lv = cfg.live
        self.clock = LiveClock(speed)
        self.s = LiveSession.empty(cfg, self.clock.t0, budget_ms=lv.budget_ms, log=log)
        self.site_names = {x.id: x.commune for x in self.s.sites}
        self.lock = threading.RLock()
        self.version = 0                                     # bumped on every change the dashboard must show
        self.history: list[dict] = []
        self.dirty = False
        self._next_history_h = 0.0
        self._rec_cache: tuple[int, list[dict]] | None = None
        self._postes = load_postes(cfg)

    # ------------------------------------------------------------------ events from the field
    def event(self, ev: dict) -> dict:
        kind = ev.get("type")
        if kind not in EVENT_TYPES:
            raise ValueError(f"type d'événement inconnu : {kind}")
        with self.lock:
            self._sync()
            now = self.s.now
            if kind == "incident_reported":
                self.s.report(self._incident(ev, now))
            elif kind == "team_on_site":
                self.s.arrived(ev["team"], ev["incident"], now)
            elif kind == "repair_done":
                self.s.repaired(ev["team"], ev["incident"], now)
            elif kind == "team_unavailable":
                until = ev.get("until_h")
                self.s.rules.append(TeamUnavailable(team=ev["team"], from_h=now, until_h=until,
                                                    reason=ev.get("reason", "signalé par le terrain")))
            self.dirty = True
            return {"ok": True, "at_h": now}

    def _incident(self, ev: dict, now: float) -> Incident:
        """An alert gives the substation; everything else about it comes from the substation data."""
        p = self._postes.loc[ev["poste_id"]]
        return Incident(id=ev["id"], poste_id=ev["poste_id"], lat=float(p.latitude), lon=float(p.longitude),
                        customers=int(p.nb_clients), sensitive=bool(p.poste_avec_client_sensible), reported_at=now,
                        est_duration=float(ev["est_duration_h"]), cause=ev.get("cause", ""), commune=str(p.commune),
                        departement=str(p.departement))

    # ------------------------------------------------------------------ the ticker (called every second)
    def tick(self) -> None:
        with self.lock:
            self._sync()
            if self.dirty or self._due():
                self._replan()
            if self.s.incidents and self.s.now >= self._next_history_h:
                self._record()

    def _sync(self) -> None:
        self.s.now = self.clock.now_h()
        self.s.hold_overruns()

    def _due(self) -> bool:
        """Something changed with time alone: a planned departure is now due, or a team's shift starts / ends."""
        if not self.s.plan:
            return False
        recs = self._recs()
        due = {r["team"] for r in self.s.recommendations(with_text=False)}
        return due != {r["team"] for r in recs}

    def _replan(self) -> None:
        self.s.replan(force=True)
        self.dirty = False
        self._rec_cache = None
        self.version += 1

    def _recs(self) -> list[dict]:
        """Recommendations of the current plan (with facts and text), computed once per plan version."""
        if self._rec_cache is None or self._rec_cache[0] != self.s.plan_version:
            recs = self.s.recommendations() if self.s.plan else []
            self._rec_cache = (self.s.plan_version, recs)
        return self._rec_cache[1]

    # ------------------------------------------------------------------ dashboard state
    def snapshot(self, decisions: list[dict] | None = None) -> dict:
        t = self.s.now
        recs = [C.recommendation(self.s, r, 0) for r in self._recs()]
        for r in recs:
            r["id"] = f"live-{r['incidentId']}"            # stable while the line stays in the plan
        return C.snapshot(self.s, t, C.iso(self.clock.t0, t), recs, decisions or [], self.site_names)

    def _record(self, decisions: list[dict] | None = None) -> None:
        self.history.append(self.snapshot(decisions))
        step = self.cfg.live.history_minutes / 60
        self._next_history_h = (int(self.s.now / step + EPS) + 1) * step
        self.version += 1

    def state(self, have: int = 0) -> dict:
        with self.lock:
            self._sync()
            return {"version": self.version, "clock": self.clock.info(), "label": self.label,
                    "snapshot": self.snapshot(), "history": self.history[have:], "historyLength": len(self.history),
                    "dispatchesPending": sum(1 for _ in self.s.in_progress)}

    def meta(self) -> dict:
        counts: dict[str, int] = {}
        for t in self.s.teams:
            counts[t.home_site] = counts.get(t.home_site, 0) + 1
        return {"crisisId": "LIVE", "mode": "live", "label": self.label, "start": C.iso(self.clock.t0, 0),
                "stepMinutes": self.cfg.live.history_minutes, "speed": self.clock.speed,
                "sites": [{"id": x.id, "name": x.commune, "lon": x.lon, "lat": x.lat, "teams": counts.get(x.id, 0)}
                          for x in self.s.sites],
                "strategies": [{"id": "ours", "label": "Copilote", "description": "Moteur optimisé, en temps réel"}],
                "roster": C.roster(self.s)}

    # ------------------------------------------------------------------ manager decisions
    def accept(self, assignments: list[dict], reason: str | None = None) -> dict:
        """Validate the plan (or some lines): each {incidentId, teamId} is dispatched now if the team is free, else
        the team is told to take it next (Force). Lines no longer valid (incident taken, team gone) are skipped."""
        with self.lock:
            self._sync()
            idle = {t.id for t in self.s.idle_on_duty()}
            recommended = {r["team"]: r["incident"] for r in self._recs()}
            done, decisions = 0, []
            for a in assignments:
                inc, team = a["incidentId"], a["teamId"]
                if inc not in self.s.pending or any(d["teamId"] == team for d in decisions):
                    continue
                kind = "accepted" if recommended.get(team) == inc else "overridden"
                if team in idle:
                    self.s._commit(team, inc)
                else:
                    self.s.rules.append(Force(team=team, incident=inc, reason=reason or "", scope="incident"))
                if self.log is not None:
                    self.log.append(self.s._log_entry(team, inc, kind if kind == "accepted" else "modified",
                                                      reason_text=a.get("reason") or reason))
                rec_team = next((t for t, i in recommended.items() if i == inc), team)
                decisions.append({"incidentId": inc, "teamId": team, "kind": kind, "recommendedTeamId": rec_team,
                                  **({"reason": a["reason"]} if a.get("reason") else {})})
                done += 1
            if done:
                self._replan()
                self._record(decisions)
            return {"dispatched": done}

    def refuse(self, incident: str, team: str, code: str | None, text: str | None) -> dict:
        with self.lock:
            self._sync()
            if incident not in self.s.pending:
                raise LookupError("incident déjà pris en charge")
            ctx_info = self.s._context_info(team, incident)
        translated = reason_to_modifiers(code, text, ctx_info, self.cfg)     # LLM call: outside the lock (seconds)
        with self.lock:
            if incident not in self.s.pending:
                raise LookupError("incident déjà pris en charge")
            return self.s.reject(team, incident, code, text, translated=translated)

    def confirm(self, pid: int) -> None:
        with self.lock:
            self._sync()
            self.s.confirm(pid)
            self._replan()

    def add_rules(self, mods: list) -> None:
        with self.lock:
            self.s.rules.extend(mods)
            self._replan()

    def remove_rule(self, index: int) -> None:
        with self.lock:
            del self.s.rules[index]
            self._replan()

    def dispatches_after(self, seq: int) -> list[dict]:
        with self.lock:
            return [{**d, "depart_at": C.iso(self.clock.t0, d["depart_h"])} for d in self.s.dispatches if d["seq"] > seq]


class Ticker:
    """Background thread: keeps the live crisis on the real clock (re-plan when needed, history)."""

    def __init__(self, get_crisis, period_s: float = 1.0):
        self.get, self.period = get_crisis, period_s
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="live-ticker")

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self.period):
            try:
                self.get().tick()
            except Exception:                                        # never kill the ticker: log and go on
                import logging
                logging.getLogger(__name__).exception("live tick failed")
