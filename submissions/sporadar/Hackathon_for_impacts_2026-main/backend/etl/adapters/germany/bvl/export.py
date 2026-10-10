"""Explicit, transaction-only initial loaders for the two documented contracts."""
import json
import uuid
from pathlib import Path
from .base import COLUMNS
from .de_bvl import VERSION


def validate(bundle):
    errors = []
    keys = {}
    for table, key in [('products', 'product_id'), ('registrations', 'registration_id'), ('uses', 'use_id')]:
        rows = getattr(bundle, table)
        ids = [r.get(key) for r in rows]
        keys[table] = set(ids)
        if None in ids or len(ids) != len(set(ids)):
            errors.append(f'{table}: missing or duplicate identity')
        for row in rows:
            if row.get('validation_status') != 'automatically_extracted':
                errors.append(f'{row.get(key)}: validation_status must be automatically_extracted')
            if row.get('is_synthetic') not in ('true', 'false'):
                errors.append(f'{row.get(key)}: explicit synthetic flag required')
    sources = {r['source_id'] for r in bundle.source_registry}
    for row in bundle.registrations:
        if row['product_id'] not in keys['products'] or row['source_id'] not in sources:
            errors.append(f'{row["registration_id"]}: missing product/source')
        if not row.get('authority_name') or row.get('country_code') != 'DE':
            errors.append(f'{row["registration_id"]}: missing authority or incorrect country')
        if row.get('status_normalized') not in {'active', 'expired', 'withdrawn', 'pending', 'unknown'}:
            errors.append(f'{row["registration_id"]}: invalid status')
        if not row.get('source_record_url', '').startswith('https://'):
            errors.append(f'{row["registration_id"]}: HTTPS source URL required')
    evidence = {(r['entity_type'], r['entity_id']) for r in bundle.field_evidence}
    for row in bundle.registrations:
        if ('registration', row['registration_id']) not in evidence:
            errors.append(f'{row["registration_id"]}: no evidence')
    for row in bundle.uses:
        if row['registration_id'] not in keys['registrations'] or ('use', row['use_id']) not in evidence:
            errors.append(f'{row["use_id"]}: missing parent or evidence')
    return dict(valid=not errors, errors=errors, counts={k: len(v) for k, v in keys.items()})


def flat_loader(directory):
    # Relative paths make the entire export relocatable; invoke psql from this directory.
    order = ('source_registry', 'products', 'product_aliases', 'registrations', 'uses', 'field_evidence', 'collection_runs')
    lines = ['\\set ON_ERROR_STOP on', '-- Initial import only. Run psql from the export directory.', 'BEGIN;']
    for table in order:
        columns = ', '.join(COLUMNS[table])
        target = table
        if table == 'source_registry':
            target = 'incoming_source'
            lines.append('CREATE TEMP TABLE incoming_source (LIKE source_registry INCLUDING DEFAULTS) ON COMMIT DROP;')
        lines.append(f"\\copy {target} ({columns}) FROM 'de_{table}.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')")
        if table == 'source_registry':
            lines.append('INSERT INTO source_registry SELECT * FROM incoming_source ON CONFLICT (source_id) DO NOTHING;')
    lines.append('COMMIT;')
    (Path(directory) / 'load-flat.sql').write_text('\n'.join(lines) + '\n')


def regulatory_loader(directory, bundle, adapter):
    """Initial unpublished import. Key collisions roll back; no history is overwritten."""
    namespace = uuid.UUID('5ea27e79-20ca-49a1-886d-1b5cd1fb26df')
    def uid(*parts):
        return str(uuid.uuid5(namespace, json.dumps(parts, ensure_ascii=False)))
    actor = object()
    def sql(value):
        if value is actor:
            return ":'actor_subject'"
        if value is None:
            return 'NULL'
        return "'" + str(value).replace("'", "''") + "'"
    lines = ['\\set ON_ERROR_STOP on', '\\if :{?actor_subject}', '\\else',
             '\\echo Supply -v actor_subject=<authenticated-importer-subject>', '\\quit 1', '\\endif',
             'BEGIN;', 'SET LOCAL standard_conforming_strings = on;',
             'SET LOCAL search_path = regulatory, public;']
    def insert(table, row, audit=True):
        lines.append(f"INSERT INTO {table} ({', '.join(row)}) VALUES ({', '.join(sql(v) for v in row.values())});")
        if audit:
            record_id = row.get('id') or row.get('use_id') or row.get('registration_version_id')
            if record_id:
                insert('audit_event', dict(actor_subject=actor, action='import', table_name=table,
                    record_id=record_id, after_data=json.dumps(row, ensure_ascii=False)), False)
    def shared(statement, table, record_id=None):
        # Audit only genuinely inserted metadata rows, within this transaction.
        record = sql(record_id) + '::uuid' if record_id else 'id'
        lines.append(f"WITH inserted AS ({statement} RETURNING *) INSERT INTO audit_event (actor_subject, action, table_name, record_id, after_data) SELECT {sql(actor)}, 'import', {sql(table)}, {record}, to_jsonb(inserted) FROM inserted;")
    # Shared lookup identities may already exist. Resolve DE by its unique code.
    shared(f"INSERT INTO jurisdiction (id, code, name) VALUES ({sql(uid('jurisdiction','DE'))}, 'DE', 'Germany') ON CONFLICT (code) DO NOTHING", 'jurisdiction')
    authority, source = uid('authority'), uid('source')
    shared(f"INSERT INTO organization (id, name) VALUES ({sql(authority)}, {sql(adapter.authority)}) ON CONFLICT (id) DO NOTHING", 'organization')
    shared(f"INSERT INTO source (id, name, publisher_id, jurisdiction_id, base_url, access_methods, reuse_notes) SELECT {sql(source)}, 'BVL PSM API', {sql(authority)}, id, {sql(adapter.pages[0]['source_url'].split('/api-v1')[0] + '/api-v1/')}, ARRAY['api'], 'Confirm current BVL reuse terms; see source manifest' FROM jurisdiction WHERE code='DE' ON CONFLICT (id) DO NOTHING", 'source')
    run_id = str(uuid.uuid4())
    insert('ingestion_run', dict(id=run_id, source_id=source, started_at=adapter.started_at,
        ended_at=bundle.collection_runs[0]['finished_at'], connector_version=VERSION,
        outcome='partial' if bundle.collection_runs[0]['status'] != 'success' else 'succeeded', errors=json.dumps(bundle.warnings, ensure_ascii=False)))
    snapshots = {}
    for page in adapter.pages:
        snapshot = uid('snapshot', run_id, page['file'])
        snapshots[id(page)] = snapshot
        insert('source_snapshot', dict(id=snapshot, ingestion_run_id=run_id, exact_url=page['source_url'],
            retrieved_at=page['collected_at'], sha256=page['sha256'], storage_uri=page['file'], media_type='application/json'))
        insert('extraction', dict(id=uid('extraction', snapshot), snapshot_id=snapshot,
            extracted_data=page['body'].decode('utf-8'), extractor_version=VERSION, review_status='to_verify'))
    for p in bundle.products:
        insert('product', dict(id=uid(p['product_id']), canonical_name=p['commercial_name'],
            record_kind='synthetic' if p['is_synthetic'] == 'true' else 'real'))
        insert('product_name', dict(id=uid('name', p['product_id']), product_id=uid(p['product_id']),
            name=p['commercial_name'], language='de', name_type='market'))
    emitted_evidence = set()
    def attach(table, key, entity):
        for row in adapter.source_rows[entity]:
            page, index = adapter.provenance(row)
            snapshot = snapshots[id(page)]
            eid = uid('evidence', snapshot, index)
            if eid not in emitted_evidence:
                emitted_evidence.add(eid)
                insert('evidence', dict(id=eid, snapshot_id=snapshot, locator=f'/items/{index}', quoted_text=json.dumps(row, ensure_ascii=False)))
            # Each source row appears once per entity, including shared dictionaries.
            insert(table, {key: uid(entity, 'version1') if table == 'registration_evidence' else uid(entity), 'evidence_id': eid, 'field_name': '*'})
    for r in bundle.registrations:
        row = dict(id=uid(r['registration_id']), product_id=uid(r['product_id']), authority_id=authority,
                   registration_number=r['registration_number'], record_kind='synthetic' if r['is_synthetic'] == 'true' else 'real')
        lines.append(f"INSERT INTO registration ({', '.join(row)}, jurisdiction_id) SELECT {', '.join(sql(v) for v in row.values())}, id FROM jurisdiction WHERE code='DE';")
        insert('audit_event', dict(actor_subject=actor, action='import', table_name='registration', record_id=row['id'], after_data=json.dumps(row)), False)
        insert('registration_version', dict(id=uid(r['registration_id'], 'version1'), registration_id=row['id'], version_number=1,
            status=r['status_normalized'], status_original=r.get('status_original'), approval_date=r.get('approval_date'),
            expiration_date=r.get('expiration_date'), review_status='to_verify'))
        attach('registration_evidence', 'registration_version_id', r['registration_id'])
    units = {r['dose_unit_normalized'] for r in bundle.uses if r.get('dose_value') is not None}
    for unit in sorted(units):
        shared(f"INSERT INTO unit (code, dimension, label) VALUES ({sql(unit)}, 'application_dose', {sql(unit)}) ON CONFLICT (code) DO NOTHING", 'unit', uid('unit', unit))
    for u in bundle.uses:
        key = u['use_id']
        insert('authorized_use', dict(id=uid(key), registration_version_id=uid(u['registration_id'], 'version1'),
            original_description=u['restrictions_original'], restrictions_original=u['restrictions_original'],
            review_status='to_verify', record_kind='synthetic' if u['is_synthetic'] == 'true' else 'real'))
        for table, field in [('use_crop', 'crop_name_original'), ('use_target', 'target_name_original')]:
            if u.get(field) is not None:
                insert(table, dict(id=uid(table, key), use_id=uid(key), original_text=u[field], mapping_status='to_verify'))
        insert('application_rule', dict(id=uid('rule', key), use_id=uid(key), dose_min=u.get('dose_value'), dose_max=u.get('dose_value'),
            dose_unit_code=u.get('dose_unit_normalized') if u.get('dose_value') is not None else None,
            max_applications=u.get('max_applications'), interval_days=u.get('application_interval_days'), phi_days=u.get('phi_days'),
            original_instructions=u['restrictions_original']))
        attach('use_evidence', 'use_id', key)
    insert('coverage_check', dict(id=str(uuid.uuid4()), source_id=source, ingestion_run_id=run_id,
        query_scope=json.dumps({'registrations': sorted(adapter.registrations), 'collections': sorted({p['collection'] for p in adapter.pages})}),
        outcome='incomplete' if bundle.collection_runs[0]['status'] != 'success' else ('matches_found' if bundle.registrations else 'no_match'),
        completeness_notes='Unpublished initial import. Missing collections and unresolved fields are listed in warnings. No result is not proof of no registration.'))
    lines.append('COMMIT;')
    (Path(directory) / 'load-regulatory.sql').write_text('\n'.join(lines) + '\n', encoding='utf-8')
