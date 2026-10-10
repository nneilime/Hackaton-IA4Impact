import os
import unittest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from scripts.economics import (
    finance_by_location,
    operation_buildings,
    operation_families,
    overview,
    load_plan,
    save_plan,
)
from scripts.shared_api import BudgetPlan
from scripts.database import revision
from fastapi import HTTPException


class EconomicTests(unittest.TestCase):
    def order(self, **changes):
        return {
            "date_commande": date(2025, 1, 1),
            "date_facture": date(2025, 2, 1),
            "montant_ttc": Decimal("200"),
            "montant_facture_ttc": Decimal("100"),
            "residence_id": "RES-A",
            "logement_id": "LGT-A1",
            "statut": "Soldée",
            **changes,
        }

    def test_invoices_and_orders_are_not_double_counted_and_future_is_excluded(self):
        orders = [
            self.order(),
            self.order(date_commande=date(2026, 1, 1)),
            self.order(statut="Annulée"),
            self.order(date_facture=date(2026, 1, 2)),
        ]
        residences, housings = finance_by_location(orders, datetime(2026, 1, 1))
        self.assertEqual(residences["RES-A"]["billed12m"], 100)
        self.assertEqual(residences["RES-A"]["outstanding"], 300)
        self.assertEqual(residences["RES-A"]["invoiceCount12m"], 1)
        self.assertEqual(residences["RES-A"], housings["LGT-A1"])

    def test_operation_matching_keeps_collective_and_individual_distinct(self):
        self.assertEqual(
            operation_families("Remplacement chaufferie collective"),
            ["chaufferie_collective"],
        )
        self.assertEqual(
            operation_families("Remplacement chaudières individuelles"),
            ["chaudiere_gaz_individuelle"],
        )
        self.assertEqual(
            operation_families(
                "Remplacement ballons électriques par ballons thermodynamiques"
            ),
            ["ballon_ecs_electrique"],
        )
        ids = ["BAT-C1", "BAT-C2", "BAT-C3", "BAT-C4"]
        self.assertEqual(operation_buildings("Bâtiments C1-C3", ids), set(ids[:3]))
        self.assertEqual(operation_buildings("30 logements", ids), set())

    def test_repairs_use_current_cycle_and_missing_prices_remain_unknown(self):
        equipment = {
            "id": "EQP-1",
            "family": "chaudiere_gaz_individuelle",
            "label": "Chaudière",
            "residenceId": "RES-A",
            "housingId": "LGT-A1",
            "buildingId": "BAT-A1",
            "providerId": "PRE1",
            "collective": False,
            "buildingHousingCount": 10,
            "underContract": True,
            "cycleStartedAt": "2025-07-01T00:00:00",
        }
        rows = {
            "interventions": [
                {
                    "equipement_id": "EQP-1",
                    "date_intervention": datetime(2025, m, 2),
                    "type_intervention": "Dépannage",
                    "symptome": "Fuite",
                }
                for m in (5, 8)
            ],
            "familles": [
                {
                    "famille": equipment["family"],
                    "cout_remplacement_min_ttc": 1000,
                    "cout_remplacement_max_ttc": 2000,
                }
            ],
            "prix_interventions": [
                {
                    "famille": equipment["family"],
                    "type_intervention": "Dépannage",
                    "type_panne": "Fuite",
                    "prix": 200,
                }
            ],
            "commandes": [],
            "investissements": [],
            "batiments": [],
        }
        with patch(
            "scripts.economics.catalog", return_value={"equipment": [equipment]}
        ):
            result = overview(
                rows, datetime(2026, 1, 1), 1, {"scores": {"EQP-1": 0.9}}, []
            )
            item = result["equipment"][0]
            self.assertEqual(item["repairCount12m"], 1)
            self.assertEqual(item["simulatedRepairCost12m"], 200)
            self.assertEqual(item["repairReplacementRatioMin"], 0.1)
            self.assertEqual(item["repairReplacementRatioMax"], 0.2)
            self.assertIsNone(item["financeContext"])
            rows["prix_interventions"] = []
            self.assertIsNone(
                overview(rows, datetime(2026, 1, 1), 1, {"scores": {}}, [])[
                    "equipment"
                ][0]["simulatedRepairCost12m"]
            )
            equipment["cycleStartedAt"] = None
            self.assertIsNone(
                overview(rows, datetime(2026, 1, 1), 1, {"scores": {}}, [])[
                    "equipment"
                ][0]["repairCount12m"]
            )


@unittest.skipUnless(os.getenv("BATIA_DB_TESTS") == "1", "BATIA_DB_TESTS=1 requis")
class BudgetDatabaseTests(unittest.TestCase):
    def setUp(self):
        from psycopg import connect
        from psycopg.rows import dict_row

        self.conn = connect(
            os.environ["DATABASE_URL"], row_factory=dict_row, sslmode="require"
        )
        self.user = str(
            self.conn.execute(
                "select user_id from public.membres where role='admin' limit 1"
            ).fetchone()["user_id"]
        )
        self.conn.execute("set local role batia_api")
        self.conn.execute(
            "select set_config('request.jwt.claims',%s,true)",
            ['{"sub":"' + self.user + '","role":"authenticated"}'],
        )
        self.year = 2098
        self.conn.execute("delete from public.budgets where annee=%s", [self.year])
        self.operation = self.conn.execute(
            "select operation_id,cout_estime_ttc from public.investissements order by cout_estime_ttc limit 1"
        ).fetchone()

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def plan(self, **changes):
        return BudgetPlan(
            **{
                "version": 0,
                "sourceRevision": revision(self.conn),
                "renovationBudget": 1500000,
                "maintenanceBudget": None,
                "operationIds": [self.operation["operation_id"]],
                **changes,
            }
        )

    def test_plan_is_shared_and_stale_edits_are_rejected(self):
        self.assertEqual(load_plan(self.conn, self.year)["version"], 0)
        saved = save_plan(self.conn, self.year, self.plan(), self.user)
        self.assertEqual(saved["version"], 1)
        self.assertEqual(load_plan(self.conn, self.year), saved)
        with self.assertRaises(HTTPException) as caught:
            save_plan(self.conn, self.year, self.plan(), self.user)
        self.assertEqual(caught.exception.status_code, 409)
        newer = save_plan(
            self.conn,
            self.year,
            self.plan(version=1, maintenanceBudget=1000),
            self.user,
        )
        self.assertEqual(newer["version"], 2)
        self.assertEqual(newer["maintenanceBudget"], 1000)

    def test_over_budget_unknown_duplicate_and_stale_revision_do_not_write(self):
        for changes, status in [
            ({"renovationBudget": 0}, 422),
            ({"operationIds": ["ABSENT"]}, 422),
            ({"operationIds": [self.operation["operation_id"]] * 2}, 422),
            ({"sourceRevision": 0}, 409),
        ]:
            with self.assertRaises(HTTPException) as caught:
                save_plan(self.conn, self.year, self.plan(**changes), self.user)
            self.assertEqual(caught.exception.status_code, status)
            self.assertEqual(load_plan(self.conn, self.year)["version"], 0)

    def test_anonymous_cannot_read_and_authenticated_cannot_write_directly(self):
        from psycopg.errors import InsufficientPrivilege
        with self.conn.transaction():
            self.conn.execute("set local role anon")
            with self.assertRaises(InsufficientPrivilege):
                with self.conn.transaction():
                    self.conn.execute("select * from public.budgets")
        with self.conn.transaction():
            self.conn.execute("set local role authenticated")
            with self.assertRaises(InsufficientPrivilege):
                with self.conn.transaction():
                    self.conn.execute(
                        "insert into public.budgets(annee,renovation) values(2097,0)"
                    )
