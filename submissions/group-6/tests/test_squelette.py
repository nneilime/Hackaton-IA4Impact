"""Tests de fumée : le paquet s'importe et la configuration se charge."""
import importlib

import pytest

from crise.config import charger_config
from crise.models import COLONNES_SIMRESULT, Equipe, EtatEquipe

MODULES = [
    "crise.models", "crise.config", "crise.trajet", "crise.simulateur", "crise.scenarios",
    "crise.policies.base", "crise.policies.baselines", "crise.policies.wspt_hongrois",
    "crise.explication", "crise.kpi", "crise.prepositionnement", "crise.benchmark",
    "crise.copilote.llm", "crise.copilote.templates", "crise.data.nettoyage",
]


@pytest.mark.parametrize("module", MODULES)
def test_import(module):
    importlib.import_module(module)


def test_config():
    cfg = charger_config()
    assert cfg["travail"]["amplitude_max_min"] == 720
    assert cfg["score"]["alpha_sensible"] == 5.0


def test_contrats():
    e = Equipe("SITE_01_E1", "SITE_01", 42.9654, 1.6060)
    assert e.etat is EtatEquipe.DISPONIBLE
    assert set(COLONNES_SIMRESULT) == {"incidents", "activites", "decisions", "serie"}
