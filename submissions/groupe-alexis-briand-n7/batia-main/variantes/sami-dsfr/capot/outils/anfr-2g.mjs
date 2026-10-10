// Extrait de l'export mensuel de l'ANFR les stations qui émettent encore en 2G (GSM), avec leur position et leur exploitant.
// L'ANFR n'a pas d'interface de requête : on lit l'archive une fois, le serveur local répond ensuite au navigateur.
// Usage : node capot/outils/anfr-2g.mjs <export.zip> <sortie.json>
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { writeFileSync } from 'node:fs';

const [zip, sortie] = process.argv.slice(2);
const EXPLOITANTS = { 23: 'Orange', 137: 'SFR', 6: 'Bouygues Telecom', 240: 'Free' };

async function lignes(table, surLigne) {
  const p = spawn('unzip', ['-p', zip, `${table}.txt`]);
  const rl = createInterface({ input: p.stdout.setEncoding('latin1') });
  let entete = null;
  for await (const l of rl) {
    const c = l.split(';');
    if (!entete) { entete = c; continue; }
    surLigne(c, entete);
  }
}

const gsm = new Set();
await lignes('SUP_EMETTEUR', (c) => { if (/^GSM/.test(c[1])) gsm.add(c[2]); });
const exploitant = new Map();
await lignes('SUP_STATION', (c) => { if (gsm.has(c[0]) && EXPLOITANTS[c[1]]) exploitant.set(c[0], EXPLOITANTS[c[1]]); });
const stations = [];
const vu = new Set();
await lignes('SUP_SUPPORT', (c) => {
  const sta = c[1];
  if (!exploitant.has(sta) || vu.has(sta)) return;
  vu.add(sta);
  const lat = (+c[3] + +c[4] / 60 + +c[5] / 3600) * (c[6] === 'S' ? -1 : 1);
  const lon = (+c[7] + +c[8] / 60 + +c[9] / 3600) * (c[10] === 'W' ? -1 : 1);
  stations.push([+lat.toFixed(5), +lon.toFixed(5), exploitant.get(sta)]);
});
writeFileSync(sortie, JSON.stringify({ source: 'ANFR, installations radioélectriques de plus de 5 W, export du 30/09/2026 (Licence Ouverte 2.0)', export: '2026-09-30', stations }));
const parOp = {}; for (const s of stations) parOp[s[2]] = (parOp[s[2]] || 0) + 1;
console.log(stations.length, 'stations 2G', parOp);
