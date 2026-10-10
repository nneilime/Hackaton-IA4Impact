// BâtIA · données réelles — la bascule « Kit du jury / Données réelles » et le monde réel.
// Branchement isolé : ce module se charge à côté de l'application (une ligne dans app/index.html) et attend la carte
// que l'application expose (window.foraine.carte). Il ne touche ni aux données ni au code du kit : en données réelles,
// tout ce qui vient du kit est masqué (classe `monde-reel` sur <body>), et rien du kit n'est posé sur un vrai immeuble.
// Lien direct : /?monde=reel
import { evaluer, LIBELLES } from './calcul.mjs';
import { monterCouche } from './couche.mjs';
import { ficheImmeuble, ficheGroupe, pastille, rue } from './fiche.mjs';

const BASE = new URL('.', import.meta.url).href;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const nb = (n) => new Intl.NumberFormat('fr-FR').format(n);
const pl = (n, un, plusieurs) => `${nb(n)} ${n > 1 ? plusieurs : un}`;
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]).replace(/'/g, '’');
const telephone = () => matchMedia('(max-width: 760px)').matches;
const reduit = matchMedia('(prefers-reduced-motion: reduce)').matches || localStorage.getItem('foraine.animations') === 'reduites';
const ORDRE = ['urgence', 'alerte', 'vigilance', 'surveiller', 'calme'];
const SEUIL_SEUL = 10;          // en dessous de 10 logements, un immeuble ne s'affiche jamais seul

// Les trois échelles du monde réel : tout le parc, puis la métropole toulousaine.
const ECHELLES = {
  france: [[-5.2, 41.3], [9.6, 51.1]],
  sudouest: [[-1.8, 42.69], [4.2, 45.58]],
  toulouse: [[1.26, 43.52], [1.58, 43.70]],
};

const S = { monde: 'kit', donnees: null, couche: null, choix: null, filtre: null, enCours: false, limite: 50 };

// Logements d'In'li dans un immeuble : la BDNB donne tout l'immeuble (copropriétés comprises), la DGFiP les locaux
// d'In'li sur ses parcelles (caves et parkings compris). Le plus petit des deux ; 0 si la DGFiP n'y voit aucun local.
export function logementsInli(im) {
  const bdnb = +im.nb_logements || 0;
  return im.locaux_inli == null ? bdnb : Math.min(bdnb, +im.locaux_inli);
}

// ── Les données : lues une fois, sans Internet ──────────────────────
async function chargerDonnees() {
  if (S.donnees) return S.donnees;
  const [parc, communes] = await Promise.all([
    fetch(BASE + 'donnees/parc-reel.json').then((r) => { if (!r.ok) throw new Error('parc-reel.json absent'); return r.json(); }),
    fetch(BASE + 'donnees/communes.json').then((r) => r.json()).catch(() => ({ communes: {} })),
  ]);
  const immeubles = [];
  const petits = new Map();
  for (const im of parc.immeubles || []) {
    if (!im.position) continue;
    const ev = evaluer(im);
    // la BDNB compte tous les logements de l'immeuble ; la DGFiP, les seuls locaux d'In'li : on garde le plus petit
    im.logements_inli = logementsInli(im);
    const seul = !im.individuel && im.logements_inli >= SEUIL_SEUL;
    if (seul) {
      immeubles.push({ id: im.id_bdnb, type: 'immeuble', position: im.position, logements: im.logements_inli, niveau: ev.niveau, libelle: ev.libelle, points: ev.points, emprise: im.emprise, im, ev });
    } else {
      // vie privée : un petit immeuble ou une maison rejoint le groupe de sa commune, posé au centre officiel de la commune
      const code = im.code_commune || 'inconnue';
      if (!petits.has(code)) petits.set(code, []);
      petits.get(code).push({ im, ev });
    }
  }
  const groupes = [];
  for (const [code, liste] of petits) {
    const c = communes.communes?.[code];
    if (!c) continue;
    const logements = liste.reduce((s, x) => s + x.im.logements_inli, 0);
    const parNiveau = {};
    const poids = {};
    for (const x of liste) {
      parNiveau[x.ev.niveau] = (parNiveau[x.ev.niveau] || 0) + 1;
      poids[x.ev.niveau] = (poids[x.ev.niveau] || 0) + Math.max(1, x.im.logements_inli);
    }
    // le niveau du groupe : celui qui porte le plus de logements (à égalité, le plus grave)
    const niveau = ORDRE.slice().sort((a, b) => (poids[b] || 0) - (poids[a] || 0) || ORDRE.indexOf(a) - ORDRE.indexOf(b))[0];
    const annees = liste.map((x) => +x.im.annee_construction).filter(Boolean);
    const compte = new Map();
    for (const x of liste) for (const r of x.ev.raisons) if (r.points > 0) { const k = r.texte.replace(/\s·.*$/, ''); compte.set(k, (compte.get(k) || 0) + 1); }
    groupes.push({
      id: `commune-${code}`, type: 'groupe', position: c.centre, logements, niveau, libelle: LIBELLES[niveau],
      points: Math.max(...liste.map((x) => x.ev.points)) / 2,
      g: { commune: c.nom, batiments: liste.length, logements, niveau, parNiveau, maisons: liste.filter((x) => x.im.individuel).length,
        annees: annees.length ? [Math.min(...annees), Math.max(...annees)] : null,
        // les raisons les plus partagées du groupe, sans désigner aucun bâtiment
        raisons: [...compte.entries()].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([t, n]) => `${t} (${n})`) },
    });
  }
  const communesTotal = new Set((parc.immeubles || []).map((im) => im.code_commune).filter(Boolean)).size;
  S.donnees = { parc, communes, immeubles, groupes, communesTotal, reperes: [...immeubles, ...groupes] };
  return S.donnees;
}

// ── L'interface du monde réel ───────────────────────────────────────
function monterInterface() {
  // la bascule est écrite dans l'en-tête (app/index.html, #place-bascule) ; à défaut, on la pose en haut au centre
  let bascule = $('#place-bascule .bascule');
  if (!bascule) {
    bascule = document.createElement('div');
    bascule.className = 'bascule';
    bascule.setAttribute('role', 'radiogroup');
    bascule.setAttribute('aria-label', 'Données affichées');
    bascule.innerHTML = '<button type="button" role="radio" data-monde="kit" aria-checked="true">Kit du jury</button><button type="button" role="radio" data-monde="reel" aria-checked="false">Données réelles</button>';
    ($('#place-bascule') || document.body).append(bascule);
  }

  // le panneau et la fiche du monde réel prennent la forme de la file et de la fiche du kit
  const panneau = document.createElement('aside');
  panneau.className = 'panneau file re-panneau';
  panneau.id = 'reel-panneau';
  panneau.setAttribute('aria-label', 'Parc réel');
  document.body.append(panneau);

  const fiche = document.createElement('aside');
  fiche.className = 'panneau fiche re-fiche';
  fiche.id = 'reel-fiche';
  fiche.setAttribute('aria-label', 'Fiche de l’immeuble');
  fiche.hidden = true;
  document.body.append(fiche);

  bascule.addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-monde]');
    if (b) basculer(b.dataset.monde);
  });
  // au clavier, les flèches passent d'un monde à l'autre, comme dans tout groupe de boutons radio
  bascule.addEventListener('keydown', (ev) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(ev.key)) return;
    ev.preventDefault();
    const m = ev.key === 'ArrowRight' ? 'reel' : 'kit';
    bascule.querySelector(`[data-monde="${m}"]`)?.focus();
    basculer(m);
  });
  panneau.addEventListener('click', (ev) => {
    const f = ev.target.closest('[data-filtre]');
    if (f) { S.filtre = S.filtre === f.dataset.filtre ? null : f.dataset.filtre; S.limite = 50; rendrePanneau(); return; }
    if (ev.target.closest('[data-plus]')) { S.limite += 50; rendrePanneau(); return; }
    const li = ev.target.closest('[data-reel]');
    if (li) ouvrir(li.dataset.reel);
  });
  fiche.addEventListener('click', (ev) => { if (ev.target.closest('[data-reel-fermer]')) fermer(); });
  // les gestes du kit : Échap ferme, ↑ ↓ (ou j k) parcourent la liste, Entrée ouvre
  document.addEventListener('keydown', (ev) => {
    if (S.monde !== 'reel' || ev.target.matches?.('input, select, textarea')) return;
    if (ev.key === 'Escape' && S.choix) {
      ev.stopImmediatePropagation();
      const id = S.choix;
      fermer();
      $$('#reel-panneau [data-reel]').find((x) => x.dataset.reel === id)?.focus({ preventScroll: true });
      return;
    }
    if ((ev.key === 'Enter' || ev.key === ' ') && ev.target.matches?.('[data-reel]')) { ev.stopImmediatePropagation(); ouvrir(ev.target.dataset.reel); return; }
    if (['ArrowDown', 'ArrowUp', 'j', 'k'].includes(ev.key) && !ev.target.closest?.('.bascule')) {
      const lignes = $$('#reel-panneau [data-reel]');
      if (!lignes.length) return;
      ev.preventDefault(); ev.stopImmediatePropagation();
      // on part de la ligne où se trouve le curseur clavier, sinon de l'immeuble ouvert
      const ici = ev.target.closest?.('#reel-panneau [data-reel]');
      const i = lignes.findIndex((x) => (ici ? x === ici : x.dataset.reel === S.choix));
      const j = i < 0 ? 0 : Math.max(0, Math.min(lignes.length - 1, i + (ev.key === 'ArrowDown' || ev.key === 'j' ? 1 : -1)));
      ouvrir(lignes[j].dataset.reel);
      lignes[j].focus({ preventScroll: true });
      lignes[j].scrollIntoView({ block: 'nearest' });
    }
  }, true);
  // les boutons d'échelle de BâtIA cadrent sur le parc réel, en laissant la place des panneaux
  document.addEventListener('click', (ev) => {
    if (S.monde !== 'reel') return;
    const e = ev.target.closest('[data-echelle]');
    if (!e) return;
    ev.stopImmediatePropagation();
    $$('.echelles [data-echelle]').forEach((b) => b.setAttribute('aria-pressed', String(b === e)));
    cadrer(e.dataset.echelle);
  }, true);
  return { bascule, panneau, fiche };
}
let UI = null;

function marges() {
  const p = telephone() ? 16 : 34;
  if (telephone()) return { top: 128, bottom: Math.round(innerHeight * 0.42) + 10, left: p, right: p };
  // offsetLeft ignore le glissement en cours : on cadre sur la place que les panneaux prendront
  const pan = $('#reel-panneau'), fi = $('#reel-fiche');
  const gauche = document.body.classList.contains('monde-reel') && pan ? pan.offsetLeft + pan.offsetWidth : 0;
  const droite = fi && !fi.hidden ? innerWidth - fi.offsetLeft : 0;
  return { top: 92, bottom: 62, left: gauche + p, right: droite + p };
}
function cadrer(cle, { duree = 1700 } = {}) {
  const map = window.foraine.carte.map;
  const m = marges();
  let cam = map.cameraForBounds(ECHELLES[cle], { padding: m });
  if (!cam) return;
  // écran trop petit pour toute la France (téléphone) : le zoom serait bridé au minimum de la carte et le décalage
  // des marges ne vaudrait plus ; on reste au zoom minimal, centré sur le parc, les marges passant en décalage
  if (cam.zoom < map.getMinZoom()) {
    const [[o, s], [e, n]] = ECHELLES.sudouest;
    cam = { center: [(o + e) / 2, (s + n) / 2], zoom: map.getMinZoom(), offset: [(m.left - m.right) / 2, (m.top - m.bottom) / 2] };
  }
  if (reduit) map.easeTo({ ...cam, pitch: 0, bearing: 0, duration: 0 });
  else map.flyTo({ ...cam, pitch: 0, bearing: 0, duration: duree, curve: 1.35, essential: true });
}

function rendrePanneau(progression = 1) {
  const d = S.donnees;
  if (!d) return;
  const logts = Math.round(d.reperes.reduce((t, r) => t + r.logements, 0) * progression);
  const parNiveau = Object.fromEntries(ORDRE.map((n) => [n, d.immeubles.filter((r) => r.niveau === n).length]));
  const liste = d.immeubles.filter((r) => !S.filtre || r.niveau === S.filtre).sort((a, b) => b.points - a.points || b.logements - a.logements);
  const dpts = Object.keys(d.parc.departements || {}).length;
  UI.panneau.innerHTML = `
    <button class="poignee" type="button" aria-label="Agrandir ou réduire la liste"></button>
    <div class="tete">
      <div class="compte"><b>${nb(logts)}</b><span>logements</span><em>${pl(dpts, 'département', 'départements')}</em></div>
      <div class="bandes" role="group" aria-label="Catégorie">${ORDRE.filter((n) => parNiveau[n]).map((n) => `<button type="button" class="cat" data-cat="${n}"${['urgence', 'alerte', 'vigilance'].includes(n) ? ' data-vive' : ''} data-filtre="${n}" aria-pressed="${S.filtre === n}">${esc(LIBELLES[n])} <b>${nb(Math.round(parNiveau[n] * progression))}</b></button>`).join('')}</div>
    </div>
    <div class="defile">
      <ol class="lignes" aria-label="Immeubles">${liste.slice(0, S.limite).map((r) => `<li class="ligne" tabindex="0" role="button" data-reel="${esc(r.id)}" aria-current="${S.choix === r.id}">
        ${pastille(r.niveau)}<span class="ligne-titre">${esc(rue(r.im.adresse, r.im.commune))}</span><span class="ligne-lieu">${esc(r.im.commune || '')} · ${pl(r.logements, 'logement', 'logements')}</span></li>`).join('')}</ol>
      ${liste.length > S.limite ? `<button class="plus" type="button" data-plus>Afficher ${nb(Math.min(50, liste.length - S.limite))} de plus</button>` : ''}
    </div>`;
}

function ouvrir(id) {
  const r = S.donnees?.reperes.find((x) => x.id === id);
  if (!r) return;
  S.choix = id;
  UI.fiche.hidden = false;
  UI.fiche.innerHTML = r.type === 'groupe' ? ficheGroupe(r.g) : ficheImmeuble(r.im, r.ev, { sources: S.donnees.parc.sources || {} });
  UI.fiche.classList.remove('re-arrive'); void UI.fiche.offsetWidth; UI.fiche.classList.add('re-arrive');
  document.body.classList.add('re-fiche-ouverte');
  S.couche?.choisir(id);
  $$('#reel-panneau [data-reel]').forEach((li) => li.setAttribute('aria-current', String(li.dataset.reel === id)));
  const m = marges();
  const decalage = telephone() ? [0, -Math.round(innerHeight * 0.2)] : [Math.round((m.left - m.right) / 2), 0];
  S.couche?.allerVers(id, { decalage });
}
function fermer() {
  S.choix = null;
  UI.fiche.hidden = true;
  document.body.classList.remove('re-fiche-ouverte');
  S.couche?.choisir(null);
  $$('#reel-panneau [data-reel]').forEach((li) => li.setAttribute('aria-current', 'false'));
}

// ── La bascule : un monde ou l'autre, jamais les deux ───────────────
async function basculer(monde, { vite = false } = {}) {
  if (monde === S.monde || S.enCours) return;
  const carte = window.foraine?.carte;
  if (!carte) return;
  S.enCours = true;
  UI.bascule.querySelectorAll('[data-monde]').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.monde === monde)));
  const url = new URL(location.href);
  if (monde === 'reel') url.searchParams.set('monde', 'reel'); else url.searchParams.delete('monde');
  history.replaceState(history.state, '', url);
  try {
    if (monde === 'reel') await versReel(carte, { vite }); else await versKit(carte);
    S.monde = monde;
  } catch (err) {
    console.error('[données réelles]', err);
    document.body.classList.remove('monde-reel');
    UI.bascule.querySelectorAll('[data-monde]').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.monde === 'kit')));
  } finally { S.enCours = false; }
}

async function versReel(carte, { vite = false } = {}) {
  const d = await chargerDonnees();
  // le kit se retire : ses fiches, sa file, ses repères ; on ne garde que le fond
  if (location.hash && location.hash !== '#/') history.replaceState(history.state, '', location.pathname + location.search + '#/');
  document.body.classList.add('monde-reel');
  rendrePanneau(0);
  requestAnimationFrame(() => UI.panneau.classList.add('arrive'));
  S.couche = monterCouche(carte, { reperes: d.reperes });
  const map = carte.map;
  // le mouvement : on prend de la hauteur sur tout le Sud-Ouest, la carte s'incline pendant qu'elle se remplit, puis se repose
  const cam = map.cameraForBounds(ECHELLES.sudouest, { padding: marges() });
  if (!reduit && !vite) {
    map.flyTo({ ...cam, pitch: 0, bearing: 0, duration: 1300, curve: 1.5, essential: true });
    await attendre(1150);
    map.easeTo({ pitch: 38, bearing: -7, zoom: cam.zoom + 0.35, duration: 2700, easing: (t) => 1 - Math.pow(1 - t, 2) });
    const t0 = performance.now();
    const compter = () => { const p = Math.min(1, (performance.now() - t0) / 2500); rendrePanneau(p); if (p < 1) requestAnimationFrame(compter); };
    requestAnimationFrame(compter);
    await S.couche.apparaitre({ duree: 2500 });
    map.easeTo({ ...cam, pitch: 0, bearing: 0, duration: 1100 });
  } else { map.jumpTo({ ...cam, pitch: 0, bearing: 0 }); await S.couche.apparaitre({ duree: vite ? 0 : undefined }); }
  rendrePanneau(1);
}

async function versKit(carte) {
  fermer();
  UI.panneau.classList.remove('arrive');
  await S.couche?.retirer();
  S.couche = null;
  document.body.classList.remove('monde-reel');
  carte.allerA('sudouest');
  carte.replacer();
}

const attendre = (ms) => new Promise((ok) => setTimeout(ok, ms));

// ── Démarrage : on attend la carte de BâtIA ───────────────────────
async function demarrer() {
  UI = monterInterface();
  const t0 = Date.now();
  while (!window.foraine?.carte && Date.now() - t0 < 30000) await attendre(80);
  if (!window.foraine?.carte) return;
  window.foraine.reel = { S, basculer, ouvrir, fermer, cadrer };
  window.foraine.carte.conteneur.addEventListener('reel:immeuble', (e) => ouvrir(e.detail.id));
  document.body.classList.add('bascule-prete');
  if (new URLSearchParams(location.search).get('monde') === 'reel') {
    // de retour de « Sous le capot », la carte réelle se remet d'un coup, sans rejouer l'onde
    const retour = document.referrer.includes('/capot/') || performance.getEntriesByType?.('navigation')?.[0]?.type === 'back_forward';
    await attendre(reduit || retour ? 0 : 900);
    // la carte du kit finit d'abord son glissement d'ouverture, sinon elle reprendrait la main
    const t1 = Date.now();
    while (retour && (!document.body.classList.contains('pret') || window.foraine.carte.map.isMoving()) && Date.now() - t1 < 6000) await attendre(80);
    basculer('reel', { vite: retour });
  }
}
demarrer().catch((err) => console.error('[données réelles]', err));
