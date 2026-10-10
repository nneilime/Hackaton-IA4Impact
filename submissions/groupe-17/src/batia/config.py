from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
REPORTS = RAW / "rapports"
OUT = ROOT / "data" / "outputs"
ASSETS = ROOT / "assets"
OUT.mkdir(parents=True, exist_ok=True)

REF_DATE = "2025-12-31"  # les données s'arrêtent là ; on prédit 2026
WINDOW_LABEL = "janv.-sept. 2026"

# Poids selon la nature de l'équipement (sécurité / continuité de service)
FAMILLE_POIDS = {
    "chaufferie_collective": 1.0,
    "ascenseur": 1.0,
    "chaudiere_gaz_individuelle": 1.0,
    "pompe_a_chaleur": 0.8,
    "ballon_thermodynamique": 0.7,
    "ballon_ecs_electrique": 0.7,
    "caisson_vmc": 0.7,
    "convecteurs_electriques": 0.6,
    "panneaux_rayonnants": 0.6,
    "production_ecs_solaire": 0.6,
}
FAMILLES_DANGER = {"chaufferie_collective", "ascenseur", "chaudiere_gaz_individuelle"}

# Seuils du signal (sur proba x poids). Réglables.
SEUIL_ROUGE = 0.30
SEUIL_ORANGE = 0.12
NB_ROUGE = 2  # nb d'équipements >= seuil rouge pour passer un bâtiment en rouge
NB_ORANGE = 4  # nb d'équipements >= seuil orange pour passer un bâtiment en orange

COULEURS = {"rouge": "#D92D20", "orange": "#F79009", "vert": "#12B76A"}
