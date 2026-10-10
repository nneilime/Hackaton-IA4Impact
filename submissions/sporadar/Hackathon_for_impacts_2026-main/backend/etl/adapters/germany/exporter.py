#!/usr/bin/env python3
"""Export Germany observations and initial-import SQL; does not connect to a DB."""
import argparse
import csv
import json
import tempfile
from pathlib import Path
from bvl import GermanyBVLAdapter
from bvl.export import validate, flat_loader, regulatory_loader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', type=Path, help='Replay directory with manifest.json and unchanged response files')
    parser.add_argument('--out', type=Path, default=Path('out/de-export'), help='New output directory; must not exist')
    parser.add_argument('--names', type=Path, help='Optional name candidates; never merges product identities')
    parser.add_argument('--registration', action='append', help='BVL registration number, repeatable (default: all)')
    parser.add_argument('--max-pages', type=int, default=2000)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Output directory already exists; use a new directory to preserve earlier evidence')
    pilot = {}
    if args.names:
        with args.names.open(encoding='utf-8-sig', newline='') as f:
            pilot = {r['name_variant']: r for r in csv.DictReader(f)}
    adapter = GermanyBVLAdapter(offline_dir=args.offline, pilot_names=pilot,
        registrations=args.registration, max_pages=args.max_pages)
    print(json.dumps(export(adapter, args.out), indent=2))


def export(adapter, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output directory already exists; choose a new directory')
    raw = adapter.fetch()
    bundle = adapter.to_canonical(raw)
    report = validate(bundle)
    if not report['valid']:
        raise ValueError(report['errors'])
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.de-staging-', dir=output.parent) as staging:
        staging = Path(staging)
        bundle.write_csv(staging, 'de_')
        adapter.write_snapshots(staging)
        flat_loader(staging)
        regulatory_loader(staging, bundle, adapter)
        (staging / 'validation_report.json').write_text(json.dumps(report, indent=2))
        staging.rename(output)
    return dict(output=str(output.resolve()), **report)


if __name__ == '__main__':
    main()
