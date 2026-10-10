"""Tests du parseur B2 sur les 55 fichiers réels du corpus."""
from pathlib import Path
import pytest
from sentinel.b2parser import parse_b2, classify, extract_field
from sentinel.corpus import corpus_root
from sentinel.config import TXT_SUBDIR

TXT = sorted((corpus_root() / TXT_SUBDIR).glob("*.txt"))


def test_55_fichiers():
    assert len(TXT) == 55


@pytest.mark.parametrize("p", TXT, ids=lambda p: p.name)
def test_aucune_ligne_perdue(p):
    r = parse_b2(p)
    raw = p.read_bytes().decode("latin-1").split("\r\n")
    nonempty = [l for l in raw if l]
    assert len(r.records) == len(nonempty)
    assert [x.raw_original or x.raw for x in r.records] == nonempty   # aucun strip global ; ligne d'origine conservée
    assert all(x.rtype in "123456" for x in r.records)
    assert r.numero_tiers and r.total_prestations and r.total_honoraires


def test_positions_facture1_01():
    r = parse_b2(corpus_root() / TXT_SUBDIR / "Facture1_01.txt")
    assert r.numero_tiers.value == "200200145" and (r.numero_tiers.start, r.numero_tiers.end) == (2, 10)
    assert r.numero_lot.value == "574"
    assert r.numero_assure.value == "2520299007001"
    assert r.numero_facture.value == "260800001"
    assert [a["acte"] for a in r.acts3] == ["GHS", "PH8", "EMI"]
    assert {a["gh"] for a in r.acts3} == {"9606"}
    assert [a["acte"] for a in r.acts4] == ["K"]
    assert r.total_prestations.cents == 81897          # 818,97 € (2 décimales implicites)
    assert r.total_honoraires.cents == 2880
    kinds = [x.kind for x in r.records]
    assert "3S" in kinds and "3H" in kinds and "4S" in kinds


def test_zeros_initiaux_conserves():
    r = parse_b2(corpus_root() / TXT_SUBDIR / "Facture3_01.txt")
    assert r.numero_facture.value == "000491901"        # chaîne, zéros conservés


def test_ccam_7_caracteres():
    r = parse_b2(corpus_root() / TXT_SUBDIR / "Facture2_01.txt")
    assert [c["code7"] for c in r.ccam4m][:2] == ["JCPD001", "YYYY405"]
    assert all(c["parent_line"] for c in r.ccam4m)


def test_sous_types_et_priorites():
    l = "3" + "x" * 34 + "H" + "xx" + "S" + "x" * 80        # S en 39 prioritaire sur H en 36
    assert classify(l) == ("3", "S")
    assert classify("3" + "x" * 34 + "H" + "x" * 90) == ("3", "H")
    assert classify("4" + "x" * 34 + "M" + "x" * 30) == ("4", "M")
    assert classify("2" + "x" * 37 + "S" + "x" * 30) == ("2", "S")


def test_ligne_trop_courte():
    f = extract_field("4" * 50, 7, "Acte", 76, 80, "code")
    assert f.status == "line_too_short" and f.value is None


def test_longueurs_variables():
    lens = {x.length for p in TXT for x in parse_b2(p).records}
    assert len(lens) > 5 and 128 in lens


def test_facture2_06_decalage_demontre_et_realigne():
    """v3.0 : le caractère blanc inséré en position 11 est démontré par des vérifications internes au fichier ; la
    lecture réalignée est utilisée et signalée. Les observations v2 « DECALAGE_POSITIONS » et « DEBUT_FACTURE_REPETE »
    étaient des artefacts du décalage (l'enregistrement 2-S était lu comme un second début de facture)."""
    r = parse_b2(corpus_root() / TXT_SUBDIR / "Facture2_06.txt")
    codes = {o.code for o in r.observations}
    assert "FICHIER_REALIGNE" in codes and "DEBUT_FACTURE_REPETE" not in codes
    assert r.alignment_shift == 0 and r.realignment["position"] == 11
    assert len(r.invoice_headers) == 1


def test_sans_entete_type0_non_bloquant():
    r = parse_b2(TXT[0])
    o = [x for x in r.observations if x.code == "SANS_ENTETE_0"]
    assert o and o[0].severity == "info"
