"""Flux complet sur le corpus réel : fichier source -> extraction (cache) -> règles -> stockage.
Instantané de régression des résultats RÉELS obtenus sur le corpus (voir docs/RESULTATS.md)."""
import json
from sentinel.db import DB
from sentinel.pipeline import init_corpus, analyze_all

EXPECTED = {
    "Facture1_01": ["R18"], "Facture1_02": [], "Facture1_03": ["R21"], "Facture1_04": ["R12"], "Facture1_05": ["R05"],
    "Facture1_09": ["R13"], "Facture1_12": ["R14", "R19"], "Facture1_19": ["R09", "R10", "R16"],
    "Facture2_02": ["R18"], "Facture2_04": ["R01", "R04", "R05"], "Facture2_19": ["R14"], "Facture2_20": ["R19"],
    "Facture3_02": ["R21"], "Facture3_08": ["R07"], "Facture3_13": [], "Facture3_15": ["R19"],
}


def test_flux_complet(tmp_path):
    db = DB(tmp_path / "it.db")
    init_corpus(db)
    r = analyze_all(db, "test", allow_compute=False)
    assert r["n_cases"] == 55
    rows = {c["id"]: c for c in db.q("SELECT * FROM cases")}
    assert len(rows) == 55
    for cid, rules in EXPECTED.items():
        got = [x["rule_id"] for x in db.q("SELECT rule_id FROM check_results WHERE case_id=? AND status='ANOMALIE' ORDER BY rule_id", (cid,))]
        assert got == rules, cid
    p = json.loads(db.one("SELECT payload FROM analyses WHERE case_id='Facture1_04'")["payload"])
    r12 = next(x for x in p["results"] if x["rule_id"] == "R12")
    assert r12["gap"]["amount_cents"] == 1                       # 818,98 € - 818,97 €
    assert r12["txt_refs"][0]["line_no"] == 12 and r12["img_refs"][0]["box"]
    assert db.one("SELECT COUNT(*) n FROM check_results WHERE status='ERREUR_TECHNIQUE'")["n"] == 0
