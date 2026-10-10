"""Simulated crisis manager, to demonstrate the feedback loop without real operator data.

The simulated manager has a HIDDEN preference (by default: never send a team from a Toulouse site to a commune
of Ariège, "routes de montagne mal connues"). It replays crises through LiveSession, refuses the recommendations
that break its preference with a reason, accepts the others. Every entry is logged with simulated=1, so the
review clearly shows these refusals are synthetic.
"""
from __future__ import annotations

from dispatch.learning.memory import DecisionLog
from dispatch.session import LiveSession

TOULOUSE_SITES = ("SITE_04", "SITE_05", "SITE_06")


def default_preference(session: LiveSession, rec: dict) -> tuple[str, str] | None:
    """Return (reason_code, reason_text) to refuse, or None to accept."""
    team = session.team(rec["team"])
    inc = session.pending[rec["incident"]]
    if team.home_site in TOULOUSE_SITES and inc.departement == "Ariège":
        return "terrain", "Équipe urbaine de Toulouse : ne connaît pas les routes de montagne de l'Ariège"
    return None


def run(cfg, crises: list[str], log: DecisionLog, preference=default_preference, budget_ms: int = 20,
        max_steps: int = 20_000) -> dict:
    counts = {"accepted": 0, "rejected": 0}
    for c in crises:
        s = LiveSession.start(cfg, c, budget_ms=budget_ms, log=log)
        s.simulated = True
        for _ in range(max_steps):
            if s.kpis()["finished"]:
                break
            recs = s.recommendations(with_text=False)
            if not recs:
                if s.next_event_time() is None:
                    break
                s.advance()
                continue
            for rec in recs:
                if rec["incident"] not in s.pending or s.team(rec["team"]).current_job:
                    continue
                why = preference(s, rec)
                if why:
                    out = s.reject(rec["team"], rec["incident"], reason_code=why[0], reason_text=why[1])
                    if "proposal_id" in out:
                        s.confirm(out["proposal_id"])
                        counts["rejected"] += 1
                else:
                    s.accept(rec["team"], rec["incident"])
                    counts["accepted"] += 1
                break                                       # recommendations change after each decision
    return counts
