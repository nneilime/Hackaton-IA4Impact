"""BVL API observations -> evidence-backed CSV exchange records.

No name-based identity merges, inferred authorization or automatic publication.
See README for the explicitly bounded source coverage and replay format.
"""
from __future__ import annotations
import hashlib
import itertools
import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo
from .base import BaseAdapter, CanonicalBundle, utcnow

BASE = os.environ.get('BVL_API_BASE', 'https://psm-api.bvl.bund.de/ords/psm/api-v1').rstrip('/')
HEADERS = {'Accept': 'application/json', 'User-Agent': 'LPC-hackathon-adapter/0.2'}
ENDPOINTS = {n: n for n in ('mittel', 'awg', 'wirkstoff', 'wirkstoff_gehalt', 'awg_kultur', 'awg_schadorg', 'awg_aufwand', 'awg_wartezeit', 'awg_zeitpunkt', 'auflagen', 'kode')}
FIELD_ALIASES = {
    'reg_no': ['kennr', 'zulassungsnummer', 'kenn_nr'],
    'name': ['mittelname', 'name', 'handelsname', 'bezeichnung'],
    'status': ['zulassungsstatus', 'status', 'zul_status'],
    'approval': ['zul_erstmalig_am', 'zulassungsbeginn', 'zul_beginn', 'zulassung_ab'],
    'expiry': ['zul_ende', 'zulassungsende', 'ende_zulassung'],
    'formulation': ['formulierung_art', 'formulierung', 'formulierungscode', 'form'],
    'active': ['wirkstoffe', 'wirkstoff', 'wirkstoff_name'],
    'crop': ['kultur', 'kultur_text', 'kulturname'],
    'target': ['schadorganismus', 'schadorg', 'schadorganismus_text'],
    'dose': ['m_aufwand', 'aufwandmenge', 'aufwand', 'dosis'],
    'dose_unit': ['m_aufwand_einheit', 'aufwandmenge_einheit', 'einheit', 'aufwand_einheit'],
    'max_apps': ['anwendungen_max_je_vegetation', 'max_anwendungen', 'anwendungen_max', 'anzahl_anwendungen'],
    'interval': ['abstand_tage', 'intervall', 'anwendungsabstand'],
    'phi': ['gesetzt_wartezeit', 'wartezeit', 'wartezeit_tage', 'wz'],
    'method': ['anwendungstechnik', 'ausbringung', 'verfahren'],
    'restr': ['auflagen', 'bemerkung', 'anwendungsbestimmungen'],
    'link_reg': ['kennr', 'mittel_kennr', 'kenn_nr'],
}
STATUS_MAP = {
    'zugelassen': 'active', 'genehmigt': 'active', 'gültig': 'active', 'gueltig': 'active',
    'abgelaufen': 'expired', 'ausgelaufen': 'expired',
    'widerrufen': 'withdrawn', 'beendet': 'withdrawn', 'zulassung beendet': 'withdrawn',
    'zurückgenommen': 'withdrawn', 'zurueckgenommen': 'withdrawn', 'aufgehoben': 'withdrawn',
    'beantragt': 'pending',
}
UNIT_MAP = {'l/ha': 'L/ha', 'kg/ha': 'kg/ha', 'g/ha': 'g/ha', 'ml/ha': 'mL/ha', 'l/m²': 'L/m2', 'kg/m²': 'kg/m2'}
VERSION = 'de-bvl/0.2'

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))

def digest(value):
    # Oracle physical row locators are not logical record identity.
    def logical(item):
        if isinstance(item, dict):
            return {k: logical(v) for k, v in item.items() if k != 'm_row$$'}
        if isinstance(item, list):
            return [logical(v) for v in item]
        return item
    return hashlib.sha256(canonical(logical(value)).encode()).hexdigest()

def original(value):
    return value if isinstance(value, str) else canonical(value)

def pick(rec, concept):
    low = {k.lower(): v for k, v in rec.items()}
    return next((low[k] for k in FIELD_ALIASES[concept] if low.get(k) not in (None, '')), None)

def norm_status(value):
    return STATUS_MAP.get(str(value).strip().casefold(), 'unknown')

def timestamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Retrieval timestamps must include a timezone')
    return dt

def norm_date(value):
    if not value:
        return None
    text = str(value)
    try:
        if 'T' in text:
            # BVL serializes German local date boundaries as UTC instants.
            return timestamp(text).astimezone(ZoneInfo('Europe/Berlin')).date().isoformat()
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
            return datetime.strptime(text, '%Y-%m-%d').date().isoformat()
        return datetime.strptime(text, '%d.%m.%Y').date().isoformat()
    except (ValueError, TypeError):
        return None

def number(value, integer=False):
    if value in (None, ''):
        return None
    try:
        val = Decimal(str(value).strip().replace(',', '.'))
        if not val.is_finite() or val < 0 or (integer and val != val.to_integral_value()):
            return None
        return str(int(val)) if integer else format(val, 'f')
    except InvalidOperation:
        return None

def to_float(value):
    val = number(value)
    return float(val) if val is not None else None

class IncompleteCollection(ValueError):
    pass

class GermanyBVLAdapter(BaseAdapter):
    country_code, source_id = 'DE', 'DE-BVL'
    authority = 'BVL (Bundesamt für Verbraucherschutz und Lebensmittelsicherheit)'

    def __init__(self, offline_dir=None, pilot_names=None, page_size=500, max_pages=2000,
                 pause=0.2, registrations=None, compact_evidence=False):
        self.offline_dir = Path(offline_dir) if offline_dir else None
        self.compact_evidence = compact_evidence
        self.pilot = pilot_names or {}  # Suggestions only; never canonical identity.
        self.page_size, self.max_pages, self.pause = page_size, max_pages, pause
        if page_size < 1 or max_pages < 1 or pause < 0:
            raise ValueError('Invalid pagination settings')
        if urllib.parse.urlparse(BASE).scheme != 'https':
            raise ValueError('BVL_API_BASE must use HTTPS')
        self.registrations = set(registrations or [])
        self.pages, self.locations, self.source_rows = [], {}, {}
        self.warnings, self.synthetic, self.started_at = [], False, utcnow()
        self.scope = dict(registrations=sorted(self.registrations), collections=list(ENDPOINTS))

    def _get(self, url):
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(request, timeout=60) as response:
                    return response.read()
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    def _record_page(self, name, body, url, collected, filename=None):
        timestamp(collected)
        if urllib.parse.urlparse(url).scheme != 'https':
            raise ValueError('Snapshot source_url must use HTTPS')
        data = json.loads(body)
        if not isinstance(data, dict) or not isinstance(data.get('items'), list) or any(not isinstance(r, dict) for r in data['items']):
            raise ValueError(f'{name}: expected an items array of objects')
        page = dict(collection=name, file=filename or f'raw/{name}-{len(self.pages):06d}.json',
                    source_url=url, collected_at=collected, sha256=hashlib.sha256(body).hexdigest(), body=body)
        self.pages.append(page)
        for index, row in enumerate(data['items']):
            self.locations[id(row)] = (page, index)
        return data

    def fetch_collection(self, name, query=None):
        params = {'limit': self.page_size}
        if query:
            params['q'] = canonical(query)
        url = f'{BASE}/{ENDPOINTS[name]}/?' + urllib.parse.urlencode(params)
        items, seen = [], set()
        for _ in range(self.max_pages):
            if url in seen:
                raise IncompleteCollection(f'{name}: pagination cycle')
            seen.add(url)
            body = self._get(url)
            data = self._record_page(name, body, url, utcnow())
            items.extend(data['items'])
            if data.get('hasMore') is False:
                return items
            if data.get('hasMore') is not True:
                raise IncompleteCollection(f'{name}: missing/invalid hasMore')
            nxt = next((l.get('href') for l in data.get('links', []) if l.get('rel') == 'next'), None)
            if not nxt:
                raise IncompleteCollection(f'{name}: hasMore without next link')
            url = urllib.parse.urljoin(url, nxt)
            if urllib.parse.urlparse(url).scheme != 'https' or urllib.parse.urlparse(url).netloc != urllib.parse.urlparse(BASE).netloc:
                raise ValueError('Pagination URL must remain on the configured HTTPS host')
            time.sleep(self.pause)
        raise IncompleteCollection(f'{name}: max_pages reached before completion')

    def _offline(self):
        manifest = json.loads((self.offline_dir / 'manifest.json').read_text())
        if type(manifest.get('is_synthetic')) is not bool:
            raise ValueError('Manifest requires explicit boolean is_synthetic')
        if manifest.get('complete') is not True:
            raise IncompleteCollection('Manifest must explicitly mark its declared scope complete')
        self.synthetic = manifest['is_synthetic']
        self.scope = manifest.get('scope', {'collections': sorted({e['collection'] for e in manifest['responses']})})
        raw = defaultdict(list)
        if not manifest.get('responses'):
            raise ValueError('Replay manifest contains no response snapshots')
        saved_urls = {e['source_url'] for e in manifest['responses']}
        for entry in manifest['responses']:
            name = entry['collection']
            if name not in ENDPOINTS:
                raise ValueError(f'Unknown collection {name}')
            path = (self.offline_dir / entry['file']).resolve()
            if not path.is_relative_to(self.offline_dir.resolve()):
                raise ValueError('Snapshot path escapes replay directory')
            body = path.read_bytes()
            if hashlib.sha256(body).hexdigest() != entry['sha256']:
                raise ValueError(f'Snapshot hash mismatch: {entry["file"]}')
            payload = json.loads(body)
            if payload.get('hasMore') is True:
                nxt = next((link.get('href') for link in payload.get('links', []) if link.get('rel') == 'next'), None)
                if not nxt or urllib.parse.urljoin(entry['source_url'], nxt) not in saved_urls:
                    raise IncompleteCollection('Replay is missing a next page')
            elif not self.synthetic and payload.get('hasMore') is not False:
                raise IncompleteCollection('Real replay page is missing hasMore')
            if not self.synthetic and 'SYNTHETIC' in str(payload.get('_note', '')).upper():
                raise ValueError('Synthetic fixture cannot be imported as real')
            data = self._record_page(name, body, entry['source_url'], entry['collected_at'])
            raw[name].extend(data['items'])
        missing = set(ENDPOINTS) - raw.keys()
        if missing:
            self.warnings.append(dict(level='incomplete', reason='Replay has limited collection coverage', collections=sorted(missing)))
        # A saved scoped extract may omit related collections; make this visible.
        return dict(raw)

    def fetch(self):
        self.pages, self.locations, self.warnings = [], {}, []
        self.started_at = utcnow()
        if self.offline_dir:
            return self._offline()
        raw = {}
        for name in ENDPOINTS:
            if not self.registrations or name in ('wirkstoff', 'kode'):
                raw[name] = self.fetch_collection(name, {'SPRACHE': 'DE'} if name == 'kode' else None)
            else:
                key = 'KENNR' if name in ('mittel', 'awg', 'wirkstoff_gehalt') else ('EBENE' if name == 'auflagen' else 'AWG_ID')
                raw[name] = []
                for reg in sorted(self.registrations):
                    value = reg if key == 'KENNR' else {'$like': reg + '/%'}
                    raw[name].extend(self.fetch_collection(name, {key: value}))
                    if key == 'EBENE':
                        raw[name].extend(self.fetch_collection(name, {key: reg}))
        found = {str(pick(m, 'reg_no')) for m in raw.get('mittel', [])}
        if self.registrations - found:
            raise ValueError(f'Requested registrations absent (not proof of no registration): {sorted(self.registrations - found)}')
        return raw

    def write_snapshots(self, directory):
        directory = Path(directory)
        entries = []
        for page in self.pages:
            target = directory / page['file']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(page['body'])
            entries.append({k: v for k, v in page.items() if k != 'body'})
        manifest = dict(adapter_version=VERSION, is_synthetic=self.synthetic, complete=True,
                        scope=self.scope,
                        responses=entries, warnings=self.warnings)
        (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    def provenance(self, row):
        try:
            return self.locations[id(row)]
        except KeyError:
            raise ValueError('Call fetch() before conversion; source rows require snapshot provenance') from None

    def evidence(self, bundle, entity, key, row):
        page, index = self.provenance(row)
        if self.compact_evidence:
            # One cited source record preserves every field, instead of one
            # duplicate excerpt/value/metadata tuple per field. Raw pages remain
            # byte-for-byte intact and the locator identifies the exact record.
            bundle.field_evidence.append(dict(entity_type=entity, entity_id=key,
                field_name=f'source.{page["collection"]}', value_original=canonical(row),
                excerpt=canonical(dict(locator=f'{page["file"]}#/items/{index}', sha256=page['sha256'])),
                document_url=page['source_url'], extraction_method='official_api_json' if not self.synthetic else 'synthetic_fixture_json',
                validation_status='automatically_extracted', collected_at=page['collected_at']))
            return
        for field, value in itertools.chain(row.items(), [('source_locator', f'{page["file"]}#/items/{index}'), ('snapshot_sha256', page['sha256'])]):
            if value is None:
                continue
            text = original(value)
            bundle.field_evidence.append(dict(entity_type=entity, entity_id=key,
                field_name=field if field in ('source_locator', 'snapshot_sha256') else f'source.{page["collection"]}.{field}',
                value_original=text, excerpt=text, document_url=page['source_url'],
                extraction_method='official_api_json' if not self.synthetic else 'synthetic_fixture_json',
                validation_status='automatically_extracted', collected_at=page['collected_at']))

    def to_canonical(self, raw):
        b = CanonicalBundle(warnings=list(self.warnings))
        synth = str(self.synthetic).lower()
        indexes = {}
        for coll, key in [('awg', 'kennr'), ('wirkstoff_gehalt', 'kennr'), ('awg_kultur', 'awg_id'), ('awg_schadorg', 'awg_id'), ('awg_aufwand', 'awg_id'), ('awg_wartezeit', 'awg_id'), ('awg_zeitpunkt', 'awg_id'), ('auflagen', 'ebene')]:
            indexes[coll] = defaultdict(list)
            for row in raw.get(coll, []):
                indexes[coll][str(row.get(key))].append(row)
        actives = {str(r['wirknr']): r for r in raw.get('wirkstoff', []) if r.get('wirknr')}
        codes = defaultdict(list)
        for row in raw.get('kode', []):
            if str(row.get('sprache', '')).upper() == 'DE':
                codes[(str(row.get('kodeliste')), str(row.get('kode')))].append(row)
        def decode(code, namespace, evidence_rows):
            if code is None or not str(code).strip():
                return None
            matches = codes[(str(namespace), str(code))]
            texts = {r.get('kodetext') for r in matches if r.get('kodetext') is not None}
            if len(texts) == 1:
                evidence_rows.extend(matches)
                return next(iter(texts))
            b.warnings.append(dict(level='uncertain', reason='Unresolved BVL code; original code retained', namespace=namespace, code=code))
            return str(code)
        def numeric(value, field, key, integer=False):
            converted = number(value, integer)
            if value not in (None, '') and converted is None:
                b.warnings.append(dict(level='uncertain', entity_id=key, field=field, value=value, reason='Not a nonnegative scalar; retained in evidence/restrictions'))
            return converted
        seen_regs, seen_uses = set(), set()
        self.source_rows = {}
        for m in raw.get('mittel', []):
            reg, name = pick(m, 'reg_no'), pick(m, 'name')
            if not reg or not name:
                b.warnings.append(dict(level='skipped', reason='Missing registration number or name', record=m))
                continue
            reg = str(reg)
            if self.registrations and reg not in self.registrations:
                continue
            if reg in seen_regs:
                raise ValueError(f'Duplicate registration {reg}')
            seen_regs.add(reg)
            token = urllib.parse.quote(reg, safe='')
            pid, rid = f'P-DE-BVL-{token}', f'R-DE-BVL-{token}'
            page, _ = self.provenance(m)
            components, product_rows = [], [m]
            for component in indexes['wirkstoff_gehalt'][reg]:
                product_rows.append(component)
                active = actives.get(str(component.get('wirknr')))
                if active:
                    product_rows.append(active)
                    components.append(active.get('wirkstoffname') or str(component['wirknr']))
                else:
                    b.warnings.append(dict(level='uncertain', registration_id=rid, reason='Unresolved active substance', record=component))
            active_original = pick(m, 'active')
            if active_original is None and components:
                active_original = '; '.join(components)
            elif isinstance(active_original, (list, dict)):
                active_original = original(active_original)
            b.products.append(dict(product_id=pid, commercial_name=name, active_entity_original=active_original,
                formulation_code=pick(m, 'formulation'), is_synthetic=synth, validation_status='automatically_extracted'))
            st = pick(m, 'status')
            approval, expiry = norm_date(pick(m, 'approval')), norm_date(pick(m, 'expiry'))
            for field, value, converted in [('approval_date', pick(m, 'approval'), approval), ('expiration_date', pick(m, 'expiry'), expiry)]:
                if value and converted is None:
                    b.warnings.append(dict(level='uncertain', registration_id=rid, field=field, value=value, reason='Invalid date; preserved in evidence'))
            if approval and expiry and expiry < approval:
                b.warnings.append(dict(level='uncertain', registration_id=rid, reason='Expiration precedes approval; normalized dates omitted'))
                approval = expiry = None
            b.registrations.append(dict(registration_id=rid, product_id=pid, country_code='DE', authority_name=self.authority,
                registration_number=reg, status_original=st, status_normalized=norm_status(st), approval_date=approval,
                expiration_date=expiry, source_id=self.source_id, source_record_url=page['source_url'],
                collected_at=page['collected_at'], validation_status='automatically_extracted', is_synthetic=synth))
            if norm_status(st) == 'unknown':
                b.warnings.append(dict(level='uncertain', registration_id=rid, reason='No recognized sourced status; never infer active from dates or presence in API'))
            for row in product_rows:
                self.evidence(b, 'product', pid, row)
            registration_rows = [m] + indexes['auflagen'][reg]
            for condition in indexes['auflagen'][reg]:
                decode(condition.get('auflage'), 74, registration_rows)
            registration_rows = list({id(row): row for row in registration_rows}.values())
            for row in registration_rows:
                self.evidence(b, 'registration', rid, row)
            self.source_rows[rid] = registration_rows
            if str(name).upper().strip() in {str(k).upper().strip() for k in self.pilot}:
                b.warnings.append(dict(level='candidate', product_id=pid, reason='Name mapping observed; product identity left source-scoped pending review'))
            for u in indexes['awg'][reg]:
                awg = str(u.get('awg_id') or digest(u))
                if awg in seen_uses:
                    raise ValueError(f'Duplicate source use {awg}')
                seen_uses.add(awg)
                crops = indexes['awg_kultur'][awg]
                targets = indexes['awg_schadorg'][awg]
                doses = indexes['awg_aufwand'][awg]
                waits = indexes['awg_wartezeit'][awg]
                times = indexes['awg_zeitpunkt'][awg]
                restrictions = indexes['auflagen'][reg] + indexes['auflagen'][awg]
                crop_options = [r for r in crops if r.get('ausgenommen') == 'N'] if crops else [None]
                target_options = [r for r in targets if r.get('ausgenommen') == 'N'] if targets else [None]
                if not crop_options or not target_options:
                    b.warnings.append(dict(level='skipped', source_use_id=awg, reason='No explicitly included crop or target; raw rows retained'))
                    continue
                counts = Counter()
                # Flat schema needs one row for each crop/target/dose alternative.
                for crop_row, target_row, dose in itertools.product(crop_options, target_options, doses or [None]):
                    identity = {'awg_id': awg, 'crop': crop_row, 'target': target_row, 'dose': dose}
                    h = digest(identity)
                    counts[h] += 1
                    uid = f'U-DE-BVL-{urllib.parse.quote(awg, safe="")}-{h}-{counts[h]}'
                    if self.compact_evidence:
                        # Product-wide restrictions are cited once on the parent
                        # registration. Use evidence covers this particular
                        # alternative and all relevant exceptions/conditions.
                        erows = ([u] + [r for r in (crop_row, target_row, dose) if r is not None]
                            + [r for r in crops + targets if r.get('ausgenommen') != 'N']
                            + waits + times + indexes['auflagen'][awg])
                    else:
                        erows = [u] + crops + targets + doses + waits + times + restrictions
                    crop_code = crop_row.get('kultur') if crop_row else pick(u, 'crop')
                    target_code = target_row.get('schadorg') if target_row else pick(u, 'target')
                    crop = decode(crop_code, 948, erows) if crop_row else crop_code
                    target = decode(target_code, 947, erows) if target_row else target_code
                    method = decode(pick(u, 'method'), 27, erows) if u.get('awg_id') else pick(u, 'method')
                    dose_source = dose or u
                    unit_code = pick(dose_source, 'dose_unit')
                    unit_text = decode(unit_code, 25, erows) if dose else unit_code
                    unit_normalized = UNIT_MAP.get(str(unit_text).strip().lower()) if unit_text else None
                    dose_value = numeric(pick(dose_source, 'dose'), 'dose_value', uid)
                    if dose_value is not None and unit_normalized is None:
                        b.warnings.append(dict(level='uncertain', entity_id=uid, reason='Dose omitted because unit cannot be normalized; raw dose retained'))
                        dose_value = None
                    # Do not apply a waiting period for a different crop or environment.
                    applicable = [w for w in waits if w.get('kultur') in (None, '', crop_code) and w.get('anwendungsbereich') in (None, '', u.get('anwendungsbereich'))]
                    phi_values = [numeric(pick(w, 'phi'), 'phi_days', uid) for w in applicable]
                    phi = phi_values[0] if phi_values and None not in phi_values and len(set(phi_values)) == 1 and all(not w.get('gesetzt_wartezeit_bem') and not w.get('erlaeuterung') for w in applicable) else None
                    if not waits:
                        phi = numeric(pick(u, 'phi'), 'phi_days', uid)
                    if waits and phi is None:
                        b.warnings.append(dict(level='uncertain', entity_id=uid, reason='Conditional/ambiguous waiting period retained in restrictions'))
                    interval = numeric(pick(u, 'interval'), 'application_interval_days', uid)
                    if u.get('aw_abstand_von') is not None:
                        interval_unit = decode(u.get('aw_abstand_einheit'), 29, erows)
                        if interval_unit in ('Tag', 'Tage') and u.get('aw_abstand_bis') in (None, u['aw_abstand_von']):
                            interval = numeric(u['aw_abstand_von'], 'application_interval_days', uid)
                    decoded_conditions = []
                    for row in restrictions:
                        decoded_conditions.append(decode(row.get('auflage'), 74,
                            [] if self.compact_evidence and row in indexes['auflagen'][reg] else erows))
                    for row in times:
                        decoded_conditions.append(decode(row.get('zeitpunkt'), 30, erows))
                    if dose:
                        decoded_conditions.append(decode(dose.get('aufwandbedingung'), 28, erows))
                    # Full source conditions avoid losing exclusions, ranges, BBCH, water volumes, etc.
                    condition_text = canonical(dict(awg=u, crops=crops, targets=targets, selected_dose=dose,
                        waiting_periods=waits, timing=times, restrictions=restrictions, decoded_conditions=[x for x in decoded_conditions if x]))
                    b.uses.append(dict(use_id=uid, registration_id=rid, crop_name_original=crop,
                        target_name_original=target, application_method=method, dose_value=dose_value,
                        dose_unit_original=unit_code, dose_unit_normalized=unit_normalized,
                        max_applications=numeric(pick(u, 'max_apps'), 'max_applications', uid, True),
                        application_interval_days=interval, phi_days=phi, restrictions_original=condition_text,
                        validation_status='automatically_extracted', is_synthetic=synth))
                    unique_rows = list({id(r): r for r in erows}.values())
                    self.source_rows[uid] = unique_rows
                    for row in unique_rows:
                        self.evidence(b, 'use', uid, row)
        orphan_regs = set(indexes['awg']) - seen_regs
        for orphan in sorted(orphan_regs):
            if not self.registrations or orphan in self.registrations:
                b.warnings.append(dict(level='skipped', reason='Use rows have no matching product registration', registration_number=orphan, rows=len(indexes['awg'][orphan])))
        missing_requested = self.registrations - seen_regs
        if missing_requested:
            raise ValueError(f'Requested registrations absent from converted data: {sorted(missing_requested)}')
        b.source_registry.append(dict(source_id=self.source_id, official_name='BVL PSM API', country_or_region='DE',
            base_url=BASE + '/', access_method='api', data_format='JSON', manual_validation_required='true',
            access_and_reuse_limits='Confirm current BVL reuse terms and attribution before redistribution.',
            notes='Source observations, not legal authorization; no result is not proof of no registration.'))
        b.collection_runs.append(dict(source_id=self.source_id, started_at=self.started_at, finished_at=utcnow(),
            input_file='manifest.json', rows_read=sum(len(rows) for rows in raw.values()),
            rows_written=len(b.products) + len(b.registrations) + len(b.uses),
            status='failed' if any(w['level'] in ('incomplete', 'skipped') for w in b.warnings) else 'success',
            notes='Conversion only. No result is not proof of no registration. See manifest and warnings.'))
        self.warnings = list(b.warnings)
        return b
