// BâtIA · données réelles — deux faits dits d'une seule façon partout : la fiche de la carte réelle, le calcul
// de risque et la page « Sous le capot » importent ce module (/reel/regles.mjs). Sans dépendance, navigateur et Node.

const LETTRES = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

// ── L'étiquette énergie d'un immeuble ───────────────────────────────
// La plus fréquente parmi les DPE de l'ADEME de l'immeuble, avec leur nombre ; à égalité, la moins bonne.
// Sans aucun DPE à l'ADEME, l'étiquette de la BDNB, et la source le dit.
//   etiquetteImmeuble({ repartition_dpe | dpe: [{ etiquette }], etiquette_dpe })
//   → { lettre: 'C', n: 15, total: 29, source: 'ADEME', texte: 'dans 15 DPE sur 29 · ADEME' } ou null
export function etiquetteImmeuble(f = {}) {
  const rep = {};
  const r = f?.repartition_dpe;
  if (r && Object.values(r).some((n) => n > 0)) for (const l of LETTRES) rep[l] = +r[l] || 0;
  else for (const d of f?.dpe || []) { const l = String(d.etiquette || '').toUpperCase(); if (LETTRES.includes(l)) rep[l] = (rep[l] || 0) + 1; }
  const total = Object.values(rep).reduce((s, n) => s + n, 0);
  if (total) {
    let lettre = null, n = 0;
    for (const l of LETTRES) if (rep[l] && rep[l] >= n) { lettre = l; n = rep[l]; }
    return { lettre, n, total, source: 'ADEME', texte: total === 1 ? 'un seul DPE · ADEME' : `dans ${n} DPE sur ${total} · ADEME` };
  }
  const b = String(f?.etiquette_dpe || '').toUpperCase();
  return LETTRES.includes(b) ? { lettre: b, n: 0, total: 0, source: 'BDNB', texte: 'BDNB · aucun DPE à l’ADEME' } : null;
}

// ── L'arrêt de la 2G ────────────────────────────────────────────────
// Calendrier de l'ARCEP et d'Orange, fiche mise à jour le 10 septembre 2026
// (recherche/donnees-publiques/fiches/19-continuite-des-reseaux-et-connectivite-des.md).
export const ARRET_2G = {
  orange: { 31: '2026-06-09', 33: '2026-10-20', 34: '2026-10-06', 40: '2026-05-12', 64: '2026-05-12' },
  orangeCommunes: { 64102: '2026-03-31', 64024: '2026-03-31', 64122: '2026-03-31' }, // Bayonne, Anglet, Biarritz
  sfr: '2026-11-15',
  bouygues: '2026-12-15',
};

// Une seule formulation, la même dans la fiche et dans les raisons ; une date passée se dit « depuis le » :
//   phrase2G('31') le 10 oct. 2026 → « Fin de la 2G en 2026 : Orange depuis le 9 juin, SFR le 15 nov., Bouygues le 15 déc. »
export function phrase2G(departement, codeCommune, aujourdhui = new Date()) {
  // hors des départements connus, la date d'Orange manque : on ne dit que celles de SFR et de Bouygues
  const orange = ARRET_2G.orangeCommunes[codeCommune] || ARRET_2G.orange[+departement];
  const dates = [orange && ['Orange', orange], ['SFR', ARRET_2G.sfr], ['Bouygues', ARRET_2G.bouygues]].filter(Boolean);
  const annees = new Set(dates.map(([, d]) => d.slice(0, 4)));
  const iso = aujourdhui.toISOString().slice(0, 10);
  const jour = (d) => { const [a, m, j] = d.split('-'); return `${+j === 1 ? '1er' : +j} ${MOIS[+m - 1]}${annees.size > 1 ? ` ${a}` : ''}`; };
  const liste = dates.map(([op, d]) => `${op} ${d <= iso ? 'depuis le' : 'le'} ${jour(d)}`);
  return `Fin de la 2G${annees.size === 1 ? ` en ${[...annees][0]}` : ''} : ${liste.join(', ')}`;
}
