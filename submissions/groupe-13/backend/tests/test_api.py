"""API : authentification, rôles, décisions, corrections humaines historisées, rapports."""
import time
from fastapi.testclient import TestClient
from sentinel.api import app, STATE

PWD = "mot-de-passe-test"


def wait_ready(c):
    for _ in range(600):
        if c.get("/api/status").json()["state"]["phase"] in ("prêt", "erreur"):
            return
        time.sleep(0.5)


def test_parcours_complet():
    with TestClient(app) as c:
        wait_ready(c)
        assert c.get("/api/cases").status_code == 401
        r = c.post("/api/setup", json={"admin_username": "admin", "admin_display_name": "Admin", "admin_password": PWD,
                                       "create_demo_accounts": True})
        assert r.status_code == 200
        assert c.post("/api/setup", json={"admin_username": "xx", "admin_display_name": "xx", "admin_password": PWD}).status_code == 409
        # auditeur : lecture seule
        c.post("/api/logout")
        assert c.post("/api/login", json={"username": "auditeur", "password": "faux"}).status_code == 401
        assert c.post("/api/login", json={"username": "auditeur", "password": PWD}).status_code == 200
        assert c.post("/api/cases/Facture1_07/decisions", json={"kind": "commentaire", "comment": "x"}).status_code == 403
        # agent : correction OCR -> règles recalculées, original conservé
        c.post("/api/logout"); c.post("/api/login", json={"username": "agent1", "password": PWD})
        case = c.get("/api/cases/Facture1_07").json()
        r03 = next(x for x in case["analysis"]["results"] if x["rule_id"] == "R03")
        assert r03["status"] == "ANOMALIE" and r03["jpg_value"] == "574" and r03["txt_value"] == "575"
        assert c.post("/api/cases/Facture1_07/corrections", json={"target": "fields.Z3", "corrected": "575", "comment": "test"}).status_code == 200
        case = c.get("/api/cases/Facture1_07").json()
        r03 = next(x for x in case["analysis"]["results"] if x["rule_id"] == "R03")
        assert r03["status"] == "CONFORME"
        z3 = case["analysis"]["extraction"]["fields"]["Z3"]
        assert z3["original"]["value"] == "574" and z3["corrected_by"] == "agent1"
        # faux positif sans motif refusé ; clôture réservée au gestionnaire
        assert c.post("/api/cases/Facture1_07/decisions", json={"kind": "faux_positif", "rule_id": "R03"}).status_code == 400
        assert c.post("/api/cases/Facture1_07/decisions", json={"kind": "statut", "value": "Clôturé"}).status_code == 403
        assert c.post("/api/cases/Facture1_07/decisions", json={"kind": "statut", "value": "Contrôle terminé"}).status_code == 200
        assert c.get("/api/supervision").status_code == 403
        # rapports
        assert c.get("/api/cases/Facture1_07/report.pdf").content[:4] == b"%PDF"
        assert c.get("/api/cases/Facture1_07/report.json").json()["dossier"] == "Facture1_07"
        # gestionnaire : supervision + journal
        c.post("/api/logout"); c.post("/api/login", json={"username": "superviseur", "password": PWD})
        s = c.get("/api/supervision").json()
        assert s["dossiers"]["total"] == 55 and s["finances"]["recupere_cents"] is None
        actions = {a["action"] for a in c.get("/api/audit").json()}
        assert {"extraction.correction", "decision.statut", "login"} <= actions
        cmp = c.post("/api/compare", json={"a": "Facture2_01", "b": "Facture2_05"}).json()
        assert cmp["homologous"] is False and any(d["field"] == "Z14" for d in cmp["field_diffs"])
