"""Flat CSV exchange contract shared by every source adapter (France, Canada, Germany...).

Pipeline:  adapter.fetch() -> adapter.to_canonical() -> CanonicalBundle -> validate -> CSV bundle -> loader -> DB

Rows are plain dicts whose keys are the column names below (same as data/*.csv and the DB).
"""
from __future__ import annotations
import csv
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

COLUMNS = {
    'products': 'product_id commercial_name active_entity_original active_entity_normalized formulation_code is_synthetic validation_status',
    'registrations': 'registration_id product_id country_code authority_name registration_number status_original status_normalized approval_date expiration_date source_id source_record_url collected_at validation_status is_synthetic',
    'uses': 'use_id registration_id crop_name_original crop_name_normalized eppo_crop_code target_name_original target_name_normalized eppo_target_code application_method dose_value dose_unit_original dose_unit_normalized max_applications application_interval_days phi_days rei_hours restrictions_original validation_status is_synthetic',
    # related_product_id: the exact product this alias describes (e.g. P-CA-32404). product_id is the pilot.
    'product_aliases': 'alias_id product_id related_product_id alias_name country_code relationship_type confidence evidence review_status is_synthetic',
    'source_registry': 'source_id official_name country_or_region base_url access_method data_format license_name access_and_reuse_limits manual_validation_required notes',
    'field_evidence': 'entity_type entity_id field_name value_original excerpt document_url page_number extraction_method model_name confidence validation_status collected_at',
    'collection_runs': 'source_id started_at finished_at input_file rows_read rows_written status notes',
}
COLUMNS = {name: columns.split() for name, columns in COLUMNS.items()}

PRIMARY_KEYS = {'products': 'product_id', 'registrations': 'registration_id', 'uses': 'use_id',
                'product_aliases': 'alias_id', 'source_registry': 'source_id'}

# ---------- allowed values (from data/field_dictionary.csv) ----------
VALIDATION_STATUS = {'automatically_extracted', 'to_verify', 'validated', 'rejected', 'obsolete', 'source_unavailable'}
REGISTRATION_STATUS = {'active', 'expired', 'withdrawn', 'pending', 'unknown'}
ALIAS_RELATIONSHIP = {'alternate_name', 'historical_name', 'sister_product_candidate', 'confirmed_sister_product'}
REQUIRED = {
    'products': ['product_id', 'commercial_name', 'is_synthetic', 'validation_status'],
    'registrations': ['registration_id', 'product_id', 'country_code', 'authority_name', 'status_normalized',
                      'source_id', 'source_record_url', 'collected_at', 'validation_status', 'is_synthetic'],
    'uses': ['use_id', 'registration_id', 'validation_status', 'is_synthetic'],
    'product_aliases': ['alias_id', 'product_id', 'alias_name', 'relationship_type', 'review_status', 'is_synthetic'],
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def _empty(v):
    return v is None or (isinstance(v, str) and not v.strip())


def _csv_value(v):
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    if isinstance(v, date):
        return v.isoformat()
    return v


@dataclass
class CanonicalBundle:
    products: list = field(default_factory=list)
    registrations: list = field(default_factory=list)
    uses: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    product_aliases: list = field(default_factory=list)
    source_registry: list = field(default_factory=list)
    field_evidence: list = field(default_factory=list)
    collection_runs: list = field(default_factory=list)

    def merge(self, other):
        result = CanonicalBundle(**{f.name: getattr(self, f.name) + getattr(other, f.name) for f in fields(self)})
        # Identical rows (e.g. the same pilot product emitted by two adapters) are kept once;
        # same ID with DIFFERENT content is a real identity conflict and must be reconciled explicitly.
        for table, key in PRIMARY_KEYS.items():
            seen = {}
            for row in getattr(result, table):
                prev = seen.get(row[key])
                if prev is not None and {k: _csv_value(v) for k, v in prev.items()} != {k: _csv_value(v) for k, v in row.items()}:
                    raise ValueError(f'Conflicting {table} rows for {key}={row[key]}; reconcile identities explicitly before merging')
                seen.setdefault(row[key], row)
            setattr(result, table, list(seen.values()))
        return result

    def validate(self):
        """Return a list of problems (empty list = valid). Catches errors at the source, before the DB."""
        errors = []
        for table, required in REQUIRED.items():
            for i, row in enumerate(getattr(self, table)):
                where = f'{table}[{i}] {row.get(PRIMARY_KEYS[table], "?")}'
                unknown = set(row) - set(COLUMNS[table])
                if unknown:
                    errors.append(f'{where}: unknown columns {sorted(unknown)}')
                for col in required:
                    if _empty(row.get(col)):
                        errors.append(f'{where}: missing {col}')
                vs = row.get('validation_status')
                if not _empty(vs) and vs not in VALIDATION_STATUS:
                    errors.append(f'{where}: validation_status {vs!r} not in {sorted(VALIDATION_STATUS)}')
                if not _empty(row.get('is_synthetic')) and _csv_value(row['is_synthetic']) not in ('true', 'false'):
                    errors.append(f'{where}: is_synthetic must be true/false')
                cc = row.get('country_code')
                if not _empty(cc) and not re.fullmatch(r'[A-Z]{2}', str(cc)):
                    errors.append(f'{where}: country_code {cc!r} must be 2 uppercase letters')
        for i, r in enumerate(self.registrations):
            where = f'registrations[{i}] {r.get("registration_id", "?")}'
            if r.get('status_normalized') not in REGISTRATION_STATUS:
                errors.append(f'{where}: status_normalized {r.get("status_normalized")!r} not in {sorted(REGISTRATION_STATUS)}')
            if urlparse(str(r.get('source_record_url') or '')).scheme not in ('http', 'https'):
                errors.append(f'{where}: source_record_url must be an http(s) URL')
            for col in ('approval_date', 'expiration_date'):
                if not _empty(r.get(col)):
                    try:
                        date.fromisoformat(_csv_value(r[col]))
                    except ValueError:
                        errors.append(f'{where}: {col} {r[col]!r} must be YYYY-MM-DD')
            if not _empty(r.get('collected_at')):
                try:
                    datetime.fromisoformat(_csv_value(r['collected_at']).replace('Z', '+00:00'))
                except ValueError:
                    errors.append(f'{where}: collected_at {r["collected_at"]!r} must be ISO 8601')
        for i, a in enumerate(self.product_aliases):
            if a.get('relationship_type') not in ALIAS_RELATIONSHIP:
                errors.append(f'product_aliases[{i}] {a.get("alias_id")}: relationship_type {a.get("relationship_type")!r} not in {sorted(ALIAS_RELATIONSHIP)}')
        # references inside the bundle (pilot products P-LPC-* live in the DB seed, so they are allowed)
        products = {p['product_id'] for p in self.products}
        regs = {r['registration_id'] for r in self.registrations}
        for r in self.registrations:
            if r['product_id'] not in products and not str(r['product_id']).startswith('P-LPC-'):
                errors.append(f'registrations {r["registration_id"]}: product {r["product_id"]} not in bundle or pilot list')
        for u in self.uses:
            if u['registration_id'] not in regs:
                errors.append(f'uses {u["use_id"]}: registration {u["registration_id"]} not in bundle')
        return errors

    def write_csv(self, outdir, prefix='', validate=True):
        if validate:
            errors = self.validate()
            if errors:
                raise ValueError('Bundle is invalid:\n- ' + '\n- '.join(errors[:30]) +
                                 (f'\n... and {len(errors) - 30} more' if len(errors) > 30 else ''))
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        for name, columns in COLUMNS.items():
            with (outdir / f'{prefix}{name}.csv').open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows({k: _csv_value(v) for k, v in row.items()} for row in getattr(self, name))
        (outdir / f'{prefix}warnings.json').write_text(json.dumps(self.warnings, indent=2, ensure_ascii=False), encoding='utf-8')

    @classmethod
    def read_csv(cls, indir, prefix=''):
        """Load a bundle written by write_csv (e.g. produced by another teammate's importer)."""
        indir = Path(indir)
        bundle = cls()
        for name in COLUMNS:
            path = indir / f'{prefix}{name}.csv'
            if path.exists():
                with path.open(encoding='utf-8-sig', newline='') as f:
                    setattr(bundle, name, [{k: (v if v != '' else None) for k, v in r.items()} for r in csv.DictReader(f)])
        w = indir / f'{prefix}warnings.json'
        if w.exists():
            bundle.warnings = json.loads(w.read_text(encoding='utf-8'))
        return bundle


# ---------- shared normalization: every adapter uses the same rules ----------
def norm(s):
    return re.sub(r'\s+', ' ', (s or '').strip()).lower()


class ReferenceData:
    """LPC mappings: microorganism synonyms, product names, EPPO crops and pests."""

    def __init__(self, entities, names, crops, pests):
        self.entities = list(entities)
        self.names = {norm(r['name_variant']): r for r in names}
        self.crops = self._eppo_index(crops)
        self.pests = self._eppo_index(pests)

    @classmethod
    def from_csv(cls, data_dir='data'):
        """Works without a database: reads the starter mapping CSVs."""
        d = Path(data_dir)
        def rows(name):
            with (d / name).open(encoding='utf-8-sig', newline='') as f:
                return list(csv.DictReader(f))
        return cls(rows('active_entity_mapping.csv'), rows('product_name_mapping.csv'),
                   rows('eppo_crop_mapping.csv'), rows('eppo_pest_mapping.csv'))

    @staticmethod
    def _eppo_index(rows):
        idx = {}
        for r in rows:
            keys = [r['name_original'], r['name_normalized'], r['scientific_name']]
            keys += [a.split(':', 1)[-1] for a in (r['multilingual_aliases'] or '').split('|')]
            for k in keys:
                if k and k.strip():
                    idx[norm(k)] = r
        return idx

    def match_entity(self, active_text):
        """(mapping_row, strain_matches) for a known microorganism in the text, else (None, False).
        Prefers the row whose strain also matches (e.g. F52 -> AE-006 rather than Ma 43 -> AE-005).
        Also matches former names, e.g. 'Gliocladium catenulatum' -> Clonostachys rosea."""
        t = norm(active_text)
        fallback = None
        for e in sorted(self.entities, key=lambda e: e['mapping_id']):
            species = ' '.join(e['name_variant'].split()[:2]).lower()
            if species in t:
                strain = norm(e['strain'])
                if strain and strain in t:
                    return e, True          # species AND strain match: best possible row
                fallback = fallback or e    # species only: keep the first as a fallback
        return fallback, False

    def _eppo(self, text, idx):
        t = norm(text)
        candidates = [t, t.rstrip('s'), re.sub(r'ies$', 'y', t)]
        candidates += [norm(m) for m in re.findall(r'\(([^)]+)\)', text or '')]   # 'GREY MOULD (BOTRYTIS CINEREA)'
        return next((idx[c] for c in candidates if c in idx), None)

    def crop(self, text):
        return self._eppo(text, self.crops)

    def pest(self, text):
        return self._eppo(text, self.pests)


class BaseAdapter(ABC):
    source_id: str = ''

    @abstractmethod
    def fetch(self): ...

    @abstractmethod
    def to_canonical(self, raw): ...

    def run(self, input_path=None):
        """input_path: optional frozen extract. Adapters whose fetch() takes no argument keep working."""
        raw = self.fetch(input_path) if input_path is not None else self.fetch()
        return self.to_canonical(raw)
    
def project_root() -> Path:
    """The repository root: the folder that contains .git (fallback: first parent with data/ and .env)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / '.git').exists():
            return parent
    for parent in here.parents:
        if (parent / 'data').is_dir() and (parent / '.env').exists():
            return parent
    raise RuntimeError(f'Could not find the project root above {here}')