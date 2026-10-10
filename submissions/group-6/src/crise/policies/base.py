"""Interface commune des stratégies (contrat §4.2). Propriétaire : P1."""
from __future__ import annotations

from collections.abc import Callable

from crise.models import Affectation, EtatSimulation

TrajetMin = Callable[[float, float, float, float], float]   # (lat1, lon1, lat2, lon2) -> minutes


class Policy:
    nom: str = "abstraite"

    def decide(self, etat: EtatSimulation, trajet_min: TrajetMin) -> list[Affectation]:
        """Appelée à chaque événement (incident apparu, équipe libérée).
        Renvoie les affectations à lancer maintenant.
        Ne doit JAMAIS proposer une affectation qui viole l'amplitude restante."""
        raise NotImplementedError
