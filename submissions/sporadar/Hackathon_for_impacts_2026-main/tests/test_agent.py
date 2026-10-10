"""Tests de l'agent /ask (backend/app/agent.py), avec ET sans clé IA.

Chaque scénario tourne sur deux « sources de données » :
  - "fake" : un faux `services` en mémoire (toujours disponible, aucune base nécessaire) ;
  - "live" : la vraie base PostgreSQL (ignoré si DATABASE_URL est absent ou si la base est vide).
Les réponses du LLM sont toujours SIMULÉES (aucun appel réseau, aucune clé nécessaire).
"""
import json
import os
from datetime import date, datetime, timezone
from functools import lru_cache

import pytest

from backend.app import agent, llm
from backend.app import models as m
from backend.app import services

DISCLAIMER = services.DISCLAIMER
NOT_COVERED_US = "US : marché non couvert par le prototype (aucune source officielle intégrée)."


# ---------------------------------------------------------------------------
# Faux `services` : mêmes formes de données que les vraies fonctions
# ---------------------------------------------------------------------------
def make_evidence(rid, source="FR-EPHY", status="automatically_extracted"):
    return {"evidenceId": f"registration:{rid}", "sourceId": source, "sourceName": f"Source {source}",
            "sourceUrl": "https://example.org/source", "sourceRecordUrl": f"https://example.org/record/{rid}",
            "collectedAt": datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc), "validationStatus": status,
            "isFrozenExtract": True, "isSynthetic": False, "languageOriginal": "fr"}


def make_registration(rid, cc, number, status="active", via=None, warnings=None, expiration=None, source="FR-EPHY"):
    return {"registrationId": rid, "productId": "P-LPC-G46", "countryCode": cc, "authorityName": "Autorité",
            "registrationNumber": number, "statusOriginal": status.upper(), "statusNormalized": status,
            "approvalDate": date(2020, 1, 15), "expirationDate": expiration,
            "productNameOriginal": "LALSTOP G46 WG", "activeEntityOriginal": "Clonostachys rosea souche J1446",
            "matchedVia": via or {"matchedName": "LALSTOP G46 WG", "matchedOn": "commercial_name"},
            "missingFields": [], "warnings": warnings or [], "isSynthetic": False, "uses": [],
            "evidence": make_evidence(rid, source)}


def make_use(uid, rid, cc, dose):
    return {"useId": uid, "cropOriginal": "tomate", "cropNormalized": "Tomato", "eppoCropCode": "LYPES",
            "targetOriginal": "botrytis", "targetNormalized": "Botrytis cinerea", "eppoTargetCode": "BOTRCI",
            "doseValue": dose, "doseUnitOriginal": "kg/ha", "doseUnitNormalized": "kg/ha", "maxApplications": 3,
            "applicationIntervalDays": 7.0, "phiDays": 1.0, "reiHours": None, "restrictionsOriginal": None,
            "isSynthetic": False, "evidence": make_evidence(rid)}


FR_REGS = [make_registration("FR-EPHY-2230771", "FR", "2230771", expiration=date(2027, 3, 31)),
           make_registration("FR-EPHY-2120177", "FR", "2120177", status="withdrawn")]
CA_REGS = [make_registration("CA-PPID-28820", "CA", "28820", source="CA-PPID",
                             via={"matchedName": "Clonostachys rosea", "matchedOn": "active_entity_alias",
                                  "aliasReviewStatus": "to_verify", "aliasConfidenceScore": 0.6},
                             warnings=["Correspondance par la substance active, encore à vérifier."])]
ALL_REGS = FR_REGS + CA_REGS


def make_coverage(cc, regs):
    if regs:
        return {"countryCode": cc, "outcome": "found", "sourceIds": sorted({r["evidence"]["sourceId"] for r in regs}),
                "registrationIds": [r["registrationId"] for r in regs], "searchedTerms": ["LALSTOP G46 WG"],
                "lastCollectedAt": datetime(2026, 10, 10, tzinfo=timezone.utc), "note": None}
    return {"countryCode": cc, "outcome": "not_covered", "sourceIds": [], "registrationIds": [], "searchedTerms": [],
            "lastCollectedAt": None, "note": "No integrated source for this country yet. Not proof of no registration."}


class FakeServices:
    """Remplace les fonctions de services.py utilisées par l'agent."""

    def product_registrations(self, product_id, country, include_synthetic, limit, offset, uses_limit):
        if product_id != "P-LPC-G46":
            raise services.NotFound(product_id)
        shown = [country] if country else ["CA", "US", "FR", "DE"]
        items = [r for r in ALL_REGS if r["countryCode"] in shown]
        coverage = [make_coverage(cc, [r for r in items if r["countryCode"] == cc]) for cc in shown]
        return {"items": items, "coverage": coverage, "warnings": services.coverage_warnings(coverage),
                "disclaimer": DISCLAIMER}

    def get_product(self, product_id):
        if product_id != "P-LPC-G46":
            raise services.NotFound(product_id)
        return {"product_id": product_id, "commercial_name": "LALSTOP G46 WG"}

    def search_products(self, q, *args, **kwargs):
        if q and q.lower().startswith("serenade"):   # deux produits au nom voisin : ambigu
            return {"items": [{"productId": "P-1", "commercialName": "SERENADE ASO", "matchedVia": {"matchedOn": "commercial_name"}},
                              {"productId": "P-2", "commercialName": "SERENADE MAX", "matchedVia": {"matchedOn": "commercial_name"}}]}
        return {"items": []}

    def sister_candidates(self, product_id, include_synthetic):
        def cand(cid, name, score, evidence):
            return {"candidateId": cid, "productId": product_id, "candidateName": name, "candidateProductId": None,
                    "marketOrCountry": "FR", "relationshipType": "sister_product_candidate", "sharedTraits": [],
                    "confidenceScore": score, "reviewStatus": "to_verify", "evidenceSummary": "Same strain family",
                    "evidenceType": "internal_product_list", "evidence": evidence}
        return {"productId": product_id, "disclaimer": DISCLAIMER,
                "warnings": ["Hypothèses à confirmer : un produit sœur n'est jamais confirmé tant que reviewStatus n'est pas « validated »."],
                "candidates": [cand("PNM-004", "PRESTOP", 0.85, [make_evidence("FR-EPHY-2120177")]),
                               cand("PNM-006", "LALFRESH S", 0.7, [])]}

    def compare_uses(self, product_id, countries, crop, target, include_synthetic, limit, offset, granularity="use"):
        regs = [r for r in ALL_REGS if r["countryCode"] in countries]
        fr_use, ca_use = make_use("U-FR-1", "FR-EPHY-2230771", "FR", 2.0), make_use("U-CA-1", "CA-PPID-28820", "CA", 3.5)
        row = {"rowId": "eppo:LYPES|eppo:BOTRCI", "cropNormalized": "Tomato", "eppoCropCode": "LYPES",
               "targetNormalized": "Botrytis cinerea", "eppoTargetCode": "BOTRCI", "differsAcrossCountries": True,
               "cells": [{"countryCode": "FR", "state": "present", "registrationId": "FR-EPHY-2230771", "uses": [fr_use]},
                         {"countryCode": "CA", "state": "present", "registrationId": "CA-PPID-28820", "uses": [ca_use]}]}
        coverage = [make_coverage(cc, [r for r in regs if r["countryCode"] == cc]) for cc in countries]
        return {"productId": product_id, "countries": countries, "registrations": regs, "rows": [row],
                "coverage": coverage, "warnings": services.coverage_warnings(coverage), "disclaimer": DISCLAIMER}

    def data_issues(self, product_id, country, issue_type, include_synthetic, limit, offset):
        issue = {"issueId": "not_validated:registration:FR-EPHY-2230771:validationStatus", "issueType": "not_validated",
                 "priority": "high", "productId": "P-LPC-G46", "countryCode": "FR", "entityType": "registration",
                 "entityId": "FR-EPHY-2230771", "field": "validationStatus", "detail": "validationStatus = automatically_extracted",
                 "confidence": None, "validationStatus": "automatically_extracted",
                 "evidence": [make_evidence("FR-EPHY-2230771")]}
        return {"items": [issue], "countsByType": {"not_validated": 2, "missing": 1}, "disclaimer": DISCLAIMER}

    def expirations(self, within_months, reference_date, country, crop, include_synthetic, limit, offset):
        item = {"registrationId": "FR-EPHY-2230771", "productId": "P-LPC-G46", "commercialName": "LALSTOP G46 WG",
                "countryCode": "FR", "registrationNumber": "2230771", "statusNormalized": "active",
                "expirationDate": date(2027, 3, 31), "daysUntilExpiration": 172,
                "evidence": make_evidence("FR-EPHY-2230771")}
        return {"referenceDate": reference_date, "withinMonths": within_months, "items": [item], "warnings": [],
                "disclaimer": DISCLAIMER}

    def list_sources(self):
        return {"items": [{"sourceId": "FR-EPHY", "officialName": "E-Phy", "countryCodes": ["FR"], "accessMethod": "download"}]}

    def registrations_of_products(self, *args, **kwargs):
        return [], []


@lru_cache(maxsize=1)
def live_available():
    """True si la vraie base est joignable et contient le produit pilote."""
    if not os.environ.get("DATABASE_URL"):
        return False
    try:
        from backend.app.db import query
        return bool(query("SELECT 1 FROM products WHERE product_id = 'P-LPC-G46'"))
    except Exception:   # noqa: BLE001
        return False


@pytest.fixture(params=["fake", "live"])
def backend(request, monkeypatch):
    """Source des données : faux services en mémoire, ou vraie base (ignorée si indisponible)."""
    if request.param == "live":
        if not live_available():
            pytest.skip("base PostgreSQL indisponible ou vide")
    else:
        fake = FakeServices()
        for name in ("product_registrations", "get_product", "search_products", "sister_candidates", "compare_uses",
                     "data_issues", "expirations", "list_sources", "registrations_of_products"):
            monkeypatch.setattr(services, name, getattr(fake, name))
    return request.param


@pytest.fixture
def no_ai(monkeypatch):
    """Mode sans clé IA : aucun appel au LLM."""
    monkeypatch.setattr(llm, "is_configured", lambda: False)


@pytest.fixture
def fake_ai(monkeypatch):
    """Simule un LLM : `fake_ai(writer)` ; `writer(payload)` renvoie le texte du rédacteur. Compréhension : mots-clés."""
    def install(writer):
        def complete(system, user, json_mode=False):
            return None if json_mode else writer(json.loads(user))   # None = « compréhension indisponible »
        monkeypatch.setattr(llm, "is_configured", lambda: True)
        monkeypatch.setattr(llm, "complete", complete)
    return install


def ask(question, **extra):
    return agent.ask(m.AskRequest(question=question, **extra))


def first_evidence_id(payload):
    return payload["faits"][0]["evidenceIds"][0]


# ---------------------------------------------------------------------------
# Mode sans clé
# ---------------------------------------------------------------------------
def test_keyword_mode_countries_of_g46(backend, no_ai):
    answer = ask("Dans quels pays LALSTOP G46 est-il homologué ?")
    assert answer["facts"], "des faits sont attendus"
    assert all(f["evidenceIds"] for f in answer["facts"])
    codes = {c["countryCode"] for c in answer["coverage"]}
    assert {"FR", "CA"} <= codes
    assert answer["generator"]["mode"] == "keyword"
    assert answer["intent"] == "registration_lookup"
    assert answer["disclaimer"] == DISCLAIMER
    assert answer["suggestedQuestions"]
    # chaque preuve citée dans le texte existe dans la réponse
    evidence_ids = {e["evidenceId"] for e in answer["evidence"]}
    assert all(i in evidence_ids for f in answer["facts"] for i in f["evidenceIds"])
    assert "[" in answer["answer"] and answer["answerStatus"] in ("answered", "partial")


def test_country_without_data_gets_the_safe_phrase(backend, no_ai):
    answer = ask("LALSTOP G46 est-il homologué aux États-Unis ?")
    assert NOT_COVERED_US in answer["answer"]
    assert "non homologué" not in answer["answer"].lower()
    assert [c["outcome"] for c in answer["coverage"]][0] in ("not_covered", "not_found", "source_unavailable")
    assert answer["answerStatus"] == "no_data"
    assert not answer["facts"]


def test_sister_products_are_hypotheses(backend, no_ai):
    answer = ask("Quels produits pourraient être des produits sœurs de LALSTOP G46 ?")
    assert answer["intent"] == "sister_product"
    assert answer["sisterCandidates"], "au moins un candidat attendu"
    assert all(c["reviewStatus"] == "to_verify" for c in answer["sisterCandidates"])
    assert "candidat" in answer["answer"].lower()
    assert "sœur" not in answer["answer"].lower() or "hypoth" in answer["answer"].lower()


def test_followup_context_product_and_countries(backend, no_ai):
    """Le productId / countries du corps de requête servent de contexte quand la question n'en nomme pas."""
    answer = ask("Comparer les usages entre deux pays.", productId="P-LPC-G46", countries=["FR", "CA"])
    assert answer["intent"] == "use_comparison"
    assert answer["parameters"]["productIds"] == ["P-LPC-G46"]
    assert answer["comparison"] is not None
    # les valeurs de chaque pays restent séparées : chaque fait de dose porte son pays
    for fact in answer["facts"]:
        if fact["field"] == "use.doseValue":
            assert fact["countryCode"] in ("FR", "CA") and f"({fact['countryCode']})" in fact["label"]


def test_missing_product_asks_for_clarification(no_ai):
    answer = ask("Dans quels pays est-il homologué ?")
    assert answer["answerStatus"] == "needs_clarification"
    assert "LALSTOP G46 WG" in answer["clarificationOptions"]
    assert not answer["facts"]


def test_ambiguous_product_name_asks_for_clarification(monkeypatch, no_ai):
    monkeypatch.setattr(services, "search_products", FakeServices().search_products)
    answer = ask("Dans quels pays SERENADE est-il homologué ?")
    assert answer["answerStatus"] == "needs_clarification"
    assert set(answer["clarificationOptions"]) == {"SERENADE ASO", "SERENADE MAX"}


def test_out_of_scope_question(no_ai):
    answer = ask("Quelle est la météo à Paris ?")
    assert answer["answerStatus"] == "out_of_scope" and answer["intent"] == "other"
    assert "Aucune recherche web" in answer["answer"]


@pytest.mark.parametrize("question,intent", [
    ("Quelles autorisations expirent dans les 12 prochains mois ?", "expiry_watch"),
    ("Quels champs sont manquants ou incertains pour LALSTOP G46 ?", "data_quality"),
    ("Donne la source officielle de chaque donnée de LALSTOP G46.", "source_lookup"),
])
def test_other_intents_return_sourced_facts(question, intent, no_ai, backend):
    answer = ask(question)
    assert answer["intent"] == intent
    assert answer["disclaimer"] == DISCLAIMER and answer["generator"]["mode"] == "keyword"
    if answer["facts"]:
        ids = {e["evidenceId"] for e in answer["evidence"]}
        assert all(i in ids for f in answer["facts"] for i in f["evidenceIds"])


def test_ingredient_search_by_species_and_crop(monkeypatch, no_ai):
    """« Quels produits contenant Gliocladium … sur la tomate » : substance + culture, produits avec leurs homologations."""
    reg = make_registration("FR-EPHY-2230771", "FR", "2230771")
    reg["uses"] = [make_use("U-FR-1", "FR-EPHY-2230771", "FR", 2.0)]
    product = {"productId": "P-LPC-G46", "commercialName": "LALSTOP G46 WG", "isSynthetic": False, "aliases": []}
    seen = {}

    def search(q, active_entity, crop, target, country, *rest):
        seen.update(active_entity=active_entity, crop=crop)
        return {"items": [product]}

    monkeypatch.setattr(services, "search_products", search)
    monkeypatch.setattr(services, "registrations_of_products", lambda *a, **k: ([reg], []))
    answer = ask("Quels produits contenant Gliocladium sont homologués sur la tomate ?")
    assert seen == {"active_entity": "Clonostachys rosea", "crop": "LYPES"}   # synonymes et code EPPO résolus par le code
    assert answer["intent"] == "ingredient_search" and answer["products"][0]["registrations"]
    assert "Clonostachys rosea" in answer["answer"] and "tomate" in answer["answer"]
    assert any(f["field"] == "use.doseValue" and f["countryCode"] == "FR" for f in answer["facts"])
    assert answer["parameters"]["crop"] == "LYPES"


def test_expiry_watch_for_one_product(monkeypatch, no_ai):
    monkeypatch.setattr(services, "product_registrations", FakeServices().product_registrations)
    monkeypatch.setattr(services, "get_product", FakeServices().get_product)
    answer = ask("Quelles autorisations de LALSTOP G46 expirent dans les 24 mois suivant le 2026-10-10 ?")
    assert answer["intent"] == "expiry_watch" and answer["parameters"]["referenceDate"] == date(2026, 10, 10)
    assert "2027-03-31" in answer["answer"]
    # seule l'homologation FR avec une date d'expiration renseignée est listée (l'autre n'a pas de date)
    assert [i["registrationId"] for i in answer["expirations"]] == ["FR-EPHY-2230771"]


# ---------------------------------------------------------------------------
# Garde-fous (étape f) avec un LLM simulé
# ---------------------------------------------------------------------------
def test_found_country_forgotten_by_the_llm_is_added_by_the_code(backend, fake_ai):
    """Le LLM ne parle que de la France : le Canada (trouvé via un produit sœur) est ajouté par le code, avec sa preuve."""
    def only_france(payload):
        fr_ids = [i for f in payload["faits"] for i in f["evidenceIds"] if "FR-EPHY" in i]
        return f"LALSTOP G46 WG est actif en France [{fr_ids[0]}]."
    fake_ai(only_france)
    answer = ask("Dans quels pays LALSTOP G46 est-il homologué ?")
    assert answer["generator"]["mode"] == "llm"
    assert {c["countryCode"] for c in answer["coverage"] if c["outcome"] == "found"} >= {"CA", "FR"}
    text = answer["answer"]
    assert "Également trouvé" in text and "CA :" in text
    assert "produit sœur ou même substance, à vérifier" in text          # le Canada n'est trouvé que par la substance active
    known = {e["evidenceId"] for e in answer["evidence"]}
    ca_ids = [i for i in agent.CITATION.findall(text.split("Également trouvé")[1]) if "CA" in i]
    assert ca_ids and all(set(x.split(", ")) <= known for x in ca_ids)    # preuve citée = preuve renvoyée
    assert answer["answerStatus"] in ("answered", "partial")
    assert len(agent.split_sentences(text)) <= 3                           # la phrase ajoutée respecte la limite de 3 phrases


def test_added_country_sentence_never_drops_the_not_covered_sentence(backend, fake_ai):
    def three_sentences(payload):
        fr_id = next(i for f in payload["faits"] for i in f["evidenceIds"] if "FR-EPHY" in i)
        return f"Actif en France [{fr_id}]. Statut extrait automatiquement [{fr_id}]. {payload['phraseSure']}"
    fake_ai(three_sentences)
    answer = ask("Dans quels pays LALSTOP G46 est-il homologué ?")
    assert "Également trouvé" in answer["answer"] and "marché non couvert" in answer["answer"]
    assert len(agent.split_sentences(answer["answer"])) <= 3


def test_no_sentence_added_when_the_llm_already_mentions_every_found_country(backend, fake_ai):
    def all_countries(payload):
        ids = {cc: next(i for f in payload["faits"] for i in f["evidenceIds"] if f"{cc}-" in i or f"-{cc}-" in i)
               for cc in ("FR", "CA")}
        return f"Actif en France [{ids['FR']}] et au Canada [{ids['CA']}]."
    fake_ai(all_countries)
    answer = ask("Dans quels pays LALSTOP G46 est-il homologué ?")
    assert "FR :" not in answer["answer"] and "CA :" not in answer["answer"]   # rien n'est répété pour FR et CA


def test_invented_number_in_llm_answer_is_blocked(backend, fake_ai):
    fake_ai(lambda p: f"LALSTOP G46 est autorisé à 777 kg/ha [{first_evidence_id(p)}].")
    answer = ask("Dans quels pays LALSTOP G46 est-il homologué ?")
    assert answer["answer"] == agent.BLOCKED_TEXT
    assert any("réponse non vérifiable bloquée" in w.lower() for w in answer["warnings"])
    assert answer["answerStatus"] == "partial" and answer["facts"]


def test_unknown_evidence_id_in_llm_answer_is_blocked(backend, fake_ai):
    fake_ai(lambda p: "LALSTOP G46 est homologué [registration:N-EXISTE-PAS].")
    answer = ask("Dans quels pays LALSTOP G46 est-il homologué ?")
    assert answer["answer"] == agent.BLOCKED_TEXT
    assert any("N-EXISTE-PAS" in w for w in answer["warnings"])


def test_llm_answer_without_citation_is_blocked(backend, fake_ai):
    fake_ai(lambda p: "LALSTOP G46 est homologué dans plusieurs pays.")
    assert ask("Dans quels pays LALSTOP G46 est-il homologué ?")["answer"] == agent.BLOCKED_TEXT


def test_llm_absence_claim_is_replaced_by_the_safe_phrase(backend, fake_ai):
    fake_ai(lambda p: f"LALSTOP G46 WG est homologué [{first_evidence_id(p)}]. Il n'est pas homologué aux États-Unis.")
    answer = ask("Dans quels pays LALSTOP G46 est-il homologué aux États-Unis, en France ?", countries=["US", "FR"])
    text = answer["answer"]
    assert NOT_COVERED_US in text
    assert "pas homologué" not in text.lower()
    assert answer["generator"]["mode"] == "llm"


def test_valid_llm_answer_is_kept(backend, fake_ai):
    fake_ai(lambda p: f"LALSTOP G46 WG est suivi dans les sources intégrées [{first_evidence_id(p)}].")
    answer = ask("Dans quels pays LALSTOP G46 est-il homologué ?")
    assert answer["answer"].startswith("LALSTOP G46 WG est suivi")
    assert answer["generator"]["mode"] == "llm"


def test_sister_answer_must_present_candidates(backend, fake_ai):
    fake_ai(lambda p: f"PRESTOP est un produit sœur de LALSTOP G46 [{first_evidence_id(p)}].")
    answer = ask("Quels produits pourraient être des produits sœurs de LALSTOP G46 ?")
    if answer["facts"]:   # (selon les données, aucun candidat n'a forcément de fiche officielle)
        assert answer["answer"] == agent.BLOCKED_TEXT


def test_llm_failure_falls_back_to_keyword_mode(backend, monkeypatch):
    monkeypatch.setattr(llm, "is_configured", lambda: True)
    monkeypatch.setattr(llm, "complete", lambda *a, **k: None)   # réseau coupé, quota dépassé…
    answer = ask("Dans quels pays LALSTOP G46 est-il homologué ?")
    assert answer["generator"]["mode"] == "keyword" and answer["facts"]
    assert any("IA indisponible" in w for w in answer["warnings"])


def test_llm_understanding_is_used_when_valid(monkeypatch):
    monkeypatch.setattr(services, "get_product", FakeServices().get_product)
    monkeypatch.setattr(services, "product_registrations", FakeServices().product_registrations)
    monkeypatch.setattr(llm, "is_configured", lambda: True)
    reply = {"intent": "registration_lookup", "productNames": ["LALSTOP G46 WG"], "countries": ["Canada"],
             "activeEntity": None, "crop": None, "target": None, "referenceDate": None}
    monkeypatch.setattr(llm, "complete", lambda s, u, json_mode=False: json.dumps(reply) if json_mode else None)
    answer = ask("Is it registered in Canada?")
    assert answer["parameters"]["countries"] == ["CA"] and answer["generator"]["mode"] == "llm"


def test_garbage_llm_understanding_falls_back_to_keywords(monkeypatch):
    monkeypatch.setattr(services, "product_registrations", FakeServices().product_registrations)
    monkeypatch.setattr(llm, "is_configured", lambda: True)
    monkeypatch.setattr(llm, "complete", lambda s, u, json_mode=False: "pas du json" if json_mode else None)
    answer = ask("Dans quels pays LALSTOP G46 est-il homologué ?")
    assert answer["intent"] == "registration_lookup" and answer["facts"]


# ---------------------------------------------------------------------------
# verify_text : fonctions pures (aucune donnée nécessaire)
# ---------------------------------------------------------------------------
FACTS = [{"factId": "f1", "label": "Dose (kg/ha) — Tomato (FR)", "value": 1.5, "evidenceIds": ["use:U1"]}]
COVERAGE = [{"countryCode": "FR", "outcome": "found"}, {"countryCode": "US", "outcome": "not_covered"},
            {"countryCode": "DE", "outcome": "not_found"}]


def verify(text, **kw):
    return agent.verify_text(text, FACTS, {"facts": FACTS, "question": ""}, COVERAGE, "registration_lookup", **kw)


def test_verify_accepts_numbers_found_in_facts():
    text, warnings, blocked = verify("Dose de 1,5 kg/ha en France [use:U1].", require_citation=True)
    assert not blocked and not warnings


@pytest.mark.parametrize("text", ["Dose de 2,5 kg/ha [use:U1].", "Dose [use:U1] de 15 kg/ha.", "Dose 1.5 [use:AUTRE]."])
def test_verify_blocks_invented_numbers_and_unknown_ids(text):
    answer, warnings, blocked = verify(text)
    assert blocked and answer == agent.BLOCKED_TEXT
    assert warnings and "bloquée" in warnings[0]


@pytest.mark.parametrize("claim", [
    "Le produit n'est pas homologué aux États-Unis.", "Aucune homologation en Allemagne.",
    "Not registered in the US.", "Produit non autorisé au US.", "Pas d'homologation pour DE.",
])
def test_verify_replaces_absence_claims_for_countries_without_result(claim):
    text, warnings, blocked = verify(claim)
    assert not blocked
    # DE = not_found -> « Aucun résultat… » ; US = not_covered -> « marché non couvert »
    assert text.startswith("Aucun résultat dans les sources intégrées pour ") or "marché non couvert par le prototype" in text
    assert "non homologué" not in text.lower()


def test_verify_leaves_statements_about_found_countries_alone():
    text, _, _ = verify("Le produit n'est plus autorisé en France [use:U1].")
    assert "France" in text and "Aucun résultat" not in text


# ---------------------------------------------------------------------------
# Compréhension par mots-clés, client IA, route HTTP
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("question,expected", [
    ("Dans quels pays LALSTOP G46 est-il homologué ?", {"intent": "registration_lookup", "productNames": ["LALSTOP G46 WG"]}),
    ("Compare LALGUARD M52 OD entre le Canada et la France.", {"intent": "use_comparison", "countries": ["CA", "FR"]}),
    ("Quels produits contenant Gliocladium sont homologués sur la tomate ?", {"intent": "ingredient_search", "activeEntity": "Clonostachys rosea"}),
    ("Quelles autorisations expirent bientôt ?", {"intent": "expiry_watch"}),
    ("Quels champs sont incertains pour CONTANS WG ?", {"intent": "data_quality", "productNames": ["CONTANS WG"]}),
    ("Produits sœurs de G46 ?", {"intent": "sister_product"}),
    ("Quelle est la capitale de la France ?", {"intent": "other"}),
])
def test_keyword_understanding(question, expected):
    result = agent.keyword_understanding(question)
    assert {k: result[k] for k in expected} == expected


def test_llm_client_never_raises(monkeypatch):
    for value in ("", "replace_me"):
        monkeypatch.setenv("AI_API_KEY", value)
        monkeypatch.setenv("AI_MODEL", "un-modele")
        assert not llm.is_configured() and llm.complete("s", "u") is None

    monkeypatch.setenv("AI_API_KEY", "cle-de-test")
    assert llm.is_configured()

    class Broken:
        class chat:   # noqa: N801
            class completions:   # noqa: N801
                @staticmethod
                def create(**kwargs):
                    raise TimeoutError("réseau coupé")
    monkeypatch.setattr(llm, "_client", lambda key, url: Broken)
    assert llm.complete("s", "u", json_mode=True) is None


def test_ask_falls_back_to_keyword_when_openai_module_is_missing(monkeypatch):
    """Clé IA configurée mais SDK openai absent (image Docker incomplète) : /ask répond 200 en mode keyword, jamais 500."""
    import sys

    from fastapi.testclient import TestClient

    from backend.app.main import app
    fake = FakeServices()
    for name in ("product_registrations", "get_product", "search_products"):
        monkeypatch.setattr(services, name, getattr(fake, name))
    monkeypatch.setenv("API_KEY", "")
    monkeypatch.setenv("AI_API_KEY", "cle-de-test")
    monkeypatch.setenv("AI_MODEL", "un-modele")
    monkeypatch.setenv("AI_FALLBACK_MODEL", "")
    monkeypatch.setitem(sys.modules, "openai", None)   # `from openai import OpenAI` lève alors ImportError
    llm._client.cache_clear()
    llm._cache.clear()
    assert llm.is_configured()
    response = TestClient(app).post("/api/ask", json={"question": "Dans quels pays LALSTOP G46 est-il homologué ?"})
    assert response.status_code == 200, response.text
    assert response.json()["generator"]["mode"] == "keyword"


def test_ask_route_matches_the_contract(monkeypatch, no_ai):
    from fastapi.testclient import TestClient

    from backend.app.main import app
    fake = FakeServices()
    for name in ("product_registrations", "get_product", "search_products"):
        monkeypatch.setattr(services, name, getattr(fake, name))
    monkeypatch.setenv("API_KEY", "")
    client = TestClient(app)
    for path in ("/ask", "/api/ask"):
        response = client.post(path, json={"question": "Dans quels pays LALSTOP G46 est-il homologué ?"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert m.Answer.model_validate(body)   # conforme au schéma Answer du contrat
        assert body["answer"] and body["facts"] and body["coverage"] and body["disclaimer"] == DISCLAIMER
        assert body["generator"]["mode"] == "keyword"
    assert client.post("/api/ask", json={"question": "a"}).status_code == 422


# ---------------------------------------------------------------------------
# Fiabilisation : retry / secours / cache, réponse courte, couverture, alignement
# ---------------------------------------------------------------------------
class RateLimited(Exception):
    status_code = 429


def reply(text):
    """Réponse factice au format du SDK OpenAI."""
    message = type("M", (), {"content": text})
    return type("R", (), {"choices": [type("C", (), {"message": message})]})


def fake_client(outcomes, calls):
    """Faux client OpenAI : chaque appel consomme une issue (exception à lever, ou texte à renvoyer)."""
    class Client:
        class chat:   # noqa: N801
            class completions:   # noqa: N801
                @staticmethod
                def create(**kwargs):
                    calls.append(kwargs["model"])
                    outcome = outcomes.pop(0)
                    if isinstance(outcome, Exception):
                        raise outcome
                    return reply(outcome)
    return Client


@pytest.fixture
def real_llm(monkeypatch):
    """Vrai llm.complete avec faux client, sans attente réelle ; renvoie la liste des attentes demandées."""
    waits = []
    monkeypatch.setenv("AI_API_KEY", "cle-de-test")
    monkeypatch.setenv("AI_MODEL", "principal")
    monkeypatch.setenv("AI_FALLBACK_MODEL", "secours")
    monkeypatch.setattr(llm.time, "sleep", waits.append)
    llm._cache.clear()
    llm.start_question()
    return waits


def test_llm_retries_after_rate_limit_then_succeeds(monkeypatch, real_llm):
    calls = []
    client = fake_client([RateLimited(), "bonjour"], calls)
    monkeypatch.setattr(llm, "_client", lambda key, url: client)
    assert llm.complete("s", "u") == "bonjour"
    assert calls == ["principal", "principal"] and real_llm == [2]   # 2 s d'attente par défaut
    assert llm.generator_info()["model"] == "principal"


def test_llm_uses_fallback_model_and_reports_it(monkeypatch, real_llm):
    calls = []
    client = fake_client([RateLimited()] * 3 + ["via secours"], calls)
    monkeypatch.setattr(llm, "_client", lambda key, url: client)
    assert llm.complete("s", "u") == "via secours"
    assert calls == ["principal"] * 3 + ["secours"] and real_llm == [2, 5]
    assert llm.generator_info()["model"] == "secours"


def test_llm_gives_up_when_retry_after_exceeds_the_budget(monkeypatch, real_llm):
    class Slow(RateLimited):
        response = type("Resp", (), {"headers": {"retry-after": "60"}})
    calls = []
    client = fake_client([Slow(), Slow()], calls)
    monkeypatch.setattr(llm, "_client", lambda key, url: client)
    assert llm.complete("s", "u") is None
    assert calls == ["principal", "secours"] and real_llm == []   # aucune attente de 60 s


def test_llm_answers_are_cached(monkeypatch, real_llm):
    calls = []
    client = fake_client(["une seule fois"], calls)
    monkeypatch.setattr(llm, "_client", lambda key, url: client)
    assert llm.complete("s", "Quelle  QUESTION ?") == "une seule fois"
    assert llm.complete("s", "quelle question ?") == "une seule fois"
    assert len(calls) == 1


def test_rate_limit_then_success_gives_llm_mode(backend, monkeypatch, real_llm):
    """De bout en bout : un 429 puis des succès -> generator.mode == llm."""
    state = {"n": 0}

    class Client:
        class chat:   # noqa: N801
            class completions:   # noqa: N801
                @staticmethod
                def create(**kwargs):
                    state["n"] += 1
                    if state["n"] == 1:
                        raise RateLimited()
                    content = kwargs["messages"][1]["content"]
                    if '"faits"' not in content:   # étape « comprendre » : JSON invalide -> mots-clés
                        return reply("{}")
                    return reply(f"LALSTOP G46 WG est suivi [{json.loads(content)['faits'][0]['evidenceIds'][0]}].")
    monkeypatch.setattr(llm, "_client", lambda key, url: Client)
    answer = ask("Dans quels pays LALSTOP G46 est-il homologué ?")
    assert answer["generator"]["mode"] == "llm" and state["n"] >= 2


def test_llm_answer_is_cut_to_three_sentences(backend, fake_ai):
    fake_ai(lambda p: " ".join(f"Phrase {i} [{first_evidence_id(p)}]." for i in range(1, 7)))
    answer = ask("Dans quels pays LALSTOP G46 est-il homologué ?")
    assert len(agent.split_sentences(answer["answer"])) <= 3


def test_llm_prompt_is_small(backend, fake_ai):
    seen = {}
    fake_ai(lambda p: seen.update(p) or f"LALSTOP G46 WG [{first_evidence_id(p)}].")
    ask("Quels champs sont manquants ou incertains pour LALSTOP G46 ?")
    assert len(seen["faits"]) <= agent.MAX_FACTS_IN_PROMPT
    assert all(len(f["evidenceIds"]) <= agent.MAX_IDS_PER_FACT for f in seen["faits"])


def test_coverage_sentences_differ_by_outcome_and_group_countries():
    cov = [{"countryCode": "FR", "outcome": "found"}, {"countryCode": "US", "outcome": "not_covered"},
           {"countryCode": "BR", "outcome": "not_covered"}, {"countryCode": "DE", "outcome": "not_found"},
           {"countryCode": "CA", "outcome": "source_unavailable"}]
    text = agent.coverage_sentence(cov)
    assert "Aucun résultat dans les sources intégrées pour DE — ce n'est pas une preuve d'absence d'homologation." in text
    assert "US, BR : marché non couvert par le prototype (aucune source officielle intégrée)." in text
    assert "CA : source officielle indisponible lors de la dernière collecte." in text


def test_row_key_aligns_by_normalized_name_when_a_country_has_no_eppo_code():
    fr = {"eppoCropCode": "LYPES", "cropNormalized": "Tomato", "cropOriginal": "tomate",
          "eppoTargetCode": None, "targetNormalized": "Botrytis", "targetOriginal": "botrytis"}
    ca = {"eppoCropCode": None, "cropNormalized": "tomato", "cropOriginal": "Tomatoes",
          "eppoTargetCode": None, "targetNormalized": "BOTRYTIS", "targetOriginal": "gray mould"}
    lookup = services.eppo_lookup([fr, ca])   # « tomato » -> LYPES grâce au pays qui a le code
    assert services.row_key(fr, lookup)[0] == services.row_key(ca, lookup)[0]
    # sans aucun code connu : alignement par nom normalisé, insensible à la casse
    other = {**ca, "cropNormalized": "TOMATO", "cropOriginal": "tomate"}
    (key_a, by_a), (key_b, by_b) = services.row_key(ca), services.row_key(other)
    assert key_a == key_b and by_a == by_b == "normalized_name"
    assert services.row_key({**ca, "cropNormalized": None, "targetNormalized": None})[1] == "original"


def test_use_comparison_switches_to_crop_level_when_uses_do_not_match(no_ai, monkeypatch):
    """Aucune ligne culture × cible commune FR/CA, mais une culture commune : bascule au niveau culture, et le dit."""
    fake = FakeServices()
    calls = []

    def compare(product_id, countries, crop, target, include_synthetic, limit, offset, granularity="use"):
        calls.append(granularity)
        data = fake.compare_uses(product_id, countries, crop, target, include_synthetic, limit, offset, granularity)
        if granularity == "use":   # une seule cellule présente par ligne : rien de comparable
            for cell in data["rows"][0]["cells"]:
                if cell["countryCode"] == "CA":
                    cell["state"], cell["uses"] = "absent_in_extracted_uses", []
        return data
    for name in ("get_product", "search_products", "product_registrations", "sister_candidates", "registrations_of_products"):
        monkeypatch.setattr(services, name, getattr(fake, name))
    monkeypatch.setattr(services, "compare_uses", compare)
    answer = ask("Compare LALSTOP G46 entre la France et le Canada", productId="P-LPC-G46", countries=["FR", "CA"])
    assert calls == ["use", "crop"]
    assert answer["answer"].startswith("Les données canadiennes ne précisent pas la cible : comparaison au niveau de la culture.")
