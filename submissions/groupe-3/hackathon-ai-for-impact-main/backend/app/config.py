"""Chemins, paramètres d'environnement et constantes des règles métier.

Les valeurs des règles viennent de livrables/03-cahier-des-charges.md (§4 et §5).
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


def db_path() -> Path:
    """Chemin de la base SQLite (surchargeable par LIO_DB_PATH, utile pour les tests)."""
    return Path(os.environ.get("LIO_DB_PATH", BACKEND_DIR / "lio.db"))


def dossiers_donnees() -> list[Path]:
    """Dossiers où chercher les vrais fichiers SNCF (jamais commités)."""
    extra = os.environ.get("LIO_DATA_DIR")
    dirs = [Path(extra)] if extra else []
    return dirs + [REPO_DIR / "data", BACKEND_DIR / "data"]


def aujourdhui() -> date:
    """Date du jour (surchargeable par LIO_AUJOURDHUI=AAAA-MM-JJ pour des tests reproductibles)."""
    forcee = os.environ.get("LIO_AUJOURDHUI")
    if forcee:
        return date.fromisoformat(forcee)
    return date.today()


def geocodage_en_ligne() -> bool:
    """Appel optionnel à l'API Adresse (désactivable par LIO_GEOCODAGE_EN_LIGNE=0)."""
    return os.environ.get("LIO_GEOCODAGE_EN_LIGNE", "1") not in ("0", "false", "non")


# --- Règles métier (cahier des charges §4) ----------------------------------
CAPACITE_GROUPE = 50          # places groupe par train liO
MIN_VOYAGEURS = 6             # R2
MAX_VOYAGEURS = 50            # R2
MARGE_VISITE_MIN = 30         # R4 : arrivée au moins 30 min avant la visite
PLAGE_DEBUT = 9 * 60          # R6 : offre groupe entre 9h ...
PLAGE_FIN = 16 * 60           # ... et 16h
DELAI_MIN_JOURS = 21          # R7 : J-21
MARCHE_MAX_GROUPE = 20        # R3 : 20 min à pied au maximum (temps de groupe)
URBAIN_MAX_MIN = 60           # R3 : réseau urbain, 1 h au maximum
URBAIN_MAX_CORRESP = 1        # R3 : moins de 2 correspondances
CORRESP_MIN = 10              # EF15 : correspondance d'au moins 10 min
CORRESP_MAX = 90              # au-delà, l'attente n'est pas raisonnable pour un groupe
COEF_MARCHE_GROUPE = 1.3      # temps de groupe = individuel × 1,3 + 5 min
REGROUPEMENT_MIN = 5
VITESSE_MARCHE_M_MIN = 80     # ~4,8 km/h, pour le trajet gare ↔ établissement
PAUSE_DEJEUNER_MIN = 60       # sortie à la journée : visite + pause déjeuner sur place
PAS_CRENEAU_MIN = 15          # créneaux de visite indicatifs, tous les quarts d'heure
MAX_PROPOSITIONS = 3
JOURS_ALTERNATIVE = 7         # recherche d'une autre date sur 7 jours au plus
RAYON_GARE_KM = 30            # au-delà, on ne propose pas de gare de départ

# Valeurs par défaut de la Demande (API_CONTRACT.md)
DUREE_DEFAUT = "journee"
HEURE_DEPART_DEFAUT = "08:00"
HEURE_RETOUR_DEFAUT = "18:00"

MESSAGE_PRE_RESERVATION = "Demande de pré-réservation transmise — confirmation en attente"


# --- RAG (recherche de lieux hors ligne) ------------------------------------
RAG_TOP58_JSON = REPO_DIR / "database_reduit_embedding" / "data" / "top-des-sites-touristiques-2021-enrichi.json"
RAG_DATATOURISME_CSV = REPO_DIR / "database_embedding" / "data" / "datatourisme-reg-occ-clean.csv"
RAG_TOP58_METRIQUES = REPO_DIR / "data" / "top58_metriques.json"
GTFS_STOPS_TXT = REPO_DIR / "reseau_urbain_gare_coordonnees" / "stops.txt"
MARCHE_VITESSE_KMH = 4.0      # hypothèse : marche d'un groupe scolaire
MARCHE_COEF_DETOUR = 1.3      # hypothèse : détour réel vs vol d'oiseau
