"""Temps de trajet : haversine × coefficient de détour, vitesse plaine/montagne (selon la destination).

Tâche(s) : T1.4 — propriétaire : P1.
Voir docs/PLAN_EQUIPE_DEFI_ENEDIS.md.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crise.models import Equipe, Incident


@dataclass(frozen=True)
class ZoneRalentie:
    """Zone où les trajets sont ralentis (stress test « routes coupées », S1).

    S'applique quand la DESTINATION est dans le rectangle. facteur=3 → vitesse divisée par 3.
    """
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    facteur: float = 3.0
    nom: str = ""

    def contient(self, lat: float, lon: float) -> bool:
        return self.lat_min <= lat <= self.lat_max and self.lon_min <= lon <= self.lon_max


# Zone prête à l'emploi pour la démo : piémont / montagne pyrénéenne (Ariège, Comminges, Luchon)
ZONE_MONTAGNE = ZoneRalentie(42.4, 43.05, -0.5, 2.4, facteur=3.0, nom="Montagne (lat < 43,05)")


def facteur_zones(lat: float, lon: float, zones: Sequence[ZoneRalentie] = ()) -> float:
    """Facteur de ralentissement à une destination (le plus fort si plusieurs zones se recouvrent)."""
    return max((z.facteur for z in zones if z.contient(lat, lon)), default=1.0)


def distance_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance orthodromique (vol d'oiseau) en kilomètres entre deux coordonnées WGS84."""
    if math.isclose(lat1, lat2, abs_tol=1e-7) and math.isclose(lon1, lon2, abs_tol=1e-7):
        return 0.0
    radius = 6371.0  # Rayon terrestre moyen en km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    # Protection contre d'éventuelles imprécisions flottantes > 1.0
    a = min(1.0, max(0.0, a))
    return 2.0 * radius * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def calculer_trajet_min(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    coef_detour: float = 1.3,
    vitesse_plaine_kmh: float = 55.0,
    vitesse_montagne_kmh: float = 35.0,
    lat_seuil_montagne: float = 43.05,
    multiplicateur_zone: float = 1.0,
    zones: Sequence[ZoneRalentie] = (),
) -> float:
    """Calcule la durée de trajet routier en minutes selon les règles du §5.2.

    Si lat2 < lat_seuil_montagne, la destination est en montagne (35 km/h).
    Sinon, elle est en plaine (55 km/h).
    Le multiplicateur_zone permet d'appliquer un ralentissement (ex: routes coupées / stress).
    zones : ralentissements locaux (ZoneRalentie), cumulés avec multiplicateur_zone.
    """
    if multiplicateur_zone <= 0:
        raise ValueError(f"multiplicateur_zone doit être strictement positif, reçu: {multiplicateur_zone}")

    d_vol = distance_haversine_km(lat1, lon1, lat2, lon2)
    if d_vol == 0.0:
        return 0.0

    d_route = d_vol * coef_detour
    vitesse_base = vitesse_montagne_kmh if lat2 < lat_seuil_montagne else vitesse_plaine_kmh
    facteur = multiplicateur_zone * facteur_zones(lat2, lon2, zones)
    vitesse_effective = max(1.0, vitesse_base / facteur)
    return (d_route / vitesse_effective) * 60.0


def trajet_min(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Signature standard conforme au contrat Policy.decide."""
    return calculer_trajet_min(lat1, lon1, lat2, lon2)


def matrice_trajet_vectorisee(
    equipes: Sequence[Equipe],
    incidents: Sequence[Incident],
    coef_detour: float = 1.3,
    vitesse_plaine_kmh: float = 55.0,
    vitesse_montagne_kmh: float = 35.0,
    lat_seuil_montagne: float = 43.05,
    multiplicateur_zone: float = 1.0,
    zones: Sequence[ZoneRalentie] = (),
):
    """Calcul vectorisé numpy (§5.2) de la matrice des temps de trajet en minutes.

    Opération en bloc (len(equipes) x len(incidents)) par diffusion (broadcasting) numpy.
    """
    import numpy as np

    if multiplicateur_zone <= 0:
        raise ValueError(f"multiplicateur_zone doit être strictement positif, reçu: {multiplicateur_zone}")

    n_eq = len(equipes)
    n_inc = len(incidents)
    if n_eq == 0 or n_inc == 0:
        return np.zeros((n_eq, n_inc), dtype=float)

    lats_eq = np.radians(np.array([eq.lat for eq in equipes], dtype=float))[:, np.newaxis]
    lons_eq = np.radians(np.array([eq.lon for eq in equipes], dtype=float))[:, np.newaxis]
    lats_inc = np.radians(np.array([inc.lat for inc in incidents], dtype=float))[np.newaxis, :]
    lons_inc = np.radians(np.array([inc.lon for inc in incidents], dtype=float))[np.newaxis, :]

    dphi = lats_inc - lats_eq
    dlambda = lons_inc - lons_eq

    a = np.sin(dphi / 2.0) ** 2 + np.cos(lats_eq) * np.cos(lats_inc) * np.sin(dlambda / 2.0) ** 2
    a = np.clip(a, 0.0, 1.0)
    d_vol = 2.0 * 6371.0 * np.arcsin(np.sqrt(a))

    d_route = d_vol * coef_detour
    lats_inc_deg = np.array([inc.lat for inc in incidents], dtype=float)[np.newaxis, :]
    vitesses_base = np.where(lats_inc_deg < lat_seuil_montagne, vitesse_montagne_kmh, vitesse_plaine_kmh)
    facteurs = np.array([facteur_zones(inc.lat, inc.lon, zones) for inc in incidents], dtype=float)[np.newaxis, :]
    vitesses_eff = np.maximum(1.0, vitesses_base / (multiplicateur_zone * facteurs))

    return (d_route / vitesses_eff) * 60.0


def matrice_trajet(
    equipes: Sequence[Equipe],
    incidents: Sequence[Incident],
    trajet_func=calculer_trajet_min,
) -> list[list[float]]:
    """Génère la matrice des temps de trajet (len(equipes) x len(incidents)) en minutes."""
    if trajet_func is calculer_trajet_min:
        try:
            return matrice_trajet_vectorisee(equipes, incidents).tolist()
        except ImportError:
            pass
    return [
        [trajet_func(eq.lat, eq.lon, inc.lat, inc.lon) for inc in incidents]
        for eq in equipes
    ]


def parametres_trajet(cfg: dict) -> dict:
    """Extrait les paramètres de trajet de la config (config/default.yaml, section « trajet »)."""
    t = cfg.get("trajet", cfg)
    return {
        "coef_detour": float(t["coef_detour"]),
        "vitesse_plaine_kmh": float(t["vitesse_plaine_kmh"]),
        "vitesse_montagne_kmh": float(t["vitesse_montagne_kmh"]),
        "lat_seuil_montagne": float(t["lat_seuil_montagne"]),
    }


def faire_trajet_min(
    cfg: dict | None = None,
    multiplicateur_zone: float = 1.0,
    zones: Sequence[ZoneRalentie] = (),
) -> Callable[[float, float, float, float], float]:
    """Fabrique la fonction trajet_min(lat1, lon1, lat2, lon2) passée à Policy.decide,
    avec les paramètres de la config (et d'éventuels ralentissements pour les stress tests).

    Exemple : trajet = faire_trajet_min(charger_config(), zones=[ZONE_MONTAGNE])
    """
    if cfg is None:
        from crise.config import charger_config

        cfg = charger_config()
    p = parametres_trajet(cfg)
    zones = tuple(zones)

    def _trajet(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        return calculer_trajet_min(lat1, lon1, lat2, lon2, **p, multiplicateur_zone=multiplicateur_zone, zones=zones)

    _trajet.parametres = {**p, "multiplicateur_zone": multiplicateur_zone, "zones": zones}
    return _trajet
