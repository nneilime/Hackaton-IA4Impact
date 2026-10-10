// Carte d'Assise — module autonome : fond vectoriel local (Protomaps), trois échelles, repères des résidences.
// Usage :
//   import { creerCarte } from './carte/carte.mjs';
//   const carte = await creerCarte(document.querySelector('#carte'), { residences, echelle: 'sudouest' });
//   carte.conteneur.addEventListener('carte:residence', (e) => ouvrir(e.detail.id));
//   carte.allerA('toulouse');  // 'france' | 'sudouest' | 'toulouse'
// Rien n'est demandé à Internet : tuiles, glyphes, styles et moteur sont servis depuis ce dossier.
import * as maplibregl from './vendor/maplibre/maplibre-gl.mjs';
import { PMTiles } from './vendor/pmtiles/pmtiles.mjs';
import { styleFond, COULEURS } from './style.mjs';

const BASE = new URL('.', import.meta.url).href;

// Trois extraits, un par palier de zoom : la France pour s'orienter, le Sud-Ouest, puis la métropole jusqu'au quartier.
export const EXTRAITS = [
  { fichier: 'fond/france-z0-8.pmtiles', min: 0, max: 8 },
  { fichier: 'fond/sud-ouest-z9-11.pmtiles', min: 9, max: 11 },
  { fichier: 'fond/toulouse-z12-14.pmtiles', min: 12, max: 14 },
];

export const ECHELLES = {
  france: { bornes: [[-5.2, 41.3], [9.6, 51.1]] },
  sudouest: { bornes: [[-1.8, 42.69], [4.2, 45.58]] },
  toulouse: null, // calculée autour des résidences
};

// Le centre de la Gironde tombe sur Bordeaux : son nom se pose dans le Médoc pour laisser la ville lisible.
const ANCRES_DPT = { 33: [-0.92, 45.13] };

const ZOOM_MAX = 15;     // l'échelle du quartier : au-delà, un secteur fictif finirait par désigner un immeuble
const SEUIL_DETAIL = 8.6; // en dessous, la métropole se lit comme un seul repère ; au-dessus, une brique par résidence

let protocole = false;
function installerProtocole() {
  if (protocole) return;
  protocole = true;
  const archives = EXTRAITS.map((x) => ({ ...x, pm: new PMTiles(BASE + x.fichier) }));
  maplibregl.addProtocol('assise-fond', async (params, abandon) => {
    const [z, x, y] = params.url.split('/').slice(-3).map(Number);
    const archive = archives.find((a) => z >= a.min && z <= a.max);
    const tuile = archive && (await archive.pm.getZxy(z, x, y, abandon.signal));
    // Hors de l'extrait : une erreur fait retomber MapLibre sur la tuile parente, au lieu d'un trou.
    if (!tuile || !tuile.data) throw new Error('hors extrait');
    return { data: new Uint8Array(tuile.data) };
  });
}

function feuilleDeStyle(href) {
  if ([...document.styleSheets].some((s) => s.href === href) || document.querySelector(`link[href="${href}"]`)) return Promise.resolve();
  return new Promise((ok) => {
    const l = Object.assign(document.createElement('link'), { rel: 'stylesheet', href });
    l.onload = l.onerror = ok;
    document.head.append(l);
  });
}

const nb = (n) => new Intl.NumberFormat('fr-FR').format(n);
const pl = (n, un, plusieurs) => `${nb(n)} ${n > 1 ? plusieurs : un}`;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

// Côté du carré : la surface suit le nombre de logements.
const cote = (logements) => Math.round(Math.max(28, Math.min(66, 4.2 * Math.sqrt(logements))));

function niveau(r) { return r.aVisiter || r.communsAVisiter ? 'prioritaire' : r.aSurveiller ? 'surveiller' : 'calme'; }

function ligneAlerte(r, { long = false } = {}) {
  // une lentille peut remplacer les mots (« à visiter », « à surveiller ») par les siens
  if (r.alerte) return long && r.alerteLongue ? r.alerteLongue : r.alerte;
  const morceaux = [];
  const communs = r.communsAVisiter && !long ? (r.aVisiter ? ` (+${nb(r.communsAVisiter)} commun${r.communsAVisiter > 1 ? 's' : ''})` : '') : '';
  if (r.aVisiter) morceaux.push(`<span class="rv-visiter">${long ? pl(r.aVisiter, 'logement', 'logements') : nb(r.aVisiter)} à visiter${communs}</span>`);
  else if (r.communsAVisiter && !long) morceaux.push(`<span class="rv-visiter">${pl(r.communsAVisiter, 'équipement commun', 'équipements communs')} à visiter</span>`);
  if (r.aSurveiller) morceaux.push(`<span class="rv-surv">${nb(r.aSurveiller)} à surveiller</span>`);
  return morceaux.length ? morceaux.join('<span class="rv-sep"> · </span>') : 'sans alerte';
}

// La brique : un carré dont la base se remplit — brique cuite pour les logements à visiter, brique claire pour ceux à surveiller.
function brique({ lettre, logements, aVisiter = 0, aSurveiller = 0 }, cotePx) {
  const h = (n) => (n > 0 ? Math.max(2.5, (n / logements) * cotePx) : 0);
  return `<span class="rv-brique" style="--cote:${cotePx}px">
      <span class="rv-remplissage" aria-hidden="true"><span class="rv-surveiller" style="height:${h(aSurveiller)}px"></span><span class="rv-visiter-barre" style="height:${h(aVisiter)}px"></span></span>
      <span class="rv-lettre">${esc(lettre)}</span>
    </span>`;
}

function cercle([lng, lat], rayonM, n = 48) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const a = (i / n) * 2 * Math.PI;
    pts.push([lng + (rayonM / (111320 * Math.cos((lat * Math.PI) / 180))) * Math.cos(a), lat + (rayonM / 110540) * Math.sin(a)]);
  }
  return pts;
}

/**
 * Monte la carte dans `conteneur`.
 * residences : [{ id, nom, lettre, position: [lat, lng], logements, aVisiter, aSurveiller, communsAVisiter }]
 * options : echelle initiale ('france' | 'sudouest' | 'toulouse'), molette (zoom à la molette), depuis (échelle de départ d'un premier glissement)
 * Événements émis sur le conteneur : 'carte:residence' (detail : { id, residence }), 'carte:echelle' (detail : { echelle }).
 */
export async function creerCarte(conteneur, { residences = [], echelle = 'sudouest', depuis = null, molette = false, metropole = 'Métropole toulousaine', zoneOccupee = () => ({ top: 0, right: 0, bottom: 0, left: 0 }) } = {}) {
  if (typeof conteneur === 'string') conteneur = document.querySelector(conteneur);
  await Promise.all([feuilleDeStyle(BASE + 'vendor/maplibre/maplibre-gl.css'), feuilleDeStyle(BASE + 'carte.css')]);
  installerProtocole();
  conteneur.classList.add('carte-assise');

  const departements = await (await fetch(BASE + 'geo/departements-sud-ouest.json')).json();
  const placees = residences.filter((r) => r.position);
  const couleurNiveau = { prioritaire: COULEURS.briqueCuite, surveiller: '#C27A4A', calme: COULEURS.joint };
  const secteurs = {
    type: 'FeatureCollection',
    features: placees.map((r) => ({ type: 'Feature', properties: { id: r.id, couleur: couleurNiveau[niveau(r)] },
      geometry: { type: 'Polygon', coordinates: [cercle([r.position[1], r.position[0]], 420)] } })),
  };

  const etiquettesDpt = { type: 'FeatureCollection', features: departements.features.filter((f) => f.properties.code !== '31').map((f) => {
    const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    const aire = (r) => Math.abs(r.reduce((a, p, i) => { const q = r[(i + 1) % r.length]; return a + p[0] * q[1] - q[0] * p[1]; }, 0) / 2);
    const anneau = polys.map((p) => p[0]).sort((a, b) => aire(b) - aire(a))[0];
    let cx = 0, cy = 0, A = 0;
    for (let i = 0; i < anneau.length - 1; i++) { const [x0, y0] = anneau[i], [x1, y1] = anneau[i + 1]; const k = x0 * y1 - x1 * y0; A += k; cx += (x0 + x1) * k; cy += (y0 + y1) * k; }
    return { type: 'Feature', properties: f.properties, geometry: { type: 'Point', coordinates: ANCRES_DPT[f.properties.code] || [cx / (3 * A), cy / (3 * A)] } };
  }) };

  const lngs = placees.map((r) => r.position[1]), lats = placees.map((r) => r.position[0]);
  const marge = (a, b) => (b - a) * 0.35;
  const bornesTls = placees.length
    ? [[Math.min(...lngs) - marge(Math.min(...lngs), Math.max(...lngs)), Math.min(...lats) - marge(Math.min(...lats), Math.max(...lats))],
       [Math.max(...lngs) + marge(Math.min(...lngs), Math.max(...lngs)), Math.max(...lats) + marge(Math.min(...lats), Math.max(...lats))]]
    : [[1.3, 43.5], [1.6, 43.7]];
  const centreTls = [(bornesTls[0][0] + bornesTls[1][0]) / 2, (bornesTls[0][1] + bornesTls[1][1]) / 2];
  const echelles = { ...ECHELLES, toulouse: { bornes: bornesTls } };

  const reduit = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const etroit = () => conteneur.clientWidth < 560;
  const marges = (cle) => {
    const p = etroit() ? 14 : 28;
    const z = zoneOccupee();
    // à l'échelle de la métropole, les étiquettes des résidences se lisent vers l'est : on leur garde de la place
    const m = cle === 'toulouse' ? { top: p + 10, bottom: p + 10, left: p, right: etroit() ? p + 40 : p + 170 } : { top: p, bottom: p, left: p, right: p };
    // les panneaux de l'application se posent sur la carte : on cadre dans l'espace qu'ils laissent libre
    return { top: m.top + z.top, bottom: m.bottom + z.bottom, left: m.left + z.left, right: m.right + z.right };
  };

  const carte = new maplibregl.Map({
    container: conteneur,
    style: styleFond({ base: BASE, tuiles: 'assise-fond://fond/{z}/{x}/{y}', departements, etiquettesDpt, secteurs }),
    bounds: echelles[depuis || echelle].bornes,
    fitBoundsOptions: { padding: marges(depuis || echelle) },
    minZoom: 3.2, maxZoom: ZOOM_MAX,
    maxBounds: [[-16, 34], [20, 56]],
    attributionControl: { compact: false },
    dragRotate: false, pitchWithRotate: false, touchPitch: false, rollEnabled: false,
    scrollZoom: molette, cooperativeGestures: false,
    fadeDuration: 220,
    renderWorldCopies: false,
    locale: {
      'NavigationControl.ZoomIn': 'Rapprocher', 'NavigationControl.ZoomOut': 'Éloigner',
      'AttributionControl.ToggleAttribution': 'Sources du fond de carte',
    },
  });
  carte.touchZoomRotate.disableRotation();
  carte.keyboard.disableRotation?.();
  carte.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
  // un trou dans l'extrait n'est pas une panne : la tuile parente prend le relais
  carte.on('error', (e) => { if (!/hors extrait/.test(e?.error?.message || '')) console.warn('[carte]', e.error || e); });

  // ── Les repères ────────────────────────────────────────────────────
  const contenuRepere = (r, c) => `<button type="button" class="rv-bouton" aria-label="${esc(r.nom)} : ${esc(pl(r.logements, 'logement', 'logements'))}, ${esc(ligneAlerte(r).replace(/<[^>]+>/g, ''))}">
        ${brique(r, c)}
        <span class="rv-texte"><b>${esc(r.titre || pl(r.logements, 'logement', 'logements'))}</b><span class="rv-alerte">${ligneAlerte(r)}</span></span>
      </button>`;
  const reperes = placees.map((r, i) => {
    const el = document.createElement('div');
    el.className = 'rv';
    el.dataset.id = r.id;
    el.style.setProperty('--rang', i);
    const x = { r, el, marqueur: null, cote: cote(r.logements) };
    x.marqueur = new maplibregl.Marker({ element: el, anchor: 'center' }).setLngLat([r.position[1], r.position[0]]).addTo(carte);
    el.addEventListener('click', (ev) => {
      if (!ev.target.closest('.rv-bouton')) return;
      ev.stopPropagation();
      conteneur.dispatchEvent(new CustomEvent('carte:residence', { detail: { id: x.r.id, residence: x.r }, bubbles: true }));
    });
    el.addEventListener('mouseenter', () => conteneur.dispatchEvent(new CustomEvent('carte:survol', { detail: { id: x.r.id }, bubbles: true })));
    el.addEventListener('mouseleave', () => conteneur.dispatchEvent(new CustomEvent('carte:survol', { detail: { id: null }, bubbles: true })));
    return x;
  });
  function dessinerRepere(x) {
    const r = x.r;
    x.el.dataset.niveau = niveau(r);
    if (r.aVisiter || r.communsAVisiter) x.el.dataset.visite = '1'; else delete x.el.dataset.visite;
    x.el.innerHTML = contenuRepere(r, x.cote);
  }
  reperes.forEach(dessinerRepere);

  // La métropole vue de loin : un seul repère qui rassemble les huit résidences.
  const somme = (liste) => liste.reduce((s, r) => ({ logements: s.logements + r.logements, aVisiter: s.aVisiter + (r.aVisiter || 0), aSurveiller: s.aSurveiller + (r.aSurveiller || 0), communsAVisiter: s.communsAVisiter + (r.communsAVisiter || 0) }), { logements: 0, aVisiter: 0, aSurveiller: 0, communsAVisiter: 0 });
  const elMetro = document.createElement('div');
  elMetro.className = 'rv rv-metro';
  function dessinerMetro(liste, metroInfo = {}) {
    const total = { ...somme(liste), ...metroInfo };
    elMetro.dataset.niveau = niveau(total);
    elMetro.innerHTML = `<button type="button" class="rv-bouton" aria-label="${esc(metropole)} : ${liste.length} résidences, ${esc(pl(total.logements, 'logement', 'logements'))}. Rapprocher.">
      ${brique({ ...total, lettre: liste.length }, 46)}
      <span class="rv-texte"><b>${esc(metropole)}</b><span class="rv-sous">${liste.length} résidences · ${pl(total.logements, 'logement', 'logements')}</span><span class="rv-alerte">${ligneAlerte(total, { long: true })}</span></span>
    </button>`;
  }
  dessinerMetro(placees);
  elMetro.addEventListener('click', (ev) => { if (!ev.target.closest('.rv-bouton')) return; ev.stopPropagation(); allerA('toulouse'); });
  const marqueurMetro = placees.length ? new maplibregl.Marker({ element: elMetro, anchor: 'center' }).setLngLat(centreTls).addTo(carte) : null;

  // Les étiquettes ne se chevauchent pas : la plus exposée se place d'abord, à droite, sinon à gauche, dessous, dessus, sinon elle se tait.
  // la résidence choisie se place d'abord, puis la plus exposée
  const rangEtiquette = (x) => (x.el.classList.contains('rv-choisi') ? 1e6 : 0) + (x.r.aVisiter || 0) * 1000 + (x.r.aSurveiller || 0);
  const metro = marqueurMetro ? { el: elMetro, marqueur: marqueurMetro, cote: 46 } : null;
  let k = 1;
  function placerEtiquettes() {
    const loin = conteneur.classList.contains('carte-loin');
    const actifs = loin ? (metro ? [metro] : []) : reperes.slice().sort((a, b) => rangEtiquette(b) - rangEtiquette(a));
    const W = conteneur.clientWidth, H = conteneur.clientHeight;
    const zo = zoneOccupee();
    const pos = new Map(actifs.map((x) => [x, carte.project(x.marqueur.getLngLat())]));
    const cote = (x) => (x === metro ? x.cote : Math.max(20, x.cote * k)); // la brique de la métropole garde sa taille
    const prises = actifs.map((x) => { const p = pos.get(x), c = cote(x) / 2 + 3; return { x1: p.x - c, y1: p.y - c, x2: p.x + c, y2: p.y + c, x }; });
    const touche = (a, b) => a.x1 < b.x2 && a.x2 > b.x1 && a.y1 < b.y2 && a.y2 > b.y1;
    // les grandes villes gardent leur nom : une étiquette de résidence ne vient pas le couvrir
    if (!loin && carte.getLayer('noms-villes')) {
      for (const f of carte.queryRenderedFeatures({ layers: ['noms-villes'] })) {
        if ((f.properties.population_rank || 0) < 11 || f.geometry.type !== 'Point') continue;
        const p = carte.project(f.geometry.coordinates), n = String(f.properties['name:fr'] || f.properties.name || '');
        const w = n.length * 9 + 10, h = 22;
        prises.push({ x1: p.x - w / 2, y1: p.y - h / 2, x2: p.x + w / 2, y2: p.y + h / 2, x: null });
      }
    }
    for (const x of actifs) {
      const t = x.el.querySelector('.rv-texte');
      const larg = t.offsetWidth || 150, haut = t.offsetHeight || 36;
      const p = pos.get(x), c = cote(x) / 2, e = 7;
      // huit places autour de la brique, de la plus naturelle (à droite, centrée) à la plus lointaine
      const places = [
        ['droite', p.x + c + e, p.y - haut / 2], ['gauche', p.x - c - e - larg, p.y - haut / 2],
        ['droite', p.x + c + e, p.y - c], ['droite', p.x + c + e, p.y + c - haut],
        ['gauche', p.x - c - e - larg, p.y - c], ['gauche', p.x - c - e - larg, p.y + c - haut],
        ['dessous', p.x - larg / 2, p.y + c + 4], ['dessus', p.x - larg / 2, p.y - c - 4 - haut],
      ];
      if (x === metro) places.unshift(places.splice(6, 1)[0]);
      const boite = ([, gx, gy]) => ({ x1: gx, y1: gy, x2: gx + larg, y2: gy + haut });
      const ok = places.find((pl_) => { const b = boite(pl_); return b.x1 > zo.left + 4 && b.x2 < W - zo.right - 4 && b.y1 > zo.top + 4 && b.y2 < H - zo.bottom - 22 && !prises.some((q) => q.x !== x && touche(b, q)); });
      x.el.dataset.etiquette = ok ? ok[0] : 'muette';
      const [cote_, gx, gy] = ok || places[0];
      t.style.left = `${Math.round(gx - (p.x - c))}px`;
      t.style.top = `${Math.round(gy - (p.y - c))}px`;
      if (ok) prises.push({ ...boite(ok), x: null });
    }
  }
  // de loin les briques se resserrent, de près elles prennent leur taille : la métropole reste lisible sur un téléphone
  function majTaille() {
    const z = carte.getZoom();
    // sur le terrain, au téléphone, l'étiquette se réduit à ce qu'il faut aller voir
    conteneur.classList.toggle('carte-etroite', etroit());
    k = Math.max(0.6, Math.min(1, 0.6 + (z - 9.4) * 0.27)) * (etroit() ? 0.86 : 1);
    conteneur.style.setProperty('--k', k.toFixed(3));
  }

  let echelleCourante = null;
  function majEchelle() {
    const z = carte.getZoom();
    const loin = z < SEUIL_DETAIL;
    const change = loin !== conteneur.classList.contains('carte-loin');
    conteneur.classList.toggle('carte-loin', loin);
    majTaille();
    if (change) placerEtiquettes();
    conteneur.classList.toggle('carte-proche', z >= 12);
    const e = z < 5.6 ? 'france' : z < SEUIL_DETAIL ? 'sudouest' : 'toulouse';
    if (e !== echelleCourante) {
      echelleCourante = e;
      conteneur.dispatchEvent(new CustomEvent('carte:echelle', { detail: { echelle: e }, bubbles: true }));
    }
  }
  carte.on('zoom', majEchelle);
  carte.on('moveend', placerEtiquettes);
  carte.on('zoomend', placerEtiquettes);
  carte.on('resize', () => { majTaille(); placerEtiquettes(); });

  function allerA(cle, { anime = true } = {}) {
    const cible = echelles[cle];
    if (!cible) return;
    const cam = carte.cameraForBounds(cible.bornes, { padding: marges(cle) });
    if (!cam) return;
    cam.zoom = Math.min(cam.zoom, ZOOM_MAX);
    if (!anime || reduit) carte.jumpTo(cam);
    // vol en arc : on s'élève un peu avant de redescendre, comme on lève les yeux d'une carte murale
    else carte.flyTo({ ...cam, duration: 1700, curve: 1.35, essential: true, easing: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2) });
  }

  await new Promise((ok) => (carte.loaded() ? ok() : carte.once('load', ok)));
  majEchelle();
  conteneur.classList.add('carte-prete');
  requestAnimationFrame(placerEtiquettes);
  if (depuis && depuis !== echelle) setTimeout(() => allerA(echelle), reduit ? 0 : 450);

  // La résidence choisie se détache ; celle qu'on survole dans une liste bat une fois.
  function choisir(id) {
    conteneur.classList.toggle('carte-choix', !!id);
    reperes.forEach((x) => x.el.classList.toggle('rv-choisi', x.r.id === id));
    if (carte.getLayer('secteurs-choisi')) carte.setFilter('secteurs-choisi', ['==', ['get', 'id'], id || '']);
    requestAnimationFrame(placerEtiquettes);
  }
  function signaler(id) {
    reperes.forEach((x) => x.el.classList.toggle('rv-signale', x.r.id === id));
    elMetro.classList.toggle('rv-signale', !!id);
  }
  // Vers une résidence : on garde le quartier lisible, la brique au centre de l'espace libre.
  function allerVers(id, { zoom = 12.9 } = {}) {
    const x = reperes.find((y) => y.r.id === id);
    if (!x) return;
    const z = zoneOccupee();
    // un décalage plutôt qu'un rembourrage : MapLibre garderait le rembourrage pour tous les mouvements suivants
    const opts = { center: x.marqueur.getLngLat(), zoom: Math.min(zoom, ZOOM_MAX), offset: [Math.round((z.left - z.right) / 2), Math.round((z.top - z.bottom) / 2)] };
    const p = carte.project(opts.center);
    const visible = p.x > z.left + 40 && p.x < conteneur.clientWidth - z.right - 40 && p.y > z.top + 40 && p.y < conteneur.clientHeight - z.bottom - 40;
    if (reduit) carte.jumpTo(opts);
    else if (visible && Math.abs(carte.getZoom() - opts.zoom) < 0.6) carte.easeTo({ ...opts, duration: 650 });
    else carte.flyTo({ ...opts, duration: 1300, curve: 1.3, essential: true });
  }
  // Les comptes changent (décision, lentille) : les briques se remplissent autrement, les étiquettes se replacent.
  function actualiser(nouvelles, metroInfo) {
    const parId = new Map(nouvelles.map((r) => [r.id, r]));
    reperes.forEach((x) => { if (parId.has(x.r.id)) { x.r = { ...x.r, ...parId.get(x.r.id) }; dessinerRepere(x); } });
    dessinerMetro(reperes.map((x) => x.r), metroInfo);
    requestAnimationFrame(placerEtiquettes);
  }
  function recadrer() {
    const e = echelleCourante || 'sudouest';
    allerA(e);
  }

  return {
    conteneur, map: carte, maplibregl,
    allerA, allerVers, choisir, signaler, actualiser, recadrer, replacer: () => placerEtiquettes(),
    get echelle() { return echelleCourante; },
    detruire() { reperes.forEach((x) => x.marqueur.remove()); marqueurMetro?.remove(); carte.remove(); conteneur.classList.remove('carte-assise', 'carte-loin', 'carte-proche', 'carte-prete'); },
  };
}
