"""Routes réelles et rôle RLS réel ; Auth seul est remplacé, aucune écriture."""

import os
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from scripts.api import app, PredictionResponse
from scripts.database import connection
from scripts.shared_api import member
from scripts.schema import DATA


@unittest.skipUnless(os.getenv("BATIA_DB_TESTS") == "1", "BATIA_DB_TESTS=1 requis")
class LiveApiTests(unittest.TestCase):
    def setUp(self):
        with connection() as conn:
            profile = conn.execute(
                "select user_id,role,nom from public.membres where role='admin' limit 1"
            ).fetchone()
        if not profile:
            self.skipTest(
                "Créer le premier administrateur pour essayer les routes réelles."
            )
        app.dependency_overrides[member] = lambda: {
            "id": str(profile["user_id"]),
            "role": profile["role"],
            "name": profile["nom"],
            "email": "test-route",
        }
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_catalog_scores_all_horizons_and_history(self):
        for horizon in (90, 180, 365, 730):
            response = self.client.get(
                f"/api/workspace?horizon={horizon}&as_of_date=2026-01-01"
            )
            self.assertEqual(response.status_code, 200, response.text[:300])
            value = response.json()
            self.assertEqual(len(value["catalog"]["equipment"]), 4217)
            self.assertEqual(len(value["result"]["scores"]), 1285)
            self.assertEqual(
                value["result"]["metadata"]["label"], f"CatBoost · {horizon} jours"
            )
        self.assertEqual(
            self.client.get("/api/equipements/EQP-01533/historique").status_code, 200
        )

    def test_prediction_contract(self):
        response = self.client.post(
            "/api/predict",
            json={"equipment_id": "EQP-01533", "as_of_date": "2026-01-01"},
        )
        self.assertEqual(response.status_code, 200, response.text[:300])
        self.assertEqual(set(response.json()), set(PredictionResponse.model_fields))

    def test_economic_data_uses_shared_sources_and_published_model(self):
        response = self.client.get(
            "/api/economies?horizon=90&as_of_date=2026-01-01&year=2026"
        )
        self.assertEqual(response.status_code, 200, response.text[:300])
        data = response.json()
        self.assertEqual(len(data["equipment"]), 4217)
        self.assertEqual(len(data["operations"]), 29)
        self.assertEqual(len(data["groups"]), 9)
        self.assertEqual(data["plan"]["renovationBudget"], 1500000)
        detail = self.client.get(
            "/api/equipements/EQP-01533/economie?horizon=730&as_of_date=2026-01-01"
        )
        self.assertEqual(detail.status_code, 200, detail.text[:300])
        item = detail.json()["equipment"]
        self.assertEqual(item["equipmentId"], "EQP-01533")
        self.assertIsNotNone(item["firstFailureCost"])
        self.assertIsNotNone(item["replacementMin"])
        self.assertLessEqual(item["replacementMin"], item["replacementMax"])
        self.assertEqual(
            self.client.get("/api/equipements/ABSENT/economie").status_code, 404
        )

    def test_preview_of_original_csv_is_unchanged(self):
        with TemporaryDirectory() as folder, patch(
            "scripts.shared_api.ROOT", Path(folder)
        ):
            response = self.client.post(
                "/api/imports/preview",
                files={
                    "files": (
                        "prestataires.csv",
                        (DATA / "09_prestataires.csv").read_bytes(),
                        "text/csv",
                    )
                },
            )
            self.assertEqual(response.status_code, 200, response.text[:300])
            value = response.json()
            self.assertEqual(value["errors"], [])
            self.assertEqual(
                value["tables"]["prestataires"],
                {"added": 0, "updated": 0, "unchanged": 14},
            )
