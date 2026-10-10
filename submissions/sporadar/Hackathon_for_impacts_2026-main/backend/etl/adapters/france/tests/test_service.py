import copy
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as service
import exporter

URL = os.environ.get('TEST_DATABASE_URL')


def fixture():
    product = {'numero AMM': '00123', 'nom produit': 'TEST', 'type produit': 'PPP',
               'Etat d’autorisation': 'AUTORISE', 'Substances actives': 'Organisme souche A 10 UFC/g',
               'Date de première autorisation': '01/02/2020', 'Date de retrait du produit': '',
               'seconds noms commerciaux': 'Alias', 'restrictions usage libelle': 'Restriction produit'}
    use = {'numero AMM': '00123', 'identifiant usage': 'Traitements généraux*Trt Sol*Champignons',
           'etat usage': 'Autorisé', 'dose retenue': '4.0', 'dose retenue unite': 'kg/ha',
           "nombre max d'application": '1', 'condition emploi': 'Fractionnement possible.',
           'delai avant recolte jour': '', 'intervalle minimum entre applications (jour)': ''}
    return {'produits_utf8.csv': [product], 'produits_usages_utf8.csv': [use],
            'produits_condition_emploi_utf8.csv': []}


class ScheduleTests(unittest.TestCase):
    def test_due_time_survives_restart(self):
        t = datetime(2026, 10, 10, tzinfo=timezone.utc)
        self.assertEqual(service.seconds_until_due(None, 604800, t), 0)
        self.assertEqual(service.seconds_until_due(t, 604800, t + timedelta(days=1)), 518400)
        self.assertEqual(service.seconds_until_due(t, 604800, t + timedelta(days=8)), 0)


@unittest.skipUnless(URL, 'Set TEST_DATABASE_URL to an isolated test database')
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = service.connect(URL)
        database = self.conn.execute('SELECT current_database()').fetchone()[0]
        if database != 'france_test':
            raise RuntimeError('Tests may only use the isolated france_test database')
        self.conn.execute('TRUNCATE source_registry, products, registrations, uses, product_aliases, field_evidence, collection_runs RESTART IDENTITY CASCADE')
        self.conn.execute("INSERT INTO source_registry(source_id,official_name,country_or_region,access_method,manual_validation_required) VALUES ('FR-EPHY','ANSES','FR','download',false)")
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def export(self, tables=None):
        return exporter.convert(tables or fixture(), self.path, 'https://example.org/source.zip',
                                '2026-10-10T00:00:00+00:00', '2026-10-10T00:00:00+00:00')['counts']

    def test_repeat_import_is_idempotent_and_preserves_other_products(self):
        self.conn.execute("INSERT INTO products(product_id,commercial_name,is_synthetic,validation_status) VALUES ('OTHER','Other country',false,'validated')")
        counts = self.export()
        with self.conn.transaction():
            service.merge(self.conn, self.path, counts)
        before = self.conn.execute('SELECT count(*) FROM field_evidence').fetchone()[0]
        with self.conn.transaction():
            service.merge(self.conn, self.path, counts)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM products').fetchone()[0], 2)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM uses').fetchone()[0], 1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM field_evidence').fetchone()[0], before)

    def test_stale_use_replaced(self):
        counts = self.export()
        with self.conn.transaction(): service.merge(self.conn, self.path, counts)
        old = self.conn.execute('SELECT use_id FROM uses').fetchone()[0]
        tables = fixture()
        tables['produits_usages_utf8.csv'][0]['dose retenue'] = '2.0'
        counts = self.export(tables)
        with self.conn.transaction(): service.merge(self.conn, self.path, counts)
        self.assertNotEqual(self.conn.execute('SELECT use_id FROM uses').fetchone()[0], old)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM field_evidence WHERE entity_id=%s', (old,)).fetchone()[0], 0)

    def test_failed_transaction_preserves_previous_snapshot(self):
        counts = self.export()
        with self.conn.transaction(): service.merge(self.conn, self.path, counts)
        with self.assertRaises(RuntimeError):
            with self.conn.transaction():
                service.merge(self.conn, self.path, counts)
                raise RuntimeError('Simulated failure before commit')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM uses').fetchone()[0], 1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM field_evidence').fetchone()[0], counts['field_evidence'])

    def test_reviewed_data_blocks_automatic_overwrite(self):
        counts = self.export()
        with self.conn.transaction(): service.merge(self.conn, self.path, counts)
        self.conn.execute("UPDATE products SET validation_status='validated'")
        with self.assertRaises(ValueError):
            with self.conn.transaction(): service.merge(self.conn, self.path, counts)
        self.assertEqual(self.conn.execute('SELECT validation_status FROM products').fetchone()[0], 'validated')

    def test_cycle_records_success_then_skips_until_due_and_unchanged(self):
        metadata = json.dumps({'resources': [{'url': 'https://example.org/export-utf8.zip'}]}).encode()
        def fetch(url): return metadata if url == exporter.CATALOGUE else b'snapshot-one'
        with patch.object(exporter, 'fetch', side_effect=fetch), patch.object(exporter, 'read_tables', return_value=fixture()):
            result = service.cycle(URL, self.path, 604800)
            self.assertEqual(result['status'], 'success')
            self.assertEqual(service.cycle(URL, self.path, 604800)['status'], 'scheduled')
            self.conn.execute("UPDATE collection_runs SET finished_at=now()-interval '8 days'")
            self.assertEqual(service.cycle(URL, self.path, 604800)['status'], 'unchanged')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM uses').fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM collection_runs WHERE status='success'").fetchone()[0], 2)

    def test_overlap_is_skipped(self):
        self.conn.execute('SELECT pg_advisory_lock(%s)', (service.LOCK,))
        self.assertEqual(service.cycle(URL, self.path, 604800)['status'], 'another_instance_running')
        self.conn.execute('SELECT pg_advisory_unlock(%s)', (service.LOCK,))

    def test_failed_download_is_audited(self):
        with patch.object(exporter, 'fetch', side_effect=OSError('network unavailable')):
            with self.assertRaises(RuntimeError): service.cycle(URL, self.path, 604800)
        self.assertEqual(self.conn.execute('SELECT status FROM collection_runs').fetchone()[0], 'failed')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM products').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
