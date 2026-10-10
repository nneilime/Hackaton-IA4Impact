"""Version 3.0 — faux positifs corrigés à la cause, contrôle géométrique, conventions décidées, confidentialité,
référentiel de validation."""
import shutil
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from sentinel.b2parser import detect_insertion, original_position, parse_b2
from sentinel.config import JPG_SUBDIR, TXT_SUBDIR
from sentinel.corpus import corpus_root
from sentinel.ocr.layout import _fit_axis, box_geometry, deskew, estimate_skew
from sentinel.privacy import mask_text
from sentinel.rules import NON_VERIFIABLE, compare_read, run_rules

TXT = lambda name: corpus_root() / TXT_SUBDIR / f"{name}.txt"   # noqa: E731


def _lines(p):
    return Path(p).read_bytes().decode("latin-1").split("\r\n")


def _write(lines, tmp):
    p = Path(tmp) / "f.txt"
    p.write_bytes("\r\n".join(lines).encode("latin-1"))
    return p


# ------------------------------------------------------------------ FP-B2 : fichier décalé (Facture2_06)
def test_facture2_06_realignee_et_seul_le_finess_reste_en_anomalie():
    p = parse_b2(TXT("Facture2_06"))
    assert p.realignment and p.realignment["position"] == 11 and len(p.realignment["preuves"]) >= 3
    assert p.alignment_shift == 0
    assert (p.numero_lot.value, p.numero_facture.value, p.numero_assure.value) == ("351", "261034506", "2540699281006")
    assert p.numero_tiers.value == "490002137"                    # avant le caractère inséré : lu tel quel
    assert any(o.code == "FICHIER_REALIGNE" and o.severity == "alerte" for o in p.observations)
    assert all(r.raw_original is not None for r in p.records)     # la ligne d'origine est conservée


def test_realignement_demontre_sur_une_copie_decalee_et_jamais_sur_un_fichier_normal():
    src = _lines(TXT("Facture2_05"))
    with tempfile.TemporaryDirectory() as t:
        shifted = [l[:10] + " " + l[10:] if l else l for l in src]
        p = parse_b2(_write(shifted, t))
        ref = parse_b2(TXT("Facture2_05"))
        assert p.realignment and p.realignment["position"] == 11
        assert [a["acte"] for a in p.acts3] == [a["acte"] for a in ref.acts3]
        assert p.total_prestations.cents == ref.total_prestations.cents
        # une position décalée est reconvertie dans la ligne d'origine pour le surlignage
        assert original_position(p, 20) == 21 and original_position(p, 5) == 5
    for f in sorted((corpus_root() / TXT_SUBDIR).glob("*.txt")):
        if f.stem != "Facture2_06":
            assert detect_insertion(_lines(f)) is None, f.stem


def test_decalage_non_demontre_reste_une_simple_observation():
    src = _lines(TXT("Facture2_05"))
    with tempfile.TemporaryDirectory() as t:
        # caractère inséré NON blanc et à des positions différentes selon les lignes : pas de réalignement
        bad = [(l[:12] + "X" + l[12:]) if i % 2 else (l[:15] + "Y" + l[15:]) for i, l in enumerate(src) if l]
        p = parse_b2(_write(bad, t))
        assert p.realignment is None


# ------------------------------------------------------------------ géométrie
def test_champ_mal_localise_jamais_rouge_ni_vert():
    fr = {"value": "574", "agreement": "concordant", "candidates": [{"value": "574", "votes": 6, "engines": ["rapidocr", "tesseract"]}],
          "geometrie": {"fiable": False, "residu_px": 9.0, "seuil_px": 4.0}}
    assert compare_read(fr, "575")[0] == NON_VERIFIABLE
    assert compare_read(fr, "574")[0] == NON_VERIFIABLE
    fr["agreement"] = "corrigé"                                    # une correction humaine lève le doute
    assert compare_read(fr, "574")[0] == "CONFORME"


def test_geometrie_locale_robuste_a_un_trait_isole():
    res = {"h": [(100, 0.5), (200, 12.0), (300, 0.0)], "v": [(50, 0.0), (150, 0.5), (400, None)]}
    assert box_geometry((40, 150, 160, 190), res, 1.0)["fiable"] is True         # un trait aberrant sur quatre
    res2 = {"h": [(100, 9.0), (200, 12.0)], "v": [(50, 8.0), (150, 7.5)]}
    assert box_geometry((40, 150, 160, 190), res2, 1.0)["fiable"] is False


def test_tableau_mal_decoupe_rend_le_controle_a_verifier():
    from sentinel import ocrcache
    from sentinel.corpus import sha256_file
    from sentinel.ocr.extract import collect_executants
    txt = parse_b2(TXT("Facture1_09"))
    ext, statut, _ = ocrcache.read(sha256_file(corpus_root() / JPG_SUBDIR / "Facture1_09.jpg"))
    if ext is None:
        pytest.skip(f"extraction en cache indisponible ({statut})")
    ext["executants"] = collect_executants(ext["tables"]["Z10"])
    base = {r["rule_id"]: r["status"] for r in run_rules(txt, ext)}
    assert base["R13"] == "ANOMALIE"
    ext = dict(ext, table_checks={"Z6:Z6a": {"geometrie": {"fiable": True}, "fiable": False, "lignes_hautes": [0],
                                             "encre_hors_lignes_px": 0}})
    r13 = next(r for r in run_rules(txt, ext) if r["rule_id"] == "R13")
    assert r13["status"] == NON_VERIFIABLE and "découpage" in r13["uncertainty"]["reason"]


def test_redressement_des_petites_rotations():
    g = np.full((900, 640), 255, np.uint8)
    for y in range(60, 860, 40):
        cv2.line(g, (30, y), (610, y), 0, 2)
        cv2.putText(g, "12345 ABCDE", (40, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 1)
    for a in (-5, -3, -1, 1, 3, 5):
        est = estimate_skew(deskew(g, a))
        assert abs(est + a) <= 0.3, (a, est)


def test_ajustement_echelle_marges():
    prof = np.zeros(1400)
    anchors = [100, 300, 520, 800, 1100]
    for a in anchors:                       # formulaire réduit à 90 % et décalé de 40 px
        prof[int(round(a * 0.9)) + 40] = 50
    s, d, hits = _fit_axis(prof, anchors, 1.0)
    assert hits == len(anchors) and abs(s - 0.9) < 0.01 and abs(d - 40) <= 2


@pytest.mark.parametrize("cid", ["Facture1_04", "Facture2_01", "Facture3_01"])
def test_marges_ou_scan_assombri_ne_changent_pas_la_mise_en_page(cid):
    """Défaut constaté en 3.0 : avec des marges ajoutées, Facture3_01 était pris pour la mise en page 2, et un
    scan assombri de Facture1_04 pour la mise en page 2 ou 3 (lecture de cases fausses → fausses anomalies)."""
    from sentinel.ocr.layout import identify_and_register
    g = cv2.imdecode(np.fromfile(str(corpus_root() / JPG_SUBDIR / f"{cid}.jpg"), np.uint8), cv2.IMREAD_GRAYSCALE)
    expected = "F" + cid[7]
    variants = {"marges": cv2.copyMakeBorder(g, 40, 40, 30, 30, cv2.BORDER_CONSTANT, value=255),
                "assombri": np.clip(g.astype(int) - 40, 0, 255).astype(np.uint8)}
    for name, v in variants.items():
        reg = identify_and_register(v)
        assert reg["family"] == expected, (name, reg["similarities"])
        assert reg["family_margin"] > 0


# ------------------------------------------------------------------ R01 et conventions décidées
def test_r01_montre_lecture_litterale_et_convention():
    ext = {"fields": {"Z1": {"value": "12278*01", "agreement": "concordant", "candidates": [{"value": "12278*01", "votes": 6,
                                                                                             "engines": ["rapidocr", "tesseract"]}]}}}
    txt = parse_b2(TXT("Facture1_02"))
    r01 = next(r for r in run_rules(txt, ext) if r["rule_id"] == "R01")
    assert r01["status"] == "CONFORME"
    assert r01["details"]["interpretations"] == {"litterale": "ANOMALIE", "convention": "CONFORME",
                                                 "appliquee": "convention", "decision": "proposée"}
    assert "non validée par la MSA" in r01["explanation"]
    r01b = next(r for r in run_rules(txt, ext, {"AMB-01": "rejetée"}) if r["rule_id"] == "R01")
    assert r01b["status"] == "ANOMALIE"


# ------------------------------------------------------------------ confidentialité
def test_masquage_des_numeros_d_assure():
    assert mask_text("Bordereau 2520299007005 01 / fichier 2520299007000") == "Bordereau 2••••••••••••01 / fichier 2••••••••••00"
    assert mask_text("facture 260800004, lot 574, 818,97 €") == "facture 260800004, lot 574, 818,97 €"


PWD = "mot-de-passe-test"


def _ready(c):
    import time
    for _ in range(600):
        st = c.get("/api/status").json()
        if st["state"]["phase"] in ("prêt", "erreur"):
            break
        time.sleep(0.5)
    if st["needs_setup"]:
        c.post("/api/setup", json={"admin_username": "admin", "admin_display_name": "Admin", "admin_password": PWD,
                                   "create_demo_accounts": True})


def _login(c, u):
    c.post("/api/logout")
    assert c.post("/api/login", json={"username": u, "password": PWD}).status_code == 200


def test_vues_globales_exports_et_journal_sans_numero_d_assure_complet():
    from sentinel.api import app
    with TestClient(app) as c:
        _ready(c); _login(c, "superviseur")
        full = c.get("/api/cases/Facture1_05").json()
        r05 = next(r for r in full["analysis"]["results"] if r["rule_id"] == "R05")
        assert r05["jpg_value"] == "2520299007005"                       # détail du dossier : valeur complète
        ano = next(a for a in c.get("/api/anomalies").json() if a["case_id"] == "Facture1_05" and a["rule_id"] == "R05")
        assert "2520299007005" not in str(ano) and "•" in ano["jpg_value"]
        csv = c.get("/api/export/results.csv").text
        assert "2520299007005" not in csv and "2520299007000" not in csv
        c.post("/api/cases/Facture1_05/corrections", json={"target": "fields.Z5", "corrected": "252029900700501", "comment": "test"})
        assert "2520299007005" not in str(c.get("/api/audit").json())
        from sentinel.api import db
        assert "2520299007005" not in str(db.q("SELECT details FROM audit"))
        corr = c.get("/api/cases/Facture1_05").json()["analysis"]["corrections"]
        c.delete(f"/api/cases/Facture1_05/corrections/{corr[-1]['id']}")


def test_referentiel_de_validation_et_metriques():
    from sentinel.api import app
    with TestClient(app) as c:
        _ready(c); _login(c, "agent1")
        items = c.get("/api/validation").json()["items"]
        assert any(i["status"] == "ANOMALIE" for i in items) and any(i["echantillon_conformes"] for i in items)
        assert c.post("/api/validation", json={"case_id": "Facture1_04", "rule_id": "R12", "verdict": "faux_positif"}).status_code == 400
        assert c.post("/api/validation", json={"case_id": "Facture1_04", "rule_id": "R12", "verdict": "ecart_reel"}).status_code == 200
        _login(c, "agent2")
        assert c.post("/api/validation", json={"case_id": "Facture1_04", "rule_id": "R12", "verdict": "faux_positif",
                                               "cause": "FP-OCR"}).status_code == 200
        _login(c, "superviseur")
        m = c.get("/api/validation/metrics").json()
        assert m["desaccords"] >= 1 and m["double_revue"] >= 1
        assert m["precision"] is None or m["matrice"]["VP"] + m["matrice"]["FP"] >= 1
        # la revue assistée par IA n'est jamais comptée comme validation humaine
        assert m["validations_humaines"] == 2
        img = c.get("/api/cases/Facture1_04/crop?rule=R12")
        assert img.status_code == 200 and img.headers["content-type"] == "image/png"


def test_corpus_absent_signale_sans_bloquer(monkeypatch, tmp_path):
    from sentinel import pipeline
    monkeypatch.setattr(pipeline, "pair_documents", lambda: (_ for _ in ()).throw(FileNotFoundError("absent")))
    assert all(p.get("source") != "corpus" for p in pipeline.all_pairs())
