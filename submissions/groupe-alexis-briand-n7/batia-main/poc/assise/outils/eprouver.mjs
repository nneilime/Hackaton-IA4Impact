// node outils/eprouver.mjs — rejoue la méthode au 31/12/2024 et la compare à « âge seul ».
import { chargerTables } from '../app/lib/chargement.mjs';
import { eprouver } from '../app/lib/epreuve.js';
import { evaluerRisques } from '../app/lib/risque.js';
const { tables } = chargerTables([new URL('../donnees/kit-batia/donnees', import.meta.url).pathname]);
const r = eprouver(tables);
console.log(JSON.stringify(r, null, 1));
const r2 = eprouver(tables, { dateReference: '2023-12-31', debut: '2024-01-01', fin: '2024-09-30' });
console.log('2024 :', JSON.stringify({ m: r2.methode, a: r2.ageSeul, p: r2.pannes }));
const actuel = evaluerRisques(tables, '2025-12-31');
const niv = {}; for (const v of actuel.values()) niv[v.niveau] = (niv[v.niveau] || 0) + 1;
console.log('niveaux au 31/12/2025', niv);
const top = [...actuel.entries()].sort((a, b) => b[1].score - a[1].score).slice(0, 4);
for (const [id, v] of top) console.log(id, v.score, v.raisons.map((x) => `${x.points}·${x.texte}`).join(' | '));
