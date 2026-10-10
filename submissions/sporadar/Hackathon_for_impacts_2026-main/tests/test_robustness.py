"""Diagnostic du banc de robustesse (scripts/run_robustness.py) : une réponse factice par étape fautive, sans réseau."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_robustness", ROOT / "scripts" / "run_robustness.py")
rr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rr)

COLUMNS = ["expected_intent", "expected_product_id", "expected_entity", "expected_crop", "expected_target",
           "expected_countries", "expected_status", "expected_answer_regex"]


def row(**values):
    base = {c: "" for c in COLUMNS}
    base.update({"expected_intent": "ingredient_search", "expected_status": "answered|partial"})
    base.update({f"expected_{k}": v for k, v in values.items()})
    return base


def response(status="answered", intent="ingredient_search", evidence=1, answer="Réponse.", **params):
    p = {"productIds": [], "countries": [], "activeEntity": None, "crop": None, "target": None}
    p.update(params)
    return {"answerStatus": status, "intent": intent, "parameters": p, "answer": answer,
            "evidence": [{}] * evidence, "facts": []}


def test_ok():
    assert rr.diagnose(row(crop="GLXMA"), 200, response(crop="GLXMA"), 3) == ("ok", [])


def test_technical():
    assert rr.diagnose(row(), 500, {"detail": "boom"}, 3)[0] == "technical"
    assert rr.diagnose(row(), 0, {"exception": "Timeout"}, None)[0] == "technical"


def test_understanding_intent():
    assert rr.diagnose(row(), 200, response(intent="registration_lookup"), 3)[0] == "understanding_intent"


def test_understanding_params_missing_product_and_country():
    stage, issues = rr.diagnose(row(product_id="P-LPC-M52", countries="FR;DE"), 200,
                                response(productIds=["P-LPC-G46"], countries=["FR"]), 3)
    assert stage == "understanding_params"
    assert len(issues) == 2


def test_resolution_eppo_blocks_when_result_wrong():
    # Cas réel : « rouille asiatique du soja » reste en texte brut -> no_data
    stage, _ = rr.diagnose(row(crop="GLXMA", target="PHAKPA"), 200,
                           response("no_data", crop="GLXMA", target="rouille asiatique du soja", evidence=0), 50)
    assert stage == "resolution_eppo"


def test_resolution_eppo_is_secondary_when_answer_ok():
    # Texte brut au lieu du code EPPO, mais la réponse est bonne : OK, l'écart reste listé en secondaire
    stage, issues = rr.diagnose(row(target="BOTRCI"), 200, response(target="botrytis"), 3)
    assert stage == "ok"
    assert issues and issues[0].startswith("[resolution_eppo]")


def test_filtering_when_probe_finds_data():
    # Cas réel : Phakopsora pachyrhizi + soja, code CA n'a jamais culture ET cible sur la même ligne
    stage, _ = rr.diagnose(row(crop="GLXMA", target="PHAKPA|phakopsora"), 200,
                           response("no_data", crop="GLXMA", target="Phakopsora pachyrhizi", evidence=0), 50)
    assert stage == "filtering"


def test_data_absent_when_probe_empty():
    assert rr.diagnose(row(), 200, response("no_data", evidence=0), 0)[0] == "data_absent"


def test_status_mismatch():
    assert rr.diagnose(row(), 200, response("needs_clarification", evidence=0), None)[0] == "status_mismatch"


def test_answer_text_and_guardrail():
    r = row(status="no_data", answer_regex="pas une preuve")
    assert rr.diagnose(r, 200, response("no_data", answer="Non homologué.", evidence=0), None)[0] == "answer_text"
    assert rr.diagnose(row(), 200, response(evidence=0), 3)[0] == "guardrail"


def test_corpus_is_valid():
    rows = rr.load_corpus()
    assert len(rows) >= 50


def test_probe_count_of():
    assert rr.probe_count_of({"items": [1, 2]}) == 2
    assert rr.probe_count_of({"candidates": [1]}) == 1
    assert rr.probe_count_of({"rows": [], "registrations": [1]}) == 0
