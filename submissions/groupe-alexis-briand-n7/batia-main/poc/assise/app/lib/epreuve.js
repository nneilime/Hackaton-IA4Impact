// Mise à l'épreuve dans le passé : on se place à une date, on calcule le risque avec
// l'historique antérieur uniquement, puis on regarde ce qui a réellement cassé ensuite.
import { evaluerRisques, scoreAgeSeul } from './risque.js';

function auc(scores, cibles) {
  const idx = scores.map((s, i) => i).sort((a, b) => scores[a] - scores[b]);
  const rangs = new Array(scores.length);
  for (let i = 0; i < idx.length; ) {
    let j = i;
    while (j + 1 < idx.length && scores[idx[j + 1]] === scores[idx[i]]) j++;
    for (let k = i; k <= j; k++) rangs[idx[k]] = (i + j) / 2 + 1;
    i = j + 1;
  }
  const nPos = cibles.filter(Boolean).length, nNeg = cibles.length - nPos;
  const somme = rangs.reduce((s, r, i) => s + (cibles[i] ? r : 0), 0);
  return (somme - (nPos * (nPos + 1)) / 2) / (nPos * nNeg);
}

function tete(scores, departage, cibles, part) {
  const n = Math.ceil(scores.length * part);
  const ordre = scores.map((s, i) => i).sort((a, b) => scores[b] - scores[a] || departage[b] - departage[a]);
  const trouvees = ordre.slice(0, n).filter((i) => cibles[i]).length;
  return { inspectes: n, trouvees };
}

export function eprouver(tables, { dateReference = '2024-12-31', debut = '2025-01-01', fin = '2025-09-30' } = {}) {
  const methode = evaluerRisques(tables, dateReference);
  const age = scoreAgeSeul(tables, dateReference);
  const pannes = new Set(tables.interventions
    .filter((it) => it.type_intervention === 'Dépannage' && it.gravite === 'Arrêt total'
      && it.date_intervention.slice(0, 10) >= debut && it.date_intervention.slice(0, 10) <= fin)
    .map((it) => it.equipement_id));
  const ids = [...methode.keys()];
  const cibles = ids.map((id) => pannes.has(id));
  const sM = ids.map((id) => methode.get(id).score);
  const sA = ids.map((id) => age.get(id));
  return {
    dateReference, debut, fin,
    equipements: ids.length,
    pannes: cibles.filter(Boolean).length,
    methode: { auc: auc(sM, cibles), dixieme: tete(sM, sA, cibles, 0.1) },
    ageSeul: { auc: auc(sA, cibles), dixieme: tete(sA, sA, cibles, 0.1) },
  };
}
