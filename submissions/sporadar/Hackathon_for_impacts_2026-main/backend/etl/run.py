"""ETL entry point: run a source adapter, or load a bundle produced by a teammate.

Run from the repository root:
  python -m etl.run canada                              # live download -> bundle -> DB
  python -m etl.run canada --input data/raw/canada/product_en.csv
  python -m etl.run canada --no-db                      # only write the CSV bundle (no database needed)
  python -m etl.run canada --scope agri                 # + competitors: all current agricultural products
  python -m etl.run load data/bundles/france            # load an existing bundle into the DB
  add --export-csv to refresh data/*.csv from the DB afterwards
Pressing Run on this file (no arguments) runs Canada from the frozen extract.
"""
import argparse
import sys
from pathlib import Path

if __package__ in (None, ''):
    # Started as a plain file (e.g. the editor's Run/Debug button): make the package imports work.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # folder that contains etl/
    __package__ = 'etl'
    import etl  # noqa: F401

from .adapters.base import CanonicalBundle, project_root
from .adapters.canada.canada import CanadaAdapter
from .adapters.canada import loader   # shared DB loader (works for every source's bundle)

ROOT = project_root()
BUNDLES = ROOT / 'data' / 'bundles'
DEFAULT_INPUT = {'canada': ROOT / 'data' / 'raw' / 'canada' / 'product_en.csv'}

# Add new sources here, e.g.:
#   from .adapters.germany.germany import GermanyAdapter   ->   'germany': GermanyAdapter
# Each adapter takes the shared ReferenceData in its constructor.
ADAPTERS = {'canada': CanadaAdapter}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source', nargs='?', default='canada', choices=sorted(ADAPTERS) + ['load'])
    ap.add_argument('bundle_dir', nargs='?', type=Path, help="with 'load': folder of an existing bundle")
    ap.add_argument('--input', type=Path, help='Frozen extract instead of live download')
    ap.add_argument('--no-db', action='store_true', help='Only write the CSV bundle')
    ap.add_argument('--scope', default='pilots', choices=['pilots', 'agri', 'agri_history', 'current', 'all'],
                    help='Canada only: which products to load (default: pilots = LPC products only)')
    ap.add_argument('--export-csv', action='store_true', help='Rewrite data/*.csv from the database')
    args = ap.parse_args()

    if args.source == 'load':
        if not args.bundle_dir:
            ap.error("'load' needs a bundle folder, e.g. data/bundles/france")
        bundle = CanonicalBundle.read_csv(args.bundle_dir)
        label = str(args.bundle_dir)
    else:
        if len(sys.argv) == 1 and DEFAULT_INPUT[args.source].exists():
            args.input = DEFAULT_INPUT[args.source]
            print(f'No arguments given: using frozen extract {args.input}')
        if args.no_db:
            refs = loader.load_references(None)
        else:
            with loader.connect() as conn:
                refs = loader.load_references(conn)
        options = {'scope': args.scope} if args.source == 'canada' else {}
        bundle = ADAPTERS[args.source](refs, **options).run(args.input)
        out = BUNDLES / args.source
        bundle.write_csv(out)            # validates first; raises with the list of problems
        label = args.source
        print(f'[{label}] bundle written to {out.relative_to(ROOT)}: {len(bundle.registrations)} registrations, '
              f'{len(bundle.products)} new products, {len(bundle.uses)} uses, {len(bundle.product_aliases)} aliases')

    for w in bundle.warnings:
        print('  WARNING:', w)
    if args.no_db:
        return
    for c in loader.load_bundle(bundle):
        print('  CHANGE:', c)
    print(f'[{label}] loaded into the database')
    if args.export_csv:
        loader.export_csv()
        print('  data/*.csv refreshed from the database')


if __name__ == '__main__':
    main()