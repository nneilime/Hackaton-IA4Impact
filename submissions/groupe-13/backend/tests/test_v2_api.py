"""Version 2.0 — API : 15 zones, permissions des imports, traitements, décisions et montants confirmés,
simulation, revue rapide, conventions, qualité, sauvegarde."""
import time

from fastapi.testclient import TestClient

from sentinel.api import app
from sentinel.config import JPG_SUBDIR, TXT_SUBDIR
from sentinel.corpus import corpus_root

PWD = "mot-de-passe-test"


def ready(c):
    for _ in range(600):
        st = c.get("/api/status").json()
        if st["state"]["phase"] in ("prêt", "erreur"):
            break
        time.sleep(0.5)
    if st["needs_setup"]:
        assert c.post("/api/setup", json={"admin_username": "admin", "admin_display_name": "Admin", "admin_password": PWD,
                                          "create_demo_accounts": True}).status_code == 200


def login(c, user):
    c.post("/api/logout")
    assert c.post("/api/login", json={"username": user, "password": PWD}).status_code == 200


def wait_job(c, jid):
    for _ in range(600):
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] not in ("en_attente", "en_cours"):
            return j
        time.sleep(0.2)
    raise AssertionError("traitement non terminé")


def test_quinze_zones_dans_le_dossier_et_recalcul_apres_correction():
    with TestClient(app) as c:
        ready(c); login(c, "agent1")
        d = c.get("/api/cases/Facture1_04").json()
        zones = d["analysis"]["zones"]
        assert [z["zone_id"] for z in zones] == [f"Z{i}" for i in range(1, 16)]
        assert all(z["regions"] for z in zones)
        z8 = next(z for z in zones if z["zone_id"] == "Z8")
        assert z8["status"] == "ANOMALIE" and any(r["rule_id"] == "R12" for r in z8["rule_results"])
        assert z8["txt"]["links"][0]["line_no"] == 12 and z8["txt"]["links"][0]["start"] == 42
        assert next(z for z in zones if z["zone_id"] == "Z13")["txt"]["absence"]      # pas de donnée TXT : explicite
        # liste des dossiers : statut des zones
        row = next(x for x in c.get("/api/cases").json() if x["id"] == "Facture1_04")
        assert row["zones"]["Z8"] == "ANOMALIE" and row["zones"]["Z2"] == "CONFORME"
        # correction invalide refusée proprement (jamais enregistrée)
        r = c.post("/api/cases/Facture1_04/corrections", json={"target": "fields.Z8", "corrected": "abc"})
        assert r.status_code == 400
        r = c.post("/api/cases/Facture1_04/corrections", json={"target": "extraction.layout", "corrected": "x"})
        assert r.status_code == 400
        # correction valide : règle et zone recalculées, effet enregistré
        r = c.post("/api/cases/Facture1_04/corrections", json={"target": "fields.Z8", "corrected": "818,98", "comment": "lu à l'écran"})
        assert r.status_code == 200
        eff = r.json()["effect"]
        # R12 devient conforme ; mais 818,98 + 28,80 ≠ 847,77 : R20 passe en anomalie (zones 8, 12 et 13)
        assert eff["regles"]["R12"] == ["ANOMALIE", "CONFORME"] and eff["regles"]["R20"] == ["CONFORME", "ANOMALIE"]
        assert eff["zones"]["Z13"] == ["CONFORME", "ANOMALIE"]
        d = c.get("/api/cases/Facture1_04").json()
        z8 = next(z for z in d["analysis"]["zones"] if z["zone_id"] == "Z8")
        assert z8["status"] == "ANOMALIE" and [r["rule_id"] for r in z8["rule_results"] if r["status"] == "ANOMALIE"] == ["R20"]
        cid = d["analysis"]["corrections"][-1]["id"]
        assert c.delete(f"/api/cases/Facture1_04/corrections/{cid}").status_code == 200
        d = c.get("/api/cases/Facture1_04").json()
        assert next(z for z in d["analysis"]["zones"] if z["zone_id"] == "Z8")["status"] == "ANOMALIE"


def test_decisions_par_regle_et_montant_confirme():
    with TestClient(app) as c:
        ready(c); login(c, "agent2")
        # Facture1_20 : R12 et R17 en anomalie (0,01 € chacune)
        assert c.post("/api/cases/Facture1_20/decisions", json={"kind": "confirmation", "rule_id": "R12"}).status_code == 200
        r = c.post("/api/cases/Facture1_20/decisions", json={"kind": "faux_positif", "rule_id": "R17", "comment": "arrondi"})
        assert r.status_code == 200
        # le dossier entier passe en « Écart confirmé » : seul R12 doit compter
        assert c.post("/api/cases/Facture1_20/decisions", json={"kind": "statut", "value": "Écart confirmé"}).status_code == 200
        f = c.get("/api/cases/Facture1_20").json()["finance"]
        assert f["confirmed_cents"] == 1 and f["confirmed_rules"] == ["R12"] and f["false_positive_rules"] == ["R17"]
        # confirmer une règle conforme : refusé
        assert c.post("/api/cases/Facture1_20/decisions", json={"kind": "confirmation", "rule_id": "R02"}).status_code == 400
        # annulation de la confirmation
        dec = c.get("/api/cases/Facture1_20").json()["decisions"]
        conf = next(d for d in dec if d["kind"] == "confirmation")
        assert c.post("/api/cases/Facture1_20/decisions", json={"kind": "annulation", "value": str(conf["id"]), "comment": "erreur"}).status_code == 200
        assert c.get("/api/cases/Facture1_20").json()["finance"]["confirmed_cents"] == 0
        login(c, "superviseur")
        s = c.get("/api/supervision").json()
        assert s["finances"]["indu_etabli_cents"] is None and s["finances"]["recupere_cents"] is None
        assert len(s["zones"]) == 15 and all(z["denominateur"] == 55 for z in s["zones"])
        assert sum(s["zones"][7]["counts"].values()) == 55                    # Z8 : chaque dossier compté une fois


def _txt_modifie():
    lines = (corpus_root() / TXT_SUBDIR / "Facture1_02.txt").read_bytes().decode("latin-1").split("\r\n")
    i5 = next(i for i, l in enumerate(lines) if l.startswith("5"))
    lines[i5] = lines[i5][:41] + "00082897" + lines[i5][49:]
    return "\r\n".join(lines).encode("latin-1")


def test_permissions_des_imports():
    img = (corpus_root() / JPG_SUBDIR / "Facture1_02.jpg").read_bytes()
    with TestClient(app) as c:
        ready(c); login(c, "agent1")
        r = c.post("/api/imports", files={"bordereau": ("Facture1_02.jpg", img, "image/jpeg"),
                                          "facture": ("modif.txt", _txt_modifie(), "text/plain")}, data={"label": "privé agent1"})
        assert r.status_code == 200
        iid, jid = r.json()["id"], r.json()["job"]["id"]
        assert wait_job(c, jid)["status"] == "termine"
        assert any(x["id"] == iid for x in c.get("/api/imports").json())
        assert c.get(f"/api/cases/{iid}").json()["analysis"]["zones"][7]["status"] == "ANOMALIE"   # Z8 : 828,97 ≠ 818,97
        # un autre agent ne voit ni la liste, ni le dossier, ni les fichiers, ni le rapport, et ne peut rien faire
        login(c, "agent2")
        assert not any(x["id"] == iid for x in c.get("/api/imports").json())
        assert not any(x["id"] == iid for x in c.get("/api/cases").json())
        for url in (f"/api/cases/{iid}", f"/api/cases/{iid}/image", f"/api/cases/{iid}/txt", f"/api/cases/{iid}/report.pdf",
                    f"/api/jobs/{jid}"):
            assert c.get(url).status_code == 403, url
        assert c.post(f"/api/cases/{iid}/decisions", json={"kind": "commentaire", "comment": "x"}).status_code == 403
        assert c.post(f"/api/cases/{iid}/reanalyze").status_code == 403
        assert c.delete(f"/api/imports/{iid}").status_code == 403
        # l'auditeur consulte mais ne supprime pas ; le gestionnaire voit tout ; statistiques : simulations exclues
        login(c, "auditeur")
        assert c.get(f"/api/cases/{iid}").status_code == 200 and c.delete(f"/api/imports/{iid}").status_code == 403
        login(c, "superviseur")
        assert any(x["id"] == iid for x in c.get("/api/imports").json())
        assert c.get("/api/supervision").json()["dossiers"]["total"] == 55
        # l'agent auteur supprime son import
        login(c, "agent1")
        assert c.delete(f"/api/imports/{iid}").status_code == 200


def test_traitements_idempotents_et_simulation():
    with TestClient(app) as c:
        ready(c); login(c, "agent1")
        j1 = c.post("/api/cases/Facture3_13/reanalyze").json()
        j2 = c.post("/api/cases/Facture3_13/reanalyze").json()        # double-clic
        assert j1["id"] == j2["id"] or wait_job(c, j1["id"])["status"] == "termine"
        wait_job(c, j1["id"])
        # simulation : TXT modifié en mémoire, original intact, valeur de longueur invalide refusée
        bad = c.post("/api/cases/Facture3_13/simulate", json={"edits": [{"line_no": 1, "start": 20, "end": 22, "value": "1"}]})
        assert bad.status_code == 400
        before = (corpus_root() / TXT_SUBDIR / "Facture3_13.txt").read_bytes()
        txt = c.get("/api/cases/Facture3_13").json()["analysis"]["txt"]
        lot = txt["numero_lot"]
        val = "999" if lot["raw"] != "999" else "998"
        r = c.post("/api/cases/Facture3_13/simulate", json={"edits": [{"line_no": lot["line_no"], "start": 20, "end": 22, "value": val}]})
        assert r.status_code == 200, r.text
        assert wait_job(c, r.json()["job"]["id"])["status"] == "termine"
        sim = c.get(f"/api/cases/{r.json()['id']}").json()
        assert sim["analysis"]["source"] == "import"
        assert next(x for x in sim["analysis"]["results"] if x["rule_id"] == "R03")["status"] == "ANOMALIE"
        assert (corpus_root() / TXT_SUBDIR / "Facture3_13.txt").read_bytes() == before
        assert c.delete(f"/api/imports/{r.json()['id']}").status_code == 200


def test_revue_rapide_conventions_qualite_sauvegarde():
    with TestClient(app) as c:
        ready(c); login(c, "agent1")
        q = c.get("/api/review/queue").json()
        assert q and all(x["effective_decision"] is None for x in q) and all(x["zones"] for x in q)
        assert q[0]["source"] == "corpus"
        conv = c.get("/api/conventions").json()["conventions"]
        assert [x["id"] for x in conv] == [f"AMB-0{i}" for i in range(1, 9)]
        amb01 = conv[0]
        assert len(amb01["dossiers_concernes"]) >= 50 and amb01["effet_changement"]["resultats_modifies"] >= 50
        assert conv[4]["effet_changement"] is None and conv[4]["effet_non_simule"]
        login(c, "superviseur")
        qual = c.get("/api/quality").json()
        assert qual["alertes"]["taux_non_verifiables"] is not None
        assert c.post("/api/admin/backup").status_code == 403
        login(c, "admin")
        bk = c.post("/api/admin/backup").json()
        assert bk["verification"]["ok"] and len(bk["sha256"]) == 64
        assert c.get("/api/admin/backups").json()[0]["file"] == bk["file"]
        assert c.get("/api/admin/cache").json()["code_hash"]
