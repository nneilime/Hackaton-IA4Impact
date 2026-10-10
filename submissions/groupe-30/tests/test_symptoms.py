"""Contrat partagé et inférence des symptômes par famille, sans recharger par équipement."""

import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
from scripts import scoring
from scripts.import_csv import parse_files
from scripts.import_price_catalog import price_lot
from scripts.predict_equipment import predict_failure_types
from scripts.train_failure_types import main as train_types


class SymptomTests(unittest.TestCase):
    def test_trainer_accepts_snapshot_path_and_keeps_future_only_family_unavailable(
        self,
    ):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "snapshot.csv"
            output = root / "models"
            pd.DataFrame(
                [
                    {
                        "snapshot_date": day,
                        "famille": family,
                        "target_failure_within_horizon": 1,
                        "target_failure_symptom": "Fuite",
                        "target_failure_intervention": "Dépannage",
                    }
                    for day, family in [
                        ("2018-01-01", "known"),
                        ("2024-01-01", "known"),
                        ("2025-01-01", "known"),
                        ("2025-01-01", "future"),
                    ]
                ]
            ).to_csv(path, index=False)
            with patch(
                "sys.argv",
                [
                    "trainer",
                    "--horizon-days",
                    "90",
                    "--input",
                    str(path),
                    "--artifacts-dir",
                    str(output),
                ],
            ):
                train_types()
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["families"]["known"]["constant_label"], ["Dépannage", "Fuite"]
            )
            self.assertEqual(manifest["families"]["future"]["status"], "unavailable")
            self.assertNotIn("target_failure_symptom", manifest["features"])

    def test_batch_uses_raw_global_score_and_one_call_per_family_and_horizon(self):
        risk = MagicMock()
        symptom = MagicMock()
        for model in (risk, symptom):
            model.feature_names_ = ["famille"]
            model.get_cat_feature_indices.return_value = [0]
        risk.predict_proba.return_value = np.array([[0.6, 0.4], [0.3, 0.7]])
        symptom.classes_ = [
            json.dumps(["Dépannage", "Fuite"]),
            json.dumps(["Remplacement", "Non renseigné"]),
        ]
        symptom.predict_proba.return_value = np.array([[0.75, 0.25], [0.5, 0.5]])
        rows = {
            "equipements": [
                dict(
                    equipement_id=f"EQP-{i}",
                    famille="test",
                    libelle_famille="Test",
                    residence_id="RES",
                    batiment_id="BAT",
                    dans_perimetre_prediction=True,
                )
                for i in range(2)
            ],
            "interventions": [],
            "demandes": [],
            "prix_interventions": [
                dict(
                    famille="test",
                    type_intervention="Dépannage",
                    type_panne="Fuite",
                    prix=100,
                ),
                dict(
                    famille="test",
                    type_intervention="Remplacement",
                    type_panne="Non renseigné",
                    prix=500,
                ),
            ],
        }
        with patch.object(
            scoring, "models", return_value={h: (risk, 0.5) for h in scoring.HORIZONS}
        ), patch.object(
            scoring,
            "failure_models",
            return_value={
                h: {"test": ({"status": "trained"}, symptom)} for h in scoring.HORIZONS
            },
        ), patch.object(
            scoring, "build_feature_row", return_value={"famille": "test"}
        ):
            results = scoring.predict_rows(rows, datetime(2026, 1, 1), "test-version")
        self.assertEqual(symptom.predict_proba.call_count, 4)
        for h in scoring.HORIZONS:
            types = results[0][f"failure_types_{h}d"]
            self.assertEqual(types["predictions"][0]["joint_probability"], 0.3)
            self.assertEqual(types["expected_price_if_failure"], 200)
            self.assertEqual(types["expected_cost_within_horizon"], 80)

    def test_missing_symptom_manifest_keeps_risk_deployment_usable(self):
        with TemporaryDirectory() as folder:
            types = predict_failure_types({}, "test", 90, Path(folder), 0.4, {})
        self.assertEqual(types["status"], "unavailable")
        self.assertEqual(types["predictions"], [])
        self.assertIsNone(types["expected_cost_within_horizon"])

    def test_model_version_includes_symptom_weights(self):
        with TemporaryDirectory() as folder, patch.object(
            scoring, "artifacts_dir", return_value=Path(folder)
        ):
            root = Path(folder)
            for h in scoring.HORIZONS:
                directory = root / f"{h}d"
                directory.mkdir()
                (directory / f"catboost_failure_{h}d.cbm").write_bytes(b"risk")
                (directory / "metrics.json").write_text("{}", encoding="utf-8")
            before = scoring.model_version()
            directory = root / "90d" / "failure_types"
            directory.mkdir()
            (directory / "manifest.json").write_text(
                json.dumps(
                    {
                        "families": {
                            "test": {"status": "trained", "model_file": "test.cbm"}
                        }
                    }
                ),
                encoding="utf-8",
            )
            (directory / "test.cbm").write_bytes(b"first")
            first = scoring.model_version()
            (directory / "test.cbm").write_bytes(b"second")
            self.assertNotEqual(before, first)
            self.assertNotEqual(first, scoring.model_version())

    def test_catalog_has_unique_prices_and_import_rejects_negative_prices(self):
        rows = price_lot()["lot"]["prix_interventions"]
        self.assertEqual(len(rows), 87)
        invalid = parse_files(
            [
                (
                    "prix.csv",
                    b"famille,type_intervention,type_panne,prix\na,depannage,fuite,-1\n",
                )
            ]
        )
        self.assertTrue(invalid["errors"])

    def test_conflicting_catalog_prices_are_rejected(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "catalog.csv"
            path.write_text(
                "famille,type_intervention,type_panne,prix\na,depannage,fuite,10\na,depannage,fuite,20\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "contradictoires"):
                price_lot(path)
