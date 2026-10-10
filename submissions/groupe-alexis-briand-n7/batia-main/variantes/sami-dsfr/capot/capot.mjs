// Sous le capot — on tape une adresse ; la fiche de l'immeuble se remplit source après source,
// l'immeuble apparaît (vu du ciel, puis de la rue), puis le verdict du calcul tombe.
// Chaque appel part du navigateur (ou du relais local) ; au-delà de deux secondes, ou sans réseau,
// l'enregistrement de l'adresse prend le relais au même rythme. Seul un petit signe le montre à l'équipe.
import * as maplibregl from '/carte/vendor/maplibre/maplibre-gl.mjs';
import { PMTiles } from '/carte/vendor/pmtiles/pmtiles.mjs';
import { styleFond } from '/carte/style.mjs';
import { ETAPES, assemblerFiche, Introuvable, dateCourte, nombre, distance } from './sources.mjs';
import { evaluer } from '/reel/calcul.mjs'; // le calcul de la carte réelle : même niveau, mêmes raisons

// Le parc d'In'li tel que la carte réelle le lit : un immeuble qui y figure reçoit ici exactement son verdict de la carte.
const parcPret = fetch('/reel/donnees/parc-reel.json').then((r) => r.json()).then((d) => d.immeubles || []).catch(() => []);
const trouverAuParc = (parc, ctx) => parc.find((im) => (ctx.bdnb?.batiment_groupe_id && im.id_bdnb === ctx.bdnb.batiment_groupe_id) || (ctx.rnb && im.id_rnb === ctx.rnb)) || null;

const $ = (s) => document.querySelector(s);
const pause = (ms) => new Promise((ok) => setTimeout(ok, ms));
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const normaliser = (s) => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[’']/g, ' ');
const RYTHME = 750;          // une ligne au plus toutes les 0,75 s : le jury a le temps de lire
const DELAI_MAX = 2000;      // au-delà, l'enregistrement prend le relais
const params = new URLSearchParams(location.search);
let forcerEnregistrements = params.has('filet');

// ── Carte : le fond vectoriel de BâtIA, puis l'orthophoto de l'IGN quand on arrive sur l'immeuble ──
const EXTRAITS = [
  { fichier: '/carte/fond/france-z0-8.pmtiles', min: 0, max: 8 },
  { fichier: '/carte/fond/sud-ouest-z9-11.pmtiles', min: 9, max: 11 },
  { fichier: '/carte/fond/toulouse-z12-14.pmtiles', min: 12, max: 14 },
].map((x) => ({ ...x, pm: new PMTiles(x.fichier) }));
maplibregl.addProtocol('capot-fond', async (p, abandon) => {
  const [z, x, y] = p.url.split('/').slice(-3).map(Number);
  const a = EXTRAITS.find((e) => z >= e.min && z <= e.max);
  const t = a && (await a.pm.getZxy(z, x, y, abandon.signal));
  if (!t || !t.data) throw new Error('hors extrait');
  return { data: new Uint8Array(t.data) };
});
let orthoLocale = false;
maplibregl.addProtocol('capot-ortho', async (p) => {
  const [z, x, y] = p.url.split('/').slice(-3).map(Number);
  if (!orthoLocale && !forcerEnregistrements) {
    try {
      const r = await fetch(`https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/jpeg&TILEMATRIX=${z}&TILEROW=${y}&TILECOL=${x}`, { signal: AbortSignal.timeout(DELAI_MAX) });
      if (r.ok) return { data: await r.arrayBuffer() };
    } catch {}
    orthoLocale = true; // une tuile manquée : les suivantes viennent de l'enregistrement, sans attendre
  }
  const r = await fetch(`/capot/enregistrements/tuiles/${z}/${x}/${y}.jpg`);
  if (!r.ok) throw new Error('tuile absente');
  return { data: await r.arrayBuffer() };
});

const VIDE = { type: 'FeatureCollection', features: [] };
const FRANCE = { center: [2.45, 46.55], zoom: 4.45 };
const carte = new maplibregl.Map({
  container: 'carte', style: styleFond({ base: '/carte/', tuiles: 'capot-fond://fond/{z}/{x}/{y}', departements: VIDE, etiquettesDpt: VIDE, secteurs: VIDE }),
  ...FRANCE, interactive: false, attributionControl: false, fadeDuration: 150, maxZoom: 19.5,
});
window.carteCapot = carte;
// Le style suffit pour commencer : sans écran, l'événement « load » attend toutes les tuiles et peut tarder.
const carteChargee = new Promise((ok) => { if (carte.isStyleLoaded()) ok(); else { carte.once('style.load', ok); carte.once('load', ok); } });
carteChargee.then(() => {
  carte.addSource('ortho', { type: 'raster', tiles: ['capot-ortho://o/{z}/{x}/{y}'], tileSize: 256, minzoom: 14, maxzoom: 18 });
  carte.addLayer({ id: 'ortho', type: 'raster', source: 'ortho', minzoom: 14, paint: { 'raster-opacity': ['interpolate', ['linear'], ['zoom'], 14.6, 0, 16.2, 1], 'raster-fade-duration': 250 } });
  carte.addSource('cone', { type: 'geojson', data: VIDE });
  carte.addLayer({ id: 'cone', type: 'fill', source: 'cone', paint: { 'fill-color': '#FFFFFF', 'fill-opacity': 0.28 } });
  carte.addLayer({ id: 'cone-bord', type: 'line', source: 'cone', paint: { 'line-color': '#FFFFFF', 'line-width': 1.5, 'line-opacity': 0.9, 'line-dasharray': [2, 2] } });
  carte.addSource('contour', { type: 'geojson', data: VIDE, lineMetrics: true });
  carte.addLayer({ id: 'contour-fond', type: 'fill', source: 'contour', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'fill-color': '#000091', 'fill-opacity': 0, 'fill-opacity-transition': { duration: 900 } } });
  carte.addLayer({ id: 'contour-trait', type: 'line', source: 'contour', filter: ['==', ['geometry-type'], 'LineString'], layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-width': 4.5, 'line-gradient': ['step', ['line-progress'], '#FFFFFF', 0, 'rgba(0,0,0,0)'] } });
  carte.addSource('point', { type: 'geojson', data: VIDE });
  carte.addLayer({ id: 'point-halo', type: 'circle', source: 'point', paint: { 'circle-radius': 16, 'circle-color': '#000091', 'circle-opacity': 0.25 } });
  carte.addLayer({ id: 'point', type: 'circle', source: 'point', paint: { 'circle-radius': 6.5, 'circle-color': '#000091', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2.5 } });
  carte.addSource('camera', { type: 'geojson', data: VIDE });
  carte.addLayer({ id: 'camera', type: 'circle', source: 'camera', paint: { 'circle-radius': 6, 'circle-color': '#fff', 'circle-stroke-color': '#161616', 'circle-stroke-width': 2 } });
});
const source = (id) => carte.getSource(id);
const vol = (opts) => new Promise((ok) => { carte.once('moveend', ok); carte.flyTo(opts); setTimeout(ok, (opts.duration || 1000) + 400); });

function anneaux(shape) {
  const polys = shape.type === 'Polygon' ? [shape.coordinates] : shape.coordinates;
  const feats = [];
  for (const poly of polys) {
    feats.push({ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: poly } });
    for (const ring of poly) feats.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: ring } });
  }
  return { type: 'FeatureCollection', features: feats };
}
function bornes(shape) {
  const pts = (shape.type === 'Polygon' ? [shape.coordinates] : shape.coordinates).flat(2);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  return [[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]];
}
async function tracerContour(shape, numero) {
  source('contour').setData(anneaux(shape));
  const t0 = performance.now(), duree = 1300;
  await new Promise((ok) => {
    const pas = () => {
      if (numero !== course) return ok();
      const p = Math.min(1, (performance.now() - t0) / duree);
      carte.setPaintProperty('contour-trait', 'line-gradient', p >= 1 ? ['step', ['line-progress'], '#FFFFFF', 1, '#FFFFFF'] : ['step', ['line-progress'], '#FFFFFF', p, 'rgba(0,0,0,0)']);
      if (p < 1) requestAnimationFrame(pas); else ok();
    };
    requestAnimationFrame(pas);
  });
  if (numero === course) carte.setPaintProperty('contour-fond', 'fill-opacity', 0.38);
}
function remettreCarte() {
  if (!carte.getSource('contour')) return;
  for (const id of ['contour', 'point', 'cone', 'camera']) source(id).setData(VIDE);
  carte.setPaintProperty('contour-fond', 'fill-opacity', 0);
  carte.jumpTo(FRANCE);
}
// Le cône de prise de vue : d'où la photo de rue a été prise, et vers où elle regarde.
function cone(pos, capDeg, ouverture, longueur) {
  const r = Math.PI / 180, kx = 1 / (111320 * Math.cos(pos[1] * r)), ky = 1 / 110540;
  const bout = (a) => [pos[0] + Math.sin(a * r) * longueur * kx, pos[1] + Math.cos(a * r) * longueur * ky];
  const pts = [pos];
  for (let a = capDeg - ouverture / 2; a <= capDeg + ouverture / 2 + 0.01; a += ouverture / 8) pts.push(bout(a));
  pts.push(pos);
  return { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [pts] } }] };
}

// ── Les adresses prêtes (enregistrées d'avance) ──
let index = [];
let selection = -1;
const champ = $('#adresse');
const indexPret = fetch('/capot/enregistrements/index.json').then((r) => r.json()).then((x) => { index = x; dessinerPretes(); }).catch(() => {});
function dessinerPretes() {
  $('#pretes').innerHTML = index.map((c, i) => `<li data-i="${i}" aria-selected="${i === selection}">${esc(c.saisie)}</li>`).join('') + '<li class="aide">↓ pour choisir · Entrée pour lancer</li>';
}
$('#pretes').addEventListener('click', (e) => { const li = e.target.closest('li[data-i]'); if (li) lancer(index[+li.dataset.i].saisie); });

// ── Une course : la cascade, puis le verdict ──
let course = 0;
async function lancer(saisie) {
  saisie = saisie.trim();
  if (!saisie) return;
  const numero = ++course;
  champ.value = saisie;
  champ.blur();
  document.body.classList.remove('vide');
  $('#fiche').innerHTML = '';
  $('#verdict').hidden = true;
  $('#photo').hidden = true;
  $('#bilan').innerHTML = '';
  $('#signe').innerHTML = '';
  document.querySelector('.erreur')?.remove();
  await carteChargee;
  carte.resize();
  remettreCarte();

  await indexPret;
  const n = normaliser(saisie);
  let enr = null;
  const choisi = index.find((c) => c.cles.some((k) => n.includes(k)));
  if (choisi) enr = await fetch(`/capot/enregistrements/${choisi.slug}.json`).then((r) => r.json()).catch(() => null);

  const parc = await parcPret;
  const t0 = performance.now();
  const ctx = { saisie };
  const lues = [];
  const modes = [];
  const appeler = async (url, opts = {}) => {
    const debut = performance.now();
    const trace = enr?.appels.find((a) => a.url === url) || enr?.appels.find((a) => a.etape === opts.etape);
    const via = opts.local ? 'local' : opts.relais ? 'relais' : 'direct';
    try {
      if (forcerEnregistrements && trace) throw new Error('enregistrements forcés');
      const ctl = new AbortController();
      const minuteur = setTimeout(() => ctl.abort(), DELAI_MAX);
      const r = await fetch(opts.relais ? `/capot/relais?u=${encodeURIComponent(url)}` : url, { signal: ctl.signal });
      const corps = await r.json();
      clearTimeout(minuteur);
      if (!r.ok) throw new Error(`statut ${r.status}`);
      if (opts.valide && !opts.valide(corps)) throw Object.assign(new Error('réponse vide'), { vide: true }); // la source répond, mais n'a rien ici
      modes.push(via);
      return corps;
    } catch (err) {
      if (!trace || opts.sansEnregistrement) throw err;
      await pause(Math.max(0, trace.duree_ms - (performance.now() - debut)));
      modes.push('enregistrement');
      return trace.corps;
    }
  };

  // Géorisques est appelé tôt : s'il ne répond pas (hors de France), on le sait avant d'arriver à sa ligne.
  let volEnCours = Promise.resolve();
  for (const etape of ETAPES) {
    if (numero !== course) return;
    const li = ligne(etape);
    const debut = performance.now();
    let res = null, erreur = null;
    const avantModes = modes.length;
    try { res = await etape.lancer(ctx, appeler); } catch (err) { erreur = err; }
    if (!ctx.connu && (ctx.rnb || ctx.bdnb)) ctx.connu = trouverAuParc(parc, ctx);
    if (etape.id === 'photo' && !erreur) ctx.photo.choisie = await chargerPhoto(ctx.photo, enr, modes[modes.length - 1]);
    const duree = performance.now() - debut;
    await pause(Math.max(0, RYTHME - duree));
    if (numero !== course) return;
    const mode = modes.slice(avantModes).includes('enregistrement') ? 'enregistrement' : modes[modes.length - 1] || 'direct';
    $('#signe').insertAdjacentHTML('beforeend', `<i class="${erreur ? '' : mode} ${forcerEnregistrements ? 'force' : ''}" title="${etape.id} : ${erreur ? 'échec' : mode}"></i>`);
    if (erreur) {
      if (etape.id === 'adresse') return echec(erreur instanceof Introuvable ? erreur.message : 'Adresse introuvable, ou pas de réseau.');
      remplir(li, etape, { valeur: erreur?.valeur || 'non trouvé', sous: erreur instanceof Introuvable ? erreur.message : 'source muette', manque: true }, duree);
      continue;
    }
    lues.push({ nom: res.source || etape.source, date_lecture: new Date().toISOString().slice(0, 10) });
    remplir(li, etape, res, duree);

    // Ce que chaque source fait apparaître sur la scène
    if (etape.id === 'adresse') {
      source('point').setData({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: ctx.position } });
      prechaufferOrtho(ctx.position);
      volEnCours = vol({ center: ctx.position, zoom: 16.3, duration: 3200, curve: 1.5, essential: true });
    }
    if (etape.id === 'batiment' && ctx.contour) {
      volEnCours = volEnCours.then(async () => {
        if (numero !== course) return;
        const b = bornes(ctx.contour);
        const cam = carte.cameraForBounds(b, { padding: { top: 70, bottom: 70, left: 90, right: Math.round(carte.getContainer().clientWidth * 0.5) }, maxZoom: 18.6 });
        await vol({ ...cam, duration: 1500, essential: true });
        if (numero !== course) return;
        source('point').setData(VIDE);
        await tracerContour(ctx.contour, numero);
      });
    }
    if (etape.id === 'photo') { await volEnCours; if (numero !== course) return; montrerPhoto(ctx); }
  }
  if (numero !== course) return;
  await volEnCours;
  if (!ctx.photo && ctx.contour) {
    // Pas de photo de rue : l'immeuble reprend le centre de la carte.
    carte.fitBounds(bornes(ctx.contour), { padding: 90, maxZoom: 18.6, duration: 900, essential: true });
    await pause(400);
  }

  // Le verdict du calcul
  const fiche = assemblerFiche(ctx, lues);
  window.ficheCourante = fiche;
  const v = evaluer(ctx.connu || fiche);
  await pause(500);
  if (numero !== course) return;
  montrerVerdict(v);
  const total = (performance.now() - t0) / 1000;
  $('#bilan').innerHTML = `<span><b>${lues.length}</b> sources publiques</span><span>·</span><span><b>${nombre(total, 1)}</b> secondes</span><span>·</span><span>rien demandé à personne</span><span class="touches"><kbd>/</kbd> autre adresse · <kbd>Entrée</kbd> rejouer · <kbd>1</kbd> à <kbd>5</kbd> adresses proposées · <kbd>Échap</kbd> carte</span>`;
}

function ligne(etape) {
  const li = document.createElement('li');
  li.className = 'ligne attente';
  li.innerHTML = `<div class="ligne-tete"><span class="ligne-titre">${esc(etape.titre)}</span><a class="ligne-source" href="${esc(etape.url || '#')}" target="_blank" rel="noopener" title="Ouvrir la source dans un nouvel onglet">${esc(etape.source)}</a></div><div class="ligne-corps"><span class="ligne-valeur">…</span></div>`;
  $('#fiche').append(li);
  return li;
}
function remplir(li, etape, res, duree) {
  li.className = `ligne${res.alerte ? ' alerte' : ''}${res.manque ? ' manque' : ''}`;
  li.innerHTML = `<div class="ligne-tete"><span class="ligne-titre">${esc(etape.titre)}</span><a class="ligne-source" href="${esc(res.url || etape.url || '#')}" target="_blank" rel="noopener" title="Ouvrir la source dans un nouvel onglet">${esc(res.source || etape.source)}${duree >= 60 ? `<small>${nombre(duree / 1000, 1)} s</small>` : ''}</a></div>
    <div class="ligne-corps"><span class="ligne-valeur">${esc(res.valeur)}</span>${res.sous ? `<span class="ligne-sous">${esc(res.sous)}</span>` : ''}</div>
    ${res.etiquette ? `<span class="etiquette" data-e="${esc(res.etiquette)}" title="Étiquette énergie la plus fréquente"><small>DPE</small>${esc(res.etiquette)}</span>` : ''}`;
}
function echec(message) {
  $('#fiche').innerHTML = '';
  $('.cadre').insertAdjacentHTML('beforeend', `<p class="erreur">${esc(message)}<small>Corrigez l’adresse puis Entrée</small></p>`);
  champ.focus();
  champ.select();
}

// La photo de rue se charge avant d'être montrée : deux secondes au plus, sinon la copie enregistrée d'avance.
function chargerPhoto(p, enr, mode) {
  const locale = enr?.photo ? `/capot/enregistrements/${enr.photo}` : null;
  const essayer = (url, delai) => new Promise((ok) => {
    if (!url) return ok(null);
    const im = new Image();
    const minuteur = setTimeout(() => ok(null), delai);
    im.onload = () => { clearTimeout(minuteur); ok(url); };
    im.onerror = () => { clearTimeout(minuteur); ok(null); };
    im.src = url;
  });
  return (async () => {
    if (mode !== 'enregistrement' && !forcerEnregistrements) { const u = await essayer(p.url, DELAI_MAX); if (u) return u; }
    return (await essayer(locale, 4000)) || p.url;
  })();
}

// Les tuiles aériennes autour de l'immeuble partent dès que l'adresse est connue : l'arrivée sera nette.
function prechaufferOrtho([lon, lat]) {
  if (forcerEnregistrements || orthoLocale) return;
  for (const z of [16, 17, 18]) {
    const n = 2 ** z, x = Math.floor(((lon + 180) / 360) * n);
    const y = Math.floor(((1 - Math.log(Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)) / Math.PI) / 2) * n);
    for (let dx = -2; dx <= 2; dx++) for (let dy = -1; dy <= 1; dy++)
      fetch(`https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/jpeg&TILEMATRIX=${z}&TILEROW=${y + dy}&TILECOL=${x + dx}`).catch(() => {});
  }
}

// L'immeuble vu de la rue : une photo à 360° recadrée vers la façade, ou une photo à plat.
function montrerPhoto(ctx) {
  const p = ctx.photo;
  if (!p) return;
  const fig = $('#photo'), img = $('#photo-image');
  const url = p.choisie || p.url;
  fig.hidden = false;
  const W = img.clientWidth, H = img.clientHeight;
  if (p.fov >= 360) {
    // Le cadre commence juste au-dessus de l'horizon de la caméra : au-dessus de la tête des passants
    // et du toit des voitures. On voit la façade, jamais la rue.
    const h = ctx.hauteur || 15, d = Math.max(8, p.distance);
    const haut = Math.atan2(h - 2.5, d) * 180 / Math.PI, bas = 1.5;
    const vfov = Math.min(100, Math.max(42, (haut - bas) * 1.15));
    const iw = (H * 360) / vfov, ih = iw / 2; // image équirectangulaire : 360° × 180°
    const ecart = ((p.cap - p.azimut + 540) % 360) - 180;
    const cx = (0.5 + ecart / 360) * iw, cy = (0.5 - (bas + vfov / 2) / 180) * ih;
    img.style.backgroundSize = `${iw}px ${ih}px`;
    img.style.backgroundPosition = `${W / 2 - cx}px ${H / 2 - cy}px`;
  } else {
    img.style.backgroundSize = 'cover';
    img.style.backgroundPosition = 'center 35%';
    img.style.backgroundRepeat = 'no-repeat';
  }
  img.style.backgroundImage = `url("${url}")`;
  $('#photo-legende').innerHTML = `<b>Vue de la rue, ${esc(dateCourte(p.date))}</b> · Panoramax · ${esc(p.auteur)} · ${esc(p.licence)}`;
  source('camera').setData({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: p.position } });
  if (ctx.contour) {
    const [[x0, y0], [x1, y1]] = bornes(ctx.contour);
    const b = [[Math.min(x0, p.position[0]), Math.min(y0, p.position[1])], [Math.max(x1, p.position[0]), Math.max(y1, p.position[1])]];
    const larg = carte.getContainer().clientWidth;
    carte.fitBounds(b, { padding: { top: 60, bottom: 60, left: 60, right: Math.round(larg * 0.5) + 30 }, maxZoom: 18.6, duration: 900, essential: true });
  }
  source('cone').setData(cone(p.position, p.cap, p.fov >= 360 ? 70 : p.fov, Math.min(70, p.distance + 12)));
}

function montrerVerdict(v) {
  const el = $('#verdict');
  el.dataset.niveau = v.niveau;
  const ECHELLE = ['calme', 'surveiller', 'vigilance', 'alerte', 'urgence'];
  const cran = ECHELLE.indexOf(v.niveau);
  const jauge = `<span class="jauge" title="${cran + 1} sur 5, du calme à l’urgence">${ECHELLE.map((_, i) => `<i class="${i <= cran ? 'plein' : ''}"></i>`).join('')}</span>`;
  // les trois raisons de « Pourquoi » dans la fiche de la carte, dans le même ordre ; leurs sources sont les lignes ci-dessus
  const raisons = v.raisons.filter((r) => r.points > 0).slice(0, 3);
  el.innerHTML = `<div class="verdict-mot"><small>Risque selon BâtIA ${jauge}</small>${esc(v.libelle)}</div>
    <div><ul>${raisons.map((r, i) => `<li style="animation-delay:${0.25 + i * 0.18}s"><span>${esc(r.texte)}</span></li>`).join('')}</ul></div>`;
  el.hidden = false;
  // au téléphone, la page défile : le verdict vient sous les yeux
  if (matchMedia('(max-width: 760px)').matches) el.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function reinitialiser() {
  course++;
  document.body.classList.add('vide');
  $('#fiche').innerHTML = '';
  $('#verdict').hidden = true;
  $('#photo').hidden = true;
  $('#bilan').innerHTML = '';
  $('#signe').innerHTML = '';
  document.querySelector('.erreur')?.remove();
  champ.value = '';
  selection = -1;
  dessinerPretes();
  remettreCarte();
  champ.focus();
}

// ── Clavier : tout se pilote sans souris ──
$('#saisie').addEventListener('submit', (e) => { e.preventDefault(); lancer(champ.value); });
$('#marque').addEventListener('click', (e) => { e.preventDefault(); retourBatIA(); });
champ.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    if (!index.length) return;
    e.preventDefault();
    selection = (selection + (e.key === 'ArrowDown' ? 1 : -1) + index.length) % index.length;
    champ.value = index[selection].saisie;
    dessinerPretes();
  } else if (e.key === 'Escape') {
    // Échap ramène à la carte, comme partout dans BâtIA ; une adresse en cours de frappe s'efface d'abord
    e.preventDefault();
    if (champ.value && document.body.classList.contains('vide')) { champ.value = ''; selection = -1; dessinerPretes(); }
    else retourBatIA();
  }
});
function retourBatIA() {
  let depuisBatIA = false;
  try { const r = new URL(document.referrer); depuisBatIA = r.origin === location.origin && !r.pathname.startsWith('/capot'); } catch {}
  if (depuisBatIA && history.length > 1) history.back(); else location.href = '/?monde=reel';
}
document.addEventListener('keydown', (e) => {
  if (e.altKey && e.key === 'ArrowLeft') { e.preventDefault(); retourBatIA(); return; }
  if (e.target === champ || e.altKey || e.ctrlKey || e.metaKey) return;
  if (e.key === 'Escape') { e.preventDefault(); retourBatIA(); }
  else if (e.key === 'Enter') { e.preventDefault(); if (champ.value) lancer(champ.value); }
  else if (/^[1-9]$/.test(e.key) && index[+e.key - 1]) { e.preventDefault(); lancer(index[+e.key - 1].saisie); }
  else if (e.key === '/') { e.preventDefault(); reinitialiser(); }
  else if (e.key === 'f' || e.key === 'F') { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.(); }
  else if (e.key === 'h' || e.key === 'H') { forcerEnregistrements = !forcerEnregistrements; $('#signe').insertAdjacentHTML('beforeend', `<i class="${forcerEnregistrements ? 'force' : ''}"></i>`); }
});
champ.focus();
if (params.get('adresse')) lancer(params.get('adresse'));
