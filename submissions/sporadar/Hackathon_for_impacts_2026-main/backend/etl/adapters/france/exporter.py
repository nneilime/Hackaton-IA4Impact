#!/usr/bin/env python3
"""Download ANSES E-Phy and export COPY-ready CSVs for the user's flat schema.

CSV export uses the standard library. --check-db requires psycopg.
Database connection checks are read-only; credentials come from DATABASE_URL.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZipFile

CATALOGUE = 'https://www.data.gouv.fr/api/1/datasets/575e9fac88ee38072a640390/'
SOURCE = 'FR-EPHY'
FILE_PREFIX = 'fr_'
HEADERS = {
    'source_registry': 'source_id official_name country_or_region base_url access_method data_format license_name access_and_reuse_limits manual_validation_required notes',
    'products': 'product_id commercial_name active_entity_original active_entity_normalized formulation_code is_synthetic validation_status',
    'product_aliases': 'alias_id product_id alias_name country_code relationship_type confidence evidence review_status is_synthetic',
    'registrations': 'registration_id product_id country_code authority_name registration_number status_original status_normalized approval_date expiration_date source_id source_record_url collected_at validation_status is_synthetic',
    'uses': 'use_id registration_id crop_name_original crop_name_normalized eppo_crop_code target_name_original target_name_normalized eppo_target_code application_method dose_value dose_unit_original dose_unit_normalized max_applications application_interval_days phi_days rei_hours restrictions_original validation_status is_synthetic',
    'field_evidence': 'entity_type entity_id field_name value_original excerpt document_url page_number extraction_method model_name confidence validation_status collected_at',
    'collection_runs': 'source_id started_at finished_at input_file rows_read rows_written status notes',
}
HEADERS = {k: v.split() for k, v in HEADERS.items()}
REQUIRED = {
    'produits_utf8.csv': ['numero AMM', 'type produit', 'nom produit', 'Etat d’autorisation', 'Substances actives', 'Date de première autorisation', 'seconds noms commerciaux'],
    'produits_usages_utf8.csv': ['numero AMM', 'identifiant usage', 'etat usage', 'dose retenue', 'dose retenue unite', 'nombre max d\'application', 'condition emploi'],
    'produits_condition_emploi_utf8.csv': ['numero AMM', 'catégorie de condition d’emploi', 'condition d’emploi libelle'],
}
FORMULATIONS = {'Granulé dispersable': 'WG', 'Poudre mouillable': 'WP',
                'Suspension concentrée': 'SC', 'Concentré émulsionnable': 'EC',
                'Dispersion huileuse': 'OD'}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def fetch(url):
    if not url.startswith('https://'):
        raise ValueError('Downloads require HTTPS')
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'LPC-EPhy-Ingestor/1.0'})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def read_tables(path):
    tables = {}
    with ZipFile(path) as archive:
        for name, required in REQUIRED.items():
            with archive.open(name) as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig', newline=''), delimiter=';')
                if not set(required).issubset(reader.fieldnames or []):
                    raise ValueError(f'{name}: missing expected columns')
                rows = []
                for line, row in enumerate(reader, 2):
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError(f'{name}:{line}: malformed CSV row')
                    rows.append(row)
                tables[name] = rows
    return tables


def number(value, warnings, context, integer=False):
    if not value.strip():
        return None
    try:
        val = Decimal(value.strip().replace(',', '.'))
        if not val.is_finite() or val < 0 or (integer and val != val.to_integral_value()):
            raise InvalidOperation
        return str(int(val)) if integer else format(val, 'f')
    except InvalidOperation:
        warnings.append({'context': context, 'value': value, 'reason': 'Not a nonnegative numeric value; retained in evidence'})
        return None


def date(value, warnings, context):
    if not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), '%d/%m/%Y').date().isoformat()
    except ValueError:
        warnings.append({'context': context, 'value': value, 'reason': 'Invalid date; retained in evidence'})
        return None


class Export:
    def __init__(self, directory, url, collected):
        self.directory, self.url, self.collected = directory, url, collected
        self.files, self.writers, self.counts = {}, {}, Counter()
        for table, columns in HEADERS.items():
            handle = (directory / (FILE_PREFIX + table + '.csv')).open('w', encoding='utf-8', newline='')
            self.files[table] = handle
            self.writers[table] = csv.DictWriter(handle, fieldnames=columns)
            self.writers[table].writeheader()

    def write(self, table, row):
        self.writers[table].writerow(row)
        self.counts[table] += 1

    def evidence(self, entity, key, field, value, filename, line):
        if value == '':
            return
        self.write('field_evidence', dict(entity_type=entity, entity_id=key, field_name=field,
            value_original=value, excerpt=value, document_url=self.url,
            extraction_method='open_data_csv', validation_status='automatically_extracted',
            collected_at=self.collected))

    def raw_evidence(self, entity, key, row, filename, line):
        for field, value in row.items():
            if field:
                self.evidence(entity, key, 'source.' + field, value, filename, line)
        self.evidence(entity, key, 'source_locator', f'{filename}: CSV record {line}', filename, line)

    def close(self):
        for handle in self.files.values():
            handle.close()


def convert(tables, output, url, collected, started, amms=None):
    warnings, excluded = [], Counter()
    if not url.startswith('https://'):
        raise ValueError('source_record_url must start with https://')
    ex = Export(output, url, collected)
    products = {}
    conditions = defaultdict(list)
    try:
        for line, row in enumerate(tables['produits_condition_emploi_utf8.csv'], 2):
            conditions[row['numero AMM']].append((line, row))
        ex.write('source_registry', dict(source_id=SOURCE, official_name='ANSES E-Phy Open Data',
            country_or_region='FR', base_url=CATALOGUE, access_method='download', data_format='CSV; ZIP',
            license_name='Licence Ouverte', access_and_reuse_limits='E-Phy/Anses attribution and data update date required; official decisions prevail; 120-day derogations excluded.',
            manual_validation_required='false', notes='PPP export; source observations require regulatory review.'))
        for line, row in enumerate(tables['produits_utf8.csv'], 2):
            amm = row['numero AMM']
            if row['type produit'] != 'PPP' or (amms and amm not in amms):
                excluded['products_outside_scope'] += 1
                continue
            if not amm or amm in products or not row['nom produit']:
                raise ValueError(f'Missing/duplicate product key or name: {amm!r}')
            pid, rid = f'P-FR-EPHY-{amm}', f'R-FR-EPHY-{amm}'
            products[amm] = row
            ex.write('products', dict(product_id=pid, commercial_name=row['nom produit'],
                active_entity_original=row['Substances actives'],
                formulation_code=FORMULATIONS.get(row.get('formulations')),
                is_synthetic='false', validation_status='automatically_extracted'))
            ex.raw_evidence('product', pid, row, 'produits_utf8.csv', line)
            ex.evidence('product', pid, 'active_entity_original', row['Substances actives'], 'produits_utf8.csv', line)
            status = {'AUTORISE': 'active', 'RETIRE': 'withdrawn'}.get(row['Etat d’autorisation'], 'unknown')
            ex.write('registrations', dict(registration_id=rid, product_id=pid, country_code='FR',
                authority_name='ANSES', registration_number=amm, status_original=row['Etat d’autorisation'],
                status_normalized=status, approval_date=date(row['Date de première autorisation'], warnings, rid),
                source_id=SOURCE, source_record_url=url, collected_at=collected,
                validation_status='automatically_extracted', is_synthetic='false'))
            for field, column in [('status_original', 'Etat d’autorisation'), ('status_normalized', 'Etat d’autorisation'), ('approval_date', 'Date de première autorisation'), ('withdrawal_date_original', 'Date de retrait du produit')]:
                ex.evidence('registration', rid, field, row.get(column, ''), 'produits_utf8.csv', line)
            for alias in sorted(set(a.strip() for a in row['seconds noms commerciaux'].split('|') if a.strip())):
                ex.write('product_aliases', dict(alias_id=f'A-FR-EPHY-{amm}-{digest(alias)[:24]}',
                    product_id=pid, alias_name=alias, country_code='FR', relationship_type='alternate_name',
                    evidence=f'{url} ; produits_utf8.csv ; AMM {amm} ; seconds noms commerciaux',
                    review_status='to_verify', is_synthetic='false'))
            for cline, condition in conditions[amm]:
                ex.raw_evidence('registration', rid, condition, 'produits_condition_emploi_utf8.csv', cline)
        if amms and set(amms) - products.keys():
            raise ValueError(f'Requested AMMs absent from PPP scope: {sorted(set(amms) - products.keys())}')
        seen = Counter()
        with (output / 'excluded_uses.jsonl').open('w', encoding='utf-8') as rejected:
            for line, row in enumerate(tables['produits_usages_utf8.csv'], 2):
                amm = row['numero AMM']
                if amm not in products:
                    continue
                # The target schema/view cannot distinguish withdrawn/provisional uses.
                reason = None
                if products[amm]['Etat d’autorisation'] != 'AUTORISE':
                    reason = 'parent_product_not_authorized'
                elif row['etat usage'] != 'Autorisé':
                    reason = 'use_not_unconditionally_authorized'
                if reason:
                    excluded[reason] += 1
                    rejected.write(json.dumps({'reason': reason, 'record': line, 'row': row}, ensure_ascii=False) + '\n')
                    continue
                canonical = json.dumps(row, sort_keys=True, ensure_ascii=False)
                hashed = digest(canonical)
                seen[hashed] += 1
                uid = f'U-FR-EPHY-{amm}-{hashed}-{seen[hashed]}'
                parts = row['identifiant usage'].split('*')
                crop = method = target = None
                if len(parts) == 3:
                    crop, method, target = parts
                elif len(parts) == 2:
                    crop = parts[0]
                    warnings.append({'context': uid, 'value': row['identifiant usage'], 'reason': 'Two-part use: crop retained; purpose not mapped to method or target'})
                else:
                    warnings.append({'context': uid, 'value': row['identifiant usage'], 'reason': 'Unparsed use description'})
                # Preserve original strings with source field labels, including BBCH,
                # buffer zones and decisions for which the target has no columns.
                restrictions = '\n'.join(f'{k}: {v}' for k, v in row.items() if k and v)
                for field in ['restrictions usage', 'restrictions usage libelle', 'mentions autorisees']:
                    if products[amm].get(field):
                        restrictions += '\nProduit - ' + field + ': ' + products[amm][field]
                for _, condition in conditions[amm]:
                    restrictions += '\n' + condition['catégorie de condition d’emploi'] + ': ' + condition['condition d’emploi libelle']
                result = dict(use_id=uid, registration_id=f'R-FR-EPHY-{amm}', crop_name_original=crop,
                    target_name_original=target, application_method=method, dose_unit_original=row['dose retenue unite'],
                    restrictions_original=restrictions, validation_status='automatically_extracted', is_synthetic='false')
                fields = {'dose_value': 'dose retenue', 'max_applications': "nombre max d'application",
                          'application_interval_days': 'intervalle minimum entre applications (jour)',
                          'phi_days': 'delai avant recolte jour'}
                for field, column in fields.items():
                    value = row.get(column, '')
                    result[field] = number(value, warnings, f'{uid}.{field}', field == 'max_applications')
                    ex.evidence('use', uid, field, value, 'produits_usages_utf8.csv', line)
                for field in ['crop_name_original', 'target_name_original', 'application_method']:
                    if result[field] is not None:
                        ex.evidence('use', uid, field, result[field], 'produits_usages_utf8.csv', line)
                ex.raw_evidence('use', uid, row, 'produits_usages_utf8.csv', line)
                ex.write('uses', result)
        report = {'scope': 'PPP products; only Autorisé uses of AUTORISE products enter uses.csv',
                  'counts': dict(ex.counts), 'excluded': dict(excluded), 'warnings': warnings,
                  'normalization': 'No inferred EPPO/species/unit mappings or numeric REI; provisional uses excluded.'}
        rows_read = sum(map(len, tables.values()))
        ex.write('collection_runs', dict(source_id=SOURCE, started_at=started, finished_at=now(),
            input_file=str((output / 'raw/fr_ephy.zip').resolve()), rows_read=rows_read,
            rows_written=sum(ex.counts.values()), status='success', notes=json.dumps(report, ensure_ascii=False)))
        return report
    finally:
        ex.close()


def loader(output, destination=None):
    # Explicit columns omit serial IDs so PostgreSQL assigns them. Single
    # transaction: a key collision rolls everything back, never silently merges.
    lines = ['\\set ON_ERROR_STOP on', 'BEGIN;']
    for table, fields in HEADERS.items():
        path = str(((destination or output) / (FILE_PREFIX + table + '.csv')).resolve())
        if any(c in path for c in "\n\r\\"):
            raise ValueError('Output path cannot contain backslashes or newlines')
        path = path.replace("'", "''")
        if table == 'source_registry':
            lines += ['CREATE TEMP TABLE incoming_source (LIKE source_registry INCLUDING DEFAULTS) ON COMMIT DROP;',
                f"\\copy incoming_source ({', '.join(fields)}) FROM '{path}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')",
                'INSERT INTO source_registry SELECT * FROM incoming_source ON CONFLICT (source_id) DO NOTHING;']
        else:
            lines.append(f"\\copy {table} ({', '.join(fields)}) FROM '{path}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')")
    lines += ['COMMIT;']
    (output / 'load.sql').write_text('\n'.join(lines) + '\n', encoding='utf-8')



def check_database(database_url):
    """Inspect the real server in a read-only transaction. Never load or alter data."""
    if not database_url:
        raise ValueError('Set DATABASE_URL before using --check-db')
    try:
        import psycopg
    except ImportError:
        raise RuntimeError('Install requirements.txt in your Python environment to use --check-db') from None
    # SQLAlchemy driver-qualified URLs are not accepted directly by libpq.
    dsn = database_url.replace('postgresql+psycopg://', 'postgresql://', 1)
    if not dsn.startswith(('postgresql://', 'postgres://')):
        raise ValueError('DATABASE_URL must be a PostgreSQL URL')
    try:
        with psycopg.connect(dsn, connect_timeout=10,
                             options='-c default_transaction_read_only=on -c statement_timeout=15000') as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT current_database(), current_user, current_schema(), version()')
                database, user, schema, version = cur.fetchone()
                cur.execute("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
                ssl_row = cur.fetchone()
                cur.execute("""SELECT table_name, column_name, data_type, is_nullable, column_default
                               FROM information_schema.columns
                               WHERE table_schema = %s AND table_name = ANY(%s)
                               ORDER BY table_name, ordinal_position""", (schema, list(HEADERS)))
                columns = {}
                for table, name, kind, nullable, default in cur.fetchall():
                    columns.setdefault(table, {})[name] = dict(type=kind, nullable=nullable, default=default)
                missing = {table: [name for name in expected if name not in columns.get(table, {})]
                           for table, expected in HEADERS.items()}
                missing = {table: fields for table, fields in missing.items() if fields}
                cur.execute("""SELECT c.relname, con.conname, pg_get_constraintdef(con.oid)
                               FROM pg_constraint con JOIN pg_class c ON c.oid = con.conrelid
                               JOIN pg_namespace n ON n.oid = c.relnamespace
                               WHERE n.nspname = %s AND c.relname = ANY(%s)
                               ORDER BY c.relname, con.conname""", (schema, list(HEADERS)))
                constraints = [dict(table=t, name=n, definition=d) for t, n, d in cur.fetchall()]
                return dict(connected=True, database=database, user=user, schema=schema,
                            server_version=version, ssl=bool(ssl_row and ssl_row[0]), read_only=True,
                            missing_columns=missing, columns=columns, constraints=constraints,
                            note='Metadata inspection only; no rows loaded or changed.')
    except psycopg.Error as exc:
        # Do not echo a DSN/password or raw server error to logs.
        state = getattr(exc, 'sqlstate', None) or 'connection_error'
        raise RuntimeError(f'Database check failed ({state}); check network access, credentials and server configuration') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New output directory (must not exist)')
    parser.add_argument('--zip', type=Path, help='Use a previously downloaded UTF-8 ZIP instead of downloading')
    parser.add_argument('--source-url', help='Exact original ZIP URL; required with --zip')
    parser.add_argument('--collected-at', help='Original timezone-aware collection timestamp; required with --zip')
    parser.add_argument('--amm', action='append', help='Restrict to AMM (repeatable); default all PPP products')
    parser.add_argument('--check-db', action='store_true', help='Read-only connection and schema check using DATABASE_URL; no export or loading')
    args = parser.parse_args()
    if args.check_db:
        if any((args.output, args.zip, args.source_url, args.collected_at, args.amm)):
            parser.error('--check-db cannot be combined with export options')
        try:
            result = check_database(os.environ.get('DATABASE_URL'))
        except (RuntimeError, ValueError) as exc:
            parser.exit(1, str(exc) + '\n')
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if args.output is None:
        parser.error('--output is required for CSV export')
    if args.zip and (not args.source_url or not args.collected_at):
        parser.error('--zip requires --source-url and --collected-at; replay must not invent provenance')
    if not args.zip and (args.source_url or args.collected_at):
        parser.error('--source-url/--collected-at are for offline --zip mode only')
    output = args.output.resolve()
    if output.exists():
        parser.error('Output already exists; choose a new directory to preserve previous runs')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.france-', dir=output.parent))
    started = now()
    try:
        raw = stage / 'raw'
        raw.mkdir()
        metadata = None
        if args.zip:
            collected = datetime.fromisoformat(args.collected_at.replace('Z', '+00:00'))
            if collected.tzinfo is None:
                raise ValueError('Collection timestamp must include timezone')
            collected = collected.astimezone(timezone.utc).isoformat()
            url = args.source_url
            if not url.startswith('https://'):
                raise ValueError('Source URL must be HTTPS')
            shutil.copyfile(args.zip, raw / 'fr_ephy.zip')
        else:
            payload = fetch(CATALOGUE)
            (raw / 'catalogue.json').write_bytes(payload)
            metadata = json.loads(payload)
            candidates = [r for r in metadata['resources'] if 'utf8' in r['url'].lower() and r['url'].lower().endswith('.zip')]
            if len(candidates) != 1:
                raise ValueError('Expected exactly one UTF-8 ZIP resource in catalogue')
            url = candidates[0]['url']
            (raw / 'fr_ephy.zip').write_bytes(fetch(url))
            collected = now()
        tables = read_tables(raw / 'fr_ephy.zip')
        report = convert(tables, stage, url, collected, started, args.amm)
        # Replace temporary staging path with final location in collection metadata.
        runfile = stage / (FILE_PREFIX + 'collection_runs.csv')
        runfile.write_text(runfile.read_text(encoding='utf-8').replace(str(stage), str(output)), encoding='utf-8')
        manifest = dict(source_id=SOURCE, source_url=url, collected_at=collected,
            csv_collected_at=collected,
            csv_timestamp_basis='Original source retrieval time',
            sha256=hashlib.sha256((raw / 'fr_ephy.zip').read_bytes()).hexdigest(),
            catalogue_last_update=metadata.get('last_update') if metadata else None,
            report=report)
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        from validate import validate
        validation = validate(stage)
        (stage / 'validation_report.json').write_text(json.dumps(validation, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        if validation['errors']:
            raise ValueError(f"CSV contract validation failed: {validation['errors']}")
        loader(stage, output)
        stage.rename(output)
        print(json.dumps({'output': str(output), 'counts': report['counts'], 'excluded': report['excluded'], 'warnings': len(report['warnings'])}, indent=2))
    except Exception:
        shutil.rmtree(stage)
        raise


if __name__ == '__main__':
    main()
