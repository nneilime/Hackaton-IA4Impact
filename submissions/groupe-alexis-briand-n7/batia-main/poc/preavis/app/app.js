'use strict';
/* Préavis — interface. Les scores viennent de moteur/risque.py (via preparer.py) : ici on ne calcule aucun risque. */

const $ = (s, el = document) => el.querySelector(s);
const nf = new Intl.NumberFormat('fr-FR');
const fmt = n => nf.format(n);
const fmt1 = n => n.toLocaleString('fr-FR', { maximumFractionDigits: 1 });
const fmt2 = n => n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const ord = n => (+n === 1 ? '1re' : `${n}e`);
const pct = x => `${Math.round(x * 100)} %`;
const euros = n => n >= 1e6 ? `${fmt1(n / 1e6)} M€` : `${fmt(Math.round(n / 1000))} k€`;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const dateFr = s => { const [y, m, d] = s.slice(0, 10).split('-'); return `${+d} ${MOIS[+m - 1]} ${y}`; };
const moisFr = s => { const [y, m] = s.slice(0, 7).split('-'); return `${MOIS[+m - 1]} ${y}`; };
const minus1 = t => (/^[A-ZÉÈÀ][a-zéèàêîôû]/.test(t) ? t[0].toLowerCase() + t.slice(1) : t);
const court = id => id.replace(/^(LGT|BAT|RES)-/, '');
const etageFr = e => +e === 0 ? 'rez-de-chaussée' : +e === 1 ? '1er étage' : `${e}e étage`;

const NIVEAU = { alerte: 'À visiter', vigilance: 'À surveiller', calme: 'Calme' };
const DEPS_INLI = { '31': 'Haute-Garonne', '34': 'Hérault', '33': 'Gironde', '40': 'Landes', '64': 'Pyrénées-Atlantiques' };
const DEP_ACTIF = '31';
// Positions fictives, choisies pour la lisibilité : le kit ne donne aucune adresse et aucune résidence réelle n'est visée.
const POSITIONS = {
  'RES-A': [1.372, 43.660], 'RES-B': [1.478, 43.672], 'RES-C': [1.548, 43.628], 'RES-D': [1.528, 43.560],
  'RES-E': [1.405, 43.532], 'RES-F': [1.338, 43.574], 'RES-G': [1.300, 43.630], 'RES-H': [1.418, 43.602],
};
const DECISIONS = {
  visite: { lib: 'Programmer une visite', fait: 'Visite à programmer' },
  surveiller: { lib: 'Garder à l’œil', fait: 'Gardé à l’œil' },
  ecarte: { lib: 'Écarter', fait: 'Écarté' },
};

const S = { niveau: 'france', resId: null, dec: lireDecisions() };

function lireDecisions() {
  try { return JSON.parse(localStorage.getItem('preavis.decisions') || '{}'); } catch { return {}; }
}
function ecrireDecisions() {
  try { localStorage.setItem('preavis.decisions', JSON.stringify(S.dec)); } catch { /* stockage indisponible : la décision vaut pour la session */ }
}
function decider(eqId, choix) {
  if (S.dec[eqId]?.choix === choix) delete S.dec[eqId];
  else S.dec[eqId] = { choix, le: new Date().toISOString().slice(0, 10) };
  ecrireDecisions();
}

/* ——— chargement ——— */
async function demarrer() {
  const [parc, deps, regions, metro] = await Promise.all([
    fetch('donnees/parc.json').then(r => r.json()),
    fetch('geo/fr-departements.json').then(r => r.json()),
    fetch('geo/fr-regions-so.json').then(r => r.json()),
    fetch('geo/metropole.json').then(r => r.json()),
  ]);
  S.parc = parc;
  S.geo = { deps, regions, metro };
  S.res = new Map(parc.residences.map(r => [r.id, r]));
  S.bat = new Map(parc.batiments.map(b => [b.id, b]));
  S.lgt = new Map(parc.logements.map(l => [l.id, l]));
  S.eq = new Map(parc.equipements.map(e => [e.id, e]));
  $('#date-ref').innerHTML = `Données au <b>${dateFr(parc.meta.date_reference)}</b><br>préavis jusqu'au ${dateFr(parc.meta.horizon_fin)}`;
  initCarte();
  window.addEventListener('hashchange', router);
  router();
}

function journal() {
  if (!S.journalP) S.journalP = fetch('donnees/journal.json').then(r => r.json()).then(j => (S.journal = j));
  return S.journalP;
}

/* ——— navigation ——— */
function router() {
  const ecran = (location.hash.replace(/^#\/?/, '') || 'carte').split('/')[0];
  const connu = ['carte', 'lundi', 'energie'].includes(ecran) ? ecran : 'carte';
  document.querySelectorAll('.ecran').forEach(s => { s.hidden = s.id !== `ecran-${connu}`; });
  document.querySelectorAll('.onglets a').forEach(a => a.toggleAttribute('aria-current', a.dataset.ecran === connu) || a.removeAttribute('aria-current'));
  document.querySelectorAll('.onglets a').forEach(a => { if (a.dataset.ecran === connu) a.setAttribute('aria-current', 'page'); });
  if (connu === 'carte') { requestAnimationFrame(() => allerA(S.niveau, S.resId, true)); }
  if (connu === 'lundi') rendreLundi();
  if (connu === 'energie') rendreEnergie();
}

/* ——— infobulle ——— */
const bulle = $('#infobulle');
function montrerBulle(ev, html) {
  bulle.innerHTML = html; bulle.hidden = false;
  const x = Math.min(ev.clientX + 14, window.innerWidth - bulle.offsetWidth - 8);
  const y = Math.min(ev.clientY + 16, window.innerHeight - bulle.offsetHeight - 8);
  bulle.style.left = `${x}px`; bulle.style.top = `${y}px`;
}
function cacherBulle() { bulle.hidden = true; }

/* ——— carte : France → Occitanie → métropole → résidence ——— */
function initCarte() {
  const svg = d3.select('#carte');
  S.svg = svg;
  S.gMonde = svg.append('g');
  S.gLab = svg.append('g');
  S.proj = d3.geoConicConformal().parallels([44, 49]).rotate([-3, 0]).fitSize([1000, 1000], S.geo.deps);
  S.path = d3.geoPath(S.proj);

  S.gMonde.append('g').selectAll('path').data(S.geo.deps.features).join('path')
    .attr('d', S.path).attr('vector-effect', 'non-scaling-stroke')
    .attr('class', d => `dep${DEPS_INLI[d.properties.code] ? ' inli' : ''}${d.properties.code === DEP_ACTIF ? ' actif' : ''}`)
    .on('click', (ev, d) => clicDep(d.properties.code))
    .on('mousemove', (ev, d) => {
      const c = d.properties.code;
      if (!DEPS_INLI[c]) return cacherBulle();
      montrerBulle(ev, c === DEP_ACTIF
        ? `<b>${esc(d.properties.nom)} (${c})</b><br>${fmt(S.parc.meta.nb_logements)} logements à l'écoute`
        : `<b>${esc(d.properties.nom)} (${c})</b><br>Territoire In'li Sud-Ouest, en attente de ses fichiers`);
    })
    .on('mouseleave', cacherBulle);
  S.gMonde.append('g').selectAll('path').data(S.geo.regions.features.filter(f => f.properties.code === '76')).join('path')
    .attr('class', 'region-occ').attr('d', S.path).attr('vector-effect', 'non-scaling-stroke').attr('opacity', 0);
  S.gCommunes = S.gMonde.append('g').attr('opacity', 0).style('pointer-events', 'none');
  S.gCommunes.selectAll('path').data(S.geo.metro.features).join('path')
    .attr('d', S.path).attr('vector-effect', 'non-scaling-stroke')
    .attr('class', d => `commune${d.properties.code === '31555' ? ' toulouse' : ''}`);

  let attente;
  window.addEventListener('resize', () => { clearTimeout(attente); attente = setTimeout(() => allerA(S.niveau, S.resId, true), 150); });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape') fermerFiche(); });
}

function clicDep(code) {
  if (code !== DEP_ACTIF) return;
  if (S.niveau === 'france') allerA('occitanie');
  else if (S.niveau === 'occitanie') allerA('metropole');
}

function cadrage(features, marge = 50) {
  const el = $('#carte').getBoundingClientRect();
  const w = el.width, h = el.height;
  const b = S.path.bounds({ type: 'FeatureCollection', features });
  const haut = 56, bas = 46;
  const k = Math.min((w - 2 * marge) / (b[1][0] - b[0][0]), (h - haut - bas - marge) / (b[1][1] - b[0][1]));
  const tx = w / 2 - k * (b[0][0] + b[1][0]) / 2;
  const ty = haut + (h - haut - bas) / 2 - k * (b[0][1] + b[1][1]) / 2;
  return d3.zoomIdentity.translate(tx, ty).scale(k);
}

function allerA(niveau, resId = null, immediat = false) {
  S.niveau = niveau; S.resId = resId;
  const deps = S.geo.deps.features;
  const sud = deps.filter(f => DEPS_INLI[f.properties.code]).concat(S.geo.regions.features.filter(f => f.properties.code === '76'));
  const cible = niveau === 'france' ? deps : niveau === 'occitanie' ? sud : S.geo.metro.features;
  const t = cadrage(cible, niveau === 'france' ? 30 : 40);
  S.t = t;
  S.gLab.selectAll('*').remove();
  cacherBulle();
  const tr = S.gMonde.transition().duration(immediat || matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 950).ease(d3.easeCubicInOut)
    .attr('transform', t.toString());
  S.gMonde.select('.region-occ').transition().duration(600).attr('opacity', niveau === 'occitanie' ? 1 : niveau === 'france' ? .45 : 0);
  S.gCommunes.transition().duration(700).attr('opacity', niveau === 'metropole' || niveau === 'residence' ? 1 : 0);
  S.gMonde.selectAll('.dep').classed('actif', d => d.properties.code === DEP_ACTIF && (niveau === 'france' || niveau === 'occitanie'));
  tr.end().catch(() => {}).then(() => { if (S.niveau === niveau) etiquettes(niveau); });
  if (immediat) etiquettes(niveau);
  $('#facades').hidden = niveau !== 'residence';
  rendreFil();
  rendreLegende();
  rendreVolet();
  if (niveau === 'residence') rendreFacades(resId);
}

function projeter(lonlat) { const p = S.proj(lonlat); return S.t.apply(p); }

function etiquettes(niveau) {
  const g = S.gLab; g.selectAll('*').remove();
  const P = S.parc;
  if (niveau === 'france' || niveau === 'occitanie') {
    for (const f of S.geo.deps.features) {
      const c = f.properties.code; if (!DEPS_INLI[c]) continue;
      const [x, y] = projeter(d3.geoCentroid(f));
      const actif = c === DEP_ACTIF;
      const lab = g.append('g').attr('transform', `translate(${x},${y})`).style('pointer-events', 'none');
      if (niveau === 'france') {
        lab.append('text').attr('class', `etiquette${actif ? ' forte claire' : ''}`).attr('text-anchor', 'middle').attr('y', actif ? -2 : 4).text(c);
      } else {
        lab.append('text').attr('class', `etiquette forte${actif ? ' claire' : ''}`).attr('text-anchor', 'middle').attr('y', -4).text(DEPS_INLI[c]);
        lab.append('text').attr('class', `etiquette${actif ? ' claire' : ''}`).attr('text-anchor', 'middle').attr('y', 13)
          .text(actif ? `${fmt(P.meta.nb_logements)} logements à l'écoute` : 'au prochain import');
      }
    }
    if (niveau === 'occitanie') {
      const occ = S.geo.regions.features.find(f => f.properties.code === '76');
      const [x, y] = projeter([3.2, 44.25]);
      g.append('text').attr('class', 'etiquette forte').attr('x', x).attr('y', y).attr('text-anchor', 'middle').text('Occitanie');
      const [x2, y2] = projeter([-0.2, 45.6]);
      g.append('text').attr('class', 'etiquette').attr('x', x2).attr('y', y2).attr('text-anchor', 'middle').text('Nouvelle-Aquitaine');
      void occ;
    }
  }
  if (niveau === 'metropole' || niveau === 'residence') {
    const tlse = S.geo.metro.features.find(f => f.properties.code === '31555');
    if (tlse) {
      const [x, y] = projeter(d3.geoCentroid(tlse));
      g.append('text').attr('class', 'etiquette').attr('x', x + 14).attr('y', y - 34).text('Toulouse');
    }
    const rmax = Math.max(...P.residences.map(r => r.nb_logements));
    const el = $('#carte').getBoundingClientRect();
    const echelle = Math.max(.7, Math.min(1.25, Math.min(el.width, el.height) / 640));
    for (const r of P.residences) {
      const [x, y] = projeter(POSITIONS[r.id]);
      const cote = (22 + 30 * Math.sqrt(r.nb_logements / rmax)) * echelle;
      const gr = g.append('g').attr('class', 'res-glyphe').attr('transform', `translate(${x},${y})`)
        .attr('tabindex', 0).attr('role', 'button').attr('aria-label', `${r.nom}, ${r.nb_logements} logements, ${r.lgt_alerte} à visiter`)
        .on('click', () => allerA('residence', r.id))
        .on('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); allerA('residence', r.id); } })
        .on('mousemove', ev => montrerBulle(ev, `<b>${esc(r.nom)}</b> · ${r.annee}<br>${fmt(r.nb_logements)} logements · ${esc(r.chauffage)}<br>${r.eq_alerte} équipements à visiter, ${r.eq_vigilance} à surveiller`))
        .on('mouseleave', cacherBulle);
      // le socle : un carré de plan dont la base se remplit de la part d'équipements en préavis
      const part = r.lgt_alerte / r.nb_logements, partV = r.lgt_vigilance / r.nb_logements;
      gr.append('rect').attr('class', 'socle').attr('x', -cote / 2).attr('y', -cote / 2).attr('width', cote).attr('height', cote).attr('rx', 2);
      const hA = Math.max(r.lgt_alerte ? 2 : 0, (cote - 2) * part);
      const hV = Math.min(cote - 2 - hA, Math.max(r.lgt_vigilance ? 2 : 0, (cote - 2) * partV));
      gr.append('rect').attr('x', -cote / 2 + 1).attr('y', cote / 2 - 1 - hA - hV).attr('width', cote - 2).attr('height', hV).attr('fill', 'var(--vigilance)');
      gr.append('rect').attr('x', -cote / 2 + 1).attr('y', cote / 2 - 1 - hA).attr('width', cote - 2).attr('height', hA).attr('fill', 'var(--alerte)');
      gr.append('text').attr('class', 'lettre').attr('y', -cote * .12).style('font-size', `${cote * .5}px`).text(r.lettre);
      gr.append('text').attr('class', 'etiquette forte').attr('x', cote / 2 + 8).attr('y', -4).text(`${fmt(r.nb_logements)} logements`);
      gr.append('text').attr('class', 'etiquette').attr('x', cote / 2 + 8).attr('y', 13)
        .text(r.lgt_alerte ? `${r.lgt_alerte} logement${r.lgt_alerte > 1 ? 's' : ''} à visiter` : r.eq_alerte ? `${r.eq_alerte} équipement${r.eq_alerte > 1 ? 's' : ''} commun${r.eq_alerte > 1 ? 's' : ''} à visiter` : 'rien d’urgent');
    }
  }
}

function rendreFil() {
  const etapes = [['france', 'France'], ['occitanie', 'Occitanie'], ['metropole', 'Métropole toulousaine']];
  if (S.niveau === 'residence') etapes.push(['residence', S.res.get(S.resId).nom]);
  const ordre = ['france', 'occitanie', 'metropole', 'residence'];
  const ici = ordre.indexOf(S.niveau);
  $('#fil').innerHTML = etapes.filter(([n]) => ordre.indexOf(n) <= ici)
    .map(([n, lib], i) => `${i ? '<span class="sep">›</span>' : ''}<button data-niveau="${n}" ${n === S.niveau ? 'aria-current="true"' : ''}>${esc(lib)}</button>`).join('');
  $('#fil').querySelectorAll('button').forEach(b => b.addEventListener('click', () => { if (b.dataset.niveau !== S.niveau) allerA(b.dataset.niveau, S.resId); }));
}

function rendreLegende() {
  const L = $('#legende');
  if (S.niveau === 'france' || S.niveau === 'occitanie') {
    L.innerHTML = `<span><i class="pastille" style="background:var(--encre)"></i>À l'écoute</span><span><i class="pastille attente"></i>Rejoint Préavis au prochain import</span>`;
  } else if (S.niveau === 'metropole') {
    L.innerHTML = `<span><i class="pastille alerte"></i>Part des logements à visiter</span><span><i class="pastille vigilance"></i>À surveiller</span><span>Positions fictives : le kit ne donne aucune adresse</span>`;
  } else {
    L.innerHTML = `<span><i class="pastille alerte"></i>À visiter</span><span><i class="pastille vigilance"></i>À surveiller</span><span><i class="pastille calme"></i>Calme</span><span>● demandes répétées du locataire</span>`;
  }
}

/* ——— volet de droite ——— */
function barreRisque(a, v, total) {
  return `<span class="barre-risque" aria-hidden="true"><i class="a" style="width:${(a / total) * 100}%"></i><i class="v" style="width:${(v / total) * 100}%"></i></span>`;
}

function rendreVolet() {
  const P = S.parc, M = P.meta, V = $('#volet');
  const lgtA = P.logements.filter(l => l.niveau === 'alerte').length;
  const lgtV = P.logements.filter(l => l.niveau === 'vigilance').length;
  if (S.niveau === 'france' || S.niveau === 'occitanie') {
    const part = M.nb_logements / M.parc_annonce;
    const autres = M.parc_annonce - M.nb_logements;
    V.innerHTML = `
      <h1>${S.niveau === 'france' ? 'Le parc In’li Sud-Ouest' : 'De l’Occitanie à l’Atlantique'}</h1>
      <p class="phrase">Environ ${fmt(M.parc_annonce)} logements sur cinq départements. Les ${fmt(M.nb_logements)} logements de la métropole toulousaine sont déjà à l'écoute : leurs équipements y donnent leur préavis.</p>
      <div class="jauge-parc"><div class="rail"><div class="plein" style="width:${part * 100}%"></div></div>
        <div class="legendes"><span>${fmt(M.nb_logements)} à l'écoute</span><span>≈ ${fmt(autres)} au prochain import</span></div></div>
      <p style="margin-top:20px"><button class="btn" data-aller="${S.niveau === 'france' ? 'occitanie' : 'metropole'}">${S.niveau === 'france' ? 'Descendre vers l’Occitanie' : 'Descendre vers Toulouse'}</button></p>
      <h2>Les cinq départements</h2>
      <ul class="liste-zones">
        ${Object.entries(DEPS_INLI).map(([c, nom]) => c === DEP_ACTIF
          ? `<li><button data-aller="${S.niveau === 'france' ? 'occitanie' : 'metropole'}"><span class="nom">${nom} (${c})</span><span class="nb">${fmt(M.nb_logements)}</span>
              <span class="detail">8 résidences · <b class="alerte-t">${lgtA} logements à visiter</b>, ${lgtV} à surveiller</span>${barreRisque(lgtA, lgtV, M.nb_logements)}</button></li>`
          : `<li><div class="ligne"><span class="nom">${nom} (${c})</span><span class="nb attente">—</span><span class="detail attente">Ses logements rejoignent Préavis avec le prochain import trimestriel.</span></div></li>`).join('')}
      </ul>`;
  } else if (S.niveau === 'metropole') {
    const eqLgtA = P.equipements.filter(e => e.niveau === 'alerte' && e.lgt).length;
    const res = [...P.residences].sort((a, b) => b.eq_alerte - a.eq_alerte || b.eq_vigilance - a.eq_vigilance);
    V.innerHTML = `
      <h1>Métropole toulousaine</h1>
      <p class="phrase">D'ici le 30 septembre 2026, <b class="alerte-t">${M.nb_alerte} équipements</b> donnent leur préavis : ${eqLgtA} dans <b>${lgtA} logements</b>, ${M.nb_alerte - eqLgtA} dans les parties communes. ${M.nb_vigilance} autres sont à surveiller.</p>
      <p>Chaque carré est une résidence, à l'échelle de son nombre de logements. Sa base se remplit à proportion de ses logements à visiter (rouge) et à surveiller (ambre).</p>
      <p style="margin-top:16px"><a class="btn" href="#/lundi" style="text-decoration:none;display:inline-block">Ouvrir la file du lundi matin</a></p>
      <h2>Les huit résidences</h2>
      <ul class="liste-zones">
        ${res.map(r => `<li><button data-res="${r.id}"><span class="nom">${esc(r.nom)}</span><span class="nb">${fmt(r.nb_logements)}</span>
          <span class="detail">${r.annee} · ${esc(r.chauffage)}<br><b class="alerte-t">${r.eq_alerte} à visiter</b> · ${r.eq_vigilance} à surveiller · ${r.pannes_par_an['2025']} pannes bloquantes en 2025</span>
          ${barreRisque(r.eq_alerte, r.eq_vigilance, r.eq_suivis)}</button></li>`).join('')}
      </ul>`;
  } else {
    const r = S.res.get(S.resId);
    const eqs = P.equipements.filter(e => e.res === r.id && e.niveau !== 'calme').slice(0, 12);
    const reps = P.logements.filter(l => l.res === r.id && l.repetition).sort((a, c) => c.repetition.n - a.repetition.n || c.score - a.score).slice(0, 8);
    const p = r.pannes_par_an;
    V.innerHTML = `
      <h1>${esc(r.nom)}</h1>
      <p>${r.annee} · ${r.nb_batiments} bâtiments · ${fmt(r.nb_logements)} logements · ${esc(r.chauffage)} · eau chaude : ${esc(r.ecs)}</p>
      <p class="phrase">${r.eq_alerte ? `<b class="alerte-t">${r.eq_alerte} équipement${r.eq_alerte > 1 ? 's' : ''} à visiter</b> avant qu'ils ne lâchent, ${r.eq_vigilance} à surveiller.` : `Rien d'urgent ici : ${r.eq_vigilance} équipements à surveiller.`}</p>
      ${sparkPannes(p)}
      <h2>Par où commencer</h2>
      ${eqs.length ? eqs.map(ligneEquipement).join('') : '<p>Aucun équipement ne donne de préavis dans cette résidence.</p>'}
      ${reps.length ? `<h2>Les locataires qui redemandent</h2>
      <p>Même sujet demandé au moins deux fois en 24 mois : un signal de priorité, à croiser avec le score.</p>
      <ul class="liste-zones">${reps.map(l => `<li><button data-lgt="${l.id}"><span class="nom">Logement ${court(l.id)}</span><span class="nb">${l.repetition.n}×</span>
        <span class="detail">« ${esc(l.repetition.objet)} » · ${NIVEAU[l.niveau].toLowerCase()}${l.score ? ` (score ${Math.round(l.score)})` : ''}</span></button></li>`).join('')}</ul>` : ''}`;
  }
  V.querySelectorAll('[data-aller]').forEach(b => b.addEventListener('click', () => allerA(b.dataset.aller)));
  V.querySelectorAll('[data-res]').forEach(b => b.addEventListener('click', () => allerA('residence', b.dataset.res)));
  V.querySelectorAll('[data-eq]').forEach(b => b.addEventListener('click', () => ouvrirDepuisEquipement(b.dataset.eq)));
  V.querySelectorAll('[data-lgt]').forEach(b => b.addEventListener('click', () => ouvrirLogement(b.dataset.lgt)));
}

function sparkPannes(p) {
  const ans = Object.keys(p).sort(); const max = Math.max(...ans.map(a => p[a]), 1);
  return `<div style="margin-top:16px"><div style="display:flex;gap:4px;align-items:flex-end;height:46px">${ans.map(a =>
    `<div title="${a} : ${p[a]} pannes bloquantes" style="flex:1;background:${a === '2025' ? 'var(--encre)' : 'var(--calme)'};height:${Math.max(2, (p[a] / max) * 46)}px;border-radius:1px"></div>`).join('')}</div>
    <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--encre-3);margin-top:4px"><span>${ans[0]}</span><span>pannes bloquantes par an</span><span>${ans[ans.length - 1]}</span></div></div>`;
}

function lieuEquipement(e) {
  const r = S.res.get(e.res);
  if (e.lgt) { const l = S.lgt.get(e.lgt); return `${r.nom} · bât. ${court(e.bat)} · logt ${court(e.lgt)} · ${etageFr(l.etage)}`; }
  return `${r.nom} · bâtiment ${court(e.bat)} · parties communes`;
}

function ligneEquipement(e) {
  return `<button class="eq-ligne" data-eq="${e.id}"><span class="score-bloc ${e.niveau}">${Math.round(e.score)}</span>
    <span class="titre">${esc(e.lib)}</span><span class="lieu">${esc(lieuEquipement(e))}</span>
    <span class="pourquoi">${esc(e.raisons[0]?.texte || '')}</span></button>`;
}

/* ——— façades d'une résidence ——— */
function rendreFacades(resId) {
  const r = S.res.get(resId);
  const bats = S.parc.batiments.filter(b => b.res === resId);
  const F = $('#facades');
  const parBat = d3.group(S.parc.logements.filter(l => l.res === resId), l => l.bat);
  const html = bats.map(b => {
    const lgts = parBat.get(b.id) || [];
    const parEtage = d3.group(lgts, l => +l.etage);
    const etages = [...parEtage.keys()].sort((a, c) => c - a);
    const eqB = (b.eq || []).map(id => S.eq.get(id)).filter(Boolean);
    const asc = eqB.find(e => e.fam === 'ascenseur');
    const vmc = eqB.filter(e => e.fam === 'caisson_vmc');
    const bas = eqB.filter(e => e.fam === 'chaufferie_collective' || e.fam === 'production_ecs_solaire');
    const bouton = (e, cls) => `<button class="equip-commun ${cls} ${e.niveau}" data-eq="${e.id}" aria-label="${esc(e.lib)}, ${NIVEAU[e.niveau]}"></button>`;
    return `<div class="batiment">
      <div class="toit">${vmc.map(e => bouton(e, 'vmc')).join('')}</div>
      <div class="corps">
        ${asc ? `<div class="colonne-asc">${bouton(asc, 'asc')}</div>` : ''}
        <div class="etages">${etages.map(et => `<div class="etage">${parEtage.get(et).sort((a, c) => a.id.localeCompare(c.id)).map(l =>
          `<button class="fenetre ${l.niveau}${l.repetition ? ' repete' : ''}" data-lgt="${l.id}" aria-label="Logement ${court(l.id)}, ${NIVEAU[l.niveau]}"></button>`).join('')}</div>`).join('')}</div>
      </div>
      <div class="sous-sol">${bas.map(e => bouton(e, e.fam === 'chaufferie_collective' ? 'chaufferie' : 'solaire')).join('')}</div>
      <div class="nom-bat">Bâtiment ${court(b.id)}</div>
    </div>`;
  }).join('');
  const sc = $('.scene').getBoundingClientRect();
  const maxEt = d3.max(bats, b => d3.group((parBat.get(b.id) || []), l => +l.etage).size) || 1;
  const largeurs = d3.sum(bats, b => d3.max([...d3.group((parBat.get(b.id) || []), l => +l.etage).values()], v => v.length) || 1);
  const f = Math.max(12, Math.min(34, (sc.height - 300) / (maxEt * 1.35), (sc.width - 80 - bats.length * 60) / (largeurs * 1.3)));
  F.style.setProperty('--f', `${f}px`);
  F.innerHTML = `<p class="facades-titre">${esc(r.nom)} en élévation : une fenêtre par logement, rangée à son étage. Les équipements communs sont à leur place : ventilation sur le toit, ascenseur dans sa gaine, chaufferie au sous-sol.</p>
    <div class="rue">${html}</div>
    <p class="note">Touchez une fenêtre pour ouvrir la vie du logement.</p>`;
  F.querySelectorAll('.fenetre').forEach(b => {
    const l = S.lgt.get(b.dataset.lgt);
    b.addEventListener('click', () => ouvrirLogement(l.id));
    b.addEventListener('mousemove', ev => {
      const top = l.eq.map(id => S.eq.get(id)).filter(Boolean).sort((a, c) => c.score - a.score)[0];
      montrerBulle(ev, `<b>Logement ${court(l.id)}</b> · ${l.typo} · ${etageFr(l.etage)}<br>${top ? `${esc(top.lib)} : ${NIVEAU[top.niveau].toLowerCase()} (${Math.round(top.score)})` : 'Aucun équipement suivi'}${l.repetition ? `<br>« ${esc(l.repetition.objet)} » demandé ${l.repetition.n} fois` : ''}`);
    });
    b.addEventListener('mouseleave', cacherBulle);
  });
  F.querySelectorAll('.equip-commun').forEach(b => {
    const e = S.eq.get(b.dataset.eq);
    b.addEventListener('click', () => ouvrirEquipementCommun(e.id));
    b.addEventListener('mousemove', ev => montrerBulle(ev, `<b>${esc(e.lib)}</b> · bâtiment ${court(e.bat)}<br>${NIVEAU[e.niveau]} (${Math.round(e.score)}) · ${esc(e.raisons[0]?.texte || '')}`));
    b.addEventListener('mouseleave', cacherBulle);
  });
}

/* ——— fiche ——— */
function ouvrirDepuisEquipement(eqId) {
  const e = S.eq.get(eqId);
  if (e.lgt) ouvrirLogement(e.lgt, eqId); else ouvrirEquipementCommun(eqId);
}

function fermerFiche() {
  $('#fiche').hidden = true; $('#fiche-voile').hidden = true;
  if (S.retourFocus) S.retourFocus.focus?.();
  if (!$('#ecran-lundi').hidden) rendreLundi(true);
}

function ouvrirFicheAvec(html) {
  S.retourFocus = document.activeElement;
  const F = $('#fiche');
  F.innerHTML = `<button class="fermer" type="button">Fermer</button>${html}`;
  F.hidden = false; $('#fiche-voile').hidden = false;
  F.scrollTop = 0;
  F.querySelector('.fermer').addEventListener('click', fermerFiche);
  $('#fiche-voile').onclick = fermerFiche;
  F.querySelector('.fermer').focus();
  cacherBulle();
}

function carteEquipement(e) {
  const max = Math.max(...e.raisons.map(r => Math.abs(r.points)), 1);
  const d = S.dec[e.id]?.choix;
  const reco = e.niveau === 'alerte' ? 'programmer une visite' : e.niveau === 'vigilance' ? 'le garder à l’œil' : 'rien pour l’instant';
  return `<div class="equip-carte" data-carte="${e.id}">
    <span class="score-bloc ${e.niveau}" title="Score de risque sur 100">${Math.round(e.score)}</span>
    <span class="nom">${esc(e.lib)} <span style="font-weight:400;color:var(--encre-2)">· ${NIVEAU[e.niveau]}</span></span>
    <span class="meta">Pose : ${dateFr(e.pose)} · ${fmt1(e.age)} ans sur ${e.duree_vie} · ${esc(e.presta_nom)}${e.contrat === 'Oui' ? ', sous contrat' : ''} · rang ${e.rang} sur ${fmt(S.parc.meta.nb_equipements_suivis)}</span>
    <ul class="raisons">${e.raisons.map(r => `<li><span>${esc(r.texte)}</span><span class="pts" title="${fmt1(r.points)} points"><i class="${r.points < 0 ? 'neg' : ''}" style="width:${(Math.abs(r.points) / max) * 100}%"></i></span></li>`).join('') || '<li><span>Aucun signal : l’appareil est jeune et silencieux.</span><span></span></li>'}</ul>
    <span class="recommande">Préavis recommande : ${reco}. La décision vous revient.</span>
    <div class="decision">${Object.entries(DECISIONS).map(([k, v]) => `<button type="button" data-choix="${k}" aria-pressed="${d === k}">${v.lib}</button>`).join('')}
      <span class="etat">${d ? `${DECISIONS[d].fait} le ${dateFr(S.dec[e.id].le)}` : ''}</span></div>
  </div>`;
}

function brancherDecisions(racine) {
  racine.querySelectorAll('[data-carte]').forEach(c => {
    c.querySelectorAll('[data-choix]').forEach(b => b.addEventListener('click', () => {
      decider(c.dataset.carte, b.dataset.choix);
      const e = S.eq.get(c.dataset.carte);
      const neuf = document.createElement('div'); neuf.innerHTML = carteEquipement(e);
      c.replaceWith(neuf.firstElementChild);
      brancherDecisions(racine);
    }));
  });
}

async function ouvrirLogement(lgtId, focusEq) {
  const l = S.lgt.get(lgtId); const r = S.res.get(l.res);
  const eqs = l.eq.map(id => S.eq.get(id)).filter(Boolean).sort((a, b) => b.score - a.score);
  const b = S.bat.get(l.bat);
  const communs = (b?.eq || []).map(id => S.eq.get(id)).filter(e => e && e.niveau !== 'calme');
  const top = eqs[0];
  const verdict = !top ? 'Aucun équipement suivi dans ce logement.'
    : top.niveau === 'alerte' ? `${top.lib} à visiter en priorité. Signal le plus fort : ${minus1(top.raisons[0]?.texte || 'usure')}.`
    : top.niveau === 'vigilance' ? `${top.lib} à surveiller. Rien ne presse, mais un signal apparaît : ${minus1(top.raisons[0]?.texte || '')}.`
    : 'Rien ne s’annonce d’ici fin septembre 2026 sur les équipements suivis.';
  ouvrirFicheAvec(`
    <h1>Logement ${court(l.id)}</h1>
    <p class="sous">${esc(r.nom)} · bâtiment ${court(l.bat)} · ${etageFr(l.etage)} · ${l.typo} · ${fmt1(l.surface)} m²</p>
    <p class="verdict">${esc(verdict)}</p>
    <div class="faits">
      <span>Locataire entré : <b>${l.entree === 'Avant 2018' ? 'avant 2018' : dateFr(l.entree)}</b></span>
      <span>Changements de locataire depuis 2018 : <b>${l.rotations}</b></span>
      <span>Demandes depuis 2019 : <b>${l.demandes_total}</b>${l.demandes_reouvertes ? `, dont ${l.demandes_reouvertes} rouvertes` : ''}</span>
      <span>DPE : <b>${l.dpe}</b> (${l.conso} kWh/m²/an)</span>
    </div>
    <h2>La vie du logement <small>de 2018 au préavis de septembre 2026</small></h2>
    <div id="vie"><p class="sous">Chargement de l'historique…</p></div>
    <h2>Ce qui s'annonce <small>score sur 100 et ses raisons</small></h2>
    ${eqs.map(carteEquipement).join('') || '<p class="sous">Aucun équipement suivi.</p>'}
    ${communs.length ? `<h2>Dans les parties communes <small>bâtiment ${court(l.bat)}</small></h2>${communs.map(carteEquipement).join('')}` : ''}
    <h2>Ce que dit le locataire <small id="dem-compte"></small></h2>
    <div id="demandes"></div>`);
  brancherDecisions($('#fiche'));
  if (focusEq) $(`[data-carte="${focusEq}"]`)?.scrollIntoView({ block: 'center' });
  const J = await journal();
  if ($('#fiche').hidden) return;
  const dem = J.demandes[l.id] || [];
  dessinerVie($('#vie'), [{ nom: 'Demandes du locataire', demandes: dem }, ...eqs.map(e => ({ nom: e.lib, eq: e, inter: J.interventions[e.id] || [] }))]);
  rendreDemandes(dem);
}

async function ouvrirEquipementCommun(eqId) {
  const e = S.eq.get(eqId); const r = S.res.get(e.res);
  ouvrirFicheAvec(`
    <h1>${esc(e.lib)}</h1>
    <p class="sous">${esc(r.nom)} · bâtiment ${court(e.bat)} · parties communes · ${S.bat.get(e.bat).nb_logements} logements desservis</p>
    <h2>La vie de l'équipement <small>de 2018 au préavis de septembre 2026</small></h2>
    <div id="vie"><p class="sous">Chargement de l'historique…</p></div>
    <h2>Ce qui s'annonce</h2>
    ${carteEquipement(e)}
    <h2>Ce que disent les locataires du bâtiment <small id="dem-compte"></small></h2>
    <div id="demandes"></div>`);
  brancherDecisions($('#fiche'));
  const J = await journal();
  if ($('#fiche').hidden) return;
  const dem = J.demandes_communes[e.bat] || [];
  dessinerVie($('#vie'), [{ nom: 'Demandes (parties communes)', demandes: dem }, { nom: e.lib, eq: e, inter: J.interventions[e.id] || [] }]);
  rendreDemandes(dem);
}

function rendreDemandes(dem) {
  const parObjet = d3.rollup(dem, v => v.length, d => d[1]);
  const vus = new Map();
  const items = dem.map(d => { const n = (vus.get(d[1]) || 0) + 1; vus.set(d[1], n); return { d, n, total: parObjet.get(d[1]) }; }).reverse();
  const repetes = [...parObjet.values()].filter(n => n > 1).length;
  $('#dem-compte').textContent = dem.length ? `${dem.length} demande${dem.length > 1 ? 's' : ''}${repetes ? `, ${repetes} sujet${repetes > 1 ? 's' : ''} qui revien${repetes > 1 ? 'nent' : 't'}` : ''}` : '';
  $('#demandes').innerHTML = dem.length ? `<ul class="demandes">${items.map(({ d, n, total }) => `<li>
      <span class="d">${dateFr(d[0])}</span>
      <span><span class="objet">${esc(d[1])}</span>${total > 1 ? `<span class="marque-rep">${n === 1 ? '1re' : `${n}e`} fois sur ${total}</span>` : ''}${d[5] === 'Oui' ? '<span class="reouv">rouverte</span>' : ''}</span>
      <span class="texte">${esc(d[3])}</span></li>`).join('')}</ul>` : '<p class="sous">Aucune demande enregistrée depuis février 2019.</p>';
}

/* ——— frise de vie ——— */
const MOTS_USURE = /usure|vieillissant|provisoire|difficile|corrosion|redémarrages|défaillance|irréparable|hors service/i;
function dessinerVie(el, couloirs) {
  const W = Math.max(320, el.getBoundingClientRect().width || 700);
  const etroit = W < 560;
  const gauche = etroit ? 8 : 205, droite = 12, hC = etroit ? 40 : 30, haut = 22;
  const H = haut + couloirs.length * hC + 30;
  // le passé est compressé, les neuf mois du préavis sont dilatés : c'est là que se joue la décision
  const coude = gauche + (W - droite - gauche) * .78;
  const x = d3.scaleTime().domain([new Date(2018, 0, 1), new Date(2026, 0, 1), new Date(2026, 8, 30)]).range([gauche, coude, W - droite]).clamp(true);
  const svg = d3.create('svg').attr('class', 'vie').attr('viewBox', `0 0 ${W} ${H}`).attr('width', W).attr('height', H);
  const debutH = x(new Date(2026, 0, 1)), finH = x(new Date(2026, 8, 30));
  svg.append('rect').attr('class', 'horizon').attr('x', debutH).attr('y', haut - 8).attr('width', finH - debutH).attr('height', H - haut - 14);
  svg.append('text').attr('class', 'horizon-txt').attr('x', etroit ? finH : (debutH + finH) / 2).attr('y', haut - 11)
    .attr('text-anchor', etroit ? 'end' : 'middle').text(etroit ? 'préavis 2026' : 'préavis : janv. → sept. 2026');
  for (let a = 2018; a <= 2026; a++) {
    const xa = x(new Date(a, 0, 1));
    svg.append('line').attr('class', 'grille').attr('x1', xa).attr('x2', xa).attr('y1', haut - 4).attr('y2', H - 22);
    svg.append('text').attr('class', 'an').attr('x', xa + 2).attr('y', H - 8).text(a === 2026 ? '' : etroit && a % 2 ? '' : a);
  }
  svg.append('line').attr('class', 'aujourdhui').attr('x1', debutH).attr('x2', debutH).attr('y1', haut - 8).attr('y2', H - 22);
  couloirs.forEach((c, i) => {
    const y0 = haut + i * hC, yc = y0 + hC / 2 + (etroit ? 6 : 0);
    svg.append('line').attr('x1', gauche).attr('x2', debutH).attr('y1', yc).attr('y2', yc).attr('stroke', 'var(--papier-3)');
    svg.append('text').attr('class', 'couloir-nom').attr('x', etroit ? gauche : gauche - 10).attr('y', etroit ? y0 + 8 : yc + 4)
      .attr('text-anchor', etroit ? 'start' : 'end').text(c.nom.length > 31 && !etroit ? `${c.nom.slice(0, 30)}…` : c.nom);
    const g = svg.append('g');
    if (c.demandes) {
      const vus = new Map();
      for (const d of c.demandes) {
        const n = (vus.get(d[1]) || 0) + 1; vus.set(d[1], n);
        const xd = x(new Date(d[0].replace(' ', 'T')));
        const ci = g.append('circle').attr('cx', xd).attr('cy', yc).attr('r', n > 1 ? 5 : 3.5)
          .attr('fill', n > 1 ? 'var(--encre)' : 'var(--blanc)').attr('stroke', d[5] === 'Oui' ? 'var(--alerte)' : 'var(--encre)').attr('stroke-width', 1.4);
        ci.append('title').text(`${dateFr(d[0])} · ${d[1]}${n > 1 ? ` (${n}e fois)` : ''}${d[5] === 'Oui' ? ' · rouverte' : ''}`);
      }
    } else {
      for (const it of c.inter) {
        const [date, type, sympt, grav, res, comm] = it;
        const xd = x(new Date(date.replace(' ', 'T')));
        const titre = `${dateFr(date)} · ${type}${sympt ? ` · ${sympt}` : ''}${grav ? ` · ${grav}` : ''} · ${res}${comm ? ` · « ${comm} »` : ''}`;
        let m;
        if (type === 'Remplacement') m = g.append('rect').attr('x', xd - 1.5).attr('y', yc - 10).attr('width', 3).attr('height', 20).attr('fill', 'var(--encre)');
        else if (type === 'Dépannage') {
          const col = grav === 'Arrêt total' ? 'var(--alerte)' : grav === 'Fonctionnement dégradé' ? 'var(--vigilance)' : 'var(--calme-fonce)';
          m = g.append('circle').attr('cx', xd).attr('cy', yc).attr('r', grav === 'Arrêt total' ? 5.5 : 4).attr('fill', col)
            .attr('stroke', MOTS_USURE.test(comm) ? 'var(--encre)' : 'none').attr('stroke-width', 1.6);
        } else if (res.startsWith('Logement absent')) m = g.append('circle').attr('cx', xd).attr('cy', yc).attr('r', 3).attr('fill', 'none').attr('stroke', 'var(--encre-3)').attr('stroke-dasharray', '1.5 1.5');
        else m = g.append('line').attr('x1', xd).attr('x2', xd).attr('y1', yc - 5).attr('y2', yc + 5).attr('stroke', res === 'Anomalie constatée' || res === 'Remplacement nécessaire' ? 'var(--alerte)' : 'var(--calme-fonce)').attr('stroke-width', 1.5);
        m.append('title').text(titre);
      }
      const e = c.eq;
      const col = e.niveau === 'alerte' ? 'var(--alerte)' : e.niveau === 'vigilance' ? 'var(--vigilance)' : 'var(--calme)';
      svg.append('rect').attr('x', debutH + 3).attr('y', yc - 7).attr('width', Math.max(6, (finH - debutH - 6) * Math.min(1, e.score / 100))).attr('height', 14).attr('fill', col).attr('rx', 1)
        .append('title').text(`Score ${Math.round(e.score)} sur 100 · ${NIVEAU[e.niveau]}`);
    }
  });
  el.innerHTML = '';
  el.append(svg.node());
  const sym = (svg, lib) => `<span class="cle"><svg width="14" height="14" viewBox="-7 -7 14 14" aria-hidden="true">${svg}</svg>${lib}</span>`;
  const leg = document.createElement('div');
  leg.className = 'cles';
  leg.innerHTML = [
    sym('<circle r="5.5" fill="var(--alerte)"/>', 'arrêt total'),
    sym('<circle r="4" fill="var(--vigilance)"/>', 'fonctionnement dégradé'),
    sym('<circle r="4" fill="var(--calme-fonce)"/>', 'gêne mineure'),
    sym('<circle r="4" fill="var(--vigilance)" stroke="var(--encre)" stroke-width="1.6"/>', 'note d’usure du technicien'),
    sym('<line y1="-5" y2="5" stroke="var(--calme-fonce)" stroke-width="1.5"/>', 'entretien'),
    sym('<line y1="-5" y2="5" stroke="var(--alerte)" stroke-width="1.5"/>', 'anomalie en visite'),
    sym('<circle r="3" fill="none" stroke="var(--encre-3)" stroke-dasharray="1.5 1.5"/>', 'locataire absent'),
    sym('<rect x="-1.5" y="-6" width="3" height="12" fill="var(--encre)"/>', 'remplacement'),
    sym('<circle r="3.5" fill="var(--blanc)" stroke="var(--encre)" stroke-width="1.4"/>', 'demande'),
    sym('<circle r="5" fill="var(--encre)"/>', 'demande qui revient'),
  ].join('');
  el.append(leg);
}

/* ——— lundi matin ——— */
function rendreLundi(garderFiltres) {
  const P = S.parc, perf = P.performance, M = P.meta;
  const E = $('#ecran-lundi');
  const filtres = garderFiltres && S.filtres ? S.filtres : (S.filtres = S.filtres || { res: '', fam: '', masquer: false });
  const alertes = P.equipements.filter(e => e.niveau === 'alerte');
  const decides = alertes.filter(e => S.dec[e.id]).length;
  const familles = [...new Map(alertes.map(e => [e.fam, e.lib])).entries()];
  const liste = alertes.filter(e => (!filtres.res || e.res === filtres.res) && (!filtres.fam || e.fam === filtres.fam) && (!filtres.masquer || !S.dec[e.id]));
  E.innerHTML = `<div class="page">
    <h1>Lundi matin : ${M.nb_alerte} équipements donnent leur préavis.</h1>
    <p class="chapeau">Classés du plus pressant au moins pressant pour la période du 1er janvier au 30 septembre 2026. Chaque ligne dit pourquoi. Préavis recommande, vous décidez.</p>
    ${perf ? `<div class="preuve">
      <div class="duel"><div class="col"><div class="n">${perf.pannes_captees_top10}</div><div class="l">avec Préavis</div></div><div class="col base"><div class="n">${perf.pannes_captees_top10_age_seul}</div><div class="l">avec l'âge seul</div></div></div>
      <p>Mis à l'épreuve sur 2025 avec les seules données connues au 31/12/2024 : en visitant les ${perf.taille_top10} équipements désignés, on aurait trouvé <b>${perf.pannes_captees_top10} des ${perf.nb_pannes} pannes bloquantes</b> de janvier à septembre 2025, contre ${perf.pannes_captees_top10_age_seul} en suivant l'âge seul. Capacité à classer (AUC) : ${fmt2(perf.auc)} contre ${fmt2(perf.auc_age_seul)}.</p>
    </div>` : ''}
    <div class="outils">
      <label>Résidence <select id="f-res"><option value="">Toutes</option>${P.residences.map(r => `<option value="${r.id}" ${filtres.res === r.id ? 'selected' : ''}>${esc(r.nom)}</option>`).join('')}</select></label>
      <label>Équipement <select id="f-fam"><option value="">Tous</option>${familles.map(([f, lib]) => `<option value="${f}" ${filtres.fam === f ? 'selected' : ''}>${esc(lib)}</option>`).join('')}</select></label>
      <label><input type="checkbox" id="f-masquer" ${filtres.masquer ? 'checked' : ''}> Masquer ce qui est décidé</label>
      <span class="compte">${decides} décidé${decides > 1 ? 's' : ''} sur ${alertes.length}</span>
      <button class="btn" id="export-file">Exporter la file</button>
      <button class="btn discret" id="export-scores">Exporter les scores</button>
      <button class="btn discret" id="imprimer">Imprimer la tournée</button>
    </div>
    <ol class="file">${liste.map(e => {
      const d = S.dec[e.id]?.choix;
      return `<li class="${d ? 'decide' : ''}">
        <span class="rang">${e.rang}</span>
        <span class="score-bloc ${e.niveau}">${Math.round(e.score)}</span>
        <div><div class="quoi"><button data-eq="${e.id}">${esc(e.lib)}</button></div>
          <div class="ou">${esc(lieuEquipement(e))} · ${fmt1(e.age)} ans sur ${e.duree_vie}</div>
          <ul class="parce">${e.raisons.slice(0, 3).map(r => `<li>${esc(r.texte)}</li>`).join('')}</ul></div>
        <div class="choix" data-ligne="${e.id}">${Object.entries(DECISIONS).map(([k, v]) => `<button type="button" data-choix="${k}" aria-pressed="${d === k}">${d === k ? v.fait : v.lib}</button>`).join('')}</div>
      </li>`;
    }).join('') || '<li class="vide">Rien à décider avec ces filtres.</li>'}</ol>
    ${piedDonnees()}
  </div>`;
  const maj = () => rendreLundi(true);
  $('#f-res').addEventListener('change', ev => { S.filtres.res = ev.target.value; maj(); });
  $('#f-fam').addEventListener('change', ev => { S.filtres.fam = ev.target.value; maj(); });
  $('#f-masquer').addEventListener('change', ev => { S.filtres.masquer = ev.target.checked; maj(); });
  E.querySelectorAll('.quoi [data-eq]').forEach(b => b.addEventListener('click', () => ouvrirDepuisEquipement(b.dataset.eq)));
  E.querySelectorAll('[data-ligne]').forEach(c => c.querySelectorAll('[data-choix]').forEach(b => b.addEventListener('click', () => {
    const y = E.scrollTop; decider(c.dataset.ligne, b.dataset.choix); maj(); E.scrollTop = y;
  })));
  $('#export-file').addEventListener('click', exporterFile);
  $('#export-scores').addEventListener('click', exporterScores);
  $('#imprimer').addEventListener('click', () => window.print());
}

function telecharger(nom, texte) {
  const url = URL.createObjectURL(new Blob([texte], { type: 'text/csv;charset=utf-8' }));
  const a = Object.assign(document.createElement('a'), { href: url, download: nom });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const cellule = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
function exporterFile() {
  const lignes = [['rang', 'equipement_id', 'equipement', 'residence', 'batiment', 'logement', 'score', 'niveau', 'raisons', 'decision', 'decide_le']];
  for (const e of S.parc.equipements.filter(x => x.niveau !== 'calme')) {
    const d = S.dec[e.id];
    lignes.push([e.rang, e.id, e.lib, S.res.get(e.res).nom, e.bat, e.lgt || 'parties communes', String(e.score).replace('.', ','), NIVEAU[e.niveau],
      e.raisons.map(r => r.texte).join(' ; '), d ? DECISIONS[d.choix].fait : '', d ? d.le : '']);
  }
  telecharger(`preavis-file-${S.parc.meta.date_reference}.csv`, '﻿' + lignes.map(l => l.map(cellule).join(';')).join('\r\n'));
}
function exporterScores() {
  const lignes = ['equipement_id,score_risque', ...S.parc.equipements.map(e => `${e.id},${e.score}`)];
  telecharger(`preavis-scores-${S.parc.meta.date_reference}.csv`, lignes.join('\n'));
}

function piedDonnees() {
  const M = S.parc.meta;
  return `<div class="pied-donnees"><span>Données au ${dateFr(M.date_reference)} · ${fmt(M.nb_logements)} logements, ${fmt(M.nb_equipements_suivis)} équipements suivis · calcul du ${dateFr(M.genere_le)}</span>
    <span>Chaque trimestre : <b>./lancer.sh dossier-du-trimestre</b> relit vos fichiers et recalcule tout.</span></div>`;
}

/* ——— énergie ——— */
function rendreEnergie() {
  const P = S.parc, E = $('#ecran-energie');
  const n = et => P.logements.filter(l => l.dpe === et).length;
  const opsPar = d3.group(P.operations, o => o.residence_id);
  const res = [...P.residences].sort((a, b) => (b.dpe.G * 3 + b.dpe.F * 2 + b.dpe.E) - (a.dpe.G * 3 + a.dpe.F * 2 + a.dpe.E));
  E.innerHTML = `<div class="page">
    <h1>Énergie : les logements que la loi rattrape.</h1>
    <p class="chapeau">La loi Climat et résilience retire progressivement de la location les logements les plus énergivores. Une case par logement, à sa couleur de DPE. Les résidences les plus exposées viennent en premier.</p>
    <div class="calendrier">
      <div><div class="annee">2025</div><div class="quoi">Étiquette G : ne peut plus être louée</div><div class="combien"><b>${n('G')}</b> logements G dans le parc suivi</div></div>
      <div><div class="annee">2028</div><div class="quoi">Étiquette F à son tour</div><div class="combien"><b>${n('F')}</b> logements F</div></div>
      <div><div class="annee">2034</div><div class="quoi">Étiquette E à son tour</div><div class="combien"><b>${n('E')}</b> logements E</div></div>
    </div>
    <div class="legende-dpe">${'ABCDEFG'.split('').map(c => `<i class="dpe-${c}">${c}</i>`).join('')}<span style="margin-left:8px">étiquette globale du DPE de chaque logement</span></div>
    <div class="dpe-res">${res.map(r => {
      const lg = P.logements.filter(l => l.res === r.id).sort((a, b) => a.dpe.localeCompare(b.dpe) || b.conso - a.conso);
      const ops = (opsPar.get(r.id) || []).sort((a, b) => a.rang_actuel_chronologique - b.rang_actuel_chronologique);
      return `<div class="dpe-ligne">
        <div><div class="nom">${esc(r.nom)}</div><div class="meta">${r.annee} · ${esc(r.energie.toLowerCase())} · ${r.conso_moy} kWh/m²/an en moyenne<br>${r.pannes_par_an['2025']} pannes bloquantes en 2025 · ${r.eq_alerte} équipements à visiter</div></div>
        <div><div class="cases">${lg.map(l => `<i class="dpe-${l.dpe}" title="Logement ${court(l.id)} : ${l.dpe}, ${l.conso} kWh/m²/an"></i>`).join('')}</div>
          <div class="dpe-compte">${'ABCDEFG'.split('').filter(c => r.dpe[c]).map(c => `<span><b>${r.dpe[c]}</b> en ${c}</span>`).join('')}</div>
          ${ops.length ? `<ul class="ops">${ops.map(o => `<li><span>${esc(o.type_operation)} · souhaitée en ${o.annee_souhaitee}${o.gain_conso_ep_estime_kwh_m2_an ? ` · −${o.gain_conso_ep_estime_kwh_m2_an} kWh/m²/an` : ''}</span><span class="cout">${euros(o.cout_estime_ttc)} · ${ord(o.rang_actuel_chronologique)} dans la file actuelle</span></li>`).join('')}</ul>` : ''}
        </div></div>`;
    }).join('')}</div>
    <p class="chapeau" style="font-size:15px;color:var(--encre-2);margin-top:26px">Les opérations viennent du plan d'investissement hypothétique du kit (table 08), avec leur rang dans l'ordre d'arrivée actuel. Croiser ce rang avec l'exposition à la loi et les pannes de 2025 aide à décider quoi rénover d'abord.</p>
    ${piedDonnees()}
  </div>`;
}

demarrer().catch(err => {
  document.body.insertAdjacentHTML('beforeend', `<p style="position:fixed;bottom:10px;left:10px;background:#fff;padding:10px;border:1px solid #c00">Chargement impossible : ${esc(err.message)}. Lancez l'application avec ./lancer.sh.</p>`);
  console.error(err);
});
