"""Train and retrospectively evaluate the CatBoost equipment-failure model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import (
    average_precision_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_COLUMN = "target_failure_within_horizon"
NON_FEATURE_COLUMNS = {
    "snapshot_date",
    "equipment_id",
    "residence_id",
    "batiment_id",
    "logement_id",
    "target_failure_within_horizon",
    "target_critical_failure_within_horizon",
    "days_to_next_failure",
    "target_failure_symptom",
    "target_failure_intervention",
}


def select_threshold(y_true: pd.Series, probabilities: pd.Series, minimum_precision: float) -> float:
    """Choose the lowest validation threshold meeting the alert precision objective."""
    precision, recall, thresholds = precision_recall_curve(y_true, probabilities)
    valid_thresholds = [
        (threshold, precision[index], recall[index])
        for index, threshold in enumerate(thresholds)
        if precision[index] >= minimum_precision
    ]
    if not valid_thresholds:
        return 0.5
    return max(valid_thresholds, key=lambda candidate: candidate[2])[0]


def evaluate(
    y_true: pd.Series, probabilities: pd.Series, threshold: float
) -> dict[str, float | int]:
    predictions = probabilities >= threshold
    return {
        "rows": int(len(y_true)),
        "positive_events": int(y_true.sum()),
        "alert_count": int(predictions.sum()),
        "alert_rate": round(float(predictions.mean()), 6),
        "roc_auc": round(float(roc_auc_score(y_true, probabilities)), 6),
        "average_precision": round(float(average_precision_score(y_true, probabilities)), 6),
        "precision": round(float(precision_score(y_true, predictions, zero_division=0)), 6),
        "recall": round(float(recall_score(y_true, predictions, zero_division=0)), 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and evaluate a leakage-safe CatBoost failure classifier."
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Monthly training table CSV. Defaults to the file for --horizon-days.",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        help="Directory where the model, metrics, and predictions are written.",
    )
    parser.add_argument(
        "--horizon-days",
        type=int,
        default=90,
        help="Prediction horizon represented by the training table (default: 90).",
    )
    parser.add_argument(
        "--minimum-precision",
        type=float,
        default=0.50,
        help="Minimum validation precision used to select the operational alert threshold.",
    )
    args = parser.parse_args()

    if not 0 < args.minimum_precision <= 1:
        raise ValueError("--minimum-precision must be in the interval (0, 1].")
    if args.horizon_days <= 0:
        raise ValueError("--horizon-days must be positive.")

    training_table = args.input or (
        PROJECT_ROOT / "table_apprentissage_mensuelle_90.csv"
        if args.horizon_days == 90
        else PROJECT_ROOT / f"table_apprentissage_mensuelle_{args.horizon_days}j.csv"
    )
    artifacts_dir = args.artifacts_dir or (
        PROJECT_ROOT / "artifacts" / f"{args.horizon_days}d"
    )
    data = pd.read_csv(training_table, parse_dates=["snapshot_date"])
    if TARGET_COLUMN not in data:
        raise ValueError(f"Missing target column: {TARGET_COLUMN}.")

    # Longer horizons need fully observed outcomes, so their last snapshot
    # year can precede 2025. Reserve the last two available years for evaluation.
    years = sorted(data["snapshot_date"].dt.year.unique())
    if len(years) < 3:
        raise ValueError("At least three snapshot years are required for chronological evaluation.")
    validation_year, test_year = int(years[-2]), int(years[-1])
    train = data[data["snapshot_date"].dt.year < validation_year].copy()
    validation = data[data["snapshot_date"].dt.year == validation_year].copy()
    test = data[data["snapshot_date"].dt.year == test_year].copy()
    if train.empty or validation.empty or test.empty:
        raise ValueError("Expected non-empty chronological train, validation, and test sets.")

    feature_columns = [column for column in data.columns if column not in NON_FEATURE_COLUMNS]
    categorical_features = [
        column
        for column in feature_columns
        if data[column].dtype == "object" or data[column].dtype.name == "string"
    ]
    for frame in (train, validation, test):
        frame[categorical_features] = frame[categorical_features].fillna("__MISSING__").astype(str)

    model = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="AUC",
        iterations=1_000,
        learning_rate=0.05,
        depth=6,
        l2_leaf_reg=5,
        auto_class_weights="Balanced",
        random_seed=42,
        verbose=100,
        allow_writing_files=False,
    )
    model.fit(
        train[feature_columns],
        train[TARGET_COLUMN],
        cat_features=categorical_features,
        eval_set=(validation[feature_columns], validation[TARGET_COLUMN]),
        early_stopping_rounds=100,
    )

    validation_probabilities = pd.Series(
        model.predict_proba(validation[feature_columns])[:, 1], index=validation.index
    )
    threshold = select_threshold(
        validation[TARGET_COLUMN], validation_probabilities, args.minimum_precision
    )
    test_probabilities = pd.Series(
        model.predict_proba(test[feature_columns])[:, 1], index=test.index
    )

    test_predictions = test[
        [
            "snapshot_date",
            "equipment_id",
            "residence_id",
            "batiment_id",
            "famille",
            "libelle_famille",
            TARGET_COLUMN,
        ]
    ].copy()
    probability_column = f"failure_probability_{args.horizon_days}d"
    test_predictions[probability_column] = test_probabilities
    test_predictions["alert_threshold"] = threshold
    test_predictions["predicted_alert"] = (
        test_predictions[probability_column] >= threshold
    ).astype(int)
    test_predictions["risk_level"] = test_predictions[
        probability_column
    ].map(
        lambda probability: (
            "critique"
            if probability >= threshold
            else "eleve"
            if probability >= 0.50
            else "modere"
            if probability >= 0.20
            else "faible"
        )
    )

    by_family = (
        test_predictions.groupby("libelle_famille", dropna=False)
        .agg(
            rows=(TARGET_COLUMN, "size"),
            actual_failures=(TARGET_COLUMN, "sum"),
            alerts=("predicted_alert", "sum"),
            mean_failure_probability=(probability_column, "mean"),
        )
        .reset_index()
        .sort_values("actual_failures", ascending=False)
    )
    importances = (
        pd.DataFrame(
            {
                "feature": feature_columns,
                "importance": model.get_feature_importance(),
            }
        )
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model.save_model(artifacts_dir / f"catboost_failure_{args.horizon_days}d.cbm")
    test_predictions.to_csv(
        artifacts_dir / f"test_predictions_{test_year}.csv", index=False, encoding="utf-8-sig"
    )
    by_family.to_csv(
        artifacts_dir / "test_metrics_by_family.csv", index=False, encoding="utf-8-sig"
    )
    importances.to_csv(
        artifacts_dir / "feature_importance.csv", index=False, encoding="utf-8-sig"
    )

    metrics = {
        "target": TARGET_COLUMN,
        "model": "CatBoostClassifier",
        "prediction_horizon_days": args.horizon_days,
        "train_period": f"{int(years[0])}-{validation_year - 1}",
        "validation_period": str(validation_year),
        "test_period": str(test_year),
        "feature_count": len(feature_columns),
        "categorical_feature_count": len(categorical_features),
        "minimum_validation_precision": args.minimum_precision,
        "selected_alert_threshold": round(float(threshold), 6),
        "validation": evaluate(
            validation[TARGET_COLUMN], validation_probabilities, threshold
        ),
        "test": evaluate(test[TARGET_COLUMN], test_probabilities, threshold),
    }
    (artifacts_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
