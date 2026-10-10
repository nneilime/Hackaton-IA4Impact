#!/usr/bin/env python3
"""Persistent, scheduled France E-Phy ingestion service."""
import argparse
import hashlib
import json
import logging
import os
import signal
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg import sql
import exporter
from validate import validate

LOG = logging.getLogger('france')
ADAPTER = 'france-service-v1'
MARKER = '%"adapter": "france-service-v1"%'
LOCK = 59391008740913
STOP = threading.Event()
TABLES = ('products', 'registrations', 'product_aliases', 'uses', 'field_evidence')
KEYS = {'products': 'product_id', 'registrations': 'registration_id',
        'product_aliases': 'alias_id', 'uses': 'use_id'}


def now():
    return datetime.now(timezone.utc)


def seconds_until_due(finished, interval, current=None):
    return max(0, interval - ((current or now()) - finished).total_seconds()) if finished else 0


def notes(**values):
    return json.dumps(dict(adapter=ADAPTER, **values), ensure_ascii=False)


def connect(url):
    return psycopg.connect(url.replace('postgresql+psycopg://', 'postgresql://', 1),
                           autocommit=True, connect_timeout=10,
                           options='-c search_path=public -c statement_timeout=300000 -c lock_timeout=15000',
                           application_name=ADAPTER)


def copy_stage(conn, directory, table):
    fields = sql.SQL(', ').join(map(sql.Identifier, exporter.HEADERS[table]))
    staging = sql.Identifier('incoming_' + table)
    conn.execute(sql.SQL('CREATE TEMP TABLE {} ON COMMIT DROP AS SELECT {} FROM {} WITH NO DATA').format(
        staging, fields, sql.Identifier(table)))
    statement = sql.SQL('COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, ENCODING \'UTF8\')').format(staging, fields)
    with (directory / ('fr_' + table + '.csv')).open('rb') as source:
        with conn.cursor().copy(statement) as copy:
            while chunk := source.read(1024 * 1024):
                copy.write(chunk)
    if table in KEYS:
        conn.execute(sql.SQL('CREATE UNIQUE INDEX ON {} ({})').format(staging, sql.Identifier(KEYS[table])))


def merge(conn, directory, counts):
    """Caller supplies a transaction. Only this adapter's source-scoped IDs change."""
    for table in TABLES:
        copy_stage(conn, directory, table)
    for table, key, prefix in [('products', 'product_id', 'P-FR-EPHY-%'),
                               ('registrations', 'registration_id', 'R-FR-EPHY-%'),
                               ('uses', 'use_id', 'U-FR-EPHY-%')]:
        protected = conn.execute(sql.SQL("SELECT count(*) FROM {} WHERE {} LIKE %s AND validation_status <> 'automatically_extracted'").format(
            sql.Identifier(table), sql.Identifier(key)), (prefix,)).fetchone()[0]
        if protected:
            raise ValueError(f'{table}: reviewed or externally managed rows require reconciliation')
    if conn.execute("SELECT count(*) FROM registrations WHERE registration_id LIKE 'R-FR-EPHY-%' AND source_id <> 'FR-EPHY'").fetchone()[0]:
        raise ValueError('Registration ownership collision')
    if conn.execute("SELECT count(*) FROM product_aliases WHERE alias_id LIKE 'A-FR-EPHY-%' AND review_status <> 'to_verify'").fetchone()[0]:
        raise ValueError('Reviewed aliases require reconciliation')
    ownership = "((entity_type = 'product' AND entity_id LIKE 'P-FR-EPHY-%') OR (entity_type = 'registration' AND entity_id LIKE 'R-FR-EPHY-%') OR (entity_type = 'use' AND entity_id LIKE 'U-FR-EPHY-%'))"
    if conn.execute("SELECT count(*) FROM field_evidence WHERE " + ownership + " AND (extraction_method <> 'open_data_csv' OR validation_status <> 'automatically_extracted')").fetchone()[0]:
        raise ValueError('Reviewed evidence requires reconciliation')
    old_count = conn.execute("SELECT count(*) FROM registrations WHERE source_id='FR-EPHY' AND registration_id LIKE 'R-FR-EPHY-%'").fetchone()[0]
    if not counts.get('registrations') or (old_count and counts['registrations'] < old_count * 0.8):
        raise ValueError('Empty or unexpectedly reduced snapshot; existing data preserved')
    for table in ('products', 'registrations', 'product_aliases'):
        fields = exporter.HEADERS[table]
        key = KEYS[table]
        assignments = sql.SQL(', ').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(c), sql.Identifier(c)) for c in fields if c != key)
        columns = sql.SQL(', ').join(map(sql.Identifier, fields))
        conn.execute(sql.SQL('INSERT INTO {} ({}) SELECT {} FROM {} ON CONFLICT ({}) DO UPDATE SET {}').format(
            sql.Identifier(table), columns, columns, sql.Identifier('incoming_' + table), sql.Identifier(key), assignments))
    # The target has no use-status column: remove uses absent from the new authorized snapshot.
    conn.execute("DELETE FROM field_evidence WHERE " + ownership)
    conn.execute("DELETE FROM uses WHERE use_id LIKE 'U-FR-EPHY-%'")
    for table in ('uses', 'field_evidence'):
        fields = sql.SQL(', ').join(map(sql.Identifier, exporter.HEADERS[table]))
        conn.execute(sql.SQL('INSERT INTO {} ({}) SELECT {} FROM {}').format(sql.Identifier(table), fields, fields, sql.Identifier('incoming_' + table)))
    conn.execute("DELETE FROM product_aliases a WHERE alias_id LIKE 'A-FR-EPHY-%' AND NOT EXISTS (SELECT 1 FROM incoming_product_aliases i WHERE i.alias_id=a.alias_id)")
    conn.execute("""UPDATE registrations r SET status_normalized='unknown'
                    WHERE r.registration_id LIKE 'R-FR-EPHY-%' AND r.source_id='FR-EPHY'
                    AND NOT EXISTS (SELECT 1 FROM incoming_registrations i WHERE i.registration_id=r.registration_id)""")


def previous_success(conn):
    row = conn.execute("""SELECT finished_at, notes FROM collection_runs WHERE source_id='FR-EPHY'
                          AND status='success' AND notes LIKE %s ORDER BY finished_at DESC LIMIT 1""", (MARKER,)).fetchone()
    return (row[0], json.loads(row[1])) if row else (None, {})


def cycle(url, data_dir, interval, force=False):
    with connect(url) as conn:
        if not conn.execute('SELECT pg_try_advisory_lock(%s)', (LOCK,)).fetchone()[0]:
            return dict(status='another_instance_running', wait=60)
        # Closing the connection releases the session lock on every exit path.
        finished, previous = previous_success(conn)
        delay = seconds_until_due(finished, interval)
        if delay and not force:
            return dict(status='scheduled', wait=delay, last_success=finished.isoformat())
        conn.execute("""INSERT INTO source_registry
            (source_id,official_name,country_or_region,base_url,access_method,data_format,license_name,manual_validation_required)
            VALUES ('FR-EPHY','ANSES E-Phy Open Data','FR',%s,'download','CSV; ZIP','Licence Ouverte',false)
            ON CONFLICT (source_id) DO NOTHING""", (exporter.CATALOGUE,))
        conn.execute("""UPDATE collection_runs SET status='failed', finished_at=clock_timestamp(), notes=%s
                        WHERE source_id='FR-EPHY' AND status='running' AND notes LIKE %s""",
                     (notes(error='Previous process stopped before completion'), MARKER))
        run_id = conn.execute("INSERT INTO collection_runs (source_id,status,notes) VALUES ('FR-EPHY','running',%s) RETURNING run_id", (notes(),)).fetchone()[0]
        directory = data_dir / str(run_id)
        try:
            directory.mkdir(parents=True, exist_ok=False)
            raw = directory / 'raw'
            raw.mkdir()
            metadata_bytes = exporter.fetch(exporter.CATALOGUE)
            (raw / 'catalogue.json').write_bytes(metadata_bytes)
            metadata = json.loads(metadata_bytes)
            resources = [r for r in metadata['resources'] if 'utf8' in r['url'].lower() and r['url'].lower().endswith('.zip')]
            if len(resources) != 1:
                raise ValueError('Expected exactly one UTF-8 ZIP')
            source_url = resources[0]['url']
            payload = exporter.fetch(source_url)
            archive = raw / 'fr_ephy.zip'
            archive.write_bytes(payload)
            sha = hashlib.sha256(payload).hexdigest()
            collected = exporter.now()
            manifest = dict(source_url=source_url, sha256=sha, collected_at=collected, run_id=run_id)
            (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
            # Compare the archive content, not its changing download URL.
            existing = conn.execute("SELECT count(*) FROM registrations WHERE registration_id LIKE 'R-FR-EPHY-%' AND source_id='FR-EPHY'").fetchone()[0]
            if previous.get('sha256') == sha and existing and not force:
                conn.execute("UPDATE collection_runs SET status='success',finished_at=clock_timestamp(),input_file=%s,rows_read=0,rows_written=0,notes=%s WHERE run_id=%s",
                             (str(archive), notes(sha256=sha, unchanged=True), run_id))
                return dict(status='unchanged', run_id=run_id, wait=interval)
            tables = exporter.read_tables(archive)
            report = exporter.convert(tables, directory, source_url, collected, collected)
            validation = validate(directory)
            (directory / 'validation_report.json').write_text(json.dumps(validation, indent=2), encoding='utf-8')
            if not validation['valid']:
                raise ValueError('Five-rule CSV validation failed')
            with conn.transaction():
                merge(conn, directory, report['counts'])
                conn.execute("UPDATE collection_runs SET status='success',finished_at=clock_timestamp(),input_file=%s,rows_read=%s,rows_written=%s,notes=%s WHERE run_id=%s",
                             (str(archive), sum(map(len, tables.values())), sum(report['counts'].get(t, 0) for t in TABLES),
                              notes(sha256=sha, counts=report['counts'], warnings=len(report['warnings'])), run_id))
            return dict(status='success', run_id=run_id, counts=report['counts'], wait=interval)
        except Exception as exc:
            # Failure messages are sanitized: no source text or credentials in logs.
            code = getattr(exc, 'sqlstate', None) or type(exc).__name__
            conn.execute("UPDATE collection_runs SET status='failed',finished_at=clock_timestamp(),notes=%s WHERE run_id=%s", (notes(error=code), run_id))
            raise RuntimeError(f'Refresh failed; run_id={run_id}, error={code}') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Run one due refresh and exit (operations/testing)')
    parser.add_argument('--force', action='store_true', help='With --once, reprocess even if not due/unchanged')
    parser.add_argument('--check-db', action='store_true', help='Read-only server metadata check')
    args = parser.parse_args()
    if args.force and not args.once:
        parser.error('--force requires --once')
    url = os.environ.get('DATABASE_URL')
    if not url:
        parser.error('DATABASE_URL is required')
    if args.check_db:
        print(json.dumps(exporter.check_database(url), indent=2))
        return
    interval = int(os.environ.get('REFRESH_INTERVAL_SECONDS', '604800'))
    retry = int(os.environ.get('RETRY_INTERVAL_SECONDS', '300'))
    if interval < 60 or retry < 1:
        parser.error('Refresh interval must be >=60 seconds; retry interval >=1 second')
    data_dir = Path(os.environ.get('DATA_DIR', str(Path(__file__).parent / 'state'))).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: STOP.set())
    def heartbeat():
        while not STOP.is_set():
            (data_dir / 'heartbeat').touch()
            STOP.wait(30)
    threading.Thread(target=heartbeat, daemon=True).start()
    failures = 0
    while not STOP.is_set():
        try:
            result = cycle(url, data_dir, interval, args.force)
            failures = 0
            LOG.info('%s', json.dumps(result))
            delay = result['wait']
        except Exception as exc:
            failures += 1
            delay = min(retry * (2 ** min(failures - 1, 6)), 3600)
            LOG.error('refresh_failed type=%s retry_seconds=%s detail=%s', type(exc).__name__, delay, str(exc) if isinstance(exc, RuntimeError) else 'See collection_runs; connection errors are redacted')
            if args.once:
                raise SystemExit(1) from None
        if args.once:
            return
        deadline = time.monotonic() + delay
        while not STOP.is_set() and time.monotonic() < deadline:
            (data_dir / 'heartbeat').touch()
            STOP.wait(min(30, max(0, deadline - time.monotonic())))
    LOG.info('Service stopped')


if __name__ == '__main__':
    main()
