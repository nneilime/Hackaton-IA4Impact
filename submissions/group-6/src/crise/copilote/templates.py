"""Textes modèles de secours : fiche d'arbitrage + point de situation préfecture.

Tâche(s) : T5.3 — propriétaire : P5 (version écrite par P1). Instantané, sans LLM, jamais de chiffre inventé :
tous les nombres viennent du JSON d'explication ou des KPI. Le LLM (copilote/llm.py) peut reformuler ces textes.
"""
from __future__ import annotations


def _h(minutes: float) -> str:
    m = int(round(minutes))
    return f"{m // 60}h{m % 60:02d}" if m >= 60 else f"{m} min"


def fiche_arbitrage(id_equipe: str, id_incident: str, expl: dict) -> str:
    """2 à 4 phrases métier à partir du JSON produit par crise.explication.expliquer()."""
    f = expl.get("facteurs", {})
    if not f:
        return f"Équipe {id_equipe} envoyée sur {id_incident} (décision du responsable)." if expl.get("forcee") \
            else f"Équipe {id_equipe} envoyée sur {id_incident}."
    raisons = [f"{f['nb_clients']} clients coupés"]
    if f.get("sensible"):
        raisons.append("présence d'un client sensible")
    if f.get("attente_min", 0) >= 60:
        raisons.append(f"incident en attente depuis {_h(f['attente_min'])}")
    phrase = (f"Équipe {id_equipe} envoyée sur {id_incident} : {', '.join(raisons)} ; "
              f"{_h(f['trajet_min'])} de route, {_h(f['duree_min'])} de dépannage.")
    alt = expl.get("alternative")
    if alt:
        d = alt["delta_clients_heures"]
        if d > 0:
            phrase += (f" Commencer plutôt par {alt['id_incident']} ({alt['nb_clients']} clients) "
                       f"coûterait {d:.0f} clients·heures de plus.")
        elif d < 0:
            phrase += (f" ⚠️ Commencer par {alt['id_incident']} ({alt['nb_clients']} clients) aurait évité "
                       f"{-d:.0f} clients·heures : choix à discuter.")
    autre = expl.get("meilleure_autre_equipe")
    if autre and autre["retard_min"] > 0:
        phrase += (f" L'équipe suivante la plus proche ({autre['id_equipe']}) "
                   f"arriverait {_h(autre['retard_min'])} plus tard.")
    phrase += f" Confiance : {expl.get('confiance', 0):.0%}."
    return phrase


def point_situation(t_min: int, serie_t: dict, kpi: dict | None = None, sensibles_attente: int = 0,
                    tension: list[str] | None = None) -> str:
    """Point de situation pour la préfecture à l'instant t (serie_t = ligne de SimResult.serie)."""
    txt = (f"Point de situation à H+{_h(t_min)} : {serie_t['clients_coupes']} clients privés d'électricité, "
           f"{serie_t['incidents_attente']} incidents en attente d'une équipe. "
           f"{serie_t['equipes_occupees']} équipes en intervention, {serie_t['equipes_repos']} en repos réglementaire.")
    if sensibles_attente:
        txt += f" {sensibles_attente} postes avec clients sensibles en attente : priorité donnée."
    if tension:
        txt += f" Zones en tension : {', '.join(tension)}."
    if kpi:
        txt += f" Fin de rétablissement estimée : H+{kpi['fin_crise_h']:.0f}."
    return txt
