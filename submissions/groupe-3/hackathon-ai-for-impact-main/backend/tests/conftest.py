"""Fixtures : une base de démonstration neuve par test, date du jour figée, mode démo."""
import os

import pytest

os.environ["LIO_AUJOURDHUI"] = "2026-10-10"
os.environ["LIO_GEOCODAGE_EN_LIGNE"] = "0"
os.environ["LIO_DATATOURISME"] = "0"
os.environ.pop("ANTHROPIC_API_KEY", None)

SCENARIO = ("Je souhaite travailler avec ma classe de 5e sur le Moyen Âge. Nous sommes 42 élèves et "
            "4 accompagnateurs. Sortie à la journée, départ le matin, retour avant 19h. Nous partons "
            "du collège de Foix.")


@pytest.fixture
def base(tmp_path, monkeypatch):
    from etl import seed_demo
    from app.services import trains

    chemin = tmp_path / "lio.db"
    monkeypatch.setenv("LIO_DB_PATH", str(chemin))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seed_demo.semer(chemin)
    trains.vider_caches()
    return chemin


@pytest.fixture
def conn(base):
    from app import db

    with db.connexion(base) as c:
        yield c


@pytest.fixture
def client(base):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def demande_scenario(conn):
    """Demande complète du scénario (message + date du 12/11/2026), passée par completer()."""
    from datetime import date
    from app import schemas
    from app.services import comprendre

    d = comprendre.fusionner(schemas.Demande(), comprendre.extraire(SCENARIO, date(2026, 10, 10)))
    d = d.model_copy(update={"date": "2026-11-12"})
    return comprendre.completer(conn, d)
