"""
Calculs géographiques : Formule de Haversine et estimation des temps de trajet.
"""
import math

from math import asin, cos, radians, sin, sqrt


def calculer_distance_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule la distance à vol d'oiseau (en kilomètres) entre deux points géographiques
    en utilisant la formule de Haversine.
    """
    R = 6371.0  # Rayon moyen de la Terre en km

    # Conversion en radians
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c

def estimer_temps_trajet(lat1: float, lon1: float, lat2: float, lon2: float, coeff_detour: float = 1.25, vitesse_moyenne_kmh: float = 50.0) -> float:
    """
    Estime le temps de trajet en heures entre deux points, en appliquant un coefficient de détour routier
    et une vitesse moyenne par défaut.
    """
    distance_vol_oiseau = calculer_distance_haversine(lat1, lon1, lat2, lon2)
    distance_routiere = distance_vol_oiseau * coeff_detour
    
    if vitesse_moyenne_kmh <= 0:
        return 0.0
        
    temps_heures = distance_routiere / vitesse_moyenne_kmh
    return temps_heures