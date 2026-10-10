"""Guardrail between the LLM (or any client) and the engine: known type, IDs exist, values in range.
Safety rules (shifts, rest, no interruption) are not modifiers, so nothing here can relax them."""
from __future__ import annotations

from dispatch.engine.modifiers import CATALOGUE, Modifier, from_dict

WEIGHTS = {"beta_sensitive": (0, 20), "lambda_stability": (0, 1e6), "starvation_gamma": (0, 100)}


class InvalidModifier(ValueError):
    pass


def validate(raw: dict, session) -> Modifier:
    """Parse one modifier dict against the live session (teams, incidents, zones, clock)."""
    if not isinstance(raw, dict) or raw.get("type") not in CATALOGUE:
        raise InvalidModifier(f"type de règle inconnu : {raw.get('type') if isinstance(raw, dict) else raw}")
    try:
        m = from_dict(raw)
    except TypeError as e:
        raise InvalidModifier(f"champ invalide : {e}") from e
    teams = {t.id for t in session.teams}
    sites = {t.home_site for t in session.teams}
    known = {i.id: i for i in session.incidents if i.reported_at <= session.now + 1e-9}
    zones = {z.lower() for i in known.values() for z in (i.commune, i.departement)}
    now = session.now
    kind = raw["type"]

    def need(cond, msg):
        if not cond:
            raise InvalidModifier(msg)

    if kind == "force":
        need(m.team in teams and m.incident in session.pending, "équipe ou incident inconnu / déjà traité")
    elif kind == "forbid":
        need(m.team_or_site in teams | sites, f"équipe ou site inconnu : {m.team_or_site}")
        need(m.incident_or_zone in known or m.incident_or_zone.lower() in zones, f"incident ou zone inconnu : {m.incident_or_zone}")
    elif kind == "team_unavailable":
        need(m.team in teams, f"équipe inconnue : {m.team}")
        need(m.until_h is None or m.until_h >= now, "l'indisponibilité doit se terminer dans le futur")
    elif kind == "zone_inaccessible":
        need(m.zone.lower() in zones, f"zone inconnue : {m.zone}")
        need(now <= m.until_h <= now + 72, "heure de fin hors plage (0 à 72 h)")
    elif kind == "travel_factor":
        need(m.zone.lower() in zones, f"zone inconnue : {m.zone}")
        need(1 <= m.factor <= 5, "facteur de trajet hors plage (1 à 5)")
    elif kind == "duration_update":
        need(m.incident in session.pending, f"incident inconnu ou déjà démarré : {m.incident}")
        need(0 < m.hours <= session.cfg.roster.work_h, "durée hors plage (doit tenir dans un poste)")
    elif kind == "priority":
        need(m.incident in known, f"incident inconnu : {m.incident}")
        need(0 < m.factor <= 10, "facteur de priorité hors plage (0 à 10)")
    elif kind == "reserve":
        need(m.site in sites and 0 <= m.n_teams <= 10, "réserve invalide")
    elif kind == "weight":
        need(m.name in WEIGHTS and WEIGHTS[m.name][0] <= m.value <= WEIGHTS[m.name][1], "poids inconnu ou hors plage")
    return m
