"""Stratégies de référence R1 et R2 — à battre par la stratégie WSPT (§5.3).

Tâche(s) : T1.6 — propriétaire : P1.

R1 — PlusProcheFCFS   : incidents par ordre d'arrivée ; chacun prend l'équipe disponible la plus proche.
R2 — PlusDeClients    : incidents par nombre de clients décroissant ; chacun prend l'équipe la plus proche.

Les deux respectent la règle d'amplitude (est_faisable) : une équipe qui n'a plus assez d'amplitude
pour un incident n'est pas proposée.
"""
from __future__ import annotations

from crise.models import Affectation, EtatSimulation, Incident
from crise.policies.base import Policy, TrajetMin


class _PlusProche(Policy):
    nom = "abstraite"

    def ordre(self, incidents: list[Incident]) -> list[Incident]:
        raise NotImplementedError

    def decide(self, etat: EtatSimulation, trajet_min: TrajetMin) -> list[Affectation]:
        from crise.simulateur import est_faisable  # import local : évite un import circulaire

        libres = list(etat.equipes_disponibles)
        choix: list[Affectation] = []
        for inc in self.ordre(etat.incidents_en_attente):
            if not libres:
                break
            candidats = []
            for eq in libres:
                tr = trajet_min(eq.lat, eq.lon, inc.lat, inc.lon)
                if est_faisable(eq, inc, tr, etat.t, etat.params):
                    candidats.append((tr, eq.id_equipe, eq))
            if not candidats:
                continue
            tr, _, eq = min(candidats)
            libres.remove(eq)
            choix.append(Affectation(eq.id_equipe, inc.id_incident, {
                "regle": self.nom, "trajet_min": round(tr, 1), "nb_clients": inc.nb_clients,
                "attente_min": etat.t - inc.t_apparition,
            }))
        return choix


class PlusProcheFCFS(_PlusProche):
    """R1 : premier arrivé, premier servi + équipe la plus proche."""
    nom = "R1_fcfs_plus_proche"

    def ordre(self, incidents):
        return sorted(incidents, key=lambda i: (i.t_apparition, i.id_incident))


class PlusDeClients(_PlusProche):
    """R2 : le plus de clients d'abord (sensibles d'abord à égalité) + équipe la plus proche."""
    nom = "R2_plus_de_clients"

    def ordre(self, incidents):
        return sorted(incidents, key=lambda i: (-i.nb_clients, not i.sensible, i.t_apparition, i.id_incident))


REFERENCES = {"R1": PlusProcheFCFS, "R2": PlusDeClients}
