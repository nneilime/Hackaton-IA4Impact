"""Tests de backend/etl/normalize.py (pas de base de données nécessaire)."""
import sys
from pathlib import Path

# Rend backend/etl importable depuis tests/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "etl"))

import normalize as nz  # noqa: E402


def test_crop_german_plural():
    result = nz.normalize_crop("Tomaten")
    assert result["eppo_code"] == "LYPES"
    assert result["normalized"] == "Tomato"
    assert result["method"] == "lpc_mapping"


def test_crop_case_accent_and_spaces():
    assert nz.normalize_crop("  weinREBE ")["eppo_code"] == "VITVI"
    assert nz.normalize_crop("Pêcher")["eppo_code"] == "PRNPS"
    assert nz.normalize_crop("PECHER")["eppo_code"] == "PRNPS"


def test_target_french_alias():
    assert nz.normalize_target("pourriture grise")["eppo_code"] == "BOTRCI"


def test_unknown_words_return_none():
    assert nz.normalize_crop("xyzzy") is None
    assert nz.normalize_target("xyzzy") is None
    assert nz.normalize_active_entity("xyzzy") is None
    assert nz.normalize_crop("") is None


def test_ambiguous_alias_returns_none():
    # "mosca blanca" désigne deux concepts (T. vaporariorum et B. tabaci) : on ne tranche pas
    assert nz.normalize_target("mosca blanca") is None


def test_active_entity_former_name():
    result = nz.normalize_active_entity("Gliocladium catenulatum J1446")
    assert result["species"] == "Clonostachys rosea"
    assert result["strain"] == "J1446"


def test_active_entity_does_not_invent_strain():
    result = nz.normalize_active_entity("Coniothyrium minitans")
    assert result["species"] == "Coniothyrium minitans"
    assert result["strain"] is None  # la souche n'est pas écrite dans le texte


def test_search_terms_include_current_name():
    terms = [t.lower() for t in nz.search_terms_for("Gliocladium")]
    assert "clonostachys rosea" in terms


def test_search_terms_unknown_term_is_kept():
    assert nz.search_terms_for("xyzzy") == ["xyzzy"]


def test_sisters_same_species_and_strain():
    products = [
        {"product_id": "A", "commercial_name": "TEST A", "active_entity_original": "Gliocladium catenulatum J1446"},
        {"product_id": "B", "commercial_name": "TEST B", "active_entity_original": "Clonostachys rosea J1446"},
        {"product_id": "C", "commercial_name": "TEST C", "active_entity_original": "Clonostachys rosea"},
    ]
    found = {(c["product_a_id"], c["product_b_id"]): c for c in nz.find_sister_candidates(products)}
    assert found[("A", "B")]["confidence"] == 0.9
    assert found[("A", "C")]["confidence"] == 0.6
    assert all(c["review_status"] == "to_verify" for c in found.values())


def test_sisters_different_strains_are_not_linked():
    products = [
        {"product_id": "A", "commercial_name": "A", "active_entity_original": "Metarhizium brunneum F52"},
        {"product_id": "B", "commercial_name": "B", "active_entity_original": "Metarhizium brunneum strain Ma 43"},
    ]
    assert nz.find_sister_candidates(products) == []


def test_sisters_from_name_mapping_keep_their_status():
    products = [{"product_id": "P-LPC-G46", "commercial_name": "LALSTOP G46 WG"}]
    names = {c["product_b"]: c for c in nz.find_sister_candidates(products)}
    assert names["PRESTOP"]["confidence"] == 0.85
    assert names["PRESTOP"]["review_status"] == "to_verify"


# --- Dictionnaire de traduction suggéré par l'IA (data/ai_term_mapping.csv) ---------------------
def test_ai_mapping_same_disease_in_german_and_french():
    de = nz.normalize_target("Echter Mehltau")
    fr = nz.normalize_target("Oïdium(s)")
    assert de["normalized"] == fr["normalized"] == "Powdery mildew"
    assert nz.normalize_target("Echte Mehltaupilze")["normalized"] == "Powdery mildew"   # forme publiée par le BVL
    assert de["method"] == fr["method"] == "ai_suggested"
    assert de["mapping_status"] == "ai_suggested"
    assert de["group"] == fr["group"] == "Powdery mildews"


def test_ai_mapping_unknown_value_returns_none():
    assert nz.normalize_crop("Plante imaginaire xyzzy") is None
    assert nz.normalize_target("Ravageur imaginaire xyzzy") is None


def test_ai_mapping_never_invents_eppo_code():
    found = nz.normalize_crop("Zierpflanzen")
    assert found["normalized"] == "Ornamental plants"
    assert found["eppo_code"] is None   # catégorie large : pas de code EPPO
    assert found["group"] == "Ornamentals"


def test_ai_mapping_keeps_review_info():
    found = nz.normalize_crop("Zierpflanzen")
    assert found["review_status"] == "to_verify"
    assert found["model_name"] and found["confidence"] is not None


def test_ai_mapping_composite_value():
    assert nz.normalize_crop("Tomate - Aubergine")["normalized"] == "Tomato; Eggplant"


def test_lpc_mapping_has_priority_over_ai_mapping(monkeypatch):
    # on fabrique une ligne IA qui contredit le mapping LPC pour "Tomate" : le résultat LPC doit rester
    fake = {("crop", nz.clean("Tomate")): {
        "kind": "crop", "value_original": "Tomate", "normalized_en": "WRONG", "group_en": "WRONG",
        "eppo_code_candidate": "XXXXX", "confidence": "0.9", "method": "ai_suggested",
        "model_name": "test", "review_status": "to_verify"}}
    monkeypatch.setattr(nz, "_load_ai_index", lambda: fake)
    found = nz.normalize_crop("Tomate")
    assert found["method"] == "lpc_mapping"
    assert found["eppo_code"] == "LYPES" and found["normalized"] == "Tomato"


def test_ai_mapping_validated_row_becomes_validated(monkeypatch):
    row = {"kind": "crop", "value_original": "Foo", "normalized_en": "Foo crop", "group_en": "Bar",
           "eppo_code_candidate": "", "confidence": "0.9", "method": "ai_suggested",
           "model_name": "test", "review_status": "validated"}
    monkeypatch.setattr(nz, "_load_ai_index", lambda: {("crop", "foo"): row})
    assert nz.normalize_crop("Foo")["mapping_status"] == "validated"


# --- Extension du dictionnaire aux termes canadiens (anglais) ---------------------------------
def test_ai_mapping_canadian_crop_types_share_the_species_name():
    spring, winter = nz.normalize_crop("SPRING WHEAT"), nz.normalize_crop("WINTER WHEAT")
    assert spring["normalized"] == winter["normalized"] == "Wheat"   # même nom que « Blé » (FR) et « Weizen » (DE)
    assert spring["eppo_code"] == winter["eppo_code"] == "TRZAX"
    assert nz.normalize_crop("Weizen")["normalized"] == nz.normalize_crop("Blé")["normalized"] == "Wheat"


def test_ai_mapping_canadian_weeds_are_grouped_as_weeds():
    for value in ("REDROOT PIGWEED", "WILD BUCKWHEAT", "KOCHIA"):
        assert nz.normalize_target(value)["group"] == "Weeds - dicotyledonous"
    assert nz.normalize_target("BARNYARD GRASS")["group"] == "Weeds - monocotyledonous"
    assert nz.normalize_target("LAMBS-QUARTERS")["normalized"] == nz.normalize_target("LAMB?S-QUARTERS")["normalized"]


def test_ai_mapping_non_agricultural_categories_are_not_forced_to_a_crop():
    for value in ("ROADSIDES", "RANGELAND", "SUMMERFALLOW", "AIRPORTS"):
        found = nz.normalize_crop(value)
        assert found["group"] == "Non-crop areas" and found["eppo_code"] is None
        assert "not a crop" in (_ai_note(value) or "")
    assert nz.normalize_target("TANK MIX")["group"] == "Application context"


def _ai_note(value):
    row = nz._load_ai_index().get(("crop", nz.clean(value)))
    return row["note"] if row else None


def test_ai_mapping_file_is_consistent():
    """Un même nom normalisé porte toujours le même code EPPO (sinon /compare n'alignerait pas les pays) ; rien d'incomplet."""
    codes = {}
    for (kind, _), row in nz._load_ai_index().items():
        assert row["normalized_en"] and row["group_en"], row["value_original"]
        assert row["method"] == "ai_suggested" and row["model_name"]
        assert row["review_status"] in ("to_verify", "validated")
        assert 0 <= float(row["confidence"]) <= 1
        codes.setdefault((kind, row["normalized_en"]), set()).add(row["eppo_code_candidate"])
    assert {name for name, values in codes.items() if len(values) > 1} == set()
