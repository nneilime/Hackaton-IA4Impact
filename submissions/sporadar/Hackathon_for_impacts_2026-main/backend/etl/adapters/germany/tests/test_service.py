"""Schedule and refresh tests. Database tests require a disposable germany_test DB."""
import copy
import csv
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import main as service
from bvl import GermanyBVLAdapter
from bvl.base import COLUMNS
from test_de import tables, replay

URL=os.environ.get('TEST_DATABASE_URL')


class ScheduleTests(unittest.TestCase):
    def test_due_time_survives_restart(self):
        t=datetime(2026,10,10,tzinfo=timezone.utc)
        self.assertEqual(service.seconds_until_due(None,604800,t),0)
        self.assertEqual(service.seconds_until_due(t,604800,t+timedelta(days=1)),518400)
        self.assertEqual(service.seconds_until_due(t,604800,t+timedelta(days=8)),0)
    def test_content_hash_ignores_paging_order_and_physical_locator(self):
        raw=tables()
        other=copy.deepcopy(raw)
        for rows in other.values():
            rows.reverse()
            for row in rows:row['m_row$$']='different-locator'
        self.assertEqual(service.snapshot_digest(raw),service.snapshot_digest(other))
        other['awg_aufwand'][0]['m_aufwand']=999
        self.assertNotEqual(service.snapshot_digest(raw),service.snapshot_digest(other))
    def test_scope_and_connector_version_affect_schedule(self):
        self.assertEqual(service.scope_config(['b','a']),service.scope_config(['a','b']))
        self.assertNotEqual(service.scope_config(),service.scope_config(['034346-00']))
        self.assertNotEqual(service.LOCK,59391008740913)


@unittest.skipUnless(URL,'Set TEST_DATABASE_URL to an isolated germany_test database')
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn=service.connect(URL)
        self.addCleanup(self.conn.close)
        if self.conn.execute('SELECT current_database()').fetchone()[0]!='germany_test':
            raise RuntimeError('Tests may only use an isolated germany_test database')
        self.conn.execute('TRUNCATE source_registry,products,registrations,uses,product_aliases,field_evidence,collection_runs RESTART IDENTITY CASCADE')
        self.conn.execute("INSERT INTO source_registry(source_id,official_name,country_or_region,access_method,manual_validation_required) VALUES ('DE-BVL','BVL','DE','api',true)")
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        self.input=self.path/'input'
        self.input.mkdir()
        self.output=self.path/'export'
        self.output.mkdir()

    def export(self,raw=None):
        replay(self.input,raw if raw is not None else tables())
        adapter=GermanyBVLAdapter(offline_dir=self.input)
        bundle=adapter.run()
        bundle.write_csv(self.output,'de_')
        return {t:len(getattr(bundle,t)) for t in service.TABLES}

    def apply(self,counts,scope=None):
        with self.conn.transaction():service.merge(self.conn,self.output,counts,scope)

    def test_repeat_import_preserves_other_products_and_counts(self):
        self.conn.execute("INSERT INTO products(product_id,commercial_name,is_synthetic,validation_status) VALUES('P-FR-EPHY-OTHER','France',false,'validated')")
        counts=self.export()
        self.apply(counts)
        before=self.conn.execute('SELECT count(*) FROM field_evidence').fetchone()[0]
        self.apply(counts)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM products').fetchone()[0],2)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM uses').fetchone()[0],2)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM field_evidence').fetchone()[0],before)

    def test_stale_use_replaced_and_previous_evidence_removed(self):
        counts=self.export();self.apply(counts)
        before={r[0] for r in self.conn.execute('SELECT use_id FROM uses')}
        raw=tables();raw['awg_aufwand'][0]['m_aufwand']='3.5'
        self.apply(self.export(raw))
        after={r[0] for r in self.conn.execute('SELECT use_id FROM uses')}
        removed=before-after
        self.assertEqual(len(removed),1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM field_evidence WHERE entity_id=ANY(%s)',(list(removed),)).fetchone()[0],0)

    def test_failed_transaction_rolls_back(self):
        counts=self.export();self.apply(counts)
        before=self.conn.execute('SELECT count(*) FROM field_evidence').fetchone()[0]
        with self.assertRaises(RuntimeError):
            with self.conn.transaction():
                service.merge(self.conn,self.output,counts)
                raise RuntimeError('failure before commit')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM field_evidence').fetchone()[0],before)

    def test_reviewed_product_blocks_refresh(self):
        counts=self.export();self.apply(counts)
        self.conn.execute("UPDATE products SET validation_status='validated'")
        with self.assertRaises(ValueError):self.apply(counts)
        self.assertEqual(self.conn.execute('SELECT validation_status FROM products').fetchone()[0],'validated')

    def test_reviewed_evidence_blocks_refresh(self):
        counts=self.export();self.apply(counts)
        self.conn.execute("UPDATE field_evidence SET validation_status='validated' WHERE evidence_id=(SELECT min(evidence_id) FROM field_evidence)")
        with self.assertRaises(ValueError):self.apply(counts)

    def test_scoped_refresh_preserves_other_german_registrations(self):
        raw=tables()
        other=copy.deepcopy(raw['mittel'][0]);other['kennr']='111111-00';other['mittelname']='Other German product'
        raw['mittel'].append(other)
        self.apply(self.export(raw))
        self.conn.execute("UPDATE products SET validation_status='validated' WHERE product_id='P-DE-BVL-111111-00'")
        self.apply(self.export(),['034346-00'])
        self.assertEqual(self.conn.execute("SELECT validation_status FROM products WHERE product_id='P-DE-BVL-111111-00'").fetchone()[0],'validated')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM registrations').fetchone()[0],2)

    def test_unexpected_drop_blocks_refresh(self):
        raw=tables()
        for index in range(4):
            row=copy.deepcopy(raw['mittel'][0]);row['kennr']=f'11111{index}-00';raw['mittel'].append(row)
        self.apply(self.export(raw))
        with self.assertRaises(ValueError):self.apply(self.export())
        self.assertEqual(self.conn.execute('SELECT count(*) FROM registrations').fetchone()[0],5)

    def test_disappeared_registration_is_unknown_and_keeps_evidence(self):
        raw=tables()
        for index in range(4):
            row=copy.deepcopy(raw['mittel'][0]);row['kennr']=f'11111{index}-00';row['status']='zugelassen';raw['mittel'].append(row)
        self.apply(self.export(raw))
        old_id='R-DE-BVL-111113-00'
        before=self.conn.execute('SELECT count(*) FROM field_evidence WHERE entity_id=%s',(old_id,)).fetchone()[0]
        raw['mittel'].pop()
        self.apply(self.export(raw))
        self.assertEqual(self.conn.execute('SELECT status_normalized FROM registrations WHERE registration_id=%s',(old_id,)).fetchone()[0],'unknown')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM field_evidence WHERE entity_id=%s',(old_id,)).fetchone()[0],before)

    def test_cycle_success_schedule_restart_and_unchanged(self):
        replay(self.input,tables())
        def adapter(**kwargs):return GermanyBVLAdapter(offline_dir=self.input,**kwargs)
        with patch.object(service,'GermanyBVLAdapter',side_effect=adapter):
            first=service.cycle(URL,self.path/'state',604800)
            self.assertEqual(first['status'],'success')
            self.assertEqual(service.cycle(URL,self.path/'state',604800)['status'],'scheduled')
            self.conn.execute("UPDATE collection_runs SET finished_at=now()-interval '8 days'")
            self.assertEqual(service.cycle(URL,self.path/'state',604800)['status'],'unchanged')
        self.assertEqual(self.conn.execute("SELECT count(*) FROM collection_runs WHERE status='success'").fetchone()[0],2)

    def test_recovery_replays_saved_snapshot_without_network(self):
        replay(self.input,tables())
        with patch.object(GermanyBVLAdapter,'_get',side_effect=AssertionError('Recovery must not download')):
            result=service.cycle(URL,self.path/'state',604800,force=True,replay_dir=self.input)
        self.assertEqual(result['status'],'success')
        collected=self.conn.execute('SELECT collected_at FROM registrations').fetchone()[0]
        self.assertEqual(collected.isoformat(),'2026-10-01T10:00:00+00:00')

    def test_lock_skips_overlapping_instance(self):
        self.conn.execute('SELECT pg_advisory_lock(%s)',(service.LOCK,))
        self.assertEqual(service.cycle(URL,self.path/'state',604800)['status'],'another_instance_running')
        self.conn.execute('SELECT pg_advisory_unlock(%s)',(service.LOCK,))

    def test_download_failure_is_audited_and_redacted(self):
        with patch.object(GermanyBVLAdapter,'fetch',side_effect=OSError('secret-connection-string')):
            with self.assertRaisesRegex(RuntimeError,'error=OSError') as error:
                service.cycle(URL,self.path/'state',604800)
        self.assertNotIn('secret',str(error.exception))
        self.assertEqual(self.conn.execute('SELECT status FROM collection_runs').fetchone()[0],'failed')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM products').fetchone()[0],0)

    def test_partial_snapshot_never_replaces_database(self):
        replay(self.input,{'mittel':tables()['mittel']})
        def adapter(**kwargs):return GermanyBVLAdapter(offline_dir=self.input,**kwargs)
        with patch.object(service,'GermanyBVLAdapter',side_effect=adapter):
            with self.assertRaises(RuntimeError):service.cycle(URL,self.path/'state',604800)
        self.assertEqual(self.conn.execute('SELECT status FROM collection_runs').fetchone()[0],'failed')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM products').fetchone()[0],0)

    def test_large_scope_uses_indexed_evidence_ownership_checks(self):
        counts=self.export()
        path=self.output/'de_uses.csv'
        with path.open(newline='') as f:
            seed=next(csv.DictReader(f))
        with path.open('a',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=COLUMNS['uses'])
            for i in range(20000):
                row=dict(seed,use_id=f'U-DE-BVL-extra-{i:08d}')
                writer.writerow(row)
        counts['uses']+=20000
        self.conn.execute("""INSERT INTO field_evidence(entity_type,entity_id,field_name,extraction_method,validation_status)
            SELECT 'use','U-FR-EPHY-unrelated-'||n,'source','open_data_csv','validated' FROM generate_series(1,20000) n""")
        self.conn.execute("SET work_mem='64kB'")
        self.conn.execute("SET statement_timeout='8s'")
        self.apply(counts)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM field_evidence WHERE entity_id LIKE 'U-FR-EPHY-%'").fetchone()[0],20000)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM uses').fetchone()[0],20002)

    def test_schema_check_is_read_only(self):
        report=service.check_database(URL)
        self.assertTrue(report['read_only'])
        self.assertTrue(report['compatible'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM collection_runs').fetchone()[0],0)

    def test_export_collection_run_matches_flat_constraints(self):
        self.export()
        with self.conn.transaction():
            service.copy_stage(self.conn,self.output,'collection_runs')
            fields=', '.join(COLUMNS['collection_runs'])
            self.conn.execute(f'INSERT INTO collection_runs ({fields}) SELECT {fields} FROM incoming_collection_runs')
        self.assertEqual(self.conn.execute('SELECT status FROM collection_runs').fetchone()[0],'success')


if __name__=='__main__':unittest.main()
