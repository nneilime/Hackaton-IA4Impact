import unittest
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from scripts.api import app
from scripts.shared_api import member
import psycopg


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def identify(self, role="membre"):
        app.dependency_overrides[member] = lambda: {
            "id": "00000000-0000-0000-0000-000000000001",
            "role": role,
        }

    def test_auth_required(self):
        for path in (
            "/api/workspace",
            "/api/catalog",
            "/api/economies",
            "/api/equipements/EQP-00001/economie",
            "/api/calculs/00000000-0000-0000-0000-000000000001",
        ):
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(
            self.client.post(
                "/api/predict", json={"equipment_id": "EQP", "as_of_date": "2026-01-01"}
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.put(
                "/api/budgets/2026",
                json={
                    "version": 0,
                    "sourceRevision": 1,
                    "renovationBudget": 0,
                    "operationIds": [],
                },
            ).status_code,
            401,
        )

    def test_member_cannot_import(self):
        self.identify()
        self.assertEqual(
            self.client.post(
                "/api/imports/preview", files={"files": ("a.csv", b"x")}
            ).status_code,
            403,
        )

    def test_prediction_body_stays_strict(self):
        self.identify()
        for body in (
            {"equipment_id": "EQP", "as_of_date": "20260101"},
            {"equipment_id": "EQP", "as_of_date": "2026-01-01", "extra": 1},
        ):
            self.assertEqual(
                self.client.post("/api/predict", json=body).status_code, 422
            )

    def test_missing_models_and_invalid_horizon(self):
        self.identify()
        with patch("scripts.shared_api.schedule", side_effect=FileNotFoundError):
            self.assertEqual(self.client.post("/api/calculs").status_code, 503)
        self.assertEqual(self.client.get("/api/workspace?horizon=91").status_code, 422)

    def test_changed_import_schedules_but_reimport_does_not(self):
        self.identify("admin")
        token = "00000000-0000-0000-0000-000000000002"
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / ".cache" / "previews" / (token + ".json")
            path.parent.mkdir(parents=True)
            conn = MagicMock()
            db = MagicMock()
            db.return_value.__enter__.return_value = conn
            with patch("scripts.shared_api.ROOT", root), patch(
                "scripts.shared_api.connection", db
            ), patch(
                "scripts.shared_api.schedule", return_value=("run", True)
            ) as schedule, patch(
                "scripts.shared_api.run_job"
            ) as run:
                for changed in (False, True):
                    path.write_text(
                        json.dumps(
                            {
                                "user": "00000000-0000-0000-0000-000000000001",
                                "time": time.time(),
                                "revision": 2,
                                "errors": [],
                                "parsed": {"lot": {}, "files": []},
                            }
                        ),
                        encoding="utf-8",
                    )
                    conn.execute.return_value.fetchone.return_value = {
                        "result": {"modelChanged": changed, "revision": 2}
                    }
                    response = self.client.post("/api/imports/" + token + "/confirm")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(schedule.call_count, int(changed))
                    self.assertEqual(run.call_count, int(changed))

    def test_auth_rejects_invalid_token(self):
        response = MagicMock()
        response.status_code = 401
        with patch("scripts.shared_api.httpx.get", return_value=response):
            self.assertEqual(
                self.client.get(
                    "/api/workspace", headers={"Authorization": "Bearer invalid"}
                ).status_code,
                401,
            )

    def test_prediction_database_outage_returns_503(self):
        self.identify()
        with patch(
            "scripts.api.connection",
            side_effect=psycopg.OperationalError("Connexion interrompue"),
        ):
            response = self.client.post(
                "/api/predict", json={"equipment_id": "EQP", "as_of_date": "2026-01-01"}
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Connexion interrompue", response.text)

    def test_budget_types_and_economic_horizon_are_validated(self):
        self.identify()
        self.assertEqual(self.client.get("/api/economies?horizon=91").status_code, 422)
        base = {
            "version": 0,
            "sourceRevision": 1,
            "renovationBudget": 1000,
            "operationIds": [],
        }
        for changes in (
            {"renovationBudget": -1},
            {"renovationBudget": 10.001},
            {"maintenanceBudget": -1},
            {"version": -1},
            {"extra": 1},
        ):
            self.assertEqual(
                self.client.put(
                    "/api/budgets/2026", json={**base, **changes}
                ).status_code,
                422,
            )
