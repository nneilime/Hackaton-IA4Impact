import os
import unittest
from contextlib import nullcontext
from datetime import date
from uuid import uuid4
from unittest.mock import patch

from psycopg import connect
from psycopg.rows import dict_row
from scripts.database import revision
from scripts.scoring import run_job
from scripts.api import interrupted_calculations


@unittest.skipUnless(os.getenv("BATIA_DB_TESTS") == "1", "BATIA_DB_TESTS=1 requis")
class JobTests(unittest.TestCase):
    def setUp(self):
        self.conn = connect(
            os.environ["DATABASE_URL"], row_factory=dict_row, sslmode="require"
        )
        self.run_id = str(uuid4())
        self.conn.execute(
            "insert into public.calculs(id,date_reference,revision,version_modele,statut) values(%s,%s,%s,'test-jobs','en_attente')",
            [self.run_id, date(1900, 1, 1), revision(self.conn)],
        )

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def status(self):
        return self.conn.execute(
            "select statut from public.calculs where id=%s", [self.run_id]
        ).fetchone()["statut"]

    def connection(self, *args, **kwargs):
        return nullcontext(self.conn)

    def test_failure_has_no_partial_scores_and_can_be_relaunched(self):
        with patch("scripts.scoring.connection", self.connection), patch(
            "scripts.scoring.predict_rows", side_effect=RuntimeError("Arrêt simulé")
        ):
            run_job(self.run_id, None)
        self.assertEqual(self.status(), "echec")
        self.assertEqual(
            self.conn.execute(
                "select count(*) n from public.predictions where calcul_id=%s",
                [self.run_id],
            ).fetchone()["n"],
            0,
        )
        self.conn.execute(
            "update public.calculs set statut='en_attente' where id=%s", [self.run_id]
        )
        self.assertEqual(self.status(), "en_attente")

    def test_new_revision_marks_job_stale_and_requests_recalculation(self):
        current = revision(self.conn)
        with patch("scripts.scoring.connection", self.connection), patch(
            "scripts.scoring.revision", return_value=current + 1
        ), patch("scripts.scoring.schedule", return_value=("next", False)) as schedule:
            run_job(self.run_id, None)
        self.assertEqual(self.status(), "depasse")
        schedule.assert_called_once_with(None, date(1900, 1, 1))

    def test_import_during_scoring_is_detected_before_publication(self):
        current = revision(self.conn)
        with patch("scripts.scoring.connection", self.connection), patch(
            "scripts.scoring.revision", side_effect=[current, current + 1]
        ), patch("scripts.scoring.predict_rows", return_value=[]), patch(
            "scripts.scoring.schedule", return_value=("next", False)
        ) as schedule:
            run_job(self.run_id, None)
        self.assertEqual(self.status(), "depasse")
        self.assertEqual(schedule.call_count, 1)

    def test_restart_marks_interrupted_job_as_failed(self):
        with patch("scripts.api.connection", self.connection):
            interrupted_calculations()
        self.assertEqual(self.status(), "echec")
