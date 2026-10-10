"""Tests sur Supabase réel, dans une transaction entièrement annulée."""

import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from copy import deepcopy
from datetime import datetime
from uuid import uuid4

import psycopg
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from psycopg.rows import dict_row
from scripts.database import connection, model_history, revision, source_rows, safe
from scripts.import_csv import canonical, initial_lot
from scripts.predict_equipment import build_feature_row, load_history, predict_equipment
from scripts.schema import DATA, ROOT, TABLES
from scripts.scoring import predict_rows, latest_result
from scripts.catalog import history
from scripts.workspace import load_workspace, save_action


@unittest.skipUnless(os.getenv("BATIA_DB_TESTS") == "1", "BATIA_DB_TESTS=1 requis")
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(
            os.environ["DATABASE_URL"], row_factory=dict_row, sslmode="require"
        )
        self.admin, self.member = str(uuid4()), str(uuid4())
        for uid, role in ((self.admin, "admin"), (self.member, "membre")):
            self.conn.execute(
                "insert into auth.users(id,aud,role,email) values(%s,'authenticated','authenticated',%s)",
                [uid, uid + "@example.invalid"],
            )
            self.conn.execute(
                "insert into public.membres(user_id,role) values(%s,%s)", [uid, role]
            )
        self.identify(self.admin)

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def identify(self, uid, role="batia_api"):
        self.conn.execute("reset role")
        self.conn.execute("set local role " + role)
        self.conn.execute(
            "select set_config('request.jwt.claims',%s,true)",
            [json.dumps({"sub": uid, "role": "authenticated"})],
        )

    def import_lot(self, lot, rev=None):
        return self.conn.execute(
            "select public.importer_lot(%s,%s,%s) result",
            [Jsonb(safe(lot)), revision(self.conn) if rev is None else rev, Jsonb([])],
        ).fetchone()["result"]

    def test_all_columns_and_features_equal_csv(self):
        expected = initial_lot()["lot"]
        actual = source_rows(self.conn)
        csv_scores = {
            r["equipment_id"]: r for r in predict_rows(expected, datetime(2026, 1, 1))
        }
        database_scores = {
            r["equipment_id"]: r for r in predict_rows(actual, datetime(2026, 1, 1))
        }
        self.assertEqual(len(database_scores), 1285)
        self.assertEqual(csv_scores, database_scores)
        for table, (keys, _) in TABLES.items():
            norm = lambda rows: {tuple(r[k] for k in keys): canonical(r) for r in rows}
            self.assertEqual(norm(actual[table]), norm(expected[table]), table)
        for equipment_id in ("EQP-00001", "EQP-01533", "EQP-03865"):
            item = next(
                r for r in actual["equipements"] if r["equipement_id"] == equipment_id
            )
            if not item["dans_perimetre_prediction"]:
                continue
            csv_data, db_data = load_history(DATA, equipment_id), model_history(
                actual, equipment_id
            )
            for day in (datetime(2024, 1, 1), datetime(2026, 1, 1)):
                self.assertEqual(
                    build_feature_row(*csv_data, day), build_feature_row(*db_data, day)
                )
            subset = {**actual, "equipements": [item]}
            self.assertEqual(
                predict_equipment(
                    equipment_id, datetime(2026, 1, 1), DATA, ROOT / "artifacts"
                ),
                predict_rows(subset, datetime(2026, 1, 1))[0],
            )

    def test_reimport_has_no_data_revision_or_recalculation(self):
        old = revision(self.conn)
        result = self.import_lot(
            {"prestataires": source_rows(self.conn, ["prestataires"])["prestataires"]}
        )
        self.assertEqual(result["revision"], old)
        self.assertFalse(result["modelChanged"])
        self.assertEqual(result["tables"]["prestataires"], {"added": 0, "updated": 0})

    def test_price_correction_and_reimport(self):
        row = source_rows(self.conn, ["prix_interventions"])["prix_interventions"][0]
        unchanged = self.import_lot({"prix_interventions": [row]})
        self.assertFalse(unchanged["modelChanged"])
        updated = self.import_lot(
            {"prix_interventions": [{**row, "prix": row["prix"] + 1}]}
        )
        self.assertTrue(updated["modelChanged"])
        self.assertEqual(
            updated["tables"]["prix_interventions"], {"added": 0, "updated": 1}
        )

    def test_correction_new_identifier_and_stale_preview(self):
        old = revision(self.conn)
        item = deepcopy(source_rows(self.conn, ["equipements"])["equipements"][0])
        item["origine_date_pose"] = "Correction QA"
        result = self.import_lot({"equipements": [item]}, old)
        self.assertTrue(result["modelChanged"])
        self.assertEqual(result["tables"]["equipements"]["updated"], 1)
        provider = {
            "prestataire_id": "QA-" + str(uuid4()),
            "nom": "QA",
            "domaine": "Test",
            "type_contrat": "Test",
        }
        self.assertEqual(
            self.import_lot({"prestataires": [provider]})["tables"]["prestataires"][
                "added"
            ],
            1,
        )
        with self.conn.transaction():
            with self.assertRaises(psycopg.errors.SerializationFailure):
                with self.conn.transaction():
                    self.import_lot({"prestataires": [provider]}, old)

    def test_entire_lot_rolls_back(self):
        old = revision(self.conn)
        item = deepcopy(source_rows(self.conn, ["equipements"])["equipements"][0])
        item["origine_date_pose"] = "Ne doit pas persister"
        invalid = {
            "batiment_id": "QA-invalid",
            "residence_id": "ABSENT",
            "nb_niveaux": 1,
            "nb_logements": 1,
            "ascenseur": False,
        }
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.import_lot({"equipements": [item], "batiments": [invalid]})
        self.assertEqual(revision(self.conn), old)
        self.assertNotEqual(
            self.conn.execute(
                "select origine_date_pose from public.equipements where equipement_id=%s",
                [item["equipement_id"]],
            ).fetchone()["origine_date_pose"],
            item["origine_date_pose"],
        )

    def test_permissions(self):
        self.identify(self.member, "authenticated")
        self.assertEqual(
            self.conn.execute("select count(*) n from public.equipements").fetchone()[
                "n"
            ],
            4217,
        )
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.conn.transaction():
                self.import_lot({})
        self.conn.execute("reset role")
        self.conn.execute("set local role anon")
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.conn.transaction():
                self.conn.execute("select * from public.equipements")

    def test_two_users_and_optimistic_conflict(self):
        action = {
            "id": "qa-" + str(uuid4()),
            "equipmentId": "EQP-01533",
            "status": "preparing",
            "owner": "QA",
            "objective": "Contrôle",
        }
        save_action(self.conn, action, self.admin)
        self.identify(self.member)
        stored = next(
            a for a in load_workspace(self.conn)["actions"] if a["id"] == action["id"]
        )
        save_action(self.conn, {**stored, "owner": "Second membre"}, self.member)
        with self.assertRaises(HTTPException) as error:
            save_action(self.conn, stored, self.member)
        self.assertEqual(error.exception.status_code, 409)
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with self.conn.transaction():
                save_action(
                    self.conn, {**action, "id": "qa-" + str(uuid4())}, self.member
                )
        self.assertEqual(
            len(
                next(
                    a
                    for a in load_workspace(self.conn)["actions"]
                    if a["id"] == action["id"]
                )["history"]
            ),
            2,
        )

    def test_empty_results_are_unscored(self):
        result = latest_result(self.conn, 90, datetime(1900, 1, 1).date())
        self.assertEqual(result["scores"], {})

    def test_history_excludes_future_reports_and_events(self):
        result = history(self.conn, "EQP-01533", datetime(2024, 1, 1))
        self.assertEqual(result["reports"]["EQP-01533"], [])
        self.assertTrue(
            all(e["date"] < "2024-01-01" for e in result["events"]["EQP-01533"])
        )

    def test_import_transactions_serialize(self):
        self.import_lot({})  # Le verrou reste détenu jusqu'au rollback.
        started, finished = Event(), Event()

        def other_import():
            with psycopg.connect(
                os.environ["DATABASE_URL"], sslmode="require", row_factory=dict_row
            ) as conn:
                started.set()
                result = conn.execute(
                    "select public.importer_lot(%s,%s,%s) result",
                    [Jsonb({}), revision(conn), Jsonb([])],
                ).fetchone()["result"]
                finished.set()
                conn.rollback()
                return result

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(other_import)
            self.assertTrue(started.wait(15))
            self.assertFalse(finished.wait(0.2))
            self.conn.rollback()
            self.assertFalse(future.result(timeout=15)["modelChanged"])

    def test_recovery_preserves_dates_and_existing_records(self):
        action = {
            "id": "qa-" + str(uuid4()),
            "equipmentId": "EQP-01533",
            "status": "closed",
            "owner": "QA",
            "objective": "Contrôle",
            "visitedDate": "2025-12-01",
            "outcome": "RAS",
            "conclusion": "Terminé",
            "createdAt": "2025-12-01T09:00:00Z",
            "updatedAt": "2025-12-02T09:00:00Z",
            "version": 3,
            "history": [
                {
                    "date": "2025-12-01T10:00:00Z",
                    "label": "Ancienne décision",
                    "note": "RAS",
                    "status": "completed",
                }
            ],
        }
        save_action(self.conn, action, self.admin, recover=True)
        self.assertFalse(
            save_action(
                self.conn, {**action, "owner": "À ignorer"}, self.admin, recover=True
            )
        )
        restored = next(
            a for a in load_workspace(self.conn)["actions"] if a["id"] == action["id"]
        )
        self.assertEqual(restored["owner"], "QA")
        self.assertTrue(restored["createdAt"].startswith("2025-12-01"))
        self.assertEqual(restored["history"][0]["label"], "Ancienne décision")
