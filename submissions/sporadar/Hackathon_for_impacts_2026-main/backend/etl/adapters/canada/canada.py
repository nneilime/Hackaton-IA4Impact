"""Health Canada PPID adapter -> CanonicalBundle (owner: Dyland).

Scopes (which products of the Canada file are loaded):
  pilots   LPC products only: microorganism listed in active_entity_mapping (default)
  agri     pilots + every CURRENT, COMMERCIAL product for agriculture (crops, greenhouse, turf, forest...)
           -> brings in competitors such as SERENADE, BOTANIGARD (~2,170 products)
  current  pilots + every current commercial/restricted product, any use (~3,800)
  agri_history  agri + HISTORICAL (no longer registered) commercial agricultural products, as withdrawn,
           with their end date (PPID 'Expiry date') -> withdrawn products per crop x pest (~980 more)
  all      every end-use product ever registered, cancelled ones included (status = withdrawn)
Technical actives / manufacturing concentrates are always skipped (raw ingredients, not sold to farmers).
"""
import csv, io, urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from ..base import BaseAdapter, CanonicalBundle, ReferenceData, norm, project_root, utcnow

ROOT = project_root()
API_URL = 'https://pest-control.canada.ca/pesticide-registry-api/api/extract/product?lang=en'
RECORD_URL = 'https://pest-control.canada.ca/pesticide-registry-api/api/extract/product/{}?lang=en'
AUTHORITY = 'Health Canada - Pest Management Regulatory Agency (PMRA)'
NON_END_USE = {'TECHNICAL ACTIVE', 'MANUFACTURING CONCENTRATE'}   # raw ingredients, not products farmers buy
ACTIVE_STATUSES = {'FULL REGISTRATION', 'TEMPORARY PRODUCT', 'EMERGENCY REGISTRATION', 'LIMITED TERM PRODUCT'}
SCOPES = ('pilots', 'agri', 'agri_history', 'current', 'all')
# Use Site Category values that mean agriculture / horticulture / forestry (e.g. '5-GREENHOUSE FOOD CROPS')
AGRI_SITE_WORDS = ('FOOD CROPS', 'FEED CROPS', 'GREENHOUSE', 'OIL SEED', 'ORNAMENTAL', 'TURF', 'FOREST')
USE_NOTE = ('Product-level list from Health Canada PPID; crop-target pairing, dose and '
            'conditions must come from the official label')


def _decode(raw: bytes) -> str:
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('latin-1')   # PPID extracts observed as ISO-8859-1


class CanadaAdapter(BaseAdapter):
    source_id = 'CA-PPID'

    def __init__(self, refs: ReferenceData, include_technical: bool = False, scope: str = 'pilots'):
        if scope not in SCOPES:
            raise ValueError(f'scope must be one of {SCOPES}')
        self.refs = refs
        self.include_technical = include_technical
        self.scope = scope

    def _in_scope(self, row):
        """Non-LPC products: does this row belong to the chosen scope?"""
        if self.scope == 'all':
            return True
        current = row['Current / Historical'].strip().lower() == 'current'
        commercial = row['Marketing type'].strip().upper() in ('COMMERCIAL', 'RESTRICTED')
        if self.scope == 'current':
            return current and commercial
        if self.scope in ('agri', 'agri_history'):
            sites = row['Use Site Category'].upper()
            agri = commercial and any(w in sites for w in AGRI_SITE_WORDS)
            return agri and (current or self.scope == 'agri_history')
        return False   # 'pilots': only LPC microorganisms

    # ---------- fetch ----------
    def fetch(self, input_path=None):
        started = utcnow()
        if input_path:
            path = Path(input_path)
            return {'text': _decode(path.read_bytes()), 'started_at': started, 'input_file': str(path),
                    'collected_at': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)}
        with urllib.request.urlopen(API_URL, timeout=120) as resp:
            text = _decode(resp.read())
        now = datetime.now(timezone.utc)
        raw_dir = ROOT / 'data' / 'raw' / 'canada'
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / f'product_en_{now:%Y%m%dT%H%M%SZ}.csv'
        raw_file.write_text(text, encoding='utf-8')          # evidence of what was collected
        return {'text': text, 'started_at': started, 'input_file': str(raw_file), 'collected_at': now}

    # ---------- transform ----------
    @staticmethod
    def _status(row, today):
        status = row['Registration Status'].strip().upper()
        if status == 'CANCELLED' or row['Current / Historical'].strip().lower() == 'historical':
            return 'withdrawn'
        exp = row['Expiry date'].strip()
        if exp and exp < today.isoformat():
            return 'expired'
        if status in ACTIVE_STATUSES:
            return 'active'
        return 'unknown'   # e.g. Phase-Out; exact wording stays in status_original

    @staticmethod
    def _status_original(row):
        """Both PPID fields, verbatim: e.g. 'Cancelled | Historical', 'Full Registration | Current'."""
        parts = [row['Registration Status'].strip(), row['Current / Historical'].strip()]
        return ' | '.join(p for p in parts if p) or None

    @staticmethod
    def _split(s):
        return [x.strip() for x in (s or '').split(';') if x.strip()]

    def to_canonical(self, raw):
        refs, today = self.refs, date.today()
        rows = list(csv.DictReader(io.StringIO(raw['text'])))
        b = CanonicalBundle()

        for row in rows:
            if row['Marketing type'].strip().upper() in NON_END_USE and not self.include_technical:
                continue
            entity, strain_match = refs.match_entity(row['Active ingredients - English'])
            if not entity and not self._in_scope(row):
                continue

            regno = row['Registration number'].strip()
            name = row['Product name - English'].strip()
            mapped = refs.names.get(norm(name)) if entity else None

            if not entity:
                # Not an LPC microorganism (e.g. a competitor): plain product, NO link to any LPC product.
                product_id = f'P-CA-{regno}'
                b.products.append({
                    'product_id': product_id, 'commercial_name': name,
                    'active_entity_original': row['Active ingredients - English'].strip() or None,
                    'active_entity_normalized': None,   # not in LPC's mapping: never guessed
                    'formulation_code': None, 'is_synthetic': False,
                    'validation_status': 'automatically_extracted'})
            # Only an exact canonical-name match joins a pilot product; anything else is its own product.
            elif mapped and mapped['relationship_type'] == 'canonical_name':
                product_id = mapped['product_id']
            else:
                product_id = f'P-CA-{regno}'
                b.products.append({
                    'product_id': product_id, 'commercial_name': name,
                    'active_entity_original': row['Active ingredients - English'].strip(),
                    'active_entity_normalized': entity['canonical_species'], 'formulation_code': None,
                    'is_synthetic': False, 'validation_status': 'automatically_extracted'})
                b.product_aliases.append(self._alias(regno, name, product_id, entity, strain_match, mapped))

            if not entity:
                pass
            elif not strain_match:
                b.warnings.append(f'{name} ({regno}): strain in source differs from LPC canonical strain - check equivalence')
            elif entity['review_status'] != 'validated':
                b.warnings.append(f"{name} ({regno}): matched via {entity['name_variant']} "
                                  f"({entity['mapping_id']}, {entity['review_status']} in LPC mapping)")

            reg_id = f'R-CA-{regno}'
            status = self._status(row, today)
            exp = row['Expiry date'].strip() or None
            b.registrations.append({
                'registration_id': reg_id, 'product_id': product_id, 'country_code': 'CA',
                'authority_name': AUTHORITY, 'registration_number': regno,
                'status_original': self._status_original(row), 'status_normalized': status,
                'approval_date': row['Date first registered'].strip() or None, 'expiration_date': exp,
                'source_id': self.source_id, 'source_record_url': RECORD_URL.format(regno),
                'collected_at': raw['collected_at'], 'validation_status': 'automatically_extracted',
                'is_synthetic': False})
            if entity and status == 'active' and exp and (date.fromisoformat(exp) - today).days <= 365:
                b.warnings.append(f'{name} ({regno}): registration expires {exp} (within 12 months)')

            # PPID lists crops and pests separately at product level: never cross-multiply them.
            for i, crop in enumerate(self._split(row['Sites of Use']), 1):
                m = refs.crop(crop)
                b.uses.append(self._use(f'U-CA-{regno}-C{i:02d}', reg_id,
                                        crop_name_original=crop,
                                        crop_name_normalized=m['name_normalized'] if m else None,
                                        eppo_crop_code=m['eppo_code'] if m else None))
            for i, pest in enumerate(self._split(row['Pests']), 1):
                m = refs.pest(pest)
                b.uses.append(self._use(f'U-CA-{regno}-T{i:02d}', reg_id,
                                        target_name_original=pest,
                                        target_name_normalized=m['name_normalized'] if m else None,
                                        eppo_target_code=m['eppo_code'] if m else None))

        b.collection_runs.append({
            'source_id': self.source_id, 'started_at': raw['started_at'], 'finished_at': utcnow(),
            'input_file': raw['input_file'], 'rows_read': len(rows), 'rows_written': len(b.registrations),
            'status': 'success', 'notes': None})
        return b

    @staticmethod
    def _use(use_id, reg_id, **values):
        row = {c: None for c in ('crop_name_original', 'crop_name_normalized', 'eppo_crop_code',
                                 'target_name_original', 'target_name_normalized', 'eppo_target_code',
                                 'application_method', 'dose_value', 'dose_unit_original', 'dose_unit_normalized',
                                 'max_applications', 'application_interval_days', 'phi_days', 'rei_hours')}
        row.update(values)
        row.update({'use_id': use_id, 'registration_id': reg_id, 'restrictions_original': USE_NOTE,
                    'validation_status': 'to_verify', 'is_synthetic': False})
        return row

    @staticmethod
    def _alias(regno, name, product_id, entity, strain_match, mapped):
        base = {'alias_id': f'AL-CA-{regno}', 'product_id': entity['product_id'],
                'related_product_id': product_id, 'alias_name': name, 'country_code': 'CA', 'is_synthetic': False}
        if mapped and mapped['review_status'] == 'validated':
            return {**base, 'relationship_type': 'confirmed_sister_product',
                    'confidence': float(mapped['confidence_score']), 'review_status': 'validated',
                    'evidence': f"LPC product_name_mapping {mapped['mapping_id']}: {mapped['evidence_summary']}"}
        evidence = (f"Same active entity ({entity['canonical_species']}"
                    f"{', same strain' if strain_match else ', strain not confirmed'}) in Health Canada PPID reg. {regno}")
        if mapped:
            evidence += f"; also listed in LPC product_name_mapping {mapped['mapping_id']}"
        return {**base, 'relationship_type': 'sister_product_candidate',
                'confidence': float(mapped['confidence_score']) if mapped else (0.80 if strain_match else 0.50),
                'review_status': 'to_verify', 'evidence': evidence}