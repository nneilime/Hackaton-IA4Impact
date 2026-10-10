from __future__ import annotations

import pytest

from crise.factice import (
    PARAMETRES_DEFAUT,
    creer_equipes_factices,
    creer_etat_exemple_ab,
    creer_etat_simulation_factice,
    creer_incidents_factices,
    creer_jeu_exemple_ab,
    creer_jeu_factice,
    creer_postes_factices,
    creer_sites_factices,
)
from crise.trajet import calculer_trajet_min


@pytest.fixture
def equipes_factices():
    """Fixture renvoyant les 3 équipes factices."""
    return creer_equipes_factices()


@pytest.fixture
def incidents_factices():
    """Fixture renvoyant les 6 incidents factices à t=60 (tous apparus)."""
    return creer_incidents_factices(t=60)


@pytest.fixture
def postes_factices():
    """Fixture renvoyant les 6 postes factices."""
    return creer_postes_factices()


@pytest.fixture
def sites_factices():
    """Fixture renvoyant les 3 sites factices."""
    return creer_sites_factices()


@pytest.fixture
def jeu_factice():
    """Fixture renvoyant le tuple (3 équipes, 6 incidents)."""
    return creer_jeu_factice(t=60)


@pytest.fixture
def etat_simulation_factice():
    """Fixture renvoyant un EtatSimulation factice à t=60."""
    return creer_etat_simulation_factice(t=60)


@pytest.fixture
def params_defaut():
    """Fixture renvoyant les paramètres par défaut de simulation et score."""
    return dict(PARAMETRES_DEFAUT)


@pytest.fixture
def trajet_min():
    """Fixture fournissant la fonction de calcul de trajet conforme au contrat §4.2."""
    return calculer_trajet_min


@pytest.fixture
def jeu_exemple_ab():
    """Fixture renvoyant (equipe, inc_a, inc_b) pour le cas canonique §5.3."""
    return creer_jeu_exemple_ab()


@pytest.fixture
def etat_exemple_ab():
    """Fixture renvoyant l'EtatSimulation pour le cas canonique A/B à t=0."""
    return creer_etat_exemple_ab()
