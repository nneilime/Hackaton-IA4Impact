"""Flat CSV exchange contract, matching the current France importer."""
from __future__ import annotations
import csv
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path

COLUMNS = {
    'products': 'product_id commercial_name active_entity_original active_entity_normalized formulation_code is_synthetic validation_status',
    'registrations': 'registration_id product_id country_code authority_name registration_number status_original status_normalized approval_date expiration_date source_id source_record_url collected_at validation_status is_synthetic',
    'uses': 'use_id registration_id crop_name_original crop_name_normalized eppo_crop_code target_name_original target_name_normalized eppo_target_code application_method dose_value dose_unit_original dose_unit_normalized max_applications application_interval_days phi_days rei_hours restrictions_original validation_status is_synthetic',
    'product_aliases': 'alias_id product_id alias_name country_code relationship_type confidence evidence review_status is_synthetic',
    'source_registry': 'source_id official_name country_or_region base_url access_method data_format license_name access_and_reuse_limits manual_validation_required notes',
    'field_evidence': 'entity_type entity_id field_name value_original excerpt document_url page_number extraction_method model_name confidence validation_status collected_at',
    'collection_runs': 'source_id started_at finished_at input_file rows_read rows_written status notes',
}
COLUMNS = {name: columns.split() for name, columns in COLUMNS.items()}

def utcnow():
    return datetime.now(timezone.utc).isoformat()

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
        for table, key in [('products', 'product_id'), ('registrations', 'registration_id'), ('uses', 'use_id')]:
            ids = [r[key] for r in getattr(result, table)]
            if len(ids) != len(set(ids)):
                raise ValueError(f'Duplicate {key}; reconcile identities explicitly before merging')
        sources = {}
        for row in result.source_registry:
            if row['source_id'] in sources and row != sources[row['source_id']]:
                raise ValueError('Conflicting source registry rows')
            sources[row['source_id']] = row
        result.source_registry = list(sources.values())
        return result

    def write_csv(self, outdir, prefix=''):
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        for name, columns in COLUMNS.items():
            with (outdir / f'{prefix}{name}.csv').open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(getattr(self, name))
        (outdir / f'{prefix}warnings.json').write_text(json.dumps(self.warnings, indent=2, ensure_ascii=False), encoding='utf-8')

class BaseAdapter(ABC):
    @abstractmethod
    def fetch(self): ...
    @abstractmethod
    def to_canonical(self, raw): ...
    def run(self):
        return self.to_canonical(self.fetch())
