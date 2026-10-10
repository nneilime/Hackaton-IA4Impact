"""Import des vrais fichiers SNCF (data/, non versionné). Sauté si les fichiers sont absents.

La construction complète prend ~80 s : on réutilise lio.db si c'est déjà une base « sncf ».
"""
from datetime import date

import pytest

from app import config, db
from etl import import_sncf as I

SANS_DATA = not I.fichiers_disponibles()


def test_pourcentages_et_heures():
    assert I._pct("63,20%") == 63.2 and I._pct("1%") == 1.0 and I._pct("") is None
    assert I._heure("10:14:00") == "10:14" and I._heure(None) is None
    assert I._train(17301.0) == "17301" and I._uic("StopPoint:OCETrain TER-87784686") == "87784686"


def test_semaine_type_prend_le_meme_jour_le_plus_recent():
    jours = {date(2026, 6, 4), date(2026, 6, 11), date(2026, 6, 25), date(2026, 6, 26)}
    assert I.jour_type_pour(jours, date(2026, 11, 12)) == date(2026, 6, 25)   # jeudi
    assert I.jour_type_pour(jours, date(2026, 11, 13)) == date(2026, 6, 26)   # vendredi
    assert I.jour_type_pour(jours, date(2026, 11, 15)) is None                # pas de dimanche


@pytest.fixture(scope="module")
def base_sncf(tmp_path_factory):
    if SANS_DATA:
        pytest.skip("data/ absent")
    courante = config.db_path()
    try:
        with db.connexion(courante) as c:
            if db.meta_get(c, "donnees") == "sncf" and db.meta_get(c, "semaine_type_du"):
                yield courante
                return
    except Exception:
        pass
    chemin = tmp_path_factory.mktemp("sncf") / "lio.db"
    I.construire(chemin)
    yield chemin


@pytest.mark.skipif(SANS_DATA, reason="data/ absent")
def test_base_sncf_volumes_et_hypotheses(base_sncf):
    with db.connexion(base_sncf) as c:
        assert db.meta_get(c, "donnees") == "sncf" and db.meta_get(c, "source_libelle") == "SNCF 2026"
        assert c.execute("SELECT COUNT(*) FROM desserte WHERE est_simule = 0").fetchone()[0] > 700_000
        assert c.execute("SELECT COUNT(*) FROM indicateur_mensuel").fetchone()[0] > 1800
        assert c.execute("SELECT COUNT(*) FROM etablissement").fetchone()[0] > 1000
        reg = [r[0] for r in c.execute("SELECT taux_regularite FROM fiabilite_train WHERE taux_regularite IS NOT NULL")]
        reg.sort()
        assert 82 <= reg[len(reg) // 2] <= 90          # médiane ~ 86 %
        assert I.hypotheses(c)                          # semaine type signalée


@pytest.mark.skipif(SANS_DATA, reason="data/ absent")
def test_scenario_foix_toulouse_12_novembre(base_sncf):
    with db.connexion(base_sncf) as c:
        g = {r["nom"]: r["code_uic"] for r in c.execute("SELECT nom, code_uic FROM gare")}
        foix, tls = g["Foix"], g["Toulouse Matabiau"]
        q = """SELECT a.train_numero, a.heure_depart, b.heure_arrivee FROM desserte a
               JOIN desserte b ON b.train_numero = a.train_numero
                 AND b.date_circulation = a.date_circulation AND b.ordre > a.ordre
               WHERE a.gare_uic = ? AND b.gare_uic = ? AND a.date_circulation = '2026-11-12'
               ORDER BY a.heure_depart"""
        aller = c.execute(q, (foix, tls)).fetchall()
        retour = c.execute(q, (tls, foix)).fetchall()
        assert any("06:00" <= r["heure_depart"] <= "11:00" for r in aller)
        assert any("14:00" <= r["heure_depart"] and r["heure_arrivee"] <= "19:00" for r in retour)
