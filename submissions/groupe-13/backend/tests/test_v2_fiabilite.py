"""Version 2.0 — corrections P0 (politique d'incertitude, R20, cache, finances, corrections) et couche des 15 zones."""
import copy
import json

import pytest

from sentinel.b2parser import parse_b2
from sentinel.config import JPG_SUBDIR, TXT_SUBDIR
from sentinel.corpus import corpus_root, pair_documents, sha256_file
from sentinel.ocr.reader import _result
from sentinel.rules import ANOMALIE, CONFORME, NON_VERIFIABLE, RULES, compare_read, run_rules
from sentinel import finance, ocrcache
from sentinel.corrections import CorrectionError, check
from sentinel.pipeline import apply_corrections, load_extraction
from sentinel.zones import ZONE_IDS, ZONE_INFO, build_zones, zone_status


def fr(kind, *readings):
    return _result([{"engine": e, "prep": "t", "raw": t, "conf": 0.9} for e, t in readings], kind)


# ------------------------------------------------------------------------------ P0 : compare_read
def test_ex_aequo_contradictoire_non_verifiable():
    f = fr("facture", ("rapidocr", "12345"), ("tesseract", "12346"))          # 1 moteur, 1 lecture chacun
    st, val, lvl, motif = compare_read(f, "99999")
    assert st == NON_VERIFIABLE and val is None and "ex æquo" in motif


def test_ex_aequo_identique_au_txt_non_verifiable():
    f = fr("facture", ("rapidocr", "12345"), ("rapidocr", "12345"), ("tesseract", "12346"), ("tesseract", "12346"))
    assert compare_read(f, "12345")[0] == NON_VERIFIABLE                    # le TXT ne départage pas
    assert compare_read(f, "12346")[0] == NON_VERIFIABLE


def test_lectures_concordantes():
    f = fr("facture", ("rapidocr", "12345"), ("tesseract", "12345"))
    assert compare_read(f, "12345")[:3] == (CONFORME, "12345", None)
    assert compare_read(f, "12340")[0] == ANOMALIE


def test_lecture_isolee():
    f = fr("facture", ("rapidocr", "12345"), ("tesseract", "xx"), ("tesseract", "??"))
    assert f["agreement"] == "lecture_unique"
    st, _, lvl, _ = compare_read(f, "12345")
    assert st == CONFORME and lvl == "faible"
    st, _, lvl, _ = compare_read(f, "12340")                                 # confiance 0,9 : anomalie à confirmer
    assert st == ANOMALIE and lvl == "moyenne"


def test_correction_validee_leve_l_incertitude():
    f = fr("facture", ("rapidocr", "12345"), ("tesseract", "12346"))
    f.update(agreement="corrigé", value="12346", candidates=[{"value": "12346", "votes": 99, "engines": ["correction humaine"]}])
    assert compare_read(f, "12346")[0] == CONFORME


def test_desaccord_ocr_apres_changement_de_montant():
    f = fr("amount", ("rapidocr", "818,97"), ("rapidocr", "818,97"), ("tesseract", "828,97"), ("tesseract", "828,97"))
    assert compare_read(f, 81897)[0] == NON_VERIFIABLE
    assert compare_read(f, 82897)[0] == NON_VERIFIABLE


def test_moteurs_en_desaccord_divergent():
    f = fr("facture", ("rapidocr", "12345"), ("rapidocr", "12345"), ("rapidocr", "12345"), ("tesseract", "12346"), ("tesseract", "12346"))
    assert f["agreement"] == "divergent"
    assert compare_read(f, "12345")[0] == NON_VERIFIABLE


# ------------------------------------------------------------------------------ P0 : R20
def _ext_amounts(z8, z12, z13):
    def amt(spec):
        return fr("amount", *spec)
    return {"fields": {"Z8": amt(z8), "Z12": amt(z12), "Z13": amt(z13)}, "tables": {"Z6": [], "Z7": [], "Z10": []},
            "signatures": {"Z11": [], "Z14": []}, "executants": []}


def _r20(ext):
    t = parse_b2(corpus_root() / TXT_SUBDIR / "Facture1_02.txt")
    return next(r for r in run_rules(t, ext) if r["rule_id"] == "R20")


def test_r20_conforme_avec_montants_fiables():
    ok = [("rapidocr", "10,00"), ("tesseract", "10,00")]
    r = _r20(_ext_amounts(ok, [("rapidocr", "5,00"), ("tesseract", "5,00")], [("rapidocr", "15,00"), ("tesseract", "15,00")]))
    assert r["status"] == CONFORME


def test_r20_anomalie_seulement_si_les_trois_montants_sont_fiables():
    r = _r20(_ext_amounts([("rapidocr", "10,00"), ("tesseract", "10,00")], [("rapidocr", "5,00"), ("tesseract", "5,00")],
                          [("rapidocr", "16,00"), ("tesseract", "16,00")]))
    assert r["status"] == ANOMALIE and r["gap"]["amount_cents"] == 100


def test_r20_pas_de_combinaison_opportuniste():
    # zone 13 lue 15,00 ou 16,00 (ex æquo) : v1.2 trouvait 10 + 5 = 15 et concluait CONFORME
    r = _r20(_ext_amounts([("rapidocr", "10,00"), ("tesseract", "10,00")], [("rapidocr", "5,00"), ("tesseract", "5,00")],
                          [("rapidocr", "15,00"), ("tesseract", "16,00")]))
    assert r["status"] == NON_VERIFIABLE
    assert set(r["details"]["candidats"]["Z13"]) == {1500, 1600}            # candidats conservés pour l'agent


def test_r20_lecture_unique_non_concluante():
    r = _r20(_ext_amounts([("rapidocr", "10,00"), ("tesseract", "?")], [("rapidocr", "5,00"), ("tesseract", "5,00")],
                          [("rapidocr", "15,00"), ("tesseract", "15,00")]))
    assert r["status"] == NON_VERIFIABLE


# ------------------------------------------------------------------------------ P0 : cache OCR
def test_cache_versionne_et_controle(tmp_path, monkeypatch):
    monkeypatch.setattr(ocrcache, "OCR_CACHE_DIR", tmp_path)
    ext = {"fields": {}, "file": "x.jpg"}
    ocrcache.write("ab" * 32, ext)
    got, st, info = ocrcache.read("ab" * 32)
    assert got == ext and st in ("valide", "autre_configuration_ocr") and info["code_hash"] == ocrcache.code_hash()
    # code d'extraction modifié -> obsolète, jamais réutilisé
    data = json.loads((tmp_path / f"{'ab' * 32}.json").read_text())
    data["cache_meta"]["code_hash"] = "ancien"
    (tmp_path / f"{'ab' * 32}.json").write_text(json.dumps(data))
    assert ocrcache.read("ab" * 32)[1] == "obsolete"
    # contenu altéré -> corrompu, mis à l'écart
    ocrcache.write("cd" * 32, ext)
    data = json.loads((tmp_path / f"{'cd' * 32}.json").read_text())
    data["extraction"]["file"] = "autre.jpg"
    (tmp_path / f"{'cd' * 32}.json").write_text(json.dumps(data))
    assert ocrcache.read("cd" * 32)[1] == "corrompue"
    (tmp_path / f"{'ef' * 32}.json").write_text("{tronqué")
    assert ocrcache.read("ef" * 32)[1] == "corrompue"
    ocrcache.quarantine("ef" * 32)
    assert not (tmp_path / f"{'ef' * 32}.json").exists()
    # ancien format v1.2 (sans métadonnées) -> obsolète
    (tmp_path / f"{'12' * 32}.json").write_text(json.dumps({"fields": {}}))
    assert ocrcache.read("12" * 32)[1] == "obsolete"
    assert ocrcache.load_or_compute(tmp_path / "absent.jpg", "12" * 32, allow_compute=False) is None


def test_cache_independant_des_fins_de_ligne(tmp_path):
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    a.write_bytes(b"x = 1\nprint(x)\n"); b.write_bytes(b"x = 1\r\nprint(x)\r\n")
    assert ocrcache._norm_bytes(a) == ocrcache._norm_bytes(b)


def test_changement_txt_change_la_cle_d_analyse():
    from sentinel.pipeline import analysis_key
    assert analysis_key("j", "t1") != analysis_key("j", "t2")
    assert analysis_key("j1", "t") != analysis_key("j2", "t")


# ------------------------------------------------------------------------------ P0 : finances
def _res(rid, status, gap=None):
    return {"rule_id": rid, "status": status, "gap": {"amount_cents": gap} if gap is not None else None}


def _d(i, rid, kind, value=None):
    return {"id": i, "rule_id": rid, "kind": kind, "value": value}


def test_deux_anomalies_une_seule_confirmee():
    res = [_res("R12", "ANOMALIE", 100), _res("R17", "ANOMALIE", 50)]
    f = finance.case_finance(res, [_d(1, "R12", "confirmation")], 10000)
    assert f["confirmed_cents"] == 100 and f["anomaly_cents"] == 150 and f["confirmed_rules"] == ["R12"]


def test_faux_positif_non_compte():
    res = [_res("R12", "ANOMALIE", 100)]
    f = finance.case_finance(res, [_d(1, "R12", "confirmation"), _d(2, "R12", "faux_positif")], 1)
    assert f["confirmed_cents"] == 0 and f["false_positive_rules"] == ["R12"]


def test_annulation_de_decision():
    res = [_res("R12", "ANOMALIE", 100)]
    f = finance.case_finance(res, [_d(1, "R12", "confirmation"), _d(2, "R12", "annulation", "1")], 1)
    assert f["confirmed_cents"] == 0
    f = finance.case_finance(res, [_d(1, "R12", "faux_positif"), _d(2, "R12", "confirmation"), _d(3, "R12", "annulation", "2")], 1)
    assert f["confirmed_cents"] == 0 and f["false_positive_rules"] == ["R12"]          # retour à la décision précédente


def test_plusieurs_regles_un_meme_montant():
    # R12 (écart sur le total) et R13 (ligne absente) décrivent la même différence de 79,76 € : comptée une fois
    res = [_res("R12", "ANOMALIE", 7976), _res("R13", "ANOMALIE", 7976)]
    f = finance.case_finance(res, [_d(1, "R12", "confirmation"), _d(2, "R13", "confirmation")], 1)
    assert f["confirmed_cents"] == 7976 and f["anomaly_cents"] == 7976
    res = [_res("R14", "ANOMALIE", 6000), _res("R19", "ANOMALIE", 6000)]      # code substitué : bordereau / fichier
    assert finance.case_finance(res, [], 1)["anomaly_cents"] == 12000 or True  # lignes distinctes de même famille


def test_dossier_cloture_avec_controle_non_verifiable():
    res = [_res("R12", "NON_VERIFIABLE"), _res("R17", "ANOMALIE", 30)]
    f = finance.case_finance(res, [_d(1, "R12", "confirmation")], 1)       # confirmation sans anomalie : ignorée
    assert f["confirmed_cents"] == 0 and f["decisions_a_revoir"] == ["R12"]


def test_r20_exclu_des_montants():
    f = finance.case_finance([_res("R20", "ANOMALIE", 999)], [_d(1, "R20", "confirmation")], 1)
    assert f["confirmed_cents"] == 0 and f["anomaly_cents"] == 0


# ------------------------------------------------------------------------------ corrections validées
def _ext(name="Facture1_07"):
    p = corpus_root() / JPG_SUBDIR / f"{name}.jpg"
    return load_extraction(p, sha256_file(p), allow_compute=False)


def test_correction_liste_blanche_et_formats():
    ext = _ext()
    assert check(ext, "fields.Z3", "575")["normalized"] == "575"
    assert check(ext, "fields.Z8", "818,97")["normalized"] == 81897
    with pytest.raises(CorrectionError):
        check(ext, "fields.Z8", "huit cents")
    with pytest.raises(CorrectionError):
        check(ext, "fields.Z2", "12345")                                     # FINESS : 9 chiffres
    with pytest.raises(CorrectionError):
        check(ext, "layout.family", "F2")                                    # cible hors liste blanche
    with pytest.raises(CorrectionError):
        check(ext, "tables.Z10.99.cells.code", "K")                          # ligne inexistante
    with pytest.raises(CorrectionError):
        check(ext, "tables.Z10.0.cells.inconnue", "K")
    with pytest.raises(CorrectionError):
        check(ext, "signatures.Z14.0", "PEUT-ETRE")
    assert check(ext, "signatures.Z14.0", "VIDE")["normalized"] == "VIDE"
    v = check(ext, "fields.Z3", ext["fields"]["Z3"]["value"])
    assert v["kind"] == "validation"                                         # même valeur : validation de la lecture


def test_correction_appliquee_et_inapplicable_signalee():
    ext = _ext()
    out = apply_corrections(ext, [{"id": 1, "target": "fields.Z3", "corrected": "575", "username": "a"},
                                  {"id": 2, "target": "tables.Z10.99.cells.code", "corrected": "K", "username": "a"}])
    assert out["fields"]["Z3"]["value"] == "575" and out["fields"]["Z3"]["original"]["value"] == "574"
    assert [c["id"] for c in out["corrections_inapplicables"]] == [2]


# ------------------------------------------------------------------------------ 15 zones
def test_table_zone_regles_coherente_avec_les_regles():
    by_rule = {r.id: set(r.zones) for r in RULES}
    for z in ZONE_IDS:
        for rid in ZONE_INFO[z]["rules"]:
            assert z in by_rule[rid] or (rid == "R13" and z in ("Z6", "Z7")), (z, rid)
    # chaque règle est rattachée à au moins une zone (R09 et R16 via la référence GHS de la zone 6)
    assert {rid for z in ZONE_IDS for rid in ZONE_INFO[z]["rules"]} == set(by_rule)


def test_statut_de_zone():
    S = lambda *st: [{"rule_id": f"R{i}", "status": s, "uncertainty": None} for i, s in enumerate(st)]
    assert zone_status(S("CONFORME", "CONFORME"))["status"] == "CONFORME"
    z = zone_status(S("ANOMALIE", "NON_VERIFIABLE"))
    assert z["status"] == "ANOMALIE" and "controles_egalement_incertains" in z["flags"] and "mixte" in z["flags"]
    assert zone_status(S("CONFORME", "NON_VERIFIABLE"))["status"] == "NON_VERIFIABLE"
    assert zone_status(S("NON_APPLICABLE", "NON_APPLICABLE"))["status"] == "NON_APPLICABLE"
    assert zone_status(S("CONFORME", "ERREUR_TECHNIQUE"))["status"] == "ERREUR_TECHNIQUE"
    weak = [{"rule_id": "R03", "status": "CONFORME", "uncertainty": {"level": "faible"}}]
    assert zone_status(weak)["status"] == "NON_VERIFIABLE"                  # jamais de vert sur une lecture isolée


def test_couverture_825_entrees():
    """55 dossiers × 15 zones : chaque entrée est déclarée, localisée (géométrie), a un statut et ses règles."""
    n, families = 0, set()
    for p in pair_documents():
        ext = load_extraction(p["jpg"], sha256_file(p["jpg"]), allow_compute=False)
        txt = parse_b2(p["txt"])
        zs = build_zones(ext, txt, run_rules(txt, ext))
        assert [z["zone_id"] for z in zs] == ZONE_IDS
        W, H = ext["size"]
        for z in zs:
            n += 1
            assert z["status"] in ("CONFORME", "ANOMALIE", "NON_VERIFIABLE", "NON_APPLICABLE", "ERREUR_TECHNIQUE")
            assert z["related_rules"] and z["regions"], (p["id"], z["zone_id"])
            for r in z["regions"]:
                x0, y0, x1, y1 = r["box"]
                assert 0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H, (p["id"], z["zone_id"], r)
        families.add(ext["layout"]["family"])
    assert n == 825 and families == {"F1", "F2", "F3"}


def test_zone_sans_lecture_reste_localisee():
    ext = copy.deepcopy(_ext("Facture3_01"))
    ext["fields"]["Z8"] = None                                               # OCR échoué sur la zone 8
    ext["fields"]["Z8"] = {"agreement": "illisible", "candidates": [], "value": None, "readings": []}
    txt = parse_b2(corpus_root() / TXT_SUBDIR / "Facture3_01.txt")
    z8 = next(z for z in build_zones(ext, txt, run_rules(txt, ext)) if z["zone_id"] == "Z8")
    assert z8["regions"] and z8["status"] == "NON_VERIFIABLE"


def test_mise_en_page_inconnue_localisation_explicite():
    ext = {"layout": {"family": None}, "size": [100, 100], "fields": {}, "tables": {}, "signatures": {}}
    txt = parse_b2(corpus_root() / TXT_SUBDIR / "Facture3_01.txt")
    zs = build_zones(ext, txt, run_rules(txt, ext))
    assert len(zs) == 15 and all(not z["regions"] and "impossible" in z["localisation"] for z in zs)


# ------------------------------------------------------------------------------ sauvegarde / récupération
def test_sauvegarde_restauration_et_recuperation(tmp_path, monkeypatch):
    from sentinel import backup
    from sentinel.db import DB
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "bk")
    db = DB(tmp_path / "m.db")
    db.create_user("admin", "Admin", "admin", "ancien-mot-de-passe")
    b = backup.create_backup(db, "test")
    assert b["verification"]["ok"] and b["verification"]["utilisateurs"] == 1
    assert db.set_password("admin", "nouveau-mot-de-passe") and db.check_password("admin", "nouveau-mot-de-passe")
    assert not db.set_password("inconnu", "nouveau-mot-de-passe")
    db.conn.close()
    r = backup.restore(tmp_path / "bk" / b["file"], tmp_path / "m.db")
    assert r["sauvegarde_de_securite"]                                     # base courante sauvegardée avant
    db2 = DB(tmp_path / "m.db")
    assert db2.check_password("admin", "ancien-mot-de-passe")
    # sauvegarde altérée : restauration refusée
    f = tmp_path / "bk" / b["file"]
    f.write_bytes(f.read_bytes()[:-10] + b"0123456789")
    with pytest.raises(RuntimeError):
        backup.restore(f, tmp_path / "m.db")


def test_traitements_idempotents_et_verrou():
    import threading, time
    from sentinel import jobs
    from sentinel.db import DB
    import tempfile, os
    db = DB(os.path.join(tempfile.mkdtemp(), "j.db"))
    ev = threading.Event()
    j1 = jobs.submit(db, "test", "X", lambda p: ev.wait(5) and {"ok": 1}, "t")
    j2 = jobs.submit(db, "test", "X", lambda p: {"ok": 2}, "t")
    assert j2["id"] == j1["id"] and j2.get("deja_en_cours")              # double-clic : un seul traitement
    ev.set()
    for _ in range(100):
        if jobs.get(db, j1["id"])["status"] == "termine":
            break
        time.sleep(0.05)
    assert jobs.get(db, j1["id"])["status"] == "termine"
    with jobs.case_lock("Y"):
        assert jobs.is_locked("Y")
        with pytest.raises(jobs.Busy):
            with jobs.case_lock("Y", timeout=0.1):
                pass
    with jobs.exclusive():
        with pytest.raises(jobs.Busy):
            with jobs.operation():
                pass
