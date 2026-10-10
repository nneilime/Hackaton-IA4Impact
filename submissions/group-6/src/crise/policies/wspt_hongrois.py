"""Stratégie principale : score WSPT pondéré + algorithme hongrois + faisabilité.

Tâche(s) : T2.2, T2.3, T2.6 — propriétaire : P2.
Voir docs/PLAN_EQUIPE_DEFI_ENEDIS.md.
"""
from __future__ import annotations

from collections.abc import Callable

from crise.factice import resoudre_affectation_hongrois
from crise.models import Affectation, EtatSimulation
from crise.policies.base import Policy

TrajetMin = Callable[[float, float, float, float], float]


class WSPTHongroisPolicy(Policy):
    """Stratégie WSPT + Algorithme Hongrois conforme aux spécifications §5.3."""

    nom: str = "wspt_hongrois"

    def decide(self, etat: EtatSimulation, trajet_min: TrajetMin) -> list[Affectation]:
        """Applique le score WSPT vectorisé et l'algorithme hongrois avec respect d'amplitude restante."""
        return resoudre_affectation_hongrois(etat, trajet_func=trajet_min)
