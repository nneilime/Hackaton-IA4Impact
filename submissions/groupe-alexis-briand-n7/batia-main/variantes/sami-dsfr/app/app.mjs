// BâtIA — la carte est l'application : la file, les fiches et l'énergie se posent dessus.
import { creerCarte } from '/carte/carte.mjs';

// ── Outils ──────────────────────────────────────────────────────────
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const nb = (n) => new Intl.NumberFormat('fr-FR').format(n);
if (new URLSearchParams(location.search).get('tete') !== 'h2') document.body.classList.add('fiche-h3');
const euros = (n) => (n >= 1e6 ? `${nb(Math.round(n / 1e5) / 10)} M€` : `${nb(Math.round(n / 1000))} k€`);
const pl = (n, un, plusieurs) => `${nb(n)} ${n > 1 ? plusieurs : un}`;
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const sansAccent = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const MOIS_LONGS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const dateCourte = (iso) => { if (!iso) return ''; const [a, m, j] = iso.slice(0, 10).split('-'); return `${+j} ${MOIS[+m - 1]} ${a}`; };
// au-delà d'un trimestre, l'âge du relevé se montre
const ageReleve = (iso) => {
  const j = Math.floor((Date.now() - Date.parse(iso)) / 864e5);
  if (!(j > 92)) return '';
  const m = Math.round(j / 30.44);
  return m < 12 ? `${m} mois` : `${Math.floor(m / 12)} an${m >= 24 ? 's' : ''}`;
};
const dateLongue = (iso) => { if (!iso) return ''; const [a, m, j] = iso.slice(0, 10).split('-'); return `${+j === 1 ? '1er' : +j} ${MOIS_LONGS[+m - 1]} ${a}`; };
const etage = (n) => (n === 0 ? 'RDC' : n === 1 ? '1<sup>er</sup>' : `${n}<sup>e</sup>`);
const etageLong = (n) => (n === 0 ? 'rez-de-chaussée' : n === 1 ? '1<sup>er</sup> étage' : `${n}<sup>e</sup> étage`);
const numLogt = (id) => id.split('-').pop();
const bat = (id) => id.replace('BAT-', '');
const lettre = (rid) => rid.replace('RES-', '');
const telephone = () => matchMedia('(max-width: 760px)').matches;
const reduit = matchMedia('(prefers-reduced-motion: reduce)').matches || localStorage.getItem('foraine.animations') === 'reduites';
const ICONE_X = '<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';
const DPE = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
// Les couleurs viennent de la palette commune (palette.css) : G est le rouge d'« Urgent », A le vert de « Lancer ».
const COULEUR_DPE = Object.fromEntries(DPE.map((l) => [l, `var(--dpe-${l})`]));
const TEXTE_DPE = Object.fromEntries(DPE.map((l) => [l, `var(--sur-dpe-${l})`]));
const etiquette = (l) => `<span class="etiquette" style="background:${COULEUR_DPE[l] || '#999'};color:${TEXTE_DPE[l] || '#fff'}">${esc(l)}</span>`;
const CHOIX = { visite: { mot: 'Visite', fait: 'Visite décidée', touche: 'v', aide: 'envoyer le prestataire' }, remplacer: { mot: 'Remplacer', fait: 'Remplacement décidé', touche: 'r', aide: 'préparer la commande' }, 'plus-tard': { mot: 'Plus tard', fait: 'Remis à plus tard', touche: 'p', aide: 'écarter pour l’instant' } };
const NIVEAU = { visiter: 'À visiter', surveiller: 'À surveiller', calme: 'Calme' };
const COUT_DEPANNAGE = 250;
// Les catégories du barème (moteur/BAREME.md), en mots courts. Couleur vive seulement pour ce qui est à visiter.
const MOT_BANDE = { urgence: 'Urgent', alerte: 'Alerte', vigilance: 'Vigilance', surveiller: 'À surveiller', calme: 'Calme', ras: 'RAS' };
const VIVES = ['urgence', 'alerte', 'vigilance'];
const CRITERES = { reglementaire: 'Obligation légale', energie: 'Énergie par euro', maintenance: 'Pannes et dépenses', locataires: 'Demandes des locataires', finDeVie: 'Fin de vie' };

// ── État ────────────────────────────────────────────────────────────
const S = {
  d: null, decisions: {}, lentille: 'pannes', onglet: 'visiter', residence: null, famille: '', semaine: false, role: localStorage.getItem('foraine.role') || 'gestionnaire',
  sel: null, page: null, limite: 50, echelle: 'sudouest',
  seuil: localStorage.getItem('foraine.seuil') || 'E',
  feuille: 'basse', bande: '', annee: null,
};
const I = { equip: new Map(), logt: new Map(), res: new Map(), bat: new Map(), equipParLogt: new Map(), plan: new Map(), kit: new Map(), op: new Map() };
const cache = new Map();
let carte = null;

async function api(url, opts) {
  const r = await fetch(url, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.erreur || `Erreur ${r.status}`);
  return j;
}

async function charger() {
  const d = await api('/api/etat');
  S.d = d; S.decisions = d.decisions || {}; S.choixRenov = d.choixRenovations || {};
  for (const m of Object.values(I)) m.clear();
  d.equipements.forEach((e) => { I.equip.set(e.id, e); if (e.l) { if (!I.equipParLogt.has(e.l)) I.equipParLogt.set(e.l, []); I.equipParLogt.get(e.l).push(e); } });
  d.logements.forEach((l) => I.logt.set(l.id, l));
  d.residences.forEach((r) => I.res.set(r.id, r));
  d.batiments.forEach((b) => I.bat.set(b.id, b));
  d.plan.forEach((o) => I.kit.set(o.id, o));
  // le plan recommandé (livrable du défi 2) : chaque opération, par résidence
  d.renovations.operations.forEach((o) => { I.op.set(o.id, o); if (!I.plan.has(o.r)) I.plan.set(o.r, []); I.plan.get(o.r).push(o); });
  const annees = d.renovations.operations.map((o) => o.debut);
  ANNEES = Array.from({ length: Math.max(...annees) - Math.min(...annees) + 1 }, (_, i) => Math.min(...annees) + i);
  ANNEE = Math.min(Math.max(new Date().getFullYear(), ANNEES[0]), ANNEES.at(-1));
  if (S.annee == null) S.annee = ANNEE;
  cache.clear();
}
let ANNEES = [], ANNEE = 2026;

// ── Lieux et comptes ────────────────────────────────────────────────
function lieu(e, { court = true } = {}) {
  const r = lettre(e.r);
  if (e.commun || !e.l) return `${r} · bât. ${bat(e.b)} · parties communes`;
  const l = I.logt.get(e.l);
  return `${r} · bât. ${bat(e.b)} · logt ${numLogt(e.l)}${l && court ? ` · ${etage(l.etage)}` : ''}`;
}
const decide = (e) => !!S.decisions[e.id];
function equipementsFiltres() {
  return S.d.equipements.filter((e) => (!S.residence || e.r === S.residence) && (!S.famille || e.famille === S.famille));
}
function comptes(liste) {
  const c = { visiter: 0, surveiller: 0, decide: 0 };
  for (const e of liste) { if (decide(e)) c.decide++; else if (e.niveau === 'visiter') c.visiter++; else if (e.niveau === 'surveiller') c.surveiller++; }
  return c;
}
function comptesBandes(liste) {
  const c = { urgence: 0, alerte: 0, vigilance: 0 };
  for (const e of liste) if (!decide(e) && e.niveau === 'visiter' && e.bande in c) c[e.bande]++;
  return c;
}
const pire = (c) => VIVES.find((b) => c[b]) || null;
// la catégorie d'un équipement, toujours écrite ; vive seulement quand elle demande une visite
function pastille(e) {
  if (decide(e)) return '<span class="cat" data-cat="decide">Décidé</span>';
  return `<span class="cat" data-cat="${e.bande}"${e.niveau === 'visiter' ? ' data-vive' : ''}>${e.niveau === 'visiter' ? ICONE_ALERTE : ''}${MOT_BANDE[e.bande]}</span>`;
}
// Le plan de rénovation : ce qui est engagé une année donnée (une opération sur deux ans compte les deux années).
const CHOIX_RENOV = { lancer: { mot: 'Lancer', fait: 'Lancement décidé' }, reporter: { mot: 'Reporter', fait: 'Report décidé' } };
const choixOp = (o) => S.choixRenov?.[o.id] || null;
const opsAnnee = (a) => S.d.renovations.operations.filter((o) => a >= o.debut && a < o.debut + o.duree);
const depenseAnnee = (a) => opsAnnee(a).reduce((s, o) => s + o.coutParAn, 0);
const NOMS_OPS = [[/convecteurs/i, 'Radiateurs à inertie'], [/chaufferie/i, 'Chaufferie collective'], [/ECS solaire/i, 'Eau chaude solaire'], [/ballons ECS électriques/i, 'Ballons d’eau chaude'], [/ballons électriques par ballons thermo/i, 'Ballons thermodynamiques'], [/ballons thermodynamiques/i, 'Ballons thermodynamiques'], [/halls/i, 'Halls et escaliers'], [/toiture/i, 'Toiture-terrasse'], [/porte de hall/i, 'Porte de hall'], [/combles et planchers/i, 'Combles et planchers bas'], [/combles/i, 'Combles'], [/VMC hygro/i, 'VMC hygroréglable'], [/VMC/i, 'VMC'], [/ascenseurs/i, 'Ascenseurs'], [/ascenseur/i, 'Ascenseur'], [/\(ITE\)/, 'Isolation par l’extérieur'], [/pompes à chaleur/i, 'Pompes à chaleur'], [/chaudières condensation/i, 'Chaudières à condensation'], [/chaudières individuelles/i, 'Chaudières individuelles'], [/menuiseries/i, 'Menuiseries']];
const nomOp = (o) => (NOMS_OPS.find(([re]) => re.test(o.type)) || [null, o.type])[1];
const auDela = (lettreDpe) => DPE.indexOf(lettreDpe) >= DPE.indexOf(S.seuil);
const motsSeuil = () => (S.seuil === 'G' ? 'en G' : S.seuil === 'F' ? 'en F ou G' : `de ${S.seuil} à G`);

// Ce que la carte doit montrer, selon la lentille : un compte et la pire catégorie présente.
const CAT_DPE = { G: 'urgence', F: 'alerte', E: 'vigilance' };
const catDpe = (logts) => ['G', 'F', 'E'].map((x) => (logts.some((l) => l.dpe === x) ? CAT_DPE[x] : null)).find(Boolean) || 'calme';
const catRenov = () => (S.annee === ANNEE ? 'lancer' : 'prevu');
const motsRenov = (n, long) => `<span class="rv-visiter">${long ? pl(n, 'opération', 'opérations') : nb(n)} ${S.annee === ANNEE ? 'à lancer' : `${n > 1 ? 'prévues' : 'prévue'} en ${S.annee}`}</span>`;
function residencesCarte() {
  return S.d.residences.map((r) => {
    if (S.lentille === 'energie') {
      const logts = S.d.logements.filter((l) => l.r === r.id && auDela(l.dpe));
      const n = logts.length;
      return { ...r, cat: catDpe(logts), aVisiter: n, aSurveiller: 0, communsAVisiter: 0, alerte: n ? `<span class="rv-visiter">${nb(n)} ${motsSeuil()}</span>` : '' };
    }
    if (S.lentille === 'renovations') {
      const ops = opsAnnee(S.annee).filter((o) => o.r === r.id);
      const suite = (I.plan.get(r.id) || []).map((o) => o.debut).filter((a) => a > S.annee).sort()[0];
      return { ...r, cat: ops.length ? catRenov() : 'calme', aVisiter: ops.length, aSurveiller: 0, communsAVisiter: 0,
        alerte: ops.length ? `${motsRenov(ops.length)} · ${euros(ops.reduce((s, o) => s + o.coutParAn, 0))}` : suite ? `en ${suite}` : '' };
    }
    const eqs = S.d.equipements.filter((e) => e.r === r.id);
    const c = comptes(eqs);
    const p = pire(comptesBandes(eqs));
    return { ...r, cat: p || (c.surveiller ? 'surveiller' : 'calme'), aVisiter: c.visiter, aSurveiller: 0, communsAVisiter: 0,
      alerte: c.visiter ? `<span class="rv-visiter">${nb(c.visiter)} à visiter</span>` : '' };
  });
}
function infoMetro() {
  if (S.lentille === 'energie') {
    const logts = S.d.logements.filter((l) => auDela(l.dpe));
    const n = logts.length;
    return { cat: catDpe(logts), alerte: `${nb(n)} ${motsSeuil()}`, alerteLongue: `<span class="rv-visiter">${pl(n, 'logement', 'logements')} ${motsSeuil()}</span>` };
  }
  if (S.lentille === 'renovations') {
    const n = opsAnnee(S.annee).length;
    return { cat: n ? catRenov() : 'calme', alerte: motsRenov(n), alerteLongue: motsRenov(n, true) };
  }
  const c = comptes(S.d.equipements);
  const p = pire(comptesBandes(S.d.equipements));
  const t = `<span class="rv-visiter">${nb(c.visiter)} à visiter</span>`;
  return { cat: p || (c.surveiller ? 'surveiller' : 'calme'), alerte: t, alerteLongue: t };
}
function majCarte() {
  if (!carte) return;
  carte.conteneur.classList.toggle('carte-energie', S.lentille === 'energie');
  carte.conteneur.classList.toggle('carte-renovations', S.lentille === 'renovations');
  carte.actualiser(residencesCarte(), infoMetro());
}

// ── La zone que les panneaux prennent sur la carte ──────────────────
function zoneOccupee() {
  const H = innerHeight;
  if (telephone()) {
    const f = $('.panneau:not([hidden]).arrive, .fiche:not([hidden])');
    return { top: 70, right: 0, left: 0, bottom: f ? hauteurFeuille() : 0 };
  }
  const file = $('#file');
  const fiche = $('#fiche');
  const left = file.classList.contains('arrive') && !document.body.classList.contains('liste-fermee') ? file.getBoundingClientRect().right + 8 : 0;
  const right = !fiche.hidden ? innerWidth - fiche.getBoundingClientRect().left + 8 : 0;
  return { top: 78, right, left, bottom: 58 + (H < 600 ? 0 : 0) };
}

// ── La file (lentille Pannes) ───────────────────────────────────────
function rendreFile() {
  const el = $('#file');
  if (S.lentille === 'energie') return rendreEnergie(el);
  if (S.lentille === 'renovations') return rendreRenovations(el);
  const liste = equipementsFiltres();
  const c = comptes(liste);
  const cb = comptesBandes(liste);
  if (S.bande && !cb[S.bande]) S.bande = '';
  const familles = [...new Map(S.d.equipements.map((e) => [e.famille, e.libelle])).entries()].sort((a, b) => a[1].localeCompare(b[1], 'fr'));
  const visibles = liste.filter((e) => (S.onglet === 'decide' ? decide(e) : !decide(e) && e.niveau === S.onglet && (S.onglet !== 'visiter' || !S.bande || e.bande === S.bande)))
    .sort((a, b) => (S.onglet === 'decide' ? (S.decisions[b.id].le || '').localeCompare(S.decisions[a.id].le || '') : a.rang - b.rang));
  const mots = { visiter: 'à visiter', surveiller: 'à surveiller', decide: c.decide > 1 ? 'décidés' : 'décidé' };
  const semaine = S.semaine && S.onglet === 'visiter';
  if (semaine) { visibles.splice(10); mots.visiter = 'actions cette semaine'; }
  document.body.classList.toggle('semaine', semaine);
  const choisi = S.sel?.type === 'equipement' ? S.sel.id : null;
  const res = S.residence ? I.res.get(S.residence) : null;

  el.innerHTML = `
    <button class="poignee" type="button" aria-label="Agrandir ou réduire la file"></button>
    <button type="button" class="fermer fermer-file" data-fermer-file aria-label="Fermer la liste">${ICONE_X}</button>
    <div class="defile">
      <div class="tete">
        <div class="compte"><b class="compte-${S.onglet}">${semaine ? nb(visibles.length) : nb(c[S.onglet])}</b><span>${mots[S.onglet]}</span>${semaine ? '<button type="button" class="semaine-fin" data-semaine-fin>Toute la liste</button>' : ''}</div>
        <div class="bandes" role="tablist" aria-label="Catégorie et niveau">
          ${S.onglet === 'visiter' && c.visiter ? VIVES.filter((b) => cb[b]).map((b) => `<button type="button" class="cat" data-cat="${b}" data-vive data-bande="${b}" aria-pressed="${S.bande === b}">${MOT_BANDE[b]} <b>${nb(cb[b])}</b></button>`).join('') : ''}
          ${['visiter', 'surveiller', 'decide'].filter((o) => o !== S.onglet && (o !== 'decide' || c.decide)).map((o) => `<button type="button" role="tab" class="cat onglet-pilule" data-onglet="${o}" aria-selected="false"><b>${nb(c[o])}</b> ${mots[o]}</button>`).join('')}
        </div>
      </div>
      <div class="filtres">
        <label class="filtre-residence-bloc${res ? ' actif' : ''}">${ICONE_LIEU}<select class="filtre-residence" aria-label="Résidence">
          <option value="">Toutes les résidences · ${nb(S.d.residences.length)}</option>
          ${S.d.residences.map((r) => `<option value="${r.id}"${S.residence === r.id ? ' selected' : ''}>${esc(r.nom)}</option>`).join('')}
        </select></label>
        <span class="portee">${res ? `${esc(res.nom)} seulement, choisie sur la carte` : `aucune résidence choisie sur la carte : les ${nb(S.d.residences.length)} résidences sont affichées`}</span>
        <select class="filtre-famille" aria-label="Type d'équipement">
          <option value="">Tous les équipements</option>
          ${familles.map(([f, l]) => `<option value="${esc(f)}"${S.famille === f ? ' selected' : ''}>${esc(l)}</option>`).join('')}
        </select>
        ${S.onglet === 'decide' && c.decide ? '<a class="exporter" href="/api/export/decisions.csv" download aria-label="Exporter les décisions (CSV)">Exporter</a>' : ''}
      </div>
      ${visibles.length ? `<ol class="lignes">${visibles.slice(0, S.limite).map((e) => ligne(e, choisi)).join('')}</ol>
      ${visibles.length > S.limite ? `<button class="plus" type="button" data-plus>Afficher ${nb(Math.min(50, visibles.length - S.limite))} de plus</button>` : ''}`
      : `<div class="vide"><b>${S.onglet === 'decide' ? 'Rien de décidé' : `Rien ${mots[S.onglet]}`}</b></div>`}
      ${PIED_TEL}
    </div>`;
}

// au téléphone, la barre n'a que la loupe : Données et Méthode passent au pied de la liste
const PIED_TEL = '<nav class="pied-tel" aria-label="Pages"><button type="button" data-rejeu>Rejeu de 2025</button><a href="#/donnees">Données</a><a href="#/methode">Méthode</a></nav>';

const ICONE_ALERTE = '<svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M10 2.8L18.3 17H1.7z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M10 7.6v4.2M10 14.3v.4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>';
const ICONE_FLECHE = '<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M3 10h13M11 5l5 5-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ICONE_LIEU = '<svg viewBox="0 0 20 20" width="15" height="15" aria-hidden="true"><path d="M10 18s-6-5.6-6-10a6 6 0 0 1 12 0c0 4.4-6 10-6 10z" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="10" cy="8" r="2.2" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>';

function resume(e) {
  const f = e.faits || {};
  const p = [];
  if (f.depannages12m >= 2) p.push(`${f.depannages12m} dépannages en 12 mois`);
  if (f.arrets12m >= 1) p.push(f.arrets12m > 1 ? `${f.arrets12m} arrêts totaux` : 'un arrêt total');
  if (f.dureeVieAns && f.ageAns / f.dureeVieAns >= 0.9) p.push('fin de durée de vie');
  if (f.dernierCommentaire) p.push('usure signalée par le technicien');
  if (f.demandes12m >= 1) p.push(f.demandes12m > 1 ? 'plaintes du locataire' : 'plainte du locataire');
  if (f.remplacementCommande) p.push('remplacement déjà commandé');
  if (!p.length) return e.raisons[0]?.texte || 'Rien à signaler sur 12 mois';
  const t = p.slice(0, 2).join(' et ');
  return t[0].toUpperCase() + t.slice(1);
}

function ligne(e, choisi, { dansResidence = !!S.residence } = {}) {
  const x = S.decisions[e.id];
  const lieu = [esc(e.libelle), dansResidence ? (e.commun ? `Bât. ${bat(e.b)} · parties communes` : `Bât. ${bat(e.b)}`) : `Résidence ${lettre(e.r)}`, e.l && !e.commun ? `Logt ${numLogt(e.l)}` : ''].filter(Boolean).join(' · ');
  const der = e.faits?.dernierDepannage;
  return `<li class="ligne" data-id="${e.id}" data-niveau="${e.niveau}"${x ? ' data-decide' : ''} aria-current="${e.id === choisi}" tabindex="0">
    <div class="ligne-haut">${pastille(e)}${e.points != null ? `<span class="ligne-score">Score <b>${nb(e.points)}</b></span>` : ''}</div>
    <span class="ligne-lieu">${x ? `${CHOIX[x.choix].fait} · ` : ''}${lieu}</span>
    <span class="ligne-titre">${esc(resume(e))}</span>
    ${S.semaine && S.onglet === 'visiter' && e.cout ? `<span class="ligne-raison"><em>Neuf : ${nb(e.cout[0])} à ${nb(e.cout[1])} €</em></span>` : ''}
    <div class="ligne-bas"><span class="ligne-date">${der ? `<small>Dernier dépannage</small>${dateCourte(der)}` : '<small>Aucun dépannage</small>depuis la pose'}</span><span class="voir">Voir le détail ${ICONE_FLECHE}</span></div>
  </li>`;
}

const ligneEnergie = (choisi) => ({ r, ls, n: k }) => `
        <li data-res="${r.id}" aria-current="${r.id === choisi}" tabindex="0">
          <span class="lettre-res">${esc(r.lettre)}</span>
          <span class="ligne-titre">${esc(r.nom)} ${etiquette(r.dpe)}</span>
          <span class="compte-dpe">${k ? `<b>${nb(k)}</b>` : '<b class="zero">0</b>'}</span>
          <span class="dpe-barre" style="grid-column:2/4" aria-hidden="true">${repartition(ls)}</span>
        </li>`;

// ── La lentille Énergie ─────────────────────────────────────────────
function rendreEnergie(el) {
  const logts = S.d.logements;
  const n = logts.filter((l) => auDela(l.dpe)).length;
  const lignes = S.d.residences.map((r) => {
    const ls = S.d.logements.filter((l) => l.r === r.id);
    return { r, ls, n: ls.filter((l) => auDela(l.dpe)).length };
  }).sort((a, b) => b.n - a.n || b.r.conso - a.r.conso);
  const choisi = S.sel?.type === 'residence' ? S.sel.id : S.residence;
  el.innerHTML = `
    <button class="poignee" type="button" aria-label="Agrandir ou réduire la liste"></button>
    <div class="tete">
      <button type="button" class="fermer fermer-file" data-fermer-file aria-label="Fermer la liste">${ICONE_X}</button>
      <div class="compte"><b>${nb(n)}</b><span>${n > 1 ? 'logements' : 'logement'} ${motsSeuil()}</span></div>
      <div class="echelle-dpe" role="radiogroup" aria-label="Seuil d'alerte DPE">
        ${DPE.map((l) => `<button type="button" role="radio" data-seuil="${l}" style="--fond-dpe:${COULEUR_DPE[l]};--sur-dpe:${TEXTE_DPE[l]}" aria-checked="${S.seuil === l}" class="${auDela(l) ? 'au-dela' : ''}${S.seuil === l ? ' seuil' : ''}" title="Alerte à partir de ${l}">${l}</button>`).join('')}
      </div>
    </div>
    <div class="defile">
      <ol class="res-energie">${lignes.filter((l) => l.n).map(ligneEnergie(choisi)).join('')}</ol>
      ${lignes.some((l) => !l.n) ? `<details class="res-zero"${lignes.every((l) => !l.n) ? ' open' : ''}><summary>${(() => { const z = lignes.filter((l) => !l.n).length; return z > 1 ? `Et ${nb(z)} résidences sans logement ${motsSeuil()}` : `Et 1 résidence sans logement ${motsSeuil()}`; })()}</summary><ol class="res-energie">${lignes.filter((l) => !l.n).map(ligneEnergie(choisi)).join('')}</ol></details>` : ''}
      ${PIED_TEL}
    </div>`;
}
function repartition(logts) {
  const n = logts.length || 1;
  return DPE.map((l) => { const k = logts.filter((x) => x.dpe === l).length; return k ? `<i style="width:${(k / n) * 100}%;background:${COULEUR_DPE[l]};opacity:${auDela(l) ? 1 : 0.35}" title="${l} : ${k}"></i>` : ''; }).join('');
}

// ── La lentille Rénovations : le calendrier recommandé sous le plafond annuel ──
function rendreRenovations(el) {
  const R = S.d.renovations;
  const cetteAnnee = opsAnnee(ANNEE).filter((o) => !choixOp(o));
  const choisi = S.sel?.type === 'operation' ? S.sel.id : null;
  const ligneEffet = (mot, a, b, unite = '') => `<tr><th scope="row">${mot}</th><td class="ce-plan">${nb(a)}${unite}</td><td>${nb(b)}${unite}</td></tr>`;
  el.innerHTML = `
    <button class="poignee" type="button" aria-label="Agrandir ou réduire la liste"></button>
    <div class="tete">
      <button type="button" class="fermer fermer-file" data-fermer-file aria-label="Fermer la liste">${ICONE_X}</button>
      <div class="compte"><b>${nb(cetteAnnee.length)}</b><span>à lancer en ${ANNEE}</span><em>${euros(cetteAnnee.reduce((t, o) => t + o.coutParAn, 0))}</em></div>
      <div class="tuiles">
        <div class="tuile"><b>${nb(R.recommande.g2028)}</b><span>logements G en 2028</span><small>au lieu de ${nb(R.actuel.g2028)} dans l’ordre des demandes</small></div>
        <div class="tuile"><b>${nb(R.recommande.f2028)}</b><span>logements F en 2028</span><small>au lieu de ${nb(R.actuel.f2028)} dans l’ordre des demandes</small></div>
      </div>
      <p class="effet-energie"><b>${nb(R.recommande.mwh2028)} MWh/an</b> économisés en 2028, au lieu de ${nb(R.actuel.mwh2028)} dans l’ordre des demandes.</p>
    </div>
    <div class="defile">
      <ol class="annees">${ANNEES.map((a) => {
        const ops = opsAnnee(a).sort((x, y) => x.rang - y.rang);
        const dep = depenseAnnee(a);
        return `<li class="annee" data-annee="${a}" aria-current="${a === S.annee}"${a === ANNEE ? ' data-maintenant' : ''}>
          <button type="button" class="annee-tete" data-choisir-annee="${a}" aria-pressed="${a === S.annee}">
            <b>${a}</b>${a === ANNEE ? '<span class="cat" data-cat="lancer" data-vive>À lancer</span>' : ''}
            <span class="budget" aria-hidden="true"><i style="width:${Math.min(100, (dep / R.plafond) * 100)}%"></i></span>
            <span class="montant">${euros(dep)}</span>
          </button>
          <ol class="ops">${ops.map((o) => `<li class="op-ligne" data-op="${o.id}" aria-current="${o.id === choisi}"${choixOp(o) ? ` data-choix="${choixOp(o).choix}"` : ''} tabindex="0">
            <span class="lettre-res">${esc(lettre(o.r))}</span>
            <span class="ligne-titre">${esc(nomOp(o))}${o.duree > 1 ? `<small>${a === o.debut ? ` · 1<sup>re</sup> année sur ${o.duree}` : ` · ${a - o.debut + 1}<sup>e</sup> année`}</small>` : ''}</span>
            <span class="montant">${choixOp(o) ? `<span class="cat" data-cat="decide">${choixOp(o).choix === 'lancer' ? 'Lancée' : 'Reportée'}</span>` : euros(o.coutParAn)}</span>
          </li>`).join('')}</ol>
        </li>`;
      }).join('')}</ol>
      <div class="pied-plan"><a href="/api/export/plan.csv" download>Exporter le plan</a></div>
      ${PIED_TEL}
    </div>`;
}

function ficheOperation(o) {
  const res = I.res.get(o.r);
  const k = I.kit.get(o.id) || {};
  const maintenant = ANNEE >= o.debut && ANNEE < o.debut + o.duree;
  const force = (v) => (v >= 6 ? 'fort' : v >= 3 ? 'moyen' : 'faible');
  const criteres = Object.entries(o.criteres).sort((a, b) => b[1] - a[1]);
  const autres = (I.plan.get(o.r) || []).filter((x) => x.id !== o.id).sort((a, b) => a.debut - b.debut);
  return `
    <div class="tete">
      <button type="button" class="fermer fermer-file" data-fermer-file aria-label="Fermer la liste">${ICONE_X}</button>
      <h2>${esc(nomOp(o))}</h2>
      <div class="fil"><button type="button" data-aller="residence/${o.r}">${esc(res.nom)}</button>${k.logements ? `<span>· ${pl(k.logements, 'logement', 'logements')}</span>` : ''}</div>
      <div class="etat">${maintenant && choixOp(o) ? `<span class="cat grand" data-cat="decide">${choixOp(o).choix === 'lancer' ? 'Lancée' : 'Reportée'}</span>` : maintenant ? `<span class="cat grand" data-cat="lancer" data-vive>À lancer en ${ANNEE}</span>` : `<span class="cat grand" data-cat="prevu">En ${o.debut}</span>`}
        ${o.ecart ? `<span class="decalage">${o.ecart > 0 ? 'reportée' : 'avancée'} ${Math.abs(o.ecart) === 1 ? 'd’un an' : `de ${nb(Math.abs(o.ecart))} ans`}</span>` : ''}</div>
      ${maintenant ? (choixOp(o) ? `<div class="decide"><div><b>${CHOIX_RENOV[choixOp(o).choix].fait}</b><br><span>le ${dateLongue(choixOp(o).le)}</span></div><button type="button" data-annuler-op="${o.id}">Annuler</button></div>`
        : `<div class="decisions deux" role="group" aria-label="Décider">${Object.entries(CHOIX_RENOV).map(([k, c]) => `<button type="button" data-choix-op="${k}">${c.mot}</button>`).join('')}</div>`) : ''}
      <div class="chiffres"><div><b>${euros(o.cout)}</b><span>${o.duree > 1 ? `sur ${o.debut} et ${o.debut + 1}` : `en ${o.debut}`}</span></div>${k.gain ? `<div><b>−${nb(k.gain)}</b><span>kWh/m²/an</span></div>` : ''}${o.pannesParAn ? `<div><b>${nb(Math.round(o.pannesParAn))}</b><span>pannes bloquantes attendues par an</span></div>` : ''}</div>
    </div>
    <div class="defile">
      <section class="bloc"><h3>Pourquoi</h3><ul class="criteres">${criteres.map(([c, v]) => `<li><span>${CRITERES[c]}</span><span class="force" data-force="${force(v)}">${force(v)}</span></li>`).join('')}</ul></section>
      <details class="plus-infos"><summary>Plus d’informations</summary>
        <dl class="faits">
          <dt>Opération</dt><dd>${esc(o.type)}</dd>
          ${k.perimetre ? `<dt>Périmètre</dt><dd>${esc(k.perimetre)}</dd>` : ''}
          <dt>Souhaitée</dt><dd>en ${o.souhaitee}${k.origine ? ` · ${esc(k.origine)}` : ''}</dd>
        </dl>
        ${autres.length ? `<h3 class="sous-bloc">Autres opérations de la résidence</h3><ul class="equip">${autres.map((x) => `<li data-aller="operation/${x.id}"><span class="cat" data-cat="${x.debut === ANNEE ? 'lancer' : 'prevu'}"${x.debut === ANNEE ? ' data-vive' : ''}>${x.debut}</span><span>${esc(nomOp(x))}</span><span class="ligne-indice">${euros(x.cout)}</span></li>`).join('')}</ul>` : ''}
      </details>
    </div>`;
}

// ── Les fiches ──────────────────────────────────────────────────────
async function rendreFiche() {
  const el = $('#fiche');
  if (!S.sel) { el.hidden = true; document.body.classList.add('sans-fiche'); return; }
  el.hidden = false; document.body.classList.remove('sans-fiche');
  const { type, id } = S.sel;
  const cle = `${type}/${id}`;
  if (!cache.has(cle) && type !== 'residence' && type !== 'operation') {
    el.innerHTML = `<button class="poignee" type="button" aria-label="Agrandir ou réduire la fiche"></button><button class="fermer" type="button" data-fermer-fiche aria-label="Fermer la fiche">${ICONE_X}</button><div class="tete"><h2>…</h2></div>`;
    try { cache.set(cle, await api(`/api/${type}/${encodeURIComponent(id)}`)); } catch (err) { el.innerHTML += `<div class="vide"><b>Introuvable</b>${esc(err.message)}</div>`; return; }
    if (!S.sel || `${S.sel.type}/${S.sel.id}` !== cle) return;
  }
  if ((type === 'residence' && !I.res.has(id)) || (type === 'operation' && !I.op.has(id))) { el.innerHTML = `<button class="fermer" type="button" data-fermer-fiche aria-label="Fermer la fiche">${ICONE_X}</button><div class="vide"><b>Introuvable</b></div>`; return; }
  const html = type === 'equipement' ? ficheEquipement(cache.get(cle)) : type === 'logement' ? ficheLogement(cache.get(cle)) : type === 'operation' ? ficheOperation(I.op.get(id)) : ficheResidence(I.res.get(id));
  const defile = $('.defile', el)?.scrollTop;
  el.innerHTML = `<button class="poignee" type="button" aria-label="Agrandir ou réduire la fiche"></button><button class="fermer" type="button" data-fermer-fiche aria-label="Fermer la fiche">${ICONE_X}</button>${html}`;
  if (S.garderDefilement && defile) $('.defile', el).scrollTop = defile;
  S.garderDefilement = false;
}

function observeCourt(t) { return t.replace(/ dans les 3 mois.*$/, '').replace(/,\s*\d+ %$/, ''); }
function observeParts(t) { const m = /(\d+) pannes? sur (\d+)/.exec(t); return m ? { n: +m[1], d: +m[2] } : null; }
function ficheEquipement({ equipement: e0, interventions, demandes, brut }) {
  const e = I.equip.get(e0.id) || e0;
  const x = S.decisions[e.id];
  const f = e.faits || {};
  const l = e.l ? I.logt.get(e.l) : null;
  const res = I.res.get(e.r);
  const histoire = melanger(interventions, demandes.filter((dm) => pertinente(dm, e)));
  const sv = suivant(e);
  return `
    <div class="tete">
      <button type="button" class="fermer fermer-file" data-fermer-file aria-label="Fermer la liste">${ICONE_X}</button>
      <h2>${esc(e.libelle)}</h2>
      <div class="fil"><button type="button" data-aller="residence/${e.r}">${esc(res.nom)}</button><span class="sep">›</span><span>Bât. ${bat(e.b)}</span>${l ? `<span class="sep">›</span><button type="button" data-aller="logement/${l.id}">Logement ${numLogt(l.id)}</button>` : '<span class="sep">›</span><span>parties communes</span>'}</div>
      <div class="tete-h2">
        <div class="etat">${x ? '<span class="cat grand" data-cat="decide">Décidé</span>' : `<span class="cat grand" data-cat="${e.bande}"${e.niveau === 'visiter' ? ' data-vive' : ''}>${MOT_BANDE[e.bande]}</span>`}${e.points != null ? `<span class="score"><b>${nb(e.points)}</b> points · ${e.rang}<sup>e</sup> sur ${nb(S.d.equipements.length)}</span>` : ''}</div>
        ${e.observe ? `<div class="encadre" data-cat="${e.bande}">${esc(observeCourt(e.observe))}<small>parmi les équipements de cette catégorie, sur 2025</small></div>` : ''}
      </div>
      <div class="tete-h3">
        <div class="etat">${x ? '<span class="cat grand" data-cat="decide">Décidé</span>' : `<span class="score-pilule" data-cat="${e.bande}">${nb(e.points)} <small>points</small></span>`}<span class="score">${e.rang}<sup>e</sup> sur ${nb(S.d.equipements.length)} · à visiter dès 45</span></div>
        ${e.observe && observeParts(e.observe) ? (({ n, d }) => `<div class="stat-pannes"><div class="stat-ligne"><b>${nb(n)} <span>sur ${nb(d)}</span></b><span class="stat-part">${Math.round(100 * n / d)} %</span></div><p>${n > 1 ? 'pannes' : 'panne'} l’an dernier parmi les ${nb(d)} équipements qui avaient ce niveau de points</p><div class="jauge" role="img" aria-label="${nb(n)} sur ${nb(d)}"><i style="width:${(100 * n / d).toFixed(1)}%"></i></div></div>`)(observeParts(e.observe)) : ''}
      </div>
      ${x ? `<div class="decide"><div><b>${CHOIX[x.choix].fait}</b><br><span>le ${dateLongue(x.le)}${x.note ? ` · ${esc(x.note)}` : ''}</span></div><button type="button" data-annuler="${e.id}">Annuler</button></div>
             <div class="retour-terrain">${x.retour ? `<span class="cat" data-cat="${x.retour === 'confirme' ? 'decide' : 'calme'}">${x.retour === 'confirme' ? 'Panne confirmée sur place' : 'Fausse alerte'}</span><small>retour du ${dateLongue(x.retourLe)}, pris en compte pour améliorer le barème</small>` : `<span>Après le passage du prestataire :</span><button type="button" data-retour="confirme">Panne confirmée</button><button type="button" data-retour="infirme">Fausse alerte</button>`}</div>
             ${sv ? `<button class="plus suivant" type="button" data-aller="equipement/${sv.id}">Suivant : ${esc(sv.libelle)}</button>` : ''}`
        : `<div class="decisions" role="group" aria-label="Décider">${Object.entries(CHOIX).map(([k, c]) => `<button type="button" data-decider="${k}" title="${c.aide} (touche ${c.touche.toUpperCase()})">${c.mot}<small>${c.aide}</small></button>`).join('')}</div>
           <p class="aide-decision">La décision est enregistrée pour cet équipement et sort dans l’export des décisions.</p>
           <details class="ajout-note"><summary>Ajouter une note</summary><input class="note" type="text" maxlength="300" placeholder="Note pour la décision" aria-label="Note pour la décision"></details>`}
    </div>
    <div class="defile">
      ${(() => { const dep = interventions.filter((i) => i.type === 'Dépannage').length; const cout = dep * COUT_DEPANNAGE; return e.cout && dep >= 2 && cout >= 0.5 * e.cout[0] ? `<div class="reparer-remplacer"><b>Réparer ou remplacer ?</b><span>${nb(dep)} dépannages depuis la pose, soit environ ${nb(cout)} € à ${nb(COUT_DEPANNAGE)} € l’intervention, pour un équipement neuf entre ${nb(e.cout[0])} et ${nb(e.cout[1])} € TTC.</span></div>` : ''; })()}
      ${e.raisons.length ? `<section class="bloc"><h3>Pourquoi <span>points</span></h3><ul class="raisons">${e.raisons.map((r) => /^Autres situations/.test(r.texte) && e.autres.length ? `<li class="autres"><details><summary><span>Autres situations <small>${e.autres.length > 1 ? `${e.autres.length} raisons plus légères` : '1 raison plus légère'}</small></span><b class="pts${r.poids < 0 ? ' moins' : ''}">${r.poids > 0 ? '+' : ''}${nb(r.poids)}</b></summary><ul>${e.autres.map((a) => `<li><span>${esc(a.texte)}</span><b class="pts${a.poids < 0 ? ' moins' : ''}">${a.poids > 0 ? '+' : ''}${nb(a.poids)}</b></li>`).join('')}</ul></details></li>` : `<li><span>${esc(r.texte)}</span><b class="pts${r.poids < 0 ? ' moins' : ''}">${r.poids > 0 ? '+' : ''}${nb(r.poids)}</b></li>`).join('')}</ul><p class="total"><span>Total</span><b>${nb(e.points)}</b></p><p class="seuil">À visiter à partir de 45 points, Urgent au-delà de 80.</p></section>` : ''}
      <details class="plus-infos"${S.histoireOuverte === 'equipement' ? ' open' : ''}><summary>Plus d’informations</summary>
      <dl class="faits">
        <dt>Posé le</dt><dd>${dateLongue(f.datePose || brut.datePose)}</dd>
        ${f.ageAns != null ? `<dt>Âge</dt><dd>${nb(f.ageAns)} ans · durée de vie prévue ${nb(f.dureeVieAns)} ans</dd>` : ''}
        <dt>Dépannages</dt><dd>${pl(f.depannages12m || 0, 'en 12 mois', 'en 12 mois')}${f.arrets12m ? ` · dont ${pl(f.arrets12m, 'arrêt total', 'arrêts totaux')}` : ''}</dd>
        ${f.visitesPrevues ? `<dt>Visites</dt><dd>${f.visitesManquees ? `${nb(f.visitesManquees)} manquée${f.visitesManquees > 1 ? 's' : ''} sur ${nb(f.visitesPrevues)}` : `${nb(f.visitesPrevues)} réalisée${f.visitesPrevues > 1 ? 's' : ''}, aucune manquée`}</dd>` : ''}
        ${e.cout ? `<dt>Neuf</dt><dd>${nb(e.cout[0])} à ${nb(e.cout[1])} € TTC, référence de la famille</dd>` : ''}
        <dt>Contrat</dt><dd>${e.contrat === 'Oui' ? 'Sous contrat d’entretien' : 'Hors contrat'}${e.prestataire ? ` · ${esc(e.prestataire)}` : ''}</dd>
        ${l ? `<dt>Logement</dt><dd>${esc(l.typo)} · ${etageLong(l.etage)} · ${pl(l.d12, 'demande', 'demandes')} en 12 mois</dd>` : ''}
      </dl>
      <h3 class="sous-bloc">Historique</h3>${listeHistoire(histoire, 8, 'equipement')}
      </details>
    </div>`;
}
// Les demandes du locataire qui touchent ce type d'équipement (chauffage, eau chaude) : les autres restent dans la fiche du logement.
function pertinente(dm, e) {
  const t = sansAccent(`${dm.motif} ${dm.objet} ${dm.texte}`);
  if (/chaudiere|pompe|chaufferie|convecteur|panneaux/.test(e.famille)) return /chauff|radiateur|chaudiere|froid|temperature|pompe|eau chaude|tiede/.test(t);
  if (/ballon|ecs/.test(e.famille)) return /eau chaude|tiede|ballon|chauffe.eau|cumulus/.test(t);
  if (/ascenseur/.test(e.famille)) return /ascenseur/.test(t);
  if (/vmc/.test(e.famille)) return /vmc|ventilation|condensation|humidite/.test(t);
  return false;
}
function suivant(e) {
  const liste = equipementsFiltres().filter((x) => !decide(x) && x.niveau === e.niveau && x.rang > e.rang).sort((a, b) => a.rang - b.rang);
  return liste[0] || null;
}
function melanger(interventions, demandes) {
  return [
    ...interventions.map((i) => ({ ...i, sorte: i.type === 'Remplacement' ? 'remplacement' : i.gravite === 'Arrêt total' ? 'arret' : i.type === 'Dépannage' ? 'depannage' : 'entretien' })),
    ...demandes.map((dm) => ({ ...dm, sorte: 'demande' })),
  ].sort((a, b) => b.date.localeCompare(a.date));
}
function listeHistoire(items, n, cle) {
  if (!items.length) return '<p class="vide" style="padding:0 0 12px">Aucun événement.</p>';
  const ouvert = S.histoireOuverte === cle;
  const vus = ouvert ? items : items.slice(0, n);
  return `<ol class="histoire">${vus.map((h) => {
    if (h.sorte === 'demande') return `<li data-sorte="demande"><span class="quand">${dateCourte(h.date)} · demande du locataire · ${esc((h.priorite || '').split(' - ')[0])}</span><span class="quoi">${esc(h.motif.charAt(0).toUpperCase() + h.motif.slice(1))}</span>${h.texte ? `<q>${esc(h.texte)}</q>` : ''}</li>`;
    const quoi = h.type === 'Entretien préventif' ? (h.resultat === 'Visite réalisée - RAS' ? 'Entretien · RAS' : h.resultat.startsWith('Logement absent') ? 'Entretien · logement absent' : `Entretien · ${h.resultat.toLowerCase()}`) : h.type === 'Remplacement' ? 'Remplacement' : `Dépannage${h.gravite ? ` · ${h.gravite.toLowerCase()}` : ''}`;
    const libelle = h.equipementLibelle ? `${esc(h.equipementLibelle)} · ` : '';
    return `<li data-sorte="${h.sorte}"><span class="quand">${dateCourte(h.date)} · ${libelle}${esc(h.prestataire || '')}</span><span class="quoi${h.sorte === 'arret' ? ' arret' : ''}">${esc(quoi)}</span>${h.symptome ? `<span class="detail"> — ${esc(h.symptome)}</span>` : ''}${h.commentaire && !/^Entretien annuel réalisé$/.test(h.commentaire) ? `<q>${esc(h.commentaire)}</q>` : ''}</li>`;
  }).join('')}</ol>${items.length > n && !ouvert ? `<button class="plus" style="margin:0 0 14px;width:100%" type="button" data-histoire="${cle}">Tout afficher · ${nb(items.length)}</button>` : ''}`;
}

function ficheLogement({ logement: l, demandes, equipements, autres, interventions }) {
  const res = I.res.get(l.r);
  const libelles = new Map([...equipements.map((e) => [e.id, e.libelle]), ...autres.map((a) => [a.id, a.libelle])]);
  const histoire = melanger(interventions.filter((i) => i.type !== 'Entretien préventif' || i.resultat !== 'Visite réalisée - RAS').map((i) => ({ ...i, equipementLibelle: libelles.get(i.equipement) })), []);
  const eqs = equipements.map((e) => I.equip.get(e.id) || e).sort((a, b) => a.rang - b.rang);
  return `
    <div class="tete">
      <button type="button" class="fermer fermer-file" data-fermer-file aria-label="Fermer la liste">${ICONE_X}</button>
      <h2>Logement ${numLogt(l.id)}</h2>
      <div class="fil"><button type="button" data-aller="residence/${l.r}">${esc(res.nom)}</button><span class="sep">›</span><span>Bât. ${bat(l.b)} · ${etageLong(l.etage)}</span></div>
      <div class="chiffres"><div><b>${nb(l.d12)}</b><span>${l.d12 > 1 ? 'demandes' : 'demande'} en 12 mois</span></div>${S.lentille === 'energie' || auDela(l.dpe) ? `<div>${etiquette(l.dpe)}</div>` : ''}</div>
    </div>
    <div class="defile">
      <section class="bloc"><h3>Équipements</h3><ul class="equip">
        ${eqs.map((e) => `<li data-aller="equipement/${e.id}">${pastille(e)}<span>${esc(e.libelle)}</span></li>`).join('')}
      </ul></section>
      <section class="bloc"><h3>Demandes du locataire</h3>${listeHistoire(demandes.map((dm) => ({ ...dm, sorte: 'demande' })), 5, 'demandes')}</section>
      <details class="plus-infos"${S.histoireOuverte === 'interventions' ? ' open' : ''}><summary>Plus d’informations</summary>
        <dl class="faits">
          <dt>Logement</dt><dd>${esc(l.typo)} · ${nb(l.surface)} m² · ${esc(l.statut.toLowerCase())}</dd>
          <dt>DPE</dt><dd>${etiquette(l.dpe)} ${nb(l.conso)} kWh/m²/an</dd>
          <dt>Demandes</dt><dd>${nb(l.dTot)} depuis 2019</dd>
          ${autres.length ? `<dt>Hors calcul</dt><dd>${autres.map((a) => esc(a.libelle)).join(', ')}</dd>` : ''}
        </dl>
        <h3 class="sous-bloc">Interventions</h3>${listeHistoire(histoire, 8, 'interventions')}
      </details>
    </div>`;
}

function ficheResidence(r) {
  const eqs = S.d.equipements.filter((e) => e.r === r.id);
  const c = comptes(eqs);
  const cb = comptesBandes(eqs);
  const logts = S.d.logements.filter((l) => l.r === r.id);
  const ops = (I.plan.get(r.id) || []).slice().sort((a, b) => a.debut - b.debut || a.rang - b.rang);
  const bats = S.d.batiments.filter((b) => b.r === r.id);
  const d12 = logts.reduce((s, l) => s + l.d12, 0);
  const auDelaListe = logts.filter((l) => auDela(l.dpe)).sort((a, b) => b.conso - a.conso);
  const aVisiter = eqs.filter((e) => e.niveau === 'visiter' && !decide(e)).sort((a, b) => a.rang - b.rang);
  const blocVisiter = aVisiter.length ? `<section class="bloc bloc-visiter"><h3>À visiter</h3><ol class="lignes">${aVisiter.map((e) => ligne(e, null, { dansResidence: true })).join('')}</ol></section>` : '';
  const blocBats = `<section class="bloc"><h3>Bâtiments</h3><ul class="equip">${bats.map((b) => {
    const eb = eqs.filter((e) => e.b === b.id);
    const cbb = comptesBandes(eb);
    const p = pire(cbb);
    const n = cbb.urgence + cbb.alerte + cbb.vigilance;
    return `<li class="inerte"><span class="lettre-res">${esc(bat(b.id))}</span><span>${p ? `<span class="cat" data-cat="${p}" data-vive>${MOT_BANDE[p]}</span> ${nb(n)} à visiter` : '<span class="calme">rien à visiter</span>'}</span></li>`;
  }).join('')}</ul></section>`;
  const blocOps = ops.length ? `<section class="bloc"><h3>Rénovations</h3><ul class="equip">${ops.map((o) => `<li data-aller="operation/${o.id}"><span class="cat" data-cat="${o.debut === ANNEE ? 'lancer' : 'prevu'}"${o.debut === ANNEE ? ' data-vive' : ''}>${o.debut}</span><span>${esc(nomOp(o))}</span><span class="ligne-indice">${euros(o.cout)}</span></li>`).join('')}</ul></section>` : '';
  const blocDpe = `<section class="bloc"><h3>Étiquettes DPE</h3>
      <div class="dpe-barre" style="height:16px">${repartition(logts)}</div>
      <div class="legende-dpe" style="margin-bottom:12px">${DPE.map((l) => { const k = logts.filter((x) => x.dpe === l).length; return `<span>${l} ${k}</span>`; }).join('')}</div>
    </section>`;
  const infos = `<details class="plus-infos"${S.histoireOuverte === 'dpe' ? ' open' : ''}><summary>Plus d’informations</summary>
      <dl class="faits">
        <dt>Construite</dt><dd>en ${r.annee}</dd>
        <dt>Logements</dt><dd>${nb(r.logements)} · ${pl(r.batiments, 'bâtiment', 'bâtiments')}${r.ascenseur === 'Oui' ? ' · ascenseurs' : ''}</dd>
        <dt>Chauffage</dt><dd>${esc(r.chauffage)}</dd>
        <dt>DPE</dt><dd>${etiquette(r.dpe)} majoritaire · ${nb(r.conso)} kWh/m²/an en moyenne</dd>
        <dt>Demandes</dt><dd>${pl(d12, 'demande', 'demandes')} en 12 mois</dd>
        <dt>Équipements</dt><dd>${nb(c.surveiller)} à surveiller · ${pl(c.decide, 'décidé', 'décidés')}</dd>
      </dl>
      ${auDelaListe.length ? `<h3 class="sous-bloc">Logements ${motsSeuil()}</h3><ul class="equip">${auDelaListe.slice(0, S.histoireOuverte === 'dpe' ? 999 : 8).map((l) => `<li data-aller="logement/${l.id}">${etiquette(l.dpe)}<span>Logement ${numLogt(l.id)} · bât. ${bat(l.b)}</span></li>`).join('')}</ul>
      ${auDelaListe.length > 8 && S.histoireOuverte !== 'dpe' ? `<button class="plus" style="margin:0 0 14px;width:100%" type="button" data-histoire="dpe">Tout afficher · ${nb(auDelaListe.length)}</button>` : ''}` : ''}
    </details>`;
  let etat, corps;
  if (S.lentille === 'energie') {
    etat = `<div class="chiffres"><div class="c-energie"><b>${nb(auDelaListe.length)}</b><span>${auDelaListe.length > 1 ? 'logements' : 'logement'} ${motsSeuil()}</span></div></div>`;
    corps = blocDpe + blocOps + infos;
  } else if (S.lentille === 'renovations') {
    etat = '';
    corps = blocOps + blocDpe + infos;
  } else {
    etat = pire(cb) ? `<div class="bandes">${VIVES.filter((b) => cb[b]).map((b) => `<span class="cat" data-cat="${b}" data-vive>${MOT_BANDE[b]} <b>${nb(cb[b])}</b></span>`).join('')}</div>` : '<div class="etat"><span class="cat grand" data-cat="calme">Rien à visiter</span></div>';
    corps = blocVisiter + blocBats + blocOps + infos;
  }
  return `
    <div class="tete">
      <button type="button" class="fermer fermer-file" data-fermer-file aria-label="Fermer la liste">${ICONE_X}</button>
      <h2>${esc(r.nom)}</h2>
      ${etat}
    </div>
    <div class="defile">${corps}</div>`;
}

// ── Le territoire : sur la page Données ──
function blocTerritoire() {
  const raccordes = S.d.logements.length;
  return `<table><tbody>
      <tr><td>Haute-Garonne · 31</td><td class="n">${pl(S.d.residences.length, 'résidence', 'résidences')} · ${nb(raccordes)} logements</td></tr>
      ${[['Gironde', 33], ['Hérault', 34], ['Landes', 40], ['Pyrénées-Atlantiques', 64]].map(([n, c]) => `<tr><td>${n} · ${c}</td><td class="n">à raccorder</td></tr>`).join('')}
    </tbody></table>`;
}

// ── Les pages à part ────────────────────────────────────────────────
async function rendrePage() {
  const el = $('#page');
  if (!S.page) { el.hidden = true; return; }
  el.hidden = false;
  const corps = $('.page-corps', el);
  corps.innerHTML = `<button class="fermer" type="button" data-fermer aria-label="Fermer">${ICONE_X}</button>` + (S.page === 'methode' ? await pageMethode() : pageDonnees());
  corps.focus();
}

async function pageMethode() {
  const R = S.d.renovations;
  return `
    <h1 id="page-titre">Méthode</h1>
    <h2>Pannes</h2>
    <p>Chaque équipement reçoit des points pour les situations de son dossier au ${dateLongue(S.d.releve)} : âge rapporté à sa durée de vie, commentaires d'usure des techniciens, demandes du locataire, dépannages récents. Le total donne sa catégorie ; les raisons de la fiche sont ces situations. Barème complet : <code>moteur/BAREME.md</code>.</p>
    <table><thead><tr><th>Catégorie</th><th>Points</th><th>En 2025, dans cette catégorie</th></tr></thead><tbody>
      <tr><td><span class="cat" data-cat="urgence" data-vive>Urgent</span></td><td>plus de 80</td><td class="n">28 pannes sur 46</td></tr>
      <tr><td><span class="cat" data-cat="alerte" data-vive>Alerte</span></td><td>61 à 80</td><td class="n">9 sur 16</td></tr>
      <tr><td><span class="cat" data-cat="vigilance" data-vive>Vigilance</span></td><td>41 à 60</td><td class="n">14 sur 109</td></tr>
      <tr><td><span class="cat" data-cat="surveiller">À surveiller</span></td><td>21 à 40</td><td class="n">18 sur 439</td></tr>
      <tr><td><span class="cat" data-cat="calme">Calme</span></td><td>1 à 20</td><td class="n">7 sur 434</td></tr>
      <tr><td><span class="cat" data-cat="ras">RAS</span></td><td>0</td><td class="n">0 sur 241</td></tr>
    </tbody></table>
    <p><b>À visiter</b> : 45 points ou plus, soit les catégories Urgent et Alerte et le haut de Vigilance. Sur 2025, les 128 premiers de la liste auraient trouvé 43 des 76 pannes bloquantes, contre 16 en suivant l'âge seul.</p>
    <h2>Rénovations</h2>
    <p>Les ${nb(R.operations.length)} opérations du plan d'investissement sont classées sur cinq critères : obligation légale (logements qui sortent de G, F ou E), énergie économisée par euro, pannes et dépenses d'entretien, demandes des locataires, fin de vie des équipements. Le calendrier tient sous ${euros(R.plafond)} par an. Il est comparé à l'ordre chronologique actuel des demandes. Détail : <code>livrables/defi2/README.md</code>.</p>
    <h2>Les données</h2>
    <p>Le jeu de données fictif du défi BâtIA : 8 résidences de la métropole toulousaine, ${nb(S.d.logements.length)} logements, ${nb(S.d.equipements.length)} équipements suivis, jusqu'au ${dateLongue(S.d.releve)}. Les positions des résidences sur la carte sont fictives. Tout est calculé sur cette machine.</p>`;
}

function pageDonnees() {
  const d = S.d;
  const nbDec = Object.keys(S.decisions).length;
  return `
    <h1 id="page-titre">Données</h1>
    <p class="chapeau">Relevé au ${dateLongue(d.releve)}${ageReleve(d.releve) ? `, il y a ${ageReleve(d.releve)}` : ''}${d.imports?.length ? ` · ${pl(d.imports.length, 'trimestre importé', 'trimestres importés')}` : ''}</p>
    <table><tbody>
      <tr><td>Résidences</td><td class="n">${nb(d.residences.length)}</td></tr>
      <tr><td>Logements</td><td class="n">${nb(d.logements.length)} sur ≈ 6 300</td></tr>
      <tr><td>Équipements suivis</td><td class="n">${nb(d.equipements.length)}</td></tr>
      <tr><td>Décisions prises</td><td class="n">${nb(nbDec)}</td></tr>
    </tbody></table>
    <h2>Exporter</h2>
    <div class="actions">
      <a class="bouton" href="/api/export/decisions.csv" download>Décisions · ${nb(nbDec)}</a>
      <a class="bouton" href="/api/export/file.csv" download>File à visiter et à surveiller</a>
      <a class="bouton" href="/api/export/scores.csv" download>Scores du défi 1</a>
      <a class="bouton" href="/api/export/plan.csv" download>Plan de rénovation</a>
    </div>
    <h2>Importer vos données</h2>
    <p>Un classeur Excel ou un fichier CSV. Chaque feuille est reconnue à ses colonnes, dans l'ordre que vous voulez, et rangée dans la bonne table : résidences, bâtiments, logements, équipements, demandes, interventions, commandes, plan d'investissement, prestataires, référentiels. Une ligne dont l'identifiant existe déjà remplace l'ancienne, les autres s'ajoutent. Les historiques et les scores sont recalculés à la date du dernier relevé.</p>
    <label class="zone-depot" data-zone-depot><input type="file" accept=".xlsx,.xlsm,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" data-importer hidden>
      <svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true"><path d="M12 16V4m0 0l-4 4m4-4l4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <b>Glissez un classeur Excel ou un CSV ici</b><span>ou cliquez pour choisir un fichier · .xlsx, .csv</span>
    </label>
    <div class="retour-import" id="retour-import" role="status" aria-live="polite">${d.journalImports?.length ? rapportImports(d) : ''}</div>
    <h2>Territoire</h2>
    ${blocTerritoire()}`;
}

// ── Navigation : l'adresse dit ce qui est ouvert ─────────────────────
function lireAdresse() {
  const h = decodeURIComponent(location.hash.replace(/^#\/?/, ''));
  const [type, id] = h.split('/');
  S.page = type === 'methode' || type === 'donnees' ? type : null;
  if (S.page) return;
  const connu = { equipement: I.equip, logement: I.logt, residence: I.res, operation: I.op }[type];
  if (connu?.has(id)) S.sel = { type, id };
  else {
    S.sel = null;
    // lien périmé ou inventé (#/residence/XXX) : on revient à l'accueil au lieu de vider la liste
    if (h) history.replaceState(null, '', '#/');
  }
  if (S.residence && !I.res.has(S.residence)) S.residence = null;
}
function aller(chemin, { remplacer = false } = {}) {
  const h = `#/${chemin}`;
  if (location.hash === h) return appliquer();
  if (remplacer) history.replaceState(null, '', h); else history.pushState(null, '', h);
  appliquer();
}
let dernierSel = null;
async function appliquer() {
  const avant = S.page;
  lireAdresse();
  if (S.page) { await rendrePage(); return; }
  if (avant) $('#page').hidden = true;
  const sel = S.sel ? `${S.sel.type}/${S.sel.id}` : null;
  if (S.sel?.type === 'residence') S.residence = S.sel.id;
  // une opération ouverte d'ailleurs (lien, fiche résidence) : la lentille Rénovations se met en place, sur son année
  if (S.sel?.type === 'operation' && sel !== dernierSel) {
    const o = I.op.get(S.sel.id);
    if (o) { if (!(S.annee >= o.debut && S.annee < o.debut + o.duree)) S.annee = o.debut; if (S.lentille !== 'renovations') poserLentille('renovations'); majCarte(); }
  }
  // un équipement ouvert d'ailleurs (recherche, fiche logement) : la file se règle pour le montrer
  if (S.sel?.type === 'equipement' && sel !== dernierSel) {
    const e = I.equip.get(S.sel.id);
    if (e) {
      const onglet = decide(e) ? 'decide' : e.niveau !== 'calme' ? e.niveau : null;
      if (onglet && onglet !== S.onglet && !(S.onglet === 'decide' && decide(e))) { S.onglet = onglet; S.limite = 50; }
      if (S.residence && S.residence !== e.r) S.residence = null;
      if (S.famille && S.famille !== e.famille) S.famille = '';
      const pos = equipementsFiltres().filter((x) => (S.onglet === 'decide' ? decide(x) : !decide(x) && x.niveau === S.onglet)).findIndex((x) => x.id === e.id);
      if (pos >= S.limite) S.limite = Math.ceil((pos + 1) / 50) * 50;
    }
  }
  if (sel !== dernierSel) S.histoireOuverte = null;
  rendreFile();
  await rendreFiche();
  if (telephone() && S.sel && S.feuille === 'basse') poserFeuille('mi');
  if (sel !== dernierSel && carte) {
    const rid = S.sel ? (S.sel.type === 'residence' ? S.sel.id : S.sel.type === 'logement' ? I.logt.get(S.sel.id)?.r : S.sel.type === 'operation' ? I.op.get(S.sel.id)?.r : I.equip.get(S.sel.id)?.r) : S.residence;
    carte.choisir(rid || null);
    if (S.sel && rid) setTimeout(() => carte.allerVers(rid, { zoom: S.sel.type === 'residence' ? 12.5 : 13.3 }), 30);
  }
  dernierSel = sel;
  const actif = $('.ligne[aria-current="true"], .res-energie li[aria-current="true"], .op-ligne[aria-current="true"]');
  if (actif) actif.scrollIntoView({ block: 'nearest' });
}

// ── Décider ─────────────────────────────────────────────────────────
async function decider(id, choix) {
  const note = $('#fiche .note')?.value || '';
  try {
    const r = await api('/api/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, choix, note }) });
    S.decisions = r.decisions;
  } catch (err) { annoncer(err.message); return; }
  const e = I.equip.get(id);
  annoncer(`${CHOIX[choix].fait} · ${e.libelle}`, { annuler: id });
  S.garderDefilement = true;
  rendreFile(); await rendreFiche(); majCarte();
}
async function annuler(id) {
  try { S.decisions = (await api(`/api/decision/${encodeURIComponent(id)}`, { method: 'DELETE' })).decisions; } catch (err) { annoncer(err.message); return; }
  annoncer('Décision annulée');
  S.garderDefilement = true;
  rendreFile(); await rendreFiche(); majCarte();
}
let minuterie = null;
function annoncer(texte, { annuler: id } = {}) {
  const el = $('#annonce');
  el.innerHTML = `<span>${texte}</span>${id ? `<button type="button" data-annuler="${id}">Annuler</button>` : ''}`;
  el.classList.add('visible');
  clearTimeout(minuterie);
  minuterie = setTimeout(() => el.classList.remove('visible'), id ? 6000 : 2600);
}

// ── Recherche ───────────────────────────────────────────────────────
let index = [];
function indexer() {
  index = [
    ...S.d.residences.map((r) => ({ type: 'Résidence', titre: r.nom, sous: `${pl(r.logements, 'logement', 'logements')}`, cle: sansAccent(`${r.nom} ${r.lettre} ${r.id}`), aller: `residence/${r.id}`, ordre: 0 })),
    ...S.d.logements.map((l) => ({ type: 'Logement', titre: `Logement ${numLogt(l.id)} · bât. ${bat(l.b)}`, sous: `${I.res.get(l.r).nom} · ${l.typo}`, cle: sansAccent(`${l.id} ${l.id.replace('LGT-', '')} ${bat(l.b)} ${numLogt(l.id)} logement`), aller: `logement/${l.id}`, ordre: 1 })),
    ...S.d.equipements.map((e) => ({ type: 'Équipement', titre: e.libelle, sous: lieu(e).replace(/<[^>]+>/g, ''), cle: sansAccent(`${e.id} ${e.libelle} ${lieu(e)}`), aller: `equipement/${e.id}`, ordre: 2, rang: e.rang })),
  ];
}
function chercher(q) {
  const mots = sansAccent(q).replace(/[·,]/g, ' ').split(/\s+/).filter(Boolean);
  if (!mots.length) return [];
  return index.filter((x) => mots.every((m) => x.cle.includes(m))).sort((a, b) => a.ordre - b.ordre || (a.rang || 0) - (b.rang || 0)).slice(0, 9);
}
function majSuggestions() {
  const input = $('#recherche');
  const ul = $('#suggestions');
  const res = chercher(input.value);
  ul.hidden = !res.length && !input.value;
  input.setAttribute('aria-expanded', String(!ul.hidden));
  ul.innerHTML = res.length ? res.map((x, i) => `<li role="option" data-aller="${x.aller}" aria-selected="${i === 0}"><span class="sug-type">${x.type}</span><span>${esc(x.titre)}</span><span class="sug-sous">${esc(x.sous)}</span></li>`).join('') : input.value ? '<li aria-disabled="true"><span class="sug-type">Aucun</span><span>Pas de résultat</span></li>' : '';
}

// ── La feuille du téléphone ─────────────────────────────────────────
function hauteurFeuille() {
  const H = innerHeight;
  return { basse: Math.min(210, H * 0.32), mi: H * 0.5, haute: H - 74 }[S.feuille] || H * 0.5;
}
function poserFeuille(etat) {
  S.feuille = etat;
  document.body.style.setProperty('--feuille', `${hauteurFeuille()}px`);
}
function brancherFeuille() {
  let depart = null, h0 = 0, parPoignee = false;
  // on tire la feuille par sa poignée ou par son en-tête (hors boutons et liens)
  document.addEventListener('pointerdown', (ev) => {
    if (!telephone()) return;
    const p = ev.target.closest('.poignee');
    const tete = !p && ev.target.closest('.panneau .tete');
    if (!p && (!tete || ev.target.closest('button, a, select, input, [data-aller]'))) return;
    depart = ev.clientY; h0 = hauteurFeuille(); parPoignee = !!p;
    document.body.classList.add('glisse');
    (p || tete).setPointerCapture(ev.pointerId);
  });
  document.addEventListener('pointercancel', () => { if (depart == null) return; depart = null; document.body.classList.remove('glisse'); poserFeuille(S.feuille); });
  document.addEventListener('pointermove', (ev) => {
    if (depart == null) return;
    const h = Math.max(90, Math.min(innerHeight - 60, h0 + (depart - ev.clientY)));
    document.body.style.setProperty('--feuille', `${h}px`);
  });
  document.addEventListener('pointerup', (ev) => {
    if (depart == null) return;
    const dy = depart - ev.clientY;
    depart = null;
    document.body.classList.remove('glisse');
    const ordre = ['basse', 'mi', 'haute'];
    const i = ordre.indexOf(S.feuille);
    if (Math.abs(dy) < 8) poserFeuille(parPoignee ? ordre[(i + 1) % 3 === 0 ? 0 : i + 1] : S.feuille);
    else poserFeuille(ordre[Math.max(0, Math.min(2, i + (dy > 0 ? 1 : -1) * (Math.abs(dy) > innerHeight * 0.28 ? 2 : 1)))]);
  });
}

// ── Les gestes ──────────────────────────────────────────────────────
let calme = 0;
function brancher() {
  // en données réelles, le kit ne répond plus : le monde réel a ses propres gestes (reel/monde.mjs)
  const ailleurs = () => document.body.classList.contains('monde-reel');
  document.addEventListener('click', async (ev) => {
    if (ailleurs()) return;
    const t = ev.target;
    const lien = t.closest('[data-aller]');
    if (lien && !lien.matches('[aria-disabled]')) { ev.preventDefault(); $('#recherche').value = ''; $('#suggestions').hidden = true; document.body.classList.remove('cherche'); return aller(lien.dataset.aller); }
    const ligneEl = t.closest('.ligne');
    if (ligneEl) return aller(`equipement/${ligneEl.dataset.id}`);
    const resEl = t.closest('.res-energie li');
    if (resEl) return aller(`residence/${resEl.dataset.res}`);
    const opEl = t.closest('.op-ligne');
    if (opEl) return aller(`operation/${opEl.dataset.op}`);
    const choixOpEl = t.closest('[data-choix-op], [data-annuler-op]');
    if (choixOpEl && (ev.detail > 1 || Date.now() < calme)) return;
    if (choixOpEl && S.sel?.type === 'operation') {
      calme = Date.now() + 600;
      try {
        const r = choixOpEl.dataset.choixOp
          ? await api('/api/renovation', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: S.sel.id, choix: choixOpEl.dataset.choixOp }) })
          : await api(`/api/renovation/${encodeURIComponent(S.sel.id)}`, { method: 'DELETE' });
        S.choixRenov = r.choixRenovations;
      } catch (err) { annoncer(err.message); return; }
      const o = I.op.get(S.sel.id);
      annoncer(choixOpEl.dataset.choixOp ? `${CHOIX_RENOV[choixOpEl.dataset.choixOp].fait} · ${nomOp(o)}, résidence ${lettre(o.r)}` : 'Décision annulée');
      S.garderDefilement = true;
      rendreFile(); await rendreFiche(); majCarte(); return;
    }
    const annee = t.closest('[data-choisir-annee]');
    if (annee) { S.annee = +annee.dataset.choisirAnnee; rendreFile(); majCarte(); return; }
    const bande = t.closest('[data-bande]');
    if (bande) { S.bande = S.bande === bande.dataset.bande ? '' : bande.dataset.bande; S.limite = 50; rendreFile(); $('#file .defile').scrollTop = 0; return; }
    const onglet = t.closest('[data-onglet]');
    if (onglet) { S.onglet = onglet.dataset.onglet; S.limite = 50; S.bande = ''; rendreFile(); $('#file .defile').scrollTop = 0; return; }
    const lentille = t.closest('[data-lentille]');
    if (lentille) {
      const deja = lentille.getAttribute('aria-selected') === 'true';
      if (deja && !document.body.classList.contains('liste-fermee')) { document.body.classList.add('liste-fermee'); lentille.setAttribute('aria-selected', 'false'); return; }
      document.body.classList.remove('liste-fermee');
      return changerLentille(lentille.dataset.lentille);
    }
    const ret = t.closest('[data-retour]');
    if (ret && S.sel?.type === 'equipement') {
      const x = S.decisions[S.sel.id];
      if (!x) return;
      try { const r = await api('/api/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: S.sel.id, choix: x.choix, note: x.note, retour: ret.dataset.retour }) }); S.decisions = r.decisions; } catch (err) { annoncer(err.message); return; }
      S.garderDefilement = true; await rendreFiche(); rendreFile(); return;
    }
    if (t.closest('[data-semaine]')) { S.semaine = true; S.onglet = 'visiter'; S.bande = ''; document.body.classList.remove('liste-fermee'); fermerCompte(); if (S.lentille !== 'pannes') return changerLentille('pannes'); rendreFile(); return; }
    if (t.closest('[data-semaine-fin]')) { S.semaine = false; rendreFile(); return; }
    if (t.closest('[data-fermer-file]')) { document.body.classList.add('liste-fermee'); $$('[data-lentille]').forEach((b) => b.setAttribute('aria-selected', 'false')); return; }
    const seuil = t.closest('[data-seuil]');
    if (seuil) { S.seuil = seuil.dataset.seuil; localStorage.setItem('foraine.seuil', S.seuil); rendreFile(); majCarte(); if (S.sel) { S.garderDefilement = true; await rendreFiche(); } return; }
    if (t.closest('[data-retirer="residence"]')) { S.residence = null; if (S.sel?.type === 'residence') return aller(''); carte.choisir(S.sel ? (I.equip.get(S.sel.id)?.r || I.logt.get(S.sel.id)?.r || null) : null); rendreFile(); return; }
    if (t.closest('[data-plus]')) { S.limite += 50; const y = $('#file .defile').scrollTop; rendreFile(); $('#file .defile').scrollTop = y; return; }
    if (t.closest('[data-fermer-fiche]')) return fermerFiche();
    if (t.closest('[data-fermer]')) return fermerPage();
    const dec = t.closest('[data-decider]');
    const ann = t.closest('[data-annuler]');
    // un double clic ne décide pas puis n'annule pas dans la foulée
    if ((dec || ann) && (ev.detail > 1 || Date.now() < calme)) return;
    if (dec || ann) calme = Date.now() + 600;
    if (dec && S.sel?.type === 'equipement') return decider(S.sel.id, dec.dataset.decider);
    if (ann) { $('#annonce').classList.remove('visible'); return annuler(ann.dataset.annuler); }
    const hist = t.closest('[data-histoire]');
    if (hist) { S.histoireOuverte = hist.dataset.histoire; S.garderDefilement = true; return rendreFiche(); }
    const ech = t.closest('[data-echelle]');
    if (ech) return carte?.allerA(ech.dataset.echelle);
    if (t.closest('.outils') && telephone() && !document.body.classList.contains('cherche')) { document.body.classList.add('cherche'); $('#recherche').focus(); return; }
  });
  document.addEventListener('change', async (ev) => {
    if (ev.target.matches('.filtre-famille')) { S.famille = ev.target.value; S.limite = 50; rendreFile(); return; }
    if (ev.target.matches('.filtre-residence')) {
      const id = ev.target.value || null;
      S.residence = id; S.limite = 50;
      if (!id && S.sel?.type === 'residence') return aller('');
      carte.choisir(id || (S.sel ? (I.equip.get(S.sel.id)?.r || I.logt.get(S.sel.id)?.r || null) : null));
      if (id) carte.allerVers(id, { zoom: 12.5 });
      rendreFile(); majCarte();
      return;
    }
    if (ev.target.matches('[data-importer]')) return importer(ev.target.files[0]);
  });
  // survoler une ligne fait battre la pastille de sa résidence
  let survol = null;
  document.addEventListener('pointerover', (ev) => {
    if (ailleurs()) return;
    const el = ev.target.closest('.ligne, .res-energie li, .op-ligne, .equip li[data-aller]');
    const rid = el ? (el.dataset.id ? I.equip.get(el.dataset.id)?.r : el.dataset.op ? I.op.get(el.dataset.op)?.r : el.dataset.res || null) : null;
    if (rid === survol) return;
    survol = rid;
    carte?.signaler(rid);
  });
  const input = $('#recherche');
  input.addEventListener('input', majSuggestions);
  input.addEventListener('focus', majSuggestions);
  input.addEventListener('blur', () => setTimeout(() => { $('#suggestions').hidden = true; input.setAttribute('aria-expanded', 'false'); if (!input.value) document.body.classList.remove('cherche'); }, 160));
  input.addEventListener('keydown', (ev) => {
    const items = $$('#suggestions li[data-aller]');
    const i = items.findIndex((x) => x.getAttribute('aria-selected') === 'true');
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
      ev.preventDefault();
      const j = Math.max(0, Math.min(items.length - 1, i + (ev.key === 'ArrowDown' ? 1 : -1)));
      items.forEach((x, k) => x.setAttribute('aria-selected', String(k === j)));
    } else if (ev.key === 'Enter' && items[Math.max(0, i)]) {
      ev.preventDefault();
      const cible = items[Math.max(0, i)].dataset.aller;
      input.value = ''; input.blur(); document.body.classList.remove('cherche');
      aller(cible);
    } else if (ev.key === 'Escape') { input.value = ''; input.blur(); }
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.target.matches('input, select, textarea')) return;
    if (ailleurs()) return;
    if (ev.key === '/') { ev.preventDefault(); input.focus(); return; }
    if (ev.key === 'Escape') { if (S.page) fermerPage(); else if (S.sel) fermerFiche(); return; }
    if (ev.key === 'Enter' && ev.target.matches('.ligne, .res-energie li, .op-ligne')) { ev.target.click(); return; }
    if (S.lentille === 'pannes' && ['ArrowDown', 'ArrowUp', 'j', 'k'].includes(ev.key)) {
      const lignes = $$('#file .ligne');
      if (!lignes.length) return;
      ev.preventDefault();
      // on part de la ligne où se trouve le curseur clavier, sinon de celle qui est ouverte
      const ici = ev.target.closest?.('#file .ligne');
      const i = lignes.findIndex((x) => (ici ? x === ici : x.getAttribute('aria-current') === 'true'));
      const j = i < 0 ? 0 : Math.max(0, Math.min(lignes.length - 1, i + (ev.key === 'ArrowDown' || ev.key === 'j' ? 1 : -1)));
      aller(`equipement/${lignes[j].dataset.id}`, { remplacer: S.sel?.type === 'equipement' });
      return;
    }
    if (S.sel?.type === 'equipement' && !S.decisions[S.sel.id]) {
      const k = Object.entries(CHOIX).find(([, c]) => c.touche === ev.key.toLowerCase());
      if (k) decider(S.sel.id, k[0]);
    }
  });
  addEventListener('popstate', appliquer);
  addEventListener('resize', () => { if (telephone()) poserFeuille(S.feuille); });
}
function fermerFiche() {
  if (S.sel?.type === 'residence') S.residence = S.sel.id;
  aller('');
  carte?.choisir(S.residence);
}
function fermerPage() {
  S.page = null; $('#page').hidden = true;
  history.pushState(null, '', S.sel ? `#/${S.sel.type}/${S.sel.id}` : '#/');
}
function poserLentille(l) {
  S.lentille = l;
  document.body.classList.toggle('energie', l === 'energie');
  document.body.classList.toggle('renovations', l === 'renovations');
  $$('[data-lentille]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.lentille === l)));
}
async function changerLentille(l) {
  if (S.lentille === l) return;
  poserLentille(l);
  const t = S.sel?.type;
  const rid = t === 'equipement' ? I.equip.get(S.sel.id)?.r : t === 'logement' ? I.logt.get(S.sel.id)?.r : t === 'operation' ? I.op.get(S.sel.id)?.r : null;
  if (t === 'equipement' && l === 'energie') {
    const e = I.equip.get(S.sel.id);
    aller(e?.l ? `logement/${e.l}` : `residence/${e.r}`, { remplacer: true });
  } else if ((t === 'equipement' || t === 'logement') && l === 'renovations') aller(`residence/${rid}`, { remplacer: true });
  else if (t === 'operation' && l !== 'renovations') aller(`residence/${rid}`, { remplacer: true });
  else { rendreFile(); await rendreFiche(); }
  majCarte();
  setTimeout(() => { const d = $('#file .defile'); if (d) d.scrollTop = 0; }, 120);
}
function rapportImports(d) {
  const parImport = new Map();
  for (const j of d.journalImports) { if (!parImport.has(j.import)) parImport.set(j.import, []); parImport.get(j.import).push(j); }
  return `<p class="rapport-titre">${pl(parImport.size, 'import chargé', 'imports chargés')} · ${d.scores?.recalcules ? `scores recalculés au ${dateLongue(d.scores.dateRef)}` : 'scores du livrable'}</p>
    <ul class="rapport">${[...parImport].map(([nom, js]) => `<li><b>${esc(nom.slice(20))}</b> ${js.map((j) => `${j.prefixe} : ${pl(j.ajoutees, 'ligne ajoutée', 'lignes ajoutées')}${j.remplacees ? `, ${nb(j.remplacees)} remplacées` : ''}`).join(' · ')}</li>`).join('')}</ul>`;
}

function rapportImport(r) {
  const s = r.scores || {};
  return `<p class="rapport-titre">Import terminé · relevé au ${dateLongue(r.releve)}${r.avant !== r.releve ? ` (avant : ${dateLongue(r.avant)})` : ''}</p>
    <ul class="rapport">
      ${r.tables.map((t) => `<li class="ok"><b>${esc(t.prefixe)}</b> ← feuille « ${esc(t.feuille)} » : ${pl(t.ajoutees, 'ligne ajoutée', 'lignes ajoutées')}${t.remplacees ? `, ${nb(t.remplacees)} remplacées` : ''}${t.manquantes?.length ? `<small> · colonnes absentes laissées vides : ${esc(t.manquantes.join(', '))}</small>` : ''}${t.extra?.length ? `<small> · colonnes ignorées : ${esc(t.extra.join(', '))}</small>` : ''}</li>`).join('')}
      ${(r.ignorees || []).map((f) => `<li class="ignore">Feuille « ${esc(f.feuille)} » ignorée : ${esc(f.raison)}</li>`).join('')}
      ${s.recalcules ? `<li class="ok"><b>Scores recalculés</b> par le moteur sur ${nb(s.equipements)} équipements au ${dateLongue(s.dateRef)}${s.changementsBande ? `, ${pl(s.changementsBande, 'équipement change', 'équipements changent')} de catégorie` : ', aucun changement de catégorie'}${s.nouveaux ? `, ${nb(s.nouveaux)} nouveaux` : ''}</li>` : `<li class="ignore">${esc(s.erreur || 'Scores inchangés.')}</li>`}
      ${r.sansPosition?.length ? `<li class="ignore">${pl(r.sansPosition.length, 'résidence sans position', 'résidences sans position')} sur la carte : ${esc(r.sansPosition.join(', '))}</li>` : ''}
    </ul>`;
}

async function importer(fichier) {
  if (!fichier) return;
  const retour = $('#retour-import');
  retour.innerHTML = `<p class="rapport-titre">Import de ${esc(fichier.name)} en cours, lecture puis recalcul des scores…</p>`;
  try {
    const classeur = /\.xls[xm]$/i.test(fichier.name);
    const r = await api('/api/import', { method: 'POST', headers: { 'Content-Type': classeur ? 'application/octet-stream' : 'text/csv', 'X-Nom-Fichier': fichier.name }, body: classeur ? await fichier.arrayBuffer() : await fichier.text() });
    await charger(); indexer(); rendreFile(); majCarte();
    retour.innerHTML = rapportImport(r);
  } catch (err) { retour.innerHTML = `<p class="rapport-titre erreur">${esc(err.message)}</p>`; }
}

for (const type of ['dragenter', 'dragover']) document.addEventListener(type, (ev) => { const z = ev.target.closest?.('[data-zone-depot]'); if (!z) return; ev.preventDefault(); z.classList.add('survol'); });
document.addEventListener('dragleave', (ev) => { const z = ev.target.closest?.('[data-zone-depot]'); if (z && !z.contains(ev.relatedTarget)) z.classList.remove('survol'); });
document.addEventListener('drop', (ev) => { const z = ev.target.closest?.('[data-zone-depot]'); if (!z) return; ev.preventDefault(); z.classList.remove('survol'); importer(ev.dataTransfer.files[0]); });

// ── Démarrage ───────────────────────────────────────────────────────
async function demarrer() {
  await charger();
  indexer();
  brancher();
  brancherFeuille();
  if (telephone()) poserFeuille('basse');
  lireAdresse();
  const lienDirect = !!S.sel || !!S.page;
  rendreFile();
  const el = $('#carte');
  el.addEventListener('carte:residence', (e) => aller(`residence/${e.detail.id}`));
  el.addEventListener('carte:echelle', (e) => {
    S.echelle = e.detail.echelle;
    $$('[data-echelle]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.echelle === S.echelle)));
    });
  el.addEventListener('carte:survol', (e) => {
    $$('.ligne').forEach((x) => x.classList.toggle('meme-residence', !!e.detail.id && I.equip.get(x.dataset.id)?.r === e.detail.id));
  });
  carte = await creerCarte(el, { residences: residencesCarte(), echelle: S.sel ? 'toulouse' : 'sudouest', depuis: lienDirect || reduit ? null : 'france', molette: true, zoneOccupee });
  window.foraine = { carte, S };
  majCarte();
  S.echelle = carte.echelle;
  $$('[data-echelle]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.echelle === S.echelle)));
  // la carte se pose d'abord ; ce qu'il faut décider arrive juste après
  setTimeout(() => {
    $('#file').classList.add('arrive');
    document.body.classList.add('pret', 'liste-fermee');
    $$('[data-lentille]').forEach((b) => b.setAttribute('aria-selected', 'false'));
    appliquer();
  }, lienDirect || reduit ? 0 : 1400);
}
demarrer().catch((err) => {
  console.error(err);
  document.body.insertAdjacentHTML('beforeend', `<div class="page"><article class="page-corps"><h1>BâtIA ne démarre pas</h1><p>${esc(err.message)}</p></article></div>`);
});

const menu = document.querySelector('.menu');
if (menu) {
  const bouton = menu.querySelector('[data-menu]');
  const liste = menu.querySelector('.menu-liste');
  const ouvrirMenu = (ouvert) => { liste.hidden = !ouvert; bouton.setAttribute('aria-expanded', String(ouvert)); };
  bouton.addEventListener('click', (ev) => { ev.stopPropagation(); ouvrirMenu(liste.hidden); });
  liste.addEventListener('click', () => setTimeout(() => ouvrirMenu(false), 0));
  document.addEventListener('click', (ev) => { if (!liste.hidden && !menu.contains(ev.target)) ouvrirMenu(false); });
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !liste.hidden) { ouvrirMenu(false); bouton.focus(); } });
}

const compte = document.querySelector('.compte-util');
function fermerCompte() { if (!compte) return; compte.querySelector('.compte-popover').hidden = true; compte.querySelector('[data-compte]').setAttribute('aria-expanded', 'false'); }
function appliquerRole() {
  document.body.classList.toggle('role-direction', S.role === 'direction');
  $$('[data-role]').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.role === S.role)));
}
function appliquerAnimations() {
  const reduites = localStorage.getItem('foraine.animations') === 'reduites';
  document.body.classList.toggle('sans-animation', reduites);
  $$('[data-anim]').forEach((b) => b.setAttribute('aria-pressed', String(reduites)));
}
if (compte) {
  const bouton = compte.querySelector('[data-compte]');
  const popover = compte.querySelector('.compte-popover');
  bouton.addEventListener('click', (ev) => { ev.stopPropagation(); const ouvert = popover.hidden; popover.hidden = !ouvert; bouton.setAttribute('aria-expanded', String(ouvert)); });
  document.addEventListener('click', (ev) => { if (!popover.hidden && !compte.contains(ev.target)) fermerCompte(); });
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !popover.hidden) { fermerCompte(); bouton.focus(); } });
  popover.addEventListener('click', (ev) => {
    const role = ev.target.closest('[data-role]');
    if (role) { S.role = role.dataset.role; localStorage.setItem('foraine.role', S.role); appliquerRole(); fermerCompte(); if (S.role === 'direction') { S.semaine = false; document.body.classList.remove('liste-fermee'); changerLentille('renovations'); } return; }
    if (ev.target.closest('[data-anim]')) { localStorage.setItem('foraine.animations', localStorage.getItem('foraine.animations') === 'reduites' ? 'normales' : 'reduites'); appliquerAnimations(); return; }
    if (ev.target.closest('[data-sortie]')) { fermerCompte(); localStorage.removeItem('foraine.compte'); location.replace('/connexion.html'); }
  });
  try {
    const c = JSON.parse(localStorage.getItem('foraine.compte'));
    if (c && c.nom) {
      $$('.compte-util .avatar').forEach((a) => { a.textContent = c.initiales || 'BA'; });
      compte.querySelector('.compte-tete b').textContent = c.nom;
      bouton.title = c.nom;
    }
  } catch {}
  appliquerRole();
  appliquerAnimations();
}
