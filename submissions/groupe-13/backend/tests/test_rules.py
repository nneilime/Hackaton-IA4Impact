"""Tests structurels du moteur de règles (données synthétiques de test, jamais comptées dans les statistiques)."""
from sentinel.b2parser import parse_b2
from sentinel.corpus import corpus_root
from sentinel.config import TXT_SUBDIR
from sentinel.rules import compare_read, run_rules, _match_codes, RULES, CONFORME, ANOMALIE, NON_VERIFIABLE
from sentinel.ocr.reader import normalize_reading, _result


def fr(*readings):
    return _result([{"engine": e, "prep": "t", "raw": t, "conf": 0.9} for e, t in readings], "facture")


def test_22_regles():
    assert [r.id for r in RULES] == [f"R{i:02d}" for i in range(1, 23)]


def test_compare_read_statuts():
    assert compare_read(fr(("a", "12345"), ("b", "12345")), "12345")[0] == CONFORME
    assert compare_read(fr(("a", "12346"), ("b", "12346")), "12345")[0] == ANOMALIE
    # une lecture isolée concorde, deux moteurs lisent autre chose -> anomalie à incertitude moyenne
    st, _, lvl, _ = compare_read(fr(("a", "12346"), ("b", "12346"), ("c", "12345")), "12345")
    assert st == ANOMALIE and lvl == "moyenne"
    # deux moteurs ex æquo, l'un lit la valeur du fichier -> v2.0 : NON VÉRIFIABLE (la valeur du fichier ne
    # départage jamais des lectures contradictoires ; ancien comportement v1.2 : conforme à incertitude moyenne)
    st, _, lvl, _ = compare_read(fr(("a", "12346"), ("a", "12346"), ("b", "12345"), ("b", "12345")), "12345")
    assert st == NON_VERIFIABLE and lvl == "forte"
    # la valeur du fichier n'est lue qu'en minorité répétée face à une majorité -> lecture humaine
    assert compare_read(fr(("a", "12346"), ("a", "12346"), ("a", "12346"), ("b", "12345"), ("b", "12345")),
                        "12345")[0] == NON_VERIFIABLE
    assert compare_read(fr(("a", "xx")), "12345")[0] == NON_VERIFIABLE           # illisible
    assert compare_read(_result([], "facture", empty=True), "12345")[0] == NON_VERIFIABLE


def test_normalisations():
    assert normalize_reading("amount", "818,97")[0] == 81897
    assert normalize_reading("amount", "1 013.22")[0] == 101322
    assert normalize_reading("amount", "3/4.4/")[0] is None                    # lecture ambiguë rejetée
    assert normalize_reading("cerfa_code", "S 3404")[0] == "S3404"
    assert normalize_reading("cerfa_id", 'n° 12278"01')[0] == "12278*01"
    assert normalize_reading("code", "JCPDO01")[0] == "JCPD001"
    assert normalize_reading("facture", "000491901")[0] == "491901"


def test_rapprochement_par_occurrence():
    img = [{"codes": ["B"], "code": "B"}, {"codes": ["B"], "code": "B"}]
    txt = [{"code": "B", "line_no": 1}]
    miss_img, miss_txt, pairs = _match_codes(img, txt)
    assert len(miss_img) == 1 and not miss_txt


def test_erreur_technique_isolee():
    t = parse_b2(corpus_root() / TXT_SUBDIR / "Facture1_01.txt")
    res = run_rules(t, {"fields": None, "tables": None})                       # extraction corrompue
    assert len(res) == 22
    assert all(r["status"] in ("ERREUR_TECHNIQUE", "NON_VERIFIABLE", "NON_APPLICABLE", "ANOMALIE", "CONFORME") for r in res)
