// BâtIA · données réelles — la fiche d'un immeuble du parc réel, ou d'un groupe de petits immeubles d'une commune.
// Même gabarit que les fiches du kit (app/app.mjs) : le nom, le lieu, la catégorie en grand, « Pourquoi », puis
// « Plus d'informations ». L'étiquette énergie suit la règle commune (regles.mjs) et nomme sa source.
//   el.innerHTML = ficheImmeuble(immeuble, evaluation, { sources });
//   el.innerHTML = ficheGroupe(groupe);
import { VIFS } from './couche.mjs';
import { LIBELLES } from './calcul.mjs';
import { etiquetteImmeuble } from './regles.mjs';

const nb = (n) => new Intl.NumberFormat('fr-FR').format(n);
const pl = (n, un, plusieurs) => `${nb(n)} ${n > 1 ? plusieurs : un}`;
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]).replace(/'/g, '’');
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const dateCourte = (iso) => { if (!iso) return ''; const [a, m, j] = String(iso).slice(0, 10).split('-'); return j ? `${+j === 1 ? '1er' : +j} ${MOIS[+m - 1]} ${a}` : a; };
// les couleurs des étiquettes : la palette commune (app/palette.css), les mêmes que dans le kit
const lettreDpe = (l) => (/^[A-G]$/.test(l) ? `<span class="etiquette" style="background:var(--dpe-${l});color:var(--sur-dpe-${l})">${esc(l)}</span>` : `<span class="etiquette" style="background:#999;color:#fff">${esc(l)}</span>`);
const X = '<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';

// la catégorie, comme dans le kit : le mot court, en couleur vive seulement pour ce qui demande une action
export function pastille(niveau, { grand = false, compte = null } = {}) {
  return `<span class="cat${grand ? ' grand' : ''}" data-cat="${niveau}"${VIFS.includes(niveau) ? ' data-vive' : ''}>${esc(LIBELLES[niveau] || niveau)}${compte != null ? ` <b>${nb(compte)}</b>` : ''}</span>`;
}

// « 34 Boulevard de l'Embouchure 31200 Toulouse » → la rue ; la commune se lit dessous
export function rue(adresse, commune) {
  const s = String(adresse || '').replace(/\s+\d{5}\s+.*$/, '').replace(/'/g, '’');
  return s || commune || 'Adresse inconnue';
}
// la BDNB écrit sans accents (« chaudiere gaz standard ») : on rend les mots du métier lisibles
const ACCENTS = [[/chaudiere/gi, 'chaudière'], [/electrique/gi, 'électrique'], [/reseau/gi, 'réseau'], [/a condensation/gi, 'à condensation'], [/temperature/gi, 'température'], [/pompe a chaleur/gi, 'pompe à chaleur'], [/auto ?r[ée]glable/gi, 'autoréglable']];
const joli = (s) => ACCENTS.reduce((t, [re, v]) => t.replace(re, (m) => (m[0] === m[0].toUpperCase() ? v[0].toUpperCase() + v.slice(1) : v)), String(s ?? ''));
const majuscule = (s) => { const t = joli(s); return t ? t[0].toUpperCase() + t.slice(1) : t; };
const chauffage = (c) => (c?.generateur ? `${esc(majuscule(c.generateur))}${c.collectif === true ? ' · collectif' : c.collectif === false ? ' · individuel' : ''}` : null);

// « 84 logements », ou « 37 logements In’li sur 243 » dans une copropriété
function partInli(im) {
  const n = im.logements_inli ?? im.nb_logements;
  if (!n && !im.nb_logements) return null;
  if (im.nb_logements && n < im.nb_logements) return `${pl(im.nb_logements, 'logement', 'logements')}, dont ${nb(n)} In’li`;
  return pl(n, 'logement', 'logements');
}

// l'étiquette de l'immeuble, dite partout de la même façon : la lettre, puis d'où elle vient
export function etiquetteEcrite(im) {
  const e = etiquetteImmeuble(im);
  return e ? `${lettreDpe(e.lettre)} <span class="re-source">${esc(e.texte)}</span>` : null;
}

export function ficheImmeuble(im, ev, { sources = {} } = {}) {
  const raisons = ev.raisons.filter((r) => r.points > 0);
  const rassurantes = ev.raisons.filter((r) => r.points < 0);
  const ligne = (k, v) => (v == null || v === '' ? '' : `<dt>${k}</dt><dd>${v}</dd>`);
  const ino = im.risques?.inondation;
  const rep = im.repartition_dpe && Object.values(im.repartition_dpe).some((n) => n > 0)
    ? `<span class="re-rep">${Object.entries(im.repartition_dpe).filter(([, n]) => n > 0).map(([l, n]) => `${lettreDpe(l)}<small>${n}</small>`).join('')}</span>` : null;
  const etiq = etiquetteEcrite(im);
  const lieu = [esc(im.commune || ''), partInli(im)].filter(Boolean).join(' · ');

  return `
    <button class="poignee" type="button" aria-label="Agrandir ou réduire la fiche"></button><button type="button" class="fermer" data-reel-fermer aria-label="Fermer la fiche">${X}</button>
    <div class="tete">
      <h2>${esc(rue(im.adresse, im.commune))}</h2>
      <div class="fil"><span>${lieu}</span></div>
      <div class="etat">${pastille(ev.niveau, { grand: true })}${etiq ? `<span class="re-etiquette">${etiq}</span>` : ''}</div>
    </div>
    <div class="defile">
      ${raisons.length ? `<section class="bloc"><h3>Pourquoi</h3><ul class="raisons">${raisons.slice(0, 3).map((r) => `<li>${esc(r.texte)}</li>`).join('')}</ul></section>` : ''}
      <details class="plus-infos"><summary>Plus d’informations</summary>
        <dl class="faits">
          ${ligne('Construit', im.annee_construction ? `en ${im.annee_construction}` : null)}
          ${ligne('Hauteur', im.nb_niveaux ? `${pl(im.nb_niveaux, 'niveau', 'niveaux')}${im.hauteur_m ? ` · ${Math.round(im.hauteur_m)} m` : ''}` : null)}
          ${ligne('Chauffage', chauffage(im.chauffage))}
          ${ligne('Eau chaude', im.eau_chaude?.generateur ? esc(majuscule(im.eau_chaude.generateur)) : null)}
          ${ligne('Ventilation', im.ventilation ? esc(majuscule(im.ventilation)) : null)}
          ${ligne('Étiquette', etiq)}
          ${ligne('DPE', rep)}
          ${ligne('Sol argileux', im.risques?.argile ? `aléa ${esc(String(im.risques.argile).toLowerCase())}` : null)}
          ${ligne('Inondation', ino && typeof ino === 'object' && (ino.ppr || ino.arretes) ? [ino.ppr ? 'plan de prévention' : '', ino.arretes ? pl(ino.arretes, 'arrêté', 'arrêtés') : ''].filter(Boolean).join(' · ') : null)}
          ${ligne('Eau', im.durete_eau_f != null ? `${String(Math.round(im.durete_eau_f * 10) / 10).replace('.', ',')} °f` : null)}
        </dl>
        ${raisons.length || rassurantes.length ? `<h3 class="sous-bloc">Raisons et sources</h3><ul class="raisons re-sources-raisons">${[...raisons, ...rassurantes].map((r) => `<li>${esc(r.texte)}<small>${esc(r.source)}</small></li>`).join('')}</ul>` : ''}
        ${ev.manque.length ? `<h3 class="sous-bloc">Non trouvé</h3><p class="re-manque">${ev.manque.map(esc).join(' · ')}</p>` : ''}
        <h3 class="sous-bloc">Sources</h3>
        <ul class="re-sources">${(im.sources || []).map((s) => `<li><b>${esc(sources[s.nom]?.nom || s.nom)}</b><span>${s.date_lecture ? `lu le ${dateCourte(s.date_lecture)}` : ''}</span></li>`).join('')}</ul>
        <p class="re-ids">${im.id_bdnb ? `BDNB ${esc(im.id_bdnb)}` : ''}${im.id_rnb ? ` · RNB ${esc(im.id_rnb)}` : ''}</p>
      </details>
    </div>`;
}

export function ficheGroupe(g) {
  const ordre = ['urgence', 'alerte', 'vigilance', 'surveiller', 'calme'];
  return `
    <button class="poignee" type="button" aria-label="Agrandir ou réduire la fiche"></button><button type="button" class="fermer" data-reel-fermer aria-label="Fermer la fiche">${X}</button>
    <div class="tete">
      <h2>${esc(g.commune)}</h2>
      <div class="fil"><span>${pl(g.batiments, 'petit bâtiment', 'petits bâtiments')} · ${pl(g.logements, 'logement', 'logements')}</span></div>
      <div class="bandes">${ordre.filter((n) => g.parNiveau[n]).map((n) => pastille(n, { compte: g.parNiveau[n] })).join('')}</div>
    </div>
    <div class="defile">
      ${g.raisons?.length ? `<section class="bloc"><h3>Pourquoi</h3><ul class="raisons">${g.raisons.slice(0, 3).map((r) => `<li>${esc(r)}</li>`).join('')}</ul></section>` : ''}
      <details class="plus-infos"><summary>Plus d’informations</summary>
        <dl class="faits">
          ${g.annees ? `<dt>Construits</dt><dd>${g.annees[0] === g.annees[1] ? `en ${g.annees[0]}` : `de ${g.annees[0]} à ${g.annees[1]}`}</dd>` : ''}
          ${g.maisons ? `<dt>Maisons</dt><dd>${nb(g.maisons)}</dd>` : ''}
        </dl>
      </details>
    </div>`;
}
