#!/usr/bin/env python3
"""Persistent scheduled Germany BVL ingestion, with the France service interface."""
import argparse
from collections import Counter
import json
import logging
import os
from pathlib import Path
import re
import signal
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote

import psycopg
from psycopg import sql
from bvl import GermanyBVLAdapter
from bvl.base import COLUMNS
from bvl.de_bvl import BASE, VERSION, digest
from bvl.export import validate

LOG = logging.getLogger('germany')
ADAPTER = 'germany-service-v1'
MARKER = '%"adapter": "germany-service-v1"%'
LOCK = 59391008740914  # Independent of France, common to all Germany instances/scopes.
STOP = threading.Event()
TABLES = ('products', 'registrations', 'product_aliases', 'uses', 'field_evidence')
KEYS = {'products': 'product_id', 'registrations': 'registration_id', 'product_aliases': 'alias_id', 'uses': 'use_id'}


def now():
    return datetime.now(timezone.utc)


def seconds_until_due(finished, interval, current=None):
    return max(0, interval - ((current or now()) - finished).total_seconds()) if finished else 0


def notes(**values):
    return json.dumps(dict(adapter=ADAPTER, **values), ensure_ascii=False)


def scope_config(registrations=None):
    return dict(base_url=BASE, registrations=sorted(set(registrations or [])), connector_version=VERSION)


def snapshot_digest(raw):
    # Response paging, retrieval timestamps and Oracle physical locations do not
    # change regulatory content. Multiplicities and all actual field values do.
    return digest({name: sorted(Counter(digest(row) for row in rows).items()) for name, rows in raw.items()})


def connect(url, read_only=False):
    options = '-c search_path=public -c statement_timeout=300000 -c lock_timeout=15000'
    if read_only:
        options += ' -c default_transaction_read_only=on'
    return psycopg.connect(url.replace('postgresql+psycopg://', 'postgresql://', 1),
        autocommit=True, connect_timeout=10, options=options, application_name=ADAPTER)


def check_database(url):
    """Read only: inspect the public flat schema used by both services."""
    try:
        with connect(url, read_only=True) as conn:
            rows = conn.execute("""SELECT table_name, column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name=ANY(%s)""", (list(COLUMNS),)).fetchall()
            present = {}
            for table, field in rows:
                present.setdefault(table, set()).add(field)
            required = {k: list(v) for k, v in COLUMNS.items()}
            required['collection_runs'].append('run_id')
            required['field_evidence'].append('evidence_id')
            missing = {table: sorted(set(fields) - present.get(table, set())) for table, fields in required.items()}
            missing = {table: fields for table, fields in missing.items() if fields}
            constraints = conn.execute("""SELECT c.relname, con.conname, pg_get_constraintdef(con.oid)
                FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relname=ANY(%s) ORDER BY c.relname,con.conname""", (list(COLUMNS),)).fetchall()
            return dict(connected=True, read_only=True, schema='public', compatible=not missing,
                missing_columns=missing, constraints=[dict(table=t, name=n, definition=d) for t,n,d in constraints],
                note='Column/constraint inspection only; no tables created or data changed.')
    except psycopg.Error as exc:
        raise RuntimeError('Database check failed (' + (exc.sqlstate or 'connection_error') + ')') from None


def copy_stage(conn, directory, table):
    columns = sql.SQL(', ').join(map(sql.Identifier, COLUMNS[table]))
    stage = sql.Identifier('incoming_' + table)
    conn.execute(sql.SQL('CREATE TEMP TABLE {} ON COMMIT DROP AS SELECT {} FROM {} WITH NO DATA').format(stage, columns, sql.Identifier(table)))
    statement = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, ENCODING 'UTF8')").format(stage, columns)
    with (directory / ('de_' + table + '.csv')).open('rb') as source:
        with conn.cursor().copy(statement) as copy:
            while chunk := source.read(1024 * 1024):
                copy.write(chunk)
    if table in KEYS:
        conn.execute(sql.SQL('CREATE UNIQUE INDEX ON {} ({})').format(stage, sql.Identifier(KEYS[table])))


def merge(conn, directory, counts, registrations=None):
    """Caller owns the transaction; reconcile only this source and selected scope."""
    for table in TABLES:
        copy_stage(conn, directory, table)
    # Serialize review guards and subsequent writes with manual edits as well as
    # other importers. Readers can continue; lock wait is bounded on connection.
    conn.execute('LOCK TABLE products, registrations, product_aliases, uses, field_evidence IN SHARE ROW EXCLUSIVE MODE')
    for table, key, prefix in [('products','product_id','P-DE-BVL-%'), ('registrations','registration_id','R-DE-BVL-%'), ('uses','use_id','U-DE-BVL-%'), ('product_aliases','alias_id','A-DE-BVL-%')]:
        if conn.execute(sql.SQL('SELECT count(*) FROM {} WHERE {} NOT LIKE %s OR is_synthetic IS DISTINCT FROM false').format(sql.Identifier('incoming_'+table), sql.Identifier(key)), (prefix,)).fetchone()[0]:
            raise ValueError('Incoming rows are synthetic or outside the Germany namespace')
    if conn.execute("SELECT count(*) FROM incoming_registrations WHERE source_id IS DISTINCT FROM 'DE-BVL' OR country_code IS DISTINCT FROM 'DE'").fetchone()[0]:
        raise ValueError('Incoming registration ownership mismatch')
    selected = ['R-DE-BVL-' + quote(reg, safe='') for reg in registrations] if registrations else None
    if selected and conn.execute('SELECT count(*) FROM incoming_registrations WHERE NOT (registration_id=ANY(%s))', (selected,)).fetchone()[0]:
        raise ValueError('Incoming registration outside selected scope')
    conn.execute('''CREATE TEMP TABLE managed_registrations ON COMMIT DROP AS
        SELECT registration_id FROM registrations WHERE registration_id LIKE 'R-DE-BVL-%%'
        AND (%s::text[] IS NULL OR registration_id=ANY(%s))
        UNION SELECT registration_id FROM incoming_registrations''', (selected, selected))
    conn.execute('''CREATE TEMP TABLE managed_products ON COMMIT DROP AS
        SELECT product_id FROM registrations JOIN managed_registrations USING(registration_id)
        UNION SELECT product_id FROM incoming_products''')
    conn.execute('''CREATE TEMP TABLE managed_uses ON COMMIT DROP AS
        SELECT use_id FROM uses JOIN managed_registrations USING(registration_id) WHERE use_id LIKE 'U-DE-BVL-%'
        UNION SELECT use_id FROM incoming_uses''')
    conn.execute('''CREATE TEMP TABLE managed_product_aliases ON COMMIT DROP AS
        SELECT alias_id FROM product_aliases JOIN managed_products USING(product_id) WHERE alias_id LIKE 'A-DE-BVL-%'
        UNION SELECT alias_id FROM incoming_product_aliases''')
    for table,key in KEYS.items():
        conn.execute(sql.SQL('CREATE UNIQUE INDEX ON {} ({})').format(sql.Identifier('managed_'+table),sql.Identifier(key)))
        conn.execute(sql.SQL('ANALYZE {}').format(sql.Identifier('managed_'+table)))
    for table,key in KEYS.items():
        status = 'review_status' if table == 'product_aliases' else 'validation_status'
        expected = 'to_verify' if table == 'product_aliases' else 'automatically_extracted'
        protected = conn.execute(sql.SQL('SELECT count(*) FROM {} JOIN {} USING ({}) WHERE {} IS DISTINCT FROM %s').format(
            sql.Identifier(table),sql.Identifier('managed_'+table),sql.Identifier(key),sql.Identifier(status)), (expected,)).fetchone()[0]
        if protected:
            raise ValueError(f'{table}: reviewed or externally managed rows require reconciliation')
    if conn.execute("""SELECT count(*) FROM registrations JOIN managed_registrations USING(registration_id)
        WHERE source_id IS DISTINCT FROM 'DE-BVL' OR country_code IS DISTINCT FROM 'DE'
        OR product_id NOT LIKE 'P-DE-BVL-%'""").fetchone()[0]:
        raise ValueError('Existing registration ownership collision')
    if conn.execute('''SELECT count(*) FROM uses u JOIN managed_uses USING(use_id)
        WHERE NOT EXISTS(SELECT 1 FROM managed_registrations r WHERE r.registration_id=u.registration_id)''').fetchone()[0]:
        raise ValueError('Existing use ownership collision')
    ownership = """((entity_type='product' AND EXISTS (SELECT 1 FROM managed_products m WHERE m.product_id=field_evidence.entity_id))
        OR (entity_type='registration' AND EXISTS (SELECT 1 FROM managed_registrations m WHERE m.registration_id=field_evidence.entity_id))
        OR (entity_type='use' AND EXISTS (SELECT 1 FROM managed_uses m WHERE m.use_id=field_evidence.entity_id)))"""
    if conn.execute("SELECT count(*) FROM field_evidence WHERE " + ownership + " AND (extraction_method IS DISTINCT FROM 'official_api_json' OR validation_status IS DISTINCT FROM 'automatically_extracted')").fetchone()[0]:
        raise ValueError('Reviewed evidence requires reconciliation')
    old_count = conn.execute("SELECT count(*) FROM registrations JOIN managed_registrations USING(registration_id) WHERE source_id='DE-BVL'").fetchone()[0]
    if not counts.get('registrations') or (old_count and counts['registrations'] < old_count * 0.8):
        raise ValueError('Empty or unexpectedly reduced snapshot; existing data preserved')
    for table in ('products','registrations','product_aliases'):
        fields = COLUMNS[table]
        key = KEYS[table]
        columns = sql.SQL(', ').join(map(sql.Identifier, fields))
        assignments = sql.SQL(', ').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(c),sql.Identifier(c)) for c in fields if c!=key)
        conn.execute(sql.SQL('INSERT INTO {} ({}) SELECT {} FROM {} ON CONFLICT ({}) DO UPDATE SET {}').format(
            sql.Identifier(table), columns, columns, sql.Identifier('incoming_'+table), sql.Identifier(key), assignments))
    # Keep evidence for registrations/products no longer observed. Remove their
    # obsolete use rows but retain the raw snapshots in persistent storage.
    evidence_replace = """((entity_type='product' AND EXISTS (SELECT 1 FROM incoming_products i WHERE i.product_id=field_evidence.entity_id))
        OR (entity_type='registration' AND EXISTS (SELECT 1 FROM incoming_registrations i WHERE i.registration_id=field_evidence.entity_id))
        OR (entity_type='use' AND EXISTS (SELECT 1 FROM managed_uses m WHERE m.use_id=field_evidence.entity_id)))"""
    conn.execute('DELETE FROM field_evidence WHERE ' + evidence_replace)
    conn.execute('DELETE FROM uses WHERE use_id IN (SELECT use_id FROM managed_uses)')
    for table in ('uses','field_evidence'):
        columns=sql.SQL(', ').join(map(sql.Identifier,COLUMNS[table]))
        conn.execute(sql.SQL('INSERT INTO {} ({}) SELECT {} FROM {}').format(sql.Identifier(table),columns,columns,sql.Identifier('incoming_'+table)))
    conn.execute('''DELETE FROM product_aliases WHERE alias_id IN (SELECT alias_id FROM managed_product_aliases)
        AND alias_id NOT IN (SELECT alias_id FROM incoming_product_aliases)''')
    conn.execute("""UPDATE registrations SET status_normalized='unknown'
        WHERE registration_id IN (SELECT registration_id FROM managed_registrations)
        AND registration_id NOT IN (SELECT registration_id FROM incoming_registrations)""")


def previous_success(conn, scope):
    row=conn.execute("""SELECT finished_at, notes FROM collection_runs WHERE source_id='DE-BVL'
        AND status='success' AND notes LIKE %s AND notes LIKE %s ORDER BY finished_at DESC LIMIT 1""",
        (MARKER, '%"scope_key": "'+digest(scope)+'"%')).fetchone()
    return (row[0],json.loads(row[1])) if row else (None,{})


def cycle(url, data_dir, interval, force=False, registrations=None, replay_dir=None):
    scope=scope_config(registrations)
    with connect(url) as conn:
        if not conn.execute('SELECT pg_try_advisory_lock(%s)', (LOCK,)).fetchone()[0]:
            return dict(status='another_instance_running', wait=60)
        finished,previous=previous_success(conn,scope)
        delay=seconds_until_due(finished,interval)
        if delay and not force:
            return dict(status='scheduled',wait=delay,last_success=finished.isoformat())
        conn.execute("""INSERT INTO source_registry (source_id,official_name,country_or_region,base_url,access_method,data_format,manual_validation_required)
            VALUES ('DE-BVL','BVL PSM API','DE',%s,'api','JSON',true) ON CONFLICT(source_id) DO NOTHING""",(BASE+'/',))
        conn.execute("""UPDATE collection_runs SET status='failed',finished_at=clock_timestamp(),notes=%s
            WHERE source_id='DE-BVL' AND status='running' AND notes LIKE %s""", (notes(error='Previous process stopped before completion'),MARKER))
        run_id=conn.execute("INSERT INTO collection_runs(source_id,status,notes) VALUES ('DE-BVL','running',%s) RETURNING run_id",(notes(scope_key=digest(scope),scope=scope),)).fetchone()[0]
        directory=Path(data_dir)/str(run_id)
        adapter_options=dict(registrations=registrations,compact_evidence=True)
        if replay_dir is not None:
            adapter_options['offline_dir']=replay_dir
        adapter=GermanyBVLAdapter(**adapter_options)
        try:
            directory.mkdir(parents=True,exist_ok=False)
            raw=adapter.fetch()
            if replay_dir and (not isinstance(adapter.scope,dict) or sorted(adapter.scope.get('registrations',[])) != sorted(registrations or [])):
                raise ValueError('Replay scope does not match configured registrations')
            adapter.write_snapshots(directory)
            sha=snapshot_digest(raw)
            bundle=adapter.to_canonical(raw)
            validation=validate(bundle)
            (directory/'validation_report.json').write_text(json.dumps(validation,indent=2))
            if not validation['valid'] or adapter.synthetic:
                raise ValueError('Germany CSV validation failed or source is synthetic')
            if any(w['level'] in ('incomplete','skipped') for w in bundle.warnings):
                raise ValueError('Incomplete source coverage; previous snapshot preserved')
            bundle.write_csv(directory,'de_')
            adapter.write_snapshots(directory)  # Include conversion warnings.
            counts={t:len(getattr(bundle,t)) for t in TABLES}
            if not counts['registrations']:
                raise ValueError('Empty source snapshot')
            # Reconcile even unchanged content: preserves review guards, repairs
            # removed DB rows, and refreshes evidence timestamps atomically.
            unchanged=previous.get('sha256')==sha and not force
            with conn.transaction():
                merge(conn,directory,counts,registrations)
                conn.execute("""UPDATE collection_runs SET status='success',finished_at=clock_timestamp(),input_file=%s,
                    rows_read=%s,rows_written=%s,notes=%s WHERE run_id=%s""",
                    (str(directory/'manifest.json'),sum(map(len,raw.values())),sum(counts.values()),
                     notes(scope_key=digest(scope),scope=scope,sha256=sha,unchanged=unchanged,counts=counts,warnings=len(bundle.warnings)),run_id))
            return dict(status='unchanged' if unchanged else 'success',run_id=run_id,counts=counts,wait=interval)
        except Exception as exc:
            code=getattr(exc,'sqlstate',None) or type(exc).__name__
            conn.execute("UPDATE collection_runs SET status='failed',finished_at=clock_timestamp(),notes=%s WHERE run_id=%s",
                (notes(scope_key=digest(scope),error=code),run_id))
            raise RuntimeError(f'Refresh failed; run_id={run_id}, error={code}') from None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once',action='store_true',help='Run one due refresh and exit (operations/testing)')
    parser.add_argument('--force',action='store_true',help='With --once, reprocess even if not due/unchanged')
    parser.add_argument('--check-db',action='store_true',help='Read-only server metadata check')
    parser.add_argument('--replay',type=Path,help='With --once --force, recover from a complete saved snapshot')
    args=parser.parse_args()
    if args.replay and not (args.once and args.force):
        parser.error('--replay requires --once --force')
    if args.force and not args.once:
        parser.error('--force requires --once')
    url=os.environ.get('DATABASE_URL')
    if not url:
        parser.error('DATABASE_URL is required')
    if args.check_db:
        try:
            report=check_database(url)
        except RuntimeError as exc:
            parser.exit(1,str(exc)+'\n')
        print(json.dumps(report,indent=2))
        raise SystemExit(0 if report['compatible'] else 1)
    try:
        interval=int(os.environ.get('REFRESH_INTERVAL_SECONDS','604800'))
        retry=int(os.environ.get('RETRY_INTERVAL_SECONDS','300'))
    except ValueError:
        parser.error('Refresh and retry intervals must be integer seconds')
    if interval<60 or retry<1:
        parser.error('Refresh interval must be >=60 seconds; retry interval >=1 second')
    registrations=sorted(set(x.strip() for x in os.environ.get('BVL_REGISTRATIONS','').split(',') if x.strip())) or None
    if registrations and any(not re.fullmatch(r'[A-Za-z0-9]+-\d{2}',reg) for reg in registrations):
        parser.error('BVL_REGISTRATIONS must contain comma-separated BVL numbers, e.g. 034346-00')
    data_dir=Path(os.environ.get('DATA_DIR',str(Path(__file__).parent/'state'))).resolve()
    data_dir.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    for sig in (signal.SIGTERM,signal.SIGINT):
        signal.signal(sig,lambda *_: STOP.set())
    def heartbeat():
        while not STOP.is_set():
            (data_dir/'heartbeat').touch()
            STOP.wait(30)
    threading.Thread(target=heartbeat,daemon=True).start()
    failures=0
    while not STOP.is_set():
        try:
            result=cycle(url,data_dir,interval,args.force,registrations,args.replay)
            failures=0
            LOG.info('%s',json.dumps(result))
            delay=result['wait']
        except Exception as exc:
            failures+=1
            delay=min(retry*(2**min(failures-1,6)),3600)
            LOG.error('refresh_failed type=%s retry_seconds=%s detail=%s',type(exc).__name__,delay,
                str(exc) if isinstance(exc,RuntimeError) else 'Connection error details redacted')
            if args.once:
                raise SystemExit(1) from None
        if args.once:
            return
        deadline=time.monotonic()+delay
        while not STOP.is_set() and time.monotonic()<deadline:
            (data_dir/'heartbeat').touch()
            STOP.wait(min(30,max(0,deadline-time.monotonic())))
    LOG.info('Service stopped')


if __name__=='__main__':
    main()
