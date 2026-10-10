"""Pose les 5 questions de evaluation/gold_questions.csv à POST /ask, écrit evaluation/our_submission.json
(format de evaluation/expected_output_template.json) puis lance scripts/evaluate_submission.py dessus.

Usage (depuis la racine du dépôt, venv activé, DATABASE_URL dans .env) :
    python scripts/run_gold.py                                  # l'API tourne en mémoire : aucun serveur à lancer
    python scripts/run_gold.py --url http://localhost:3000/api/ask   # ou contre un serveur déjà démarré

Contexte envoyé avec les questions (champs prévus par le contrat AskRequest) :
    productId = P-LPC-G46 (LALSTOP G46 WG, le produit pilote des questions « le produit pilote »)
    T02 « Comparer les usages entre deux pays » ne nomme aucun pays : on passe countries = FR, CA.
Le score automatique ne note que la forme (traçabilité, disclaimer, warnings, M365) : 70 sur 70.
La qualité des réponses se juge à la main avec evaluation/evaluation_rubric.csv.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")   # Windows : évite le plantage sur les espaces insécables
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOLD_FILE = ROOT / "evaluation" / "gold_questions.csv"
OUTPUT_FILE = ROOT / "evaluation" / "our_submission.json"
PILOT_PRODUCT_ID = "P-LPC-G46"
CONTEXT = {"T02": {"countries": ["FR", "CA"]}}   # contexte propre à une question

KNOWN_LIMITATIONS = [
    "Couverture limitée aux sources intégrées (FR-EPHY, CA-PPID, DE-BVL) : les autres pays sont renvoyés comme not_covered, "
    "ce qui n'est pas une preuve d'absence d'homologation.",
    "Données issues d'extraits figés (fichiers ou API interrogés à une date donnée) : pas de mise à jour en continu.",
    "Un même produit est retrouvé par nom, alias et substance active : les rapprochements « to_verify » sont signalés "
    "mais restent à valider par Regulatory Affairs.",
    "Produits sœurs = hypothèses (to_verify) ; seuls les candidats avec une fiche officielle rattachée portent une preuve.",
    "Aucune conversion d'unités de dose : deux unités différentes sont signalées comme une différence, pas comparées.",
    "Mode sans clé IA : compréhension par mots-clés (noms de produits connus, quelques synonymes, français) et phrases par "
    "gabarit ; réponses en français uniquement. Le mode avec IA n'a pas été testé avec un vrai fournisseur (pas de clé).",
    "Pas de validation humaine intégrée (route /reviews non implémentée). Prototype, pas une source réglementaire officielle.",
]


def make_caller(url):
    """Renvoie une fonction ask(body) -> (code HTTP, JSON) : en mémoire (TestClient) ou via HTTP."""
    key = os.environ.get("API_KEY", "").strip()
    headers = {"X-API-Key": key} if key else {}
    if url:
        import requests

        def call(body):
            response = requests.post(url, json=body, headers=headers, timeout=120)
            return response.status_code, response.json()
        return call

    from fastapi.testclient import TestClient

    from backend.app.main import app
    client = TestClient(app)

    def call(body):
        response = client.post("/api/ask", json=body, headers=headers)
        return response.status_code, response.json()
    return call


def to_submission_evidence(ev):
    return {"source_id": ev.get("sourceId"), "source_url": ev.get("sourceUrl"), "collected_at": ev.get("collectedAt"),
            "validation_status": ev.get("validationStatus"), "evidence_id": ev.get("evidenceId"),
            "source_record_url": ev.get("sourceRecordUrl"), "is_synthetic": ev.get("isSynthetic", False)}


def to_submission_fact(fact):
    return {"fact_id": fact["factId"], "label": fact["label"], "field": fact.get("field"), "value": fact.get("value"),
            "value_original": fact.get("valueOriginal"), "country_code": fact.get("countryCode"),
            "validation_status": fact.get("validationStatus"), "confidence": fact.get("confidence"),
            "evidence_ids": fact["evidenceIds"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", help="URL complète de POST /ask d'un serveur déjà lancé (sinon : API en mémoire)")
    args = parser.parse_args()

    with open(GOLD_FILE, newline="", encoding="utf-8-sig") as f:
        gold = list(csv.DictReader(f))
    ask = make_caller(args.url)

    answers = []
    for row in gold:
        body = {"question": row["question_fr"], "language": "fr", "productId": PILOT_PRODUCT_ID, **CONTEXT.get(row["test_id"], {})}
        code, data = ask(body)
        if code != 200:
            sys.exit(f"{row['test_id']} : /ask a répondu {code} : {data}")
        evidence = [to_submission_evidence(e) for e in data.get("evidence", [])]
        answers.append({"test_id": row["test_id"], "answer": data["answer"],
                        "facts": [to_submission_fact(f) for f in data.get("facts") or []],
                        "evidence": evidence, "warnings": data.get("warnings", []), "disclaimer": data["disclaimer"]})
        print(f"{row['test_id']} [{data.get('intent')}, {data.get('answerStatus')}, "
              f"{(data.get('generator') or {}).get('mode')}] {len(data.get('facts') or [])} faits, {len(evidence)} preuves")
        print(f"      {data['answer']}")
        if not evidence:
            print(f"      ATTENTION : {row['test_id']} n'a aucune preuve (base vide ou produit introuvable ?)")

    submission = {
        "submission_id": "lpc-regulatory-agent",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "answers": answers,
        "m365_integration": {"mechanism": "api", "documentation_url": "connector/power-platform.swagger.yaml"},
        "known_limitations": KNOWN_LIMITATIONS,
    }
    OUTPUT_FILE.write_text(json.dumps(submission, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nÉcrit : {OUTPUT_FILE.relative_to(ROOT)}\n")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "evaluate_submission.py"), str(OUTPUT_FILE)], check=True)


if __name__ == "__main__":
    main()
