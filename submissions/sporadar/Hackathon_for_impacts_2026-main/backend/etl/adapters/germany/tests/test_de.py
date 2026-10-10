"""Standard-library regression suite; no network or database required."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bvl import GermanyBVLAdapter
from bvl.base import COLUMNS
from bvl.de_bvl import IncompleteCollection, norm_status, norm_date, number
from bvl.export import validate, flat_loader, regulatory_loader

ROOT = Path(__file__).resolve().parents[1]


def replay(directory, tables, synthetic=False, url='https://psm-api.bvl.bund.de/ords/psm/api-v1/'):
    entries = []
    for name, items in tables.items():
        body = json.dumps(dict(items=items, hasMore=False), ensure_ascii=False).encode()
        (directory / f'{name}.json').write_bytes(body)
        entries.append(dict(collection=name, file=f'{name}.json', source_url=url + name + '/',
            collected_at='2026-10-01T10:00:00+00:00', sha256=hashlib.sha256(body).hexdigest()))
    (directory / 'manifest.json').write_text(json.dumps(dict(complete=True, is_synthetic=synthetic, responses=entries)))


def tables():
    return dict(
        mittel=[dict(kennr='034346-00', mittelname='PRESTOP', formulierung_art='WG', zul_erstmalig_am='2019-07-31T22:00:00Z', zul_ende='2033-07-30T22:00:00Z')],
        awg=[dict(awg_id='034346-00/01-001', kennr='034346-00', anwendungen_max_je_vegetation=2, anwendungstechnik='SXX', anwendungsbereich='FX')],
        wirkstoff=[dict(wirknr='123', wirkstoffname='Original active')],
        wirkstoff_gehalt=[dict(kennr='034346-00', wirknr='123', gehalt_rein=20)],
        awg_kultur=[dict(awg_id='034346-00/01-001', kultur='CROP', ausgenommen='N'), dict(awg_id='034346-00/01-001', kultur='EXCLUDED', ausgenommen='J')],
        awg_schadorg=[dict(awg_id='034346-00/01-001', schadorg='PEST', ausgenommen='N')],
        awg_aufwand=[dict(awg_id='034346-00/01-001', sortier_nr=1, m_aufwand='2,0', m_aufwand_einheit='KH', aufwandbedingung='ET10'), dict(awg_id='034346-00/01-001', sortier_nr=2, m_aufwand=4, m_aufwand_einheit='KH', aufwandbedingung='ET20')],
        awg_wartezeit=[dict(awg_id='034346-00/01-001', kultur='CROP', anwendungsbereich='FX', gesetzt_wartezeit=7)],
        awg_zeitpunkt=[], auflagen=[dict(ebene='034346-00', auflage='NOTICE')],
        kode=[dict(kodeliste=n, kode=k, sprache='DE', kodetext=v) for n,k,v in [(948,'CROP','Raps'),(947,'PEST','Sclerotinia'),(25,'KH','kg/ha'),(27,'SXX','Spritzen'),(28,'ET10','Condition one'),(28,'ET20','Condition two'),(74,'NOTICE','Original restriction')]])


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def convert(self, raw=None, **kwargs):
        replay(self.directory, raw if raw is not None else tables())
        adapter = GermanyBVLAdapter(offline_dir=self.directory, **kwargs)
        return adapter, adapter.run()

    def test_real_joins_and_condition_alternatives(self):
        _, b = self.convert()
        self.assertEqual(b.products[0]['active_entity_original'], 'Original active')
        self.assertEqual(b.products[0]['formulation_code'], 'WG')
        self.assertEqual(len(b.uses), 2)
        self.assertEqual({u['dose_value'] for u in b.uses}, {'2.0', '4'})
        for u in b.uses:
            self.assertEqual((u['crop_name_original'], u['target_name_original']), ('Raps','Sclerotinia'))
            self.assertEqual(u['dose_unit_original'], 'KH')
            self.assertEqual(u['dose_unit_normalized'], 'kg/ha')
            self.assertEqual(u['max_applications'], '2')
            self.assertEqual(u['phi_days'], '7')
            self.assertIn('EXCLUDED', u['restrictions_original'])
            self.assertIn('Original restriction', u['restrictions_original'])
        self.assertTrue(validate(b)['valid'])

    def test_unknown_status_is_not_inferred(self):
        _, b = self.convert()
        self.assertEqual(b.registrations[0]['status_normalized'], 'unknown')
        for s in ('nicht zugelassen', 'nicht mehr gültig', 'ruhend', 'abgelaufen aber früher zugelassen'):
            self.assertEqual(norm_status(s), 'unknown')
        self.assertEqual(norm_status('Zulassung beendet'), 'withdrawn')

    def test_dates_use_german_calendar_and_validate(self):
        _, b = self.convert()
        self.assertEqual(b.registrations[0]['approval_date'], '2019-08-01')
        self.assertEqual(b.registrations[0]['expiration_date'], '2033-07-31')
        self.assertEqual(norm_date('2024-12-30T23:00:00Z'), '2024-12-31')
        self.assertIsNone(norm_date('2024-02-31'))
        self.assertIsNone(norm_date('2024-01-01junk'))
        self.assertIsNone(norm_date('2024-01-01T10:00:00'))

    def test_candidate_identity_never_merges(self):
        _, b = self.convert(pilot_names={'PRESTOP':'P-LPC-G46'})
        self.assertEqual(b.products[0]['product_id'], 'P-DE-BVL-034346-00')
        self.assertTrue(any(w['level']=='candidate' for w in b.warnings))

    def test_explicit_synthetic_flag_and_original_timestamp(self):
        _, b = self.convert()
        self.assertEqual(b.products[0]['is_synthetic'], 'false')
        self.assertEqual(b.registrations[0]['collected_at'], '2026-10-01T10:00:00+00:00')
        self.assertEqual({e['collected_at'] for e in b.field_evidence}, {'2026-10-01T10:00:00+00:00'})
        renamed = self.directory / 'fixtures_real'
        renamed.mkdir()
        replay(renamed, tables(), False)
        self.assertEqual(GermanyBVLAdapter(offline_dir=renamed).run().products[0]['is_synthetic'], 'false')

    def test_fixture_is_synthetic_after_directory_move(self):
        moved = self.directory / 'demo'
        shutil.copytree(ROOT/'fixtures/de', moved)
        b = GermanyBVLAdapter(offline_dir=moved).run()
        self.assertEqual({p['is_synthetic'] for p in b.products}, {'true'})
        self.assertEqual(len(b.uses), 2)

    def test_no_timestamp_or_synthetic_guessing(self):
        replay(self.directory, tables())
        path = self.directory / 'manifest.json'
        m = json.loads(path.read_text())
        del m['is_synthetic']
        path.write_text(json.dumps(m))
        with self.assertRaises(ValueError):
            GermanyBVLAdapter(offline_dir=self.directory).fetch()

    def test_hash_mismatch_rejected(self):
        replay(self.directory, tables())
        (self.directory/'mittel.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            GermanyBVLAdapter(offline_dir=self.directory).fetch()

    def test_original_source_values_in_evidence(self):
        _, b = self.convert()
        self.assertTrue(any(e['field_name']=='source.awg_aufwand.m_aufwand' and e['value_original']=='2,0' for e in b.field_evidence))
        self.assertTrue(any(e['field_name']=='snapshot_sha256' for e in b.field_evidence))
        self.assertTrue(any(e['field_name']=='source_locator' for e in b.field_evidence))

    def test_stable_ids_when_responses_reordered(self):
        raw = tables()
        _, first = self.convert(raw)
        for rows in raw.values():
            rows.reverse()
        _, second = self.convert(raw)
        self.assertEqual({u['use_id']:u['dose_value'] for u in first.uses}, {u['use_id']:u['dose_value'] for u in second.uses})

    def test_numeric_invalid_and_missing_unit(self):
        for value in ('NaN','Infinity','-1','1-2','F'):
            self.assertIsNone(number(value))
        self.assertIsNone(number('1.5', True))
        raw=tables()
        raw['awg_aufwand'][0]['m_aufwand_einheit']='UNMAPPED'
        _, b=self.convert(raw)
        row=next(u for u in b.uses if u['dose_unit_original']=='UNMAPPED')
        self.assertIsNone(row['dose_value'])
        self.assertIn('2,0', row['restrictions_original'])

    def test_conditional_waiting_period_not_flattened(self):
        raw=tables()
        raw['awg_wartezeit'].append(dict(awg_id='034346-00/01-001', kultur='CROP', anwendungsbereich='FX', gesetzt_wartezeit=14))
        _,b=self.convert(raw)
        self.assertTrue(all(u['phi_days'] is None for u in b.uses))
        self.assertTrue(all('14' in u['restrictions_original'] for u in b.uses))

    def test_duplicate_registration_rejected(self):
        raw=tables()
        raw['mittel']*=2
        with self.assertRaisesRegex(ValueError,'Duplicate registration'):
            self.convert(raw)

    def test_no_lossy_merge(self):
        _, b=self.convert()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            b.merge(b)

    def test_missing_collections_are_visible(self):
        _,b=self.convert({'mittel':tables()['mittel'], 'awg':tables()['awg']})
        self.assertTrue(any(w['level']=='incomplete' for w in b.warnings))
        self.assertEqual(b.collection_runs[0]['status'],'failed')

    def test_snapshots_round_trip_without_timestamp_or_bytes_change(self):
        a,b=self.convert()
        output=self.directory/'out'
        output.mkdir()
        a.write_snapshots(output)
        replayed=GermanyBVLAdapter(offline_dir=output)
        b2=replayed.run()
        self.assertEqual(b.registrations,b2.registrations)
        self.assertEqual(b.uses,b2.uses)
        self.assertEqual([p['body'] for p in a.pages],[p['body'] for p in replayed.pages])

    def test_oracle_row_locator_does_not_change_identity(self):
        raw=tables()
        _, first=self.convert(raw)
        for rows in raw.values():
            for row in rows:
                row['m_row$$']='different-physical-location'
        _,second=self.convert(raw)
        self.assertEqual({u['use_id'] for u in first.uses},{u['use_id'] for u in second.uses})

    def test_offline_missing_next_page_is_rejected(self):
        replay(self.directory,tables())
        path=self.directory/'awg.json'
        data=json.loads(path.read_text())
        data.update(hasMore=True,links=[dict(rel='next',href='?offset=500')])
        body=json.dumps(data).encode()
        path.write_bytes(body)
        manifest_path=self.directory/'manifest.json'
        m=json.loads(manifest_path.read_text())
        for entry in m['responses']:
            if entry['collection']=='awg': entry['sha256']=hashlib.sha256(body).hexdigest()
        manifest_path.write_text(json.dumps(m))
        with self.assertRaises(IncompleteCollection): GermanyBVLAdapter(offline_dir=self.directory).fetch()

    def test_requested_registration_absent_from_replay_fails(self):
        with self.assertRaisesRegex(ValueError,'Requested registrations absent'):
            self.convert(registrations=['999999-00'])

    def test_compact_evidence_keeps_original_records_and_citations(self):
        replay(self.directory,tables())
        detailed=GermanyBVLAdapter(offline_dir=self.directory).run()
        compact=GermanyBVLAdapter(offline_dir=self.directory,compact_evidence=True).run()
        self.assertEqual(detailed.uses,compact.uses)
        self.assertLess(len(compact.field_evidence),len(detailed.field_evidence))
        for row in compact.field_evidence:
            self.assertIsInstance(json.loads(row['value_original']),dict)
            locator=json.loads(row['excerpt'])
            self.assertIn('#/items/',locator['locator'])
            self.assertEqual(len(locator['sha256']),64)
        reg_rows=[json.loads(e['value_original']) for e in compact.field_evidence if e['entity_type']=='registration']
        self.assertTrue(any(r.get('kodetext')=='Original restriction' for r in reg_rows))
        self.assertTrue(validate(compact)['valid'])

    def test_both_export_contracts(self):
        a,b=self.convert()
        b.write_csv(self.directory,'de_')
        flat_loader(self.directory)
        regulatory_loader(self.directory,b,a)
        for table,columns in COLUMNS.items():
            with (self.directory/f'de_{table}.csv').open() as f:
                self.assertEqual(next(csv.reader(f)),columns)
        sql=(self.directory/'load-regulatory.sql').read_text()
        self.assertIn('INSERT INTO registration_version',sql)
        self.assertIn('INSERT INTO source_snapshot',sql)
        self.assertIn('INSERT INTO use_evidence',sql)
        self.assertIn("'to_verify'",sql)
        self.assertNotIn('published_at',sql)
        self.assertNotIn("'automatically_extracted'",sql.split('INSERT INTO registration_version')[1].split(';')[0])


class PaginationTests(unittest.TestCase):
    def adapter(self,pages,max_pages=3):
        a=GermanyBVLAdapter(pause=0,max_pages=max_pages)
        queue=iter(pages)
        a._get=lambda url:json.dumps(next(queue)).encode()
        return a
    def test_multiple_pages(self):
        a=self.adapter([dict(items=[{'id':1}],hasMore=True,links=[dict(rel='next',href='?offset=1')]),dict(items=[{'id':2}],hasMore=False)])
        self.assertEqual(a.fetch_collection('awg'),[{'id':1},{'id':2}])
        self.assertEqual(len(a.pages),2)
    def test_limit_does_not_silently_truncate(self):
        a=self.adapter([dict(items=[{'id':1}],hasMore=True,links=[dict(rel='next',href='?offset=1')])],1)
        with self.assertRaises(IncompleteCollection): a.fetch_collection('awg')
    def test_missing_next_link_rejected(self):
        a=self.adapter([dict(items=[],hasMore=True)])
        with self.assertRaises(IncompleteCollection): a.fetch_collection('awg')
    def test_missing_has_more_rejected(self):
        a=self.adapter([dict(items=[])])
        with self.assertRaises(IncompleteCollection): a.fetch_collection('awg')
    def test_external_next_link_rejected(self):
        a=self.adapter([dict(items=[],hasMore=True,links=[dict(rel='next',href='https://example.org/')])])
        with self.assertRaises(ValueError): a.fetch_collection('awg')


if __name__=='__main__':
    unittest.main()
