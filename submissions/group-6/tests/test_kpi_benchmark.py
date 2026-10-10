"""Tests du module KPI et du banc d'essai (versions express)."""
import pytest

from crise.benchmark import parser_crises, resoudre_strategie, resumer
from crise.config import chemin_projet
from crise.kpi import calculer_kpi, gini_pondere, separer_apprentissage_test
from crise.models import Equipe, Incident, Site
from crise.policies.baselines import PlusDeClients, PlusProcheFCFS
from crise.simulateur import parametres_simulation, simuler


def test_gini():
    assert gini_pondere([5, 5, 5, 5]) == pytest.approx(0.0)
    assert gini_pondere([0, 0, 0, 10]) == pytest.approx(0.75)
    assert gini_pondere([1, 3], [3, 1]) == pytest.approx(gini_pondere([1, 1, 1, 3]))


def test_kpi_cas_simple():
    def trajet(a, b, c, d):
        return 0.0

    incs = [Incident("A", "P1", 0, 120, 120, "x", 100, True, 43.0, 1.0),
            Incident("B", "P2", 0, 480, 480, "x", 50, False, 43.0, 1.0)]
    res = simuler([Site("S1", "V", 43.0, 1.0, 1)], [Equipe("S1_E1", "S1", 43.0, 1.0)], incs, PlusDeClients(),
                  parametres_simulation(), trajet)
    k = calculer_kpi(res)
    assert k["clients_heures"] == pytest.approx(100 * 2 + 50 * 10)
    assert k["pct_clients_retablis_2h"] == pytest.approx(100 * 100 / 150)
    assert k["attente_max_sensible_h"] == 0 and k["depassements_amplitude"] == 0


def test_outils():
    assert parser_crises("1-3,7") == [1, 2, 3, 7]
    assert resoudre_strategie("R1") is PlusProcheFCFS
    app, test = separer_apprentissage_test([f"CRISE_{i:03d}" for i in range(1, 101)])
    assert len(app) == 80 and test[0] == "CRISE_081"


CLEAN = chemin_projet("data", "clean")


@pytest.mark.skipif(not (CLEAN / "incidents.parquet").exists(), reason="lancer python -m crise.data.nettoyage")
def test_banc_essai_court():
    from crise.benchmark import lancer

    kpi, series = lancer([1, 2], {"R1": PlusProcheFCFS, "R2": PlusDeClients}, n_jobs=1)
    assert len(kpi) == 4 and (kpi["depassements_amplitude"] == 0).all()
    r = resumer(kpi)
    assert "gain_vs_R1_pct" in r.columns and set(series["strategie"]) == {"R1", "R2"}
