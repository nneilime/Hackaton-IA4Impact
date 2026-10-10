"""Explications d'une décision (§4.3 / §5.4) : facteurs, contributions, alternative, confiance, limites.

Tâche(s) : T2.5 — propriétaire : P2 (version écrite par P1, calculée par le simulateur pour TOUTE stratégie).

Principe : l'explication ne dépend pas de la stratégie qui a décidé. On lit chaque décision avec la grille
WSPT du plan (score = w / (trajet + durée), w = N × (1 + α·sensible) × (1 + β·attente_h)) :
    - facteurs bruts + contribution de chacun (décomposition du log du score) ;
    - alternative : le meilleur AUTRE incident que cette équipe aurait pu prendre ;
    - delta_clients_heures : coût exact (règle d'échange de Smith pour 1 équipe) d'avoir fait
      l'alternative d'abord ; > 0 ⇒ notre choix évite ce nombre de clients·heures ;
    - meilleure_autre_equipe : l'équipe libre suivante pour cet incident, et son retard ;
    - confiance (0–1) : marge de score entre le choix et l'alternative ;
    - limites : hypothèses qui pèsent sur cette décision.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from crise.models import Equipe, Incident

TrajetMin = Callable[[float, float, float, float], float]

LIMITES_TOUJOURS = [
    "trajet estimé : vol d'oiseau × 1,3, 55 km/h en plaine, 35 km/h en montagne",
    "durée de dépannage nominale (2h/4h/8h) : la durée réelle peut varier",
]


def poids(inc: Incident, t: int, params: dict) -> tuple[float, float, float]:
    """(w, facteur_sensible, facteur_attente)."""
    alpha = float(params.get("alpha_sensible", 5.0))
    beta = float(params.get("beta_attente_par_h", 0.1))
    f_s = 1 + alpha * bool(inc.sensible)
    f_a = 1 + beta * max(0, t - inc.t_apparition) / 60
    return inc.nb_clients * f_s * f_a, f_s, f_a


def score(inc: Incident, trajet: float, t: int, params: dict) -> float:
    w, _, _ = poids(inc, t, params)
    return w / (trajet + inc.duree_nominale)


def expliquer(
    equipe: Equipe,
    incident: Incident,
    t: int,
    params: dict,
    trajet_min: TrajetMin,
    incidents_en_attente: Sequence[Incident],
    equipes_libres: Sequence[Equipe],
) -> dict:
    from crise.simulateur import est_faisable

    tr = trajet_min(equipe.lat, equipe.lon, incident.lat, incident.lon)
    w, f_s, f_a = poids(incident, t, params)
    sc = w / (tr + incident.duree_nominale)

    # contributions : log(score) = log N + log f_s + log f_a − log(trajet + durée)
    temps = tr + incident.duree_nominale
    termes = {
        "clients": math.log(max(incident.nb_clients, 1)),
        "sensible": math.log(f_s),
        "attente": math.log(f_a),
        "trajet": -math.log(temps) * (tr / temps) if temps else 0.0,
        "duree": -math.log(temps) * (incident.duree_nominale / temps) if temps else 0.0,
    }
    total = sum(abs(v) for v in termes.values()) or 1.0
    contributions = {k: round(100 * v / total) for k, v in termes.items()}

    # alternative : meilleur autre incident faisable pour cette équipe
    alt, alt_sc, alt_tr = None, -1.0, 0.0
    for j in incidents_en_attente:
        if j.id_incident == incident.id_incident:
            continue
        trj = trajet_min(equipe.lat, equipe.lon, j.lat, j.lon)
        if not est_faisable(equipe, j, trj, t, params):
            continue
        s = score(j, trj, t, params)
        if s > alt_sc:
            alt, alt_sc, alt_tr = j, s, trj
    alternative = None
    if alt is not None:
        # échange de Smith : faire alt puis i, au lieu de i puis alt (même équipe)
        delta_min = (incident.nb_clients * (alt_tr + alt.duree_nominale)
                     - alt.nb_clients * (tr + incident.duree_nominale))
        alternative = {
            "id_incident": alt.id_incident, "score": round(alt_sc, 3), "nb_clients": alt.nb_clients,
            "sensible": bool(alt.sensible), "trajet_min": round(alt_tr, 1), "duree_min": alt.duree_nominale,
            "delta_clients_heures": round(delta_min / 60, 1),
        }

    # meilleure autre équipe libre pour cet incident
    autre = None
    for e in equipes_libres:
        if e.id_equipe == equipe.id_equipe:
            continue
        tre = trajet_min(e.lat, e.lon, incident.lat, incident.lon)
        if est_faisable(e, incident, tre, t, params) and (autre is None or tre < autre[1]):
            autre = (e, tre)
    meilleure_autre = None if autre is None else {
        "id_equipe": autre[0].id_equipe, "retard_min": round(autre[1] - tr, 1)}

    if alternative is None:
        confiance = 1.0
    else:
        confiance = max(0.0, min(1.0, (sc - alt_sc) / sc)) if sc > 0 else 0.0
        confiance = round(0.5 + 0.5 * confiance, 2) if sc >= alt_sc else round(0.5 * sc / alt_sc, 2)

    limites = list(LIMITES_TOUJOURS)
    if incident.lat < float(params.get("trajet", {}).get("lat_seuil_montagne", 43.05)):
        limites.append("destination en zone de montagne : trajet plus incertain")
    if incident.duree_nominale >= 480:
        limites.append("chantier long (8h) : l'équipe sera immobilisée longtemps")

    return {
        "score": round(sc, 3),
        "facteurs": {
            "nb_clients": incident.nb_clients, "sensible": bool(incident.sensible),
            "attente_min": int(t - incident.t_apparition), "trajet_min": round(tr, 1),
            "duree_min": incident.duree_nominale, "poids_sensible": round(f_s, 2), "poids_attente": round(f_a, 2),
        },
        "contributions_pct": contributions,
        "alternative": alternative,
        "meilleure_autre_equipe": meilleure_autre,
        "confiance": confiance,
        "limites": limites,
    }
