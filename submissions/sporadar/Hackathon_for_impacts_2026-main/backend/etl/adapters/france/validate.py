#!/usr/bin/env python3
"""Check only the five requested submission rules, without database access."""
import argparse
import csv
import json
from pathlib import Path

FILE_PREFIX = 'fr_'


def validate(directory):
    directory = Path(directory)
    csv.field_size_limit(16 * 1024 * 1024)
    errors, counts = [], {}
    for table in ('products', 'registrations', 'uses'):
        path = directory / (FILE_PREFIX + table + '.csv')
        def error(record, field, value, message, key=None):
            errors.append(dict(file=path.name, csv_record=record, entity_id=key,
                               field=field, value=value, error=message))
        if not path.exists():
            error(0, '*', None, 'Required input file is missing')
            continue
        fields = ['validation_status']
        if table == 'registrations':
            fields += ['authority_name', 'status_normalized', 'source_record_url', 'country_code']
        count = 0
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            for field in fields:
                if field not in (reader.fieldnames or []):
                    error(1, field, None, 'Required rule column is missing')
            for record, row in enumerate(reader, 2):
                count += 1
                key = row.get({'products': 'product_id', 'registrations': 'registration_id', 'uses': 'use_id'}[table])
                if None in row or any(v is None for v in row.values()):
                    error(record, '*', None, 'Malformed CSV record; cannot check rules', key)
                    continue
                def reject(field, message):
                    error(record, field, row.get(field), message, key)
                if row.get('validation_status') != 'automatically_extracted':
                    reject('validation_status', 'Must be automatically_extracted')
                if table == 'registrations':
                    if not row.get('authority_name', '').strip():
                        reject('authority_name', 'Must always be filled')
                    if row.get('status_normalized') not in {'active', 'expired', 'withdrawn', 'pending', 'unknown'}:
                        reject('status_normalized', 'Must be active, expired, withdrawn, pending or unknown')
                    if not row.get('source_record_url', '').startswith('https://'):
                        reject('source_record_url', 'Required and must start with https://')
                    if row.get('country_code') not in {'CA', 'FR', 'DE'}:
                        reject('country_code', 'Must be CA, FR or DE')
        counts[table] = count
    return dict(contract='Only the five latest user-requested submission rules',
                counts=counts, rejected_rows=len({(e['file'], e['csv_record']) for e in errors}),
                errors=errors, valid=not errors,
                scope='Not a full SQL schema, foreign-key, date, boolean or normalization audit. No database connection.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', nargs='?', type=Path, default=Path('data/incoming'))
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = validate(args.directory)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report['valid'] else 1)


if __name__ == '__main__':
    main()
