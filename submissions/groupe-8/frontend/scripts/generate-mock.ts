// Generates the mock crisis scenario from the real CSVs in data/.
//
//   npm run generate            -> always regenerate
//   tsx generate-mock.ts --if-stale  -> only if CSVs are newer than the output (used by predev)
//
// Output:
//   public/mock/<crisis>/scenario.json            input of the in-browser mock engine
//   fixtures/<crisis>/snapshots_ours.json         contract fixtures: what the real engine
//   fixtures/<crisis>/snapshots_reference.json    should return (not served to the browser)

import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { runCrisis } from '../src/data/mock/engine';
import type { Scenario, ScenarioIncident, ScenarioTeam } from '../src/data/mock/scenario';

const CRISIS = process.env.CRISIS ?? 'CRISE_027';
const STEP_MINUTES = 30;

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dataDir = join(root, '..', 'backend', 'data', 'raw');   // shared with the backend
const outDir = join(root, 'public', 'mock', CRISIS.toLowerCase());
const files = {
  postes: join(dataDir, 'poste_v2.csv'),
  coupures: join(dataDir, 'coupures_v2_100_crises.csv'),
  agents: join(dataDir, 'agents_v2.csv'),
};
const fixturesDir = join(root, 'fixtures', CRISIS.toLowerCase());
const outScenario = join(outDir, 'scenario.json');

if (!Object.values(files).every(existsSync)) {
  if (existsSync(outScenario)) {
    console.log('[mock] CSVs absent, scénario existant conservé.');
    process.exit(0);
  }
  console.error('[mock] CSVs manquants dans data/ et aucun scénario généré.');
  process.exit(1);
}
if (process.argv.includes('--if-stale') && existsSync(outScenario)) {
  const outT = statSync(outScenario).mtimeMs;
  const srcT = Math.max(
    ...Object.values(files).map((f) => statSync(f).mtimeMs),
    statSync(join(root, 'src/data/mock/engine.ts')).mtimeMs,
    statSync(fileURLToPath(import.meta.url)).mtimeMs,
  );
  if (outT > srcT) {
    console.log(`[mock] ${CRISIS} à jour.`);
    process.exit(0);
  }
}

function readCsv(path: string): Record<string, string>[] {
  const text = readFileSync(path, 'utf8').replace(/^﻿/, '');
  const [head, ...lines] = text.split(/\r?\n/).filter((l) => l.trim() !== '');
  const cols = head.split(';');
  return lines.map((l) => {
    const v = l.split(';');
    return Object.fromEntries(cols.map((c, i) => [c, v[i]]));
  });
}

// "09/10/2016 21:39" in Europe/Paris -> UTC epoch ms
const parisFmt = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/Paris',
  hourCycle: 'h23',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
});
function parisToUtc(s: string): number {
  const [d, m, y, h, mi] = s.split(/[/ :]/).map(Number);
  const guess = Date.UTC(y, m - 1, d, h, mi);
  const p = Object.fromEntries(parisFmt.formatToParts(guess).map((x) => [x.type, x.value]));
  const asParis = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute);
  return guess - (asParis - guess);
}

// Deterministic pseudo-random in [0,1) from a string
function hash01(s: string): number {
  let h = 2166136261;
  for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return ((h >>> 0) % 10000) / 10000;
}

const postes = new Map(readCsv(files.postes).map((p) => [p.id_poste, p]));
const rows = readCsv(files.coupures).filter((r) => r.numero_crise === CRISIS);
const missing = rows.filter((r) => !postes.has(r.id_poste));
const kept = rows.filter((r) => postes.has(r.id_poste));

const times = kept.map((r) => parisToUtc(r.dateHeureIncident));
const step = STEP_MINUTES * 60000;
const startMs = Math.floor(Math.min(...times) / step) * step;

const incidents: ScenarioIncident[] = kept.map((r, idx) => {
  const p = postes.get(r.id_poste)!;
  return {
    id: r.id_incident,
    posteId: r.id_poste,
    lon: +p.longitude,
    lat: +p.latitude,
    commune: p.commune,
    departement: p.departement,
    clients: +p.nb_clients,
    sensitive: p.poste_avec_client_sensible === '1',
    cause: r.causeInterruption,
    repairHours: parseInt(r.dureeDepannage, 10),
    reportedMin: Math.round((times[idx] - startMs) / 60000),
  };
});

const shortName = (commune: string) =>
  commune.replace(/\s*\(Toulouse\)/, '').replace('Bagnères de Luchon', 'Luchon').replace('Villefranche-de-Lauragais', 'Villefranche');

const agents = readCsv(files.agents);
const sites = agents.map((a) => ({
  id: a.id_site,
  name: a.commune,
  lon: +a.longitude,
  lat: +a.latitude,
  teams: +a.nb_equipes,
}));
const teams: ScenarioTeam[] = agents.flatMap((a) =>
  Array.from({ length: +a.nb_equipes }, (_, n) => {
    const id = `${a.id_site.replace('SITE_', 'EQ-')}-${n + 1}`;
    return {
      id,
      label: `${shortName(a.commune)}-${n + 1}`,
      siteId: a.id_site,
      siteName: a.commune,
      lon: +a.longitude,
      lat: +a.latitude,
      // Rosters are staggered when the storm hits: ~1 team in 5 is off duty,
      // the others have 3 to 12 h left in their shift.
      initialRestHours: hash01(`rest:${id}`) < 0.2 ? 1 + Math.round(hash01(`r:${id}`) * 14) / 2 : 0,
      initialShiftHours: 3 + Math.round(hash01(id) * 18) / 2,
    };
  }),
);

const scenario: Scenario = { crisisId: CRISIS, startMs, stepMinutes: STEP_MINUTES, sites, teams, incidents };

const t0 = performance.now();
const run = runCrisis(scenario);
const ms = performance.now() - t0;

mkdirSync(outDir, { recursive: true });
writeFileSync(outScenario, JSON.stringify(scenario));
mkdirSync(fixturesDir, { recursive: true });
writeFileSync(join(fixturesDir, 'snapshots_ours.json'), JSON.stringify(run.ours));
writeFileSync(join(fixturesDir, 'snapshots_reference.json'), JSON.stringify(run.reference));

const last = run.ours[run.ours.length - 1].kpis;
console.log(
  `[mock] ${CRISIS}: ${incidents.length} incidents` +
    (missing.length ? ` (${missing.length} ignorés, poste inconnu : ${missing.map((m) => m.id_poste).join(', ')})` : '') +
    `, ${teams.length} équipes, ${run.ours.length} pas de ${STEP_MINUTES} min, simulé en ${ms.toFixed(0)} ms`,
);
console.log(
  `[mock] score final : copilote ${last.score.toLocaleString('fr-FR')} clients·h, référence ${last.scoreBaseline.toLocaleString(
    'fr-FR',
  )} clients·h (${(((last.score - last.scoreBaseline) / last.scoreBaseline) * 100).toFixed(1)} %)`,
);
