"""Train conditional next-failure classifiers, separately by equipment family."""

import argparse
import json
from datetime import timedelta
from pathlib import Path

import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import accuracy_score

from scripts.train_failure_model import NON_FEATURE_COLUMNS, PROJECT_ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--horizon-days", type=int, choices=(90, 180, 365, 730), required=True
    )
    parser.add_argument("--iterations", type=int, default=250)
    parser.add_argument(
        "--input", type=Path, help="Monthly table from CSV or a database snapshot."
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        help="Output directory for this horizon's symptom models.",
    )
    args = parser.parse_args()
    horizon = args.horizon_days
    name = (
        "table_apprentissage_mensuelle_90.csv"
        if horizon == 90
        else f"table_apprentissage_mensuelle_{horizon}j.csv"
    )
    data = pd.read_csv(args.input or PROJECT_ROOT / name, parse_dates=["snapshot_date"])
    required = {"target_failure_symptom", "target_failure_intervention"}
    if not required.issubset(data.columns):
        raise ValueError("Rebuild the monthly training table to add symptom targets.")
    features = [c for c in data.columns if c not in NON_FEATURE_COLUMNS]
    categorical = [c for c in features if data[c].dtype == "object"]
    data[categorical] = data[categorical].fillna("__MISSING__").astype(str)
    years = sorted(data.snapshot_date.dt.year.unique())
    if len(years) < 3:
        raise ValueError(
            "At least three snapshot years are required for chronological evaluation."
        )
    validation_start = pd.Timestamp(year=int(years[-2]), month=1, day=1)
    test_start = pd.Timestamp(year=int(years[-1]), month=1, day=1)
    gap = timedelta(days=horizon)
    positive = data[data.target_failure_within_horizon == 1].copy()
    positive["label"] = [
        json.dumps([t, s], ensure_ascii=False)
        for t, s in zip(
            positive.target_failure_intervention,
            positive.target_failure_symptom.fillna("Non renseigné"),
        )
    ]
    output = (
        args.artifacts_dir
        or PROJECT_ROOT / "artifacts" / f"{horizon}d" / "failure_types"
    )
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "horizon_days": horizon,
        "meaning": "First failure type conditional on a failure within the horizon",
        "features": features,
        "families": {},
        "split": "Chronological, horizon purged at both boundaries",
    }
    for family, frame in positive.groupby("famille"):
        train = frame[frame.snapshot_date + gap < validation_start]
        valid = frame[
            (frame.snapshot_date >= validation_start)
            & (frame.snapshot_date + gap < test_start)
        ]
        test = frame[frame.snapshot_date >= test_start]
        if train.empty:
            manifest["families"][family] = {
                "status": "unavailable",
                "reason": "No training failures",
            }
            continue
        labels = sorted(train.label.unique())
        entry = {
            "status": "trained",
            "training_rows": len(train),
            "classes": [json.loads(x) for x in labels],
        }
        if len(labels) == 1:
            entry["constant_label"] = json.loads(labels[0])
            predicted = [labels[0]] * len(test)
            top3 = [[label] for label in predicted]
        else:
            model = CatBoostClassifier(
                loss_function="MultiClass",
                iterations=args.iterations,
                depth=5,
                learning_rate=0.08,
                random_seed=42,
                thread_count=4,
                allow_writing_files=False,
                verbose=False,
            )
            known_valid = valid[valid.label.isin(labels)]
            options = (
                {
                    "eval_set": (known_valid[features], known_valid.label),
                    "early_stopping_rounds": 40,
                }
                if len(known_valid)
                else {}
            )
            model.fit(train[features], train.label, cat_features=categorical, **options)
            entry["model_file"] = f"{family}.cbm"
            model.save_model(output / entry["model_file"])
            predicted = (
                model.predict(test[features]).reshape(-1).tolist() if len(test) else []
            )
            probabilities = model.predict_proba(test[features]) if len(test) else []
            top3 = [list(model.classes_[p.argsort()[-3:]]) for p in probabilities]
        entry["test_rows"] = len(test)
        entry["unseen_test_labels"] = int((~test.label.isin(labels)).sum())
        if len(test):
            entry["accuracy"] = float(accuracy_score(test.label, predicted))
            entry["top3_accuracy"] = sum(
                y in candidates for y, candidates in zip(test.label, top3)
            ) / len(test)
            most_common = train.label.value_counts().index[0]
            entry["majority_baseline_accuracy"] = float(
                (test.label == most_common).mean()
            )
        manifest["families"][family] = entry
        print(f"{horizon}d {family}: {entry}", flush=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
