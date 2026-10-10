"""Chargement de la configuration (config/default.yaml)."""
from __future__ import annotations

from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
CONFIG_DEFAUT = RACINE / "config" / "default.yaml"


def charger_config(chemin: str | Path | None = None) -> dict:
    """Renvoie la configuration sous forme de dict. `chemin` permet de surcharger le fichier par défaut."""
    with open(chemin or CONFIG_DEFAUT, encoding="utf-8") as f:
        return yaml.safe_load(f)


def chemin_projet(*parties: str) -> Path:
    """Chemin absolu à partir de la racine du dépôt, ex. chemin_projet('data', 'clean')."""
    return RACINE.joinpath(*parties)
