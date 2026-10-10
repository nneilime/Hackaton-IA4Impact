"""Predict 90-day, 180-day, 365-day and 730-day failure risks for one equipment item."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from catboost import CatBoostClassifier

from scripts.build_monthly_training_table import (
    DEFAULT_DATA_DIR,
    FAILURE_TYPES,
    age_days_as_of,
    count_events,
    count_matching,
    days_since,
    most_recent,
    parse_timestamp,
    read_csv,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRICE_CATALOG = (
    PROJECT_ROOT
    / "extra"
    / "11_equipements_interventions_pannes_possibles_avec_prix.csv"
)


def unavailable_failure_types():
    return {
        "status": "unavailable",
        "predictions": [],
        "other_conditional_probability": 0.0,
        "expected_price_if_failure": None,
        "expected_cost_within_horizon": None,
    }


def prediction_frame(model, features):
    frame = pd.DataFrame(features)[model.feature_names_]
    cats = [model.feature_names_[i] for i in model.get_cat_feature_indices()]
    frame[cats] = frame[cats].replace("", pd.NA).fillna("__MISSING__").astype(str)
    return frame


def summarize_failure_types(distribution, family, failure_probability, prices):
    """Même calcul des symptômes et coûts pour la CLI et l'inférence par lot."""
    candidates = []
    for (intervention, symptom), probability in distribution:
        candidates.append(
            {
                "type_intervention": intervention,
                "type_panne": symptom,
                "conditional_probability": round(probability, 6),
                "joint_probability": round(failure_probability * probability, 6),
                "prix": prices.get((family, intervention, symptom)),
            }
        )
    candidates.sort(key=lambda c: c["conditional_probability"], reverse=True)
    complete_prices = all(c["prix"] is not None for c in candidates)
    expected = (
        sum(p * prices[(family, t, s)] for (t, s), p in distribution)
        if complete_prices
        else None
    )
    return {
        "status": "available",
        "predictions": candidates[:3],
        "other_conditional_probability": round(
            sum(c["conditional_probability"] for c in candidates[3:]), 6
        ),
        "expected_price_if_failure": (
            round(expected, 2) if expected is not None else None
        ),
        "expected_cost_within_horizon": (
            round(expected * failure_probability, 2) if expected is not None else None
        ),
    }


def predict_failure_types(
    features, family, horizon, artifacts_dir, failure_probability, prices
):
    directory = artifacts_dir / f"{horizon}d" / "failure_types"
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return unavailable_failure_types()
    entry = manifest["families"].get(family)
    if not entry or entry["status"] != "trained":
        return unavailable_failure_types()
    if "constant_label" in entry:
        distribution = [(entry["constant_label"], 1.0)]
    else:
        model = CatBoostClassifier()
        model.load_model(directory / entry["model_file"])
        row = prediction_frame(model, [features])
        distribution = [
            (json.loads(label), float(p))
            for label, p in zip(model.classes_, model.predict_proba(row)[0])
        ]
    return summarize_failure_types(distribution, family, failure_probability, prices)


def load_history(
    data_dir: Path, equipment_id: str
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    equipment = {
        row["equipement_id"]: row for row in read_csv(data_dir / "04_equipements.csv")
    }
    item = equipment.get(equipment_id)
    if not item:
        raise ValueError(f"Unknown equipment_id: {equipment_id}.")
    if item["dans_perimetre_prediction"].strip().lower() != "oui":
        raise ValueError(
            f"{equipment_id} is excluded because dans_perimetre_prediction is not 'Oui'."
        )

    events = []
    request_ids = set()
    for intervention in read_csv(data_dir / "06_interventions.csv"):
        if intervention["equipement_id"] != equipment_id:
            continue
        intervention["_timestamp"] = parse_timestamp(intervention["date_intervention"])
        events.append(intervention)
        if intervention["demande_id_liee"]:
            request_ids.add(intervention["demande_id_liee"])
    events.sort(key=lambda event: event["_timestamp"])

    requests = []
    for request in read_csv(data_dir / "05_demandes_locataires.csv"):
        if request["demande_id"] in request_ids:
            request["_timestamp"] = parse_timestamp(request["date_creation"])
            requests.append(request)
    requests.sort(key=lambda request: request["_timestamp"])
    return item, events, requests


def build_feature_row(
    item: dict[str, str],
    events: list[dict[str, str]],
    requests: list[dict[str, str]],
    snapshot: datetime,
) -> dict[str, object]:
    """Rebuild the same input features as the monthly training table."""
    last_event = most_recent(events, snapshot)
    last_failure = most_recent(
        [event for event in events if event["type_intervention"] in FAILURE_TYPES],
        snapshot,
    )
    last_preventive = most_recent(
        [
            event
            for event in events
            if event["type_intervention"] == "Entretien préventif"
        ],
        snapshot,
    )
    age_days = age_days_as_of(item, events, snapshot)

    return {
        "famille": item["famille"],
        "libelle_famille": item["libelle_famille"],
        "niveau_rattachement": item["niveau_rattachement"],
        "duree_vie_reference_ans": int(item["duree_vie_reference_ans"]),
        "equipment_age_days": age_days,
        "equipment_age_ratio_reference": (
            round(age_days / (int(item["duree_vie_reference_ans"]) * 365.25), 4)
            if age_days is not None
            else None
        ),
        "interventions_30d": count_events(
            events, snapshot - timedelta(days=30), snapshot
        ),
        "interventions_90d": count_events(
            events, snapshot - timedelta(days=90), snapshot
        ),
        "interventions_180d": count_events(
            events, snapshot - timedelta(days=180), snapshot
        ),
        "interventions_365d": count_events(
            events, snapshot - timedelta(days=365), snapshot
        ),
        "depannages_30d": count_matching(
            events,
            snapshot - timedelta(days=30),
            snapshot,
            "type_intervention",
            {"Dépannage"},
        ),
        "depannages_90d": count_matching(
            events,
            snapshot - timedelta(days=90),
            snapshot,
            "type_intervention",
            {"Dépannage"},
        ),
        "depannages_365d": count_matching(
            events,
            snapshot - timedelta(days=365),
            snapshot,
            "type_intervention",
            {"Dépannage"},
        ),
        "preventive_maintenance_365d": count_matching(
            events,
            snapshot - timedelta(days=365),
            snapshot,
            "type_intervention",
            {"Entretien préventif"},
        ),
        "replacements_365d": count_matching(
            events,
            snapshot - timedelta(days=365),
            snapshot,
            "type_intervention",
            {"Remplacement"},
        ),
        "critical_interventions_365d": count_matching(
            events, snapshot - timedelta(days=365), snapshot, "gravite", {"Arrêt total"}
        ),
        "anomalies_365d": count_matching(
            events,
            snapshot - timedelta(days=365),
            snapshot,
            "resultat",
            {"Anomalie constatée"},
        ),
        "uncompleted_visits_365d": count_matching(
            events,
            snapshot - timedelta(days=365),
            snapshot,
            "resultat",
            {"Logement absent - visite non réalisée"},
        ),
        "days_since_last_intervention": days_since(last_event, snapshot),
        "days_since_last_failure": days_since(last_failure, snapshot),
        "days_since_last_preventive_maintenance": days_since(last_preventive, snapshot),
        "last_intervention_type": last_event["type_intervention"] if last_event else "",
        "last_intervention_result": last_event["resultat"] if last_event else "",
        "last_intervention_gravity": last_event["gravite"] if last_event else "",
        "last_symptome": last_event["symptome"] if last_event else "",
        "linked_tenant_requests_90d": count_events(
            requests, snapshot - timedelta(days=90), snapshot
        ),
        "reopened_tenant_requests_365d": count_matching(
            requests,
            snapshot - timedelta(days=365),
            snapshot,
            "demande_reouverte",
            {"Oui"},
        ),
    }


def load_prediction(
    model_path: Path, metrics_path: Path, features: dict[str, object]
) -> tuple[float, float]:
    model = CatBoostClassifier()
    model.load_model(model_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    feature_names = model.feature_names_
    row = pd.DataFrame([{name: features[name] for name in feature_names}])

    categorical_names = [
        feature_names[index] for index in model.get_cat_feature_indices()
    ]
    row[categorical_names] = (
        row[categorical_names].replace("", pd.NA).fillna("__MISSING__").astype(str)
    )
    probability = float(model.predict_proba(row)[:, 1][0])
    return probability, float(metrics["selected_alert_threshold"])


def risk_level(probability: float, threshold: float) -> str:
    if probability >= threshold:
        return "critique"
    if probability >= 0.50:
        return "eleve"
    if probability >= 0.20:
        return "modere"
    return "faible"


def recommended_action(
    alert_90d: bool,
    alert_180d: bool,
    alert_365d: bool = False,
    alert_730d: bool = False,
) -> str:
    if alert_90d:
        return (
            "Planifier une visite préventive prioritaire et mobiliser le prestataire."
        )
    if alert_180d:
        return "Inscrire une visite préventive au plan de maintenance des six prochains mois."
    if alert_365d:
        return "Planifier une visite préventive dans les douze prochains mois."
    if alert_730d:
        return (
            "Intégrer cet équipement au plan de maintenance des deux prochaines années."
        )
    return "Maintenir le cycle d'entretien préventif habituel."


def predict_equipment(
    equipment_id: str,
    snapshot: datetime,
    data_dir: Path = DEFAULT_DATA_DIR,
    artifacts_dir: Path = PROJECT_ROOT / "artifacts",
    price_catalog: Path = DEFAULT_PRICE_CATALOG,
) -> dict[str, object]:
    """Compute the shared prediction result for the CLI and HTTP API."""
    item, events, requests = load_history(data_dir.resolve(), equipment_id)
    features = build_feature_row(item, events, requests, snapshot)
    prices = {}
    for row in read_csv(price_catalog):
        key = (row["famille"], row["type_intervention"], row["type_panne"])
        price = float(row["prix"])
        if key in prices and prices[key] != price:
            raise ValueError(f"Inconsistent catalogue price: {key}")
        prices[key] = price
    result = {
        "equipment_id": equipment_id,
        "as_of_date": snapshot.date().isoformat(),
        "residence_id": item["residence_id"],
        "batiment_id": item["batiment_id"],
        "libelle_famille": item["libelle_famille"],
    }
    alerts = []
    for horizon in (90, 180, 365, 730):
        probability, threshold = load_prediction(
            artifacts_dir / f"{horizon}d" / f"catboost_failure_{horizon}d.cbm",
            artifacts_dir / f"{horizon}d" / "metrics.json",
            features,
        )
        alert = probability >= threshold
        alerts.append(alert)
        result.update(
            {
                f"failure_probability_{horizon}d": round(probability, 6),
                f"alert_threshold_{horizon}d": threshold,
                f"predicted_alert_{horizon}d": alert,
                f"risk_level_{horizon}d": risk_level(probability, threshold),
            }
        )
        result[f"failure_types_{horizon}d"] = predict_failure_types(
            features, item["famille"], horizon, artifacts_dir, probability, prices
        )
    result["recommended_action"] = recommended_action(*alerts)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Predict 90-day, 180-day, 365-day and 730-day failure risks for one equipment item."
    )
    parser.add_argument("--equipment-id", required=True, help="Equipment identifier.")
    parser.add_argument(
        "--as-of-date",
        required=True,
        help="Prediction date in ISO format: YYYY-MM-DD.",
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--artifacts-dir", type=Path, default=PROJECT_ROOT / "artifacts"
    )
    parser.add_argument(
        "--output", type=Path, help="Optional JSON file for the prediction result."
    )
    parser.add_argument("--price-catalog", type=Path, default=DEFAULT_PRICE_CATALOG)
    args = parser.parse_args()

    try:
        snapshot = datetime.fromisoformat(args.as_of_date)
    except ValueError as error:
        raise ValueError("--as-of-date must use the YYYY-MM-DD format.") from error

    result = predict_equipment(
        args.equipment_id,
        snapshot,
        args.data_dir,
        args.artifacts_dir,
        args.price_catalog,
    )
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
