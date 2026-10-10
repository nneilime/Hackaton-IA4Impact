"""WSPT + algorithme hongrois — version EXPRESS de secours (P1), conforme au plan §5.3.

Sert de filet de sécurité pour la démo si la stratégie de P2 (wspt_hongrois.py) ne se branche pas.

score_ij = w_i / (trajet_ij + durée_i)
w_i      = N_i × (1 + α·sensible_i) × (1 + β·attente_i_en_heures)
Affectation globale qui maximise Σ score (scipy.optimize.linear_sum_assignment).
"""
from __future__ import annotations

import numpy as np

from crise.models import Affectation, EtatSimulation
from crise.policies.base import Policy, TrajetMin

INFAISABLE = -1e9


class WSPTExpress(Policy):
    nom = "WSPT_express"

    def decide(self, etat: EtatSimulation, trajet_min: TrajetMin) -> list[Affectation]:
        from scipy.optimize import linear_sum_assignment

        from crise.simulateur import est_faisable

        eqs, incs, p = etat.equipes_disponibles, etat.incidents_en_attente, etat.params
        if not eqs or not incs:
            return []
        alpha, beta = float(p.get("alpha_sensible", 5.0)), float(p.get("beta_attente_par_h", 0.1))
        S = np.full((len(eqs), len(incs)), INFAISABLE)
        T = np.zeros_like(S)
        for a, e in enumerate(eqs):
            for b, i in enumerate(incs):
                tr = trajet_min(e.lat, e.lon, i.lat, i.lon)
                T[a, b] = tr
                if est_faisable(e, i, tr, etat.t, p):
                    w = i.nb_clients * (1 + alpha * i.sensible) * (1 + beta * (etat.t - i.t_apparition) / 60)
                    S[a, b] = w / (tr + i.duree_nominale)
        lignes, colonnes = linear_sum_assignment(-S)
        choix = []
        for a, b in zip(lignes, colonnes, strict=True):
            if S[a, b] <= INFAISABLE / 2:
                continue
            i = incs[b]
            autres = np.sort(S[a][S[a] > INFAISABLE / 2])[::-1]
            marge = float((autres[0] - autres[1]) / autres[0]) if len(autres) > 1 and autres[0] > 0 else 1.0
            choix.append(Affectation(eqs[a].id_equipe, i.id_incident, {
                "regle": self.nom, "score": round(float(S[a, b]), 3), "nb_clients": i.nb_clients,
                "sensible": bool(i.sensible), "attente_min": etat.t - i.t_apparition,
                "trajet_min": round(float(T[a, b]), 1), "duree_min": i.duree_nominale,
                "confiance": round(marge, 2),
            }))
        return choix
