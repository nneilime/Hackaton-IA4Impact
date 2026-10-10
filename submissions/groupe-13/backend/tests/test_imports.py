"""Import manuel d'un dossier : dépôt, validation, analyse, exclusion des statistiques du corpus."""
import time
from fastapi.testclient import TestClient
from sentinel.api import app
from sentinel.corpus import corpus_root
from sentinel.config import JPG_SUBDIR, TXT_SUBDIR

PWD = "mot-de-passe-test"


def _login(c):
    st = c.get("/api/status").json()
    for _ in range(600):
        if st["state"]["phase"] in ("prêt", "erreur"):
            break
        time.sleep(0.5); st = c.get("/api/status").json()
    if st["needs_setup"]:
        c.post("/api/setup", json={"admin_username": "admin", "admin_display_name": "Admin", "admin_password": PWD,
                                   "create_demo_accounts": True})
    c.post("/api/logout")
    assert c.post("/api/login", json={"username": "superviseur", "password": PWD}).status_code == 200


def test_import_dossier_modifie():
    root = corpus_root()
    img = (root / JPG_SUBDIR / "Facture1_02.jpg").read_bytes()
    lines = (root / TXT_SUBDIR / "Facture1_02.txt").read_bytes().decode("latin-1").split("\r\n")
    i5 = next(i for i, l in enumerate(lines) if l.startswith("5"))
    l = lines[i5]
    lines[i5] = l[:41] + "00090000" + l[49:]                  # TotalPrestations -> 900,00 € (longueur inchangée)
    txt = "\r\n".join(lines).encode("latin-1")
    with TestClient(app) as c:
        _login(c)
        bad = c.post("/api/imports", files={"bordereau": ("x.jpg", b"pas une image", "image/jpeg"),
                                            "facture": ("f.txt", txt, "text/plain")})
        assert bad.status_code == 400
        r = c.post("/api/imports", files={"bordereau": ("Facture1_02.jpg", img, "image/jpeg"),
                                          "facture": ("Facture1_02_modifiee.txt", txt, "text/plain")},
                   data={"label": "test total modifié"})
        assert r.status_code == 200
        iid = r.json()["id"]
        for _ in range(240):
            st = next(x for x in c.get("/api/imports").json() if x["id"] == iid)
            if st["status"] != "analyse":
                break
            time.sleep(0.5)
        assert st["status"] == "prêt", st
        case = c.get(f"/api/cases/{iid}").json()
        r12 = next(x for x in case["analysis"]["results"] if x["rule_id"] == "R12")
        assert r12["status"] == "ANOMALIE" and r12["gap"]["amount_cents"] == 90000 - 81897
        assert case["analysis"]["source"] == "import"
        assert c.get(f"/api/cases/{iid}/image").status_code == 200
        sup = c.get("/api/supervision").json()
        assert sup["dossiers"]["total"] == 55 and sup["denominateurs"]["dossiers_importes"] >= 1
        assert c.delete(f"/api/imports/{iid}").status_code == 200
        assert c.get(f"/api/cases/{iid}").status_code == 404
