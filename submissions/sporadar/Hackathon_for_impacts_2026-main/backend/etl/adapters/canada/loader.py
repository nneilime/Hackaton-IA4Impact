"""Loads any CanonicalBundle into PostgreSQL (shared by all sources)."""
import os, re
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from ..base import COLUMNS, PRIMARY_KEYS, CanonicalBundle, ReferenceData, _csv_value, project_root, utcnow

ROOT = project_root()
EXPORT_TABLES = ['source_registry', 'products', 'product_aliases', 'registrations', 'uses']


def database_url() -> str:
    """DATABASE_URL from the environment or .env; accepts the SQLAlchemy form (postgresql+psycopg://)."""
    url = os.getenv('DATABASE_URL', '')
    env = ROOT / '.env'
    if not url and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith('DATABASE_URL='):
                url = line.split('=', 1)[1].strip().strip('"').strip("'")
    if not url:
        raise SystemExit('DATABASE_URL is not set (export it or put it in .env)')
    return re.sub(r'^postgres(ql)?\+\w+://', 'postgresql://', url)


def connect():
    return psycopg.connect(database_url(), row_factory=dict_row)


def load_references(conn=None) -> ReferenceData:
    """Mappings from the DB when connected, otherwise from data/*.csv."""
    if conn is None:
        return ReferenceData.from_csv(ROOT / 'data')
    q = lambda sql: conn.execute(sql).fetchall()
    return ReferenceData(q('SELECT * FROM active_entity_mapping'), q('SELECT * FROM product_name_mapping'),
                         q('SELECT * FROM eppo_crop_mapping'), q('SELECT * FROM eppo_pest_mapping'))


def _db_value(v):
    return None if v is None or v == '' else v


def _upsert(conn, table, rows, update=True):
    if not rows:
        return
    pk, cols = PRIMARY_KEYS[table], COLUMNS[table]
    action = ('DO UPDATE SET ' + ', '.join(f'{c} = EXCLUDED.{c}' for c in cols if c != pk)) if update else 'DO NOTHING'
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
           f"ON CONFLICT ({pk}) {action}")
    with conn.cursor() as cur:
        cur.executemany(sql, [tuple(_db_value(r.get(c)) for c in cols) for r in rows])


def _insert(conn, table, rows):
    if not rows:
        return
    cols = COLUMNS[table]
    with conn.cursor() as cur:
        cur.executemany(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                        [tuple(_db_value(r.get(c)) for c in cols) for r in rows])


def _detect_changes(conn, source_id, regs):
    """Compare the new registrations of one source with what is already in the DB (bonus: change detection)."""
    old = {r['registration_id']: r for r in conn.execute(
        'SELECT registration_id, status_normalized, expiration_date::text AS exp '
        'FROM registrations WHERE source_id = %s', (source_id,)).fetchall()}
    changes = []
    for r in regs:
        prev = old.pop(r['registration_id'], None)
        new_exp = _csv_value(r.get('expiration_date')) or None
        if prev is None:
            changes.append(f"NEW {r['registration_id']}")
        elif prev['status_normalized'] != r['status_normalized'] or (prev['exp'] or None) != new_exp:
            changes.append(f"CHANGED {r['registration_id']}: {prev['status_normalized']}/{prev['exp']} "
                           f"-> {r['status_normalized']}/{new_exp}")
    gone = list(old)
    changes += [f'NO LONGER IN SOURCE {rid} (marked obsolete, not deleted)' for rid in gone]
    return changes, gone


def load_bundle(bundle: CanonicalBundle) -> list:
    """Validate, then write the bundle in one transaction. Returns the list of detected changes."""
    errors = bundle.validate()
    if errors:
        raise ValueError('Bundle is invalid, nothing loaded:\n- ' + '\n- '.join(errors[:30]))
    all_changes = []
    with connect() as conn, conn.transaction():
        by_source = {}
        for r in bundle.registrations:
            by_source.setdefault(r['source_id'], []).append(r)
        gone_all = []
        for source_id, regs in by_source.items():
            changes, gone = _detect_changes(conn, source_id, regs)
            all_changes += changes
            gone_all += gone

        _upsert(conn, 'source_registry', bundle.source_registry, update=False)   # never overwrite reference rows
        _upsert(conn, 'products', bundle.products)
        _upsert(conn, 'registrations', bundle.registrations)
        _upsert(conn, 'product_aliases', bundle.product_aliases)
        reg_ids = [r['registration_id'] for r in bundle.registrations]
        conn.execute('DELETE FROM uses WHERE registration_id = ANY(%s)', (reg_ids,))
        _upsert(conn, 'uses', bundle.uses)
        _insert(conn, 'field_evidence', bundle.field_evidence)
        if gone_all:
            conn.execute("UPDATE registrations SET validation_status = 'obsolete' WHERE registration_id = ANY(%s)",
                         (gone_all,))
        notes = '\n'.join(all_changes + bundle.warnings) or None
        runs = bundle.collection_runs or [{'source_id': s, 'status': 'success', 'rows_written': len(r)}
                                          for s, r in by_source.items()]
        _insert(conn, 'collection_runs', [{**run, 'started_at': run.get('started_at') or utcnow(),
                                           'status': run.get('status') or 'success',
                                           'notes': '\n'.join(filter(None, [run.get('notes'), notes])) or None}
                                          for run in runs])
    return all_changes


def export_csv():
    """Write the DB back to data/*.csv so scripts/validate_data.py and the CSV export stay in sync."""
    import csv
    with connect() as conn:
        for table in EXPORT_TABLES:
            with conn.cursor() as cur:
                cur.execute(f'SELECT * FROM {table} ORDER BY 1')
                cols = [d.name for d in cur.description]
                rows = cur.fetchall()
            with (ROOT / 'data' / f'{table}.csv').open('w', encoding='utf-8', newline='') as f:
                w = csv.writer(f)
                w.writerow(cols)
                w.writerows([_csv_value(r[c]) for c in cols] for r in rows)
