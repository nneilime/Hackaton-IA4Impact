"""Engine objects -> the front-end contract (frontend/src/data/contract.ts): camelCase, ISO times with the
Europe/Paris offset (the CSV times are local French times)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dispatch.engine.shifts import is_on_duty, window

PARIS = ZoneInfo("Europe/Paris")


def iso(t0: datetime, h: float) -> str:
    """Hours since H0 -> ISO time with the Paris offset, rounded to the minute."""
    return (t0 + timedelta(minutes=round(h * 60))).replace(tzinfo=PARIS).isoformat()


def team_label(team, site_name: str) -> str:
    """'Foix-3', 'Laurencin-1' (short site name + team number)."""
    short = re.sub(r"\s*\(.*\)", "", site_name).strip()
    n = team.id.rsplit("_E", 1)[-1]
    return f"{short}-{n}"


def team_status(s, team, t: float) -> str:
    W, R = s.cfg.roster.work_h, s.cfg.roster.rest_h
    if team.current_job and team.current_job in s.in_progress:
        if s.external_field:                                            # live: on site only once the team says so
            return "repairing" if team.current_job in s.on_site else "travelling"
        _, go, arrive, _ = s.in_progress[team.current_job]
        return "travelling" if t < arrive else "repairing"
    return "available" if is_on_duty(team.shift_start, t, W, R) else "resting"


def roster_group(cfg, team) -> str:
    """Shift group of a team: A starts at H0, B at H0 + b_offset_h, C (the relief) at H0 + c_offset_h."""
    r = cfg.roster
    if abs(team.shift_start - r.b_offset_h) < 1e-9 and team.shift_start:
        return "B"
    if abs(team.shift_start - getattr(r, "c_offset_h", -1)) < 1e-9 and team.shift_start:
        return "C"
    return "A"


def roster(s) -> dict:
    """The fixed shift schedule, for the manager: work_h on / rest_h off, three groups staggered from H0."""
    r = s.cfg.roster
    offsets = {"A": 0.0, "B": float(r.b_offset_h), "C": float(getattr(r, "c_offset_h", 12.0))}
    counts = {g: 0 for g in offsets}
    for team in s.teams:
        counts[roster_group(s.cfg, team)] += 1
    return {"workHours": r.work_h, "restHours": r.rest_h,
            "groups": [{"id": g, "offsetHours": off, "firstShiftStart": iso(s.t0, off), "teams": counts[g]}
                       for g, off in offsets.items() if counts[g]]}


def shift_hours_left(s, team, t: float) -> float:
    W, R = s.cfg.roster.work_h, s.cfg.roster.rest_h
    if not is_on_duty(team.shift_start, t, W, R):
        return 0.0
    _, e = window(team.shift_start, t, W, R)
    return round(max(0.0, e - t), 1)


def restore90_hours(s, projected: dict[str, float], t: float) -> float | None:
    """Hours since H0 until 90 % of what is cut so far is restored, per the plan; None if never.
    Counted on the service target's basis (config `service_target.basis`): incidents (the spec) or customers."""
    cut = [i for i in s.incidents if i.reported_at <= t + 1e-9]
    weight = (lambda i: i.customers) if getattr(s.cfg.service_target, "basis", "incidents") == "customers" else (lambda i: 1)
    total = sum(weight(i) for i in cut)
    if not total:
        return None
    done = sorted((projected[i.id], weight(i)) for i in cut if i.id in projected)
    acc = 0
    for C, n in done:
        acc += n
        if acc >= 0.9 * total:
            return round(C, 1)
    return None


def snapshot(s, t: float, time_iso: str, recs: list[dict], decisions: list[dict], site_names: dict) -> dict:
    """One Snapshot at clock t (hours since H0)."""
    known = [i for i in s.incidents if i.reported_at <= t + 1e-9]
    proj = s.projected_restoration()
    statuses, team_of = {}, {}
    for i in known:
        if i.id in s.restored:
            statuses[i.id] = "restored"
        elif i.id in s.in_progress:
            tid, go, arrive, C = s.in_progress[i.id]
            on_site = i.id in s.on_site if s.external_field else t >= arrive
            statuses[i.id] = "repairing" if on_site else "enroute"
            team_of[i.id] = tid
        else:
            statuses[i.id] = "waiting"
    teams, avail = [], {"available": 0, "busy": 0, "resting": 0}
    for team in s.teams:
        st = team_status(s, team, t)
        avail["available" if st == "available" else "resting" if st == "resting" else "busy"] += 1
        lat, lon = s.position(team, t)
        W, R = s.cfg.roster.work_h, s.cfg.roster.rest_h
        sh_s, sh_e = window(team.shift_start, t, W, R)                # current shift, or the next one when resting
        teams.append({"id": team.id, "label": team_label(team, site_names[team.home_site]),
                      "siteName": site_names[team.home_site], "lon": lon, "lat": lat, "status": st,
                      "shiftHoursLeft": shift_hours_left(s, team, t), "group": roster_group(s.cfg, team),
                      "shiftStart": iso(s.t0, sh_s), "shiftEnd": iso(s.t0, sh_e),
                      **({"incidentId": team.current_job} if team.current_job else {})})
    cut_now = sum(i.customers for i in known if statuses[i.id] != "restored")
    restored = sum(i.customers for i in known if statuses[i.id] == "restored")
    score = sum(i.customers * (min(t, s.restored.get(i.id, t)) - i.reported_at) for i in known)
    kpis = {"clientsCut": cut_now, "clientsRestored": restored,
            "incidentsWaiting": sum(v == "waiting" for v in statuses.values()),
            "teamsAvailable": avail["available"], "teamsBusy": avail["busy"], "teamsResting": avail["resting"],
            "score": round(score, 1), "scoreBaseline": 0.0, "restore90Hours": restore90_hours(s, proj, t)}
    incidents = [{"id": i.id, "posteId": i.poste_id, "lon": i.lon, "lat": i.lat, "commune": i.commune,
                  "clients": i.customers, "sensitive": bool(i.sensitive), "cause": i.cause, "repairHours": i.est_duration,
                  "reportedAt": iso(s.t0, i.reported_at), "status": statuses[i.id],
                  **({"teamId": team_of[i.id]} if i.id in team_of else {})} for i in known]
    return {"time": time_iso, "kpis": kpis, "incidents": incidents, "teams": teams,
            "recommendations": recs, "decisions": decisions}


def recommendation(s, rec: dict, step: int) -> dict:
    """Engine recommendation (session.recommendations) -> contract Recommendation (+ ADDED fields)."""
    f = rec.get("facts") or {}
    x = f.get("factors", {})
    alts = []
    for a in f.get("alternatives") or []:
        alt = {"teamId": a["team"], "deltaScore": round(a["delta"]) if a.get("delta") is not None else 0,
               "travelMinutes": a.get("travel_min", 0), "eta": iso(s.t0, a.get("arrive_h", s.now)),
               "shiftHoursLeftAfter": a.get("shift_left_after_h", 0.0), "feasible": a["feasible"]}
        if a.get("reason"):
            alt["reason"] = a["reason"]
        if a.get("recommended_for"):
            alt["recommendedFor"] = a["recommended_for"]
        alts.append(alt)
    return {
        "id": f"{step}-{rec['incident']}", "teamId": rec["team"], "incidentId": rec["incident"],
        "eta": iso(s.t0, rec["arrive_h"]), "travelMinutes": x.get("travel_min", 0),
        "priority": x.get("priority_index", 0.0),
        "factors": {"clients": x.get("customers", 0), "sensitive": bool(x.get("sensitive")),
                    "travelMinutes": x.get("travel_min", 0), "repairHours": x.get("repair_h", 0),
                    "shiftHoursLeftAfter": x.get("shift_left_h", 0.0)},
        "alternatives": alts,
        "note": rec.get("headline"),
        # ADDED (ignored by the current UI): card text and the 3 best paths
        "headline": rec.get("headline"), "details": rec.get("details"),
        "options": [{**o, "restoredAt": iso(s.t0, o["restored_h"])} for o in rec.get("options", [])],
        "pastRefusals": rec.get("past_refusals"),
    }


def rule_names(s, site_names: dict) -> dict:
    """Display names for rule labels: team id -> 'Balma-3', incident id -> 'poste de Fronton', site id -> 'Balma'."""
    return {"t0": s.t0,
            **{t.id: team_label(t, site_names[t.home_site]) for t in s.teams},
            **{i.id: f"poste de {i.commune}" for i in s.incidents},
            **{k: re.sub(r"\s*\(.*\)", "", v).strip() for k, v in site_names.items()}}


def describe_rule(m, names: dict | None = None) -> str:
    """French one-liner for an operator rule (active rules panel, refusal restatement).
    With `names` (rule_names), ids become team / place names and crisis hours become clock times."""
    from dispatch.engine import modifiers as M
    n = names or {}
    nm = lambda x: n.get(x, x)                                          # noqa: E731
    t0 = n.get("t0")

    def until(h: float) -> str:
        if t0 is None:
            return f"H0 + {h:.1f} h"
        d = (t0 + timedelta(minutes=round(h * 60))).replace(tzinfo=PARIS)
        return f"{d.hour:02d}h{d.minute:02d}" + ("" if (d.date() == t0.date()) else f" ({_DAYS[d.weekday()]})")
    if isinstance(m, M.ZoneInaccessible):
        return f"{nm(m.zone)} inaccessible jusqu'à {until(m.until_h)}"
    if isinstance(m, M.TravelFactor):
        return f"Trajets vers {nm(m.zone)} × {m.factor:g}"
    if isinstance(m, M.TeamUnavailable):
        return f"Équipe {nm(m.team)} indisponible" + (f" jusqu'à {until(m.until_h)}" if m.until_h else " jusqu'à la fin de la crise")
    if isinstance(m, M.DurationUpdate):
        return f"Dépannage du {nm(m.incident)} : {m.hours:g} h"
    if isinstance(m, M.Priority):
        return f"{nm(m.incident)[:1].upper()}{nm(m.incident)[1:]} prioritaire (× {m.factor:g})"
    if isinstance(m, M.Forbid):
        who = m.team_or_site
        if "_E" not in who and who in n:                                # a whole site
            return f"Aucune équipe de {nm(who)} vers {nm(m.incident_or_zone)}"
        return f"Pas de {nm(who)} sur {nm(m.incident_or_zone)}"
    if isinstance(m, M.Force):
        return f"{nm(m.team)} imposée sur {nm(m.incident)}"
    if isinstance(m, M.Reserve):
        return f"{m.n_teams} équipe(s) de {nm(m.site)} en réserve"
    if isinstance(m, M.Weight):
        return f"Poids {m.name} = {m.value:g}"
    return type(m).__name__


_DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
