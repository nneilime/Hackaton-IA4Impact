"""ETL des vrais fichiers SNCF, testé sur de petits fichiers synthétiques au même format."""
import csv
import json

from app import db
from etl import build_db

GARES = [("87611301", "Foix", 42.96975, 1.60715), ("87611004", "Toulouse Matabiau", 43.61121, 1.45362),
         ("87611202", "Pamiers", 43.11621, 1.61945)]


def _fichiers(dossier):
    json.dump([{"nom": n, "codes_uic": c, "position_geographique": {"lat": la, "lon": lo}}
               for c, n, la, lo in GARES], open(dossier / "gares.json", "w", encoding="utf-8"))
    with open(dossier / "desserte.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "train", "ordre", "code", "stop", "arr", "dep"])
        for jour in ("2026-06-18", "2026-06-25"):  # deux jeudis
            for train, dep, arr in (("871605", "08:05:00", "09:16:00"), ("871607", "09:00:00", "10:11:00")):
                w.writerow([jour, train, 1, "StopPoint:OCETrain TER-87611301", "Foix", "", dep])
                w.writerow([jour, train, 2, "StopPoint:OCETrain TER-87611202", "Pamiers", "08:20:00", "08:21:00"])
                w.writerow([jour, train, 3, "StopPoint:OCETrain TER-87611004", "Toulouse Matabiau", arr, ""])
            w.writerow([jour, "871622", 1, "StopPoint:OCETrain TER-87611004", "Toulouse Matabiau", "", "14:35:00"])
            w.writerow([jour, "871622", 2, "StopPoint:OCETrain TER-87611301", "Foix", "15:46:00", ""])
    with open(dossier / "Data_Hackathon.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Mois", "Année", "N° Train", "Axe", "Origine / Destination", "Frequentation",
                    "Taux régularité du train", "Nombre de suppressions", "Minutes perdues"])
        for mois in ("Mai", "Juin"):
            for t in ("871605", "871607", "871622"):
                w.writerow([mois, "2026", t, "TOULOUSE - LATOUR DE CAROL", "Foix / Toulouse", "320",
                            "94,50%", "1", "40"])


def test_construction_depuis_les_fichiers_sncf(tmp_path, monkeypatch):
    dossier = tmp_path / "data"
    dossier.mkdir()
    _fichiers(dossier)
    monkeypatch.setenv("LIO_DATA_DIR", str(dossier))
    chemin = tmp_path / "lio.db"
    monkeypatch.setenv("LIO_DB_PATH", str(chemin))
    assert build_db.fichiers_sncf_disponibles()
    build_db.construire(chemin)
    with db.connexion(chemin) as conn:
        assert db.meta_get(conn, "donnees") == "sncf"
        assert conn.execute("SELECT COUNT(*) FROM gare").fetchone()[0] == 3
        assert conn.execute("SELECT autorise_groupe FROM train WHERE numero = '871605'").fetchone()[0] == 1
        f = conn.execute("SELECT * FROM fiabilite_train WHERE train_numero = '871605'").fetchone()
        assert round(f["taux_regularite"], 1) == 94.5 and f["nb_mois"] == 2
        # sites du catalogue rattachés aux gares présentes (par le nom)
        ids = {r[0] for r in conn.execute("SELECT id FROM site_culturel")}
        assert "toulouse-saint-sernin" in ids and "foix-chateau" in ids
        # option simulée du scénario sur le premier train groupe du matin Foix -> Toulouse
        p = conn.execute("SELECT * FROM positionnement").fetchone()
        assert (p["train_numero"], p["date_sortie"], p["nb_places"], p["est_simule"]) == \
            ("871605", "2026-11-12", 10, 1)
