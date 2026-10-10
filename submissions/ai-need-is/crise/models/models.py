from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Equipe:
    id_equipe: str
    nom: str
    latitude: float
    longitude: float
    disponible: bool = True
    competence: str = "general"

@dataclass
class Incident:
    id_incident: str
    latitude: float
    longitude: float
    priorite: int
    charge_travail: float  # en heures
    clients_impactes: int
    resolu: bool = False

@dataclass
class Decision:
    id_equipe: str
    id_incident: str
    temps_estime_trajet: float
    strategie_utilisee: str
    explication: str

@dataclass
class ScenarioState:
    temps_actuel: str  # ex: "T1"
    incidents_actifs: List[Incident] = field(default_factory=list)
    equipes: List[Equipe] = field(default_factory=list)
    historique_decisions: List[Decision] = field(default_factory=list)