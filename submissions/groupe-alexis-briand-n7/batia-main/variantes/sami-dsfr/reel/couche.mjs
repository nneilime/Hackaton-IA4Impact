// BâtIA · données réelles — la couche de carte du parc réel d'In'li Sud-Ouest.
// Posée sur la carte de BâtIA (carte/carte.mjs) sans la modifier : on reçoit l'objet `carte` qu'elle rend
// (carte.map est l'instance MapLibre) et on ajoute nos sources et nos couches, qu'on retire en partant.
//
//   const couche = monterCouche(carte, { reperes });
//   carte.conteneur.addEventListener('reel:immeuble', (e) => ouvrir(e.detail.id));
//   await couche.apparaitre();   // la carte se remplit, en onde depuis Toulouse
//   couche.choisir(id); couche.allerVers(id); await couche.retirer();
//
// repères : [{ id, type: 'immeuble' | 'groupe', position: [lon, lat], logements, niveau, libelle, points, emprise? }]
// Un immeuble de moins de 10 logements, ou une maison, n'arrive jamais ici seul : il est déjà fondu dans le groupe de sa commune.

// Les couleurs de BâtIA (app/app.css) : vives pour Urgent, Alerte et Vigilance ; gris pâle pour À surveiller,
// contour seul pour Calme. Le mot est toujours écrit à côté de la couleur.
export const COULEURS_NIVEAU = {
  urgence: '#D7261E',
  alerte: '#F27C14',
  vigilance: '#F7C51E',
  surveiller: '#E5E5E5',
  calme: '#FFFFFF',
};
export const VIFS = ['urgence', 'alerte', 'vigilance'];
const SOMBRE_NIVEAU = { urgence: '#8F120C', alerte: '#9C3E06', vigilance: '#7A5800', surveiller: '#666666', calme: '#929292' };

const ZOOM_MAX_REEL = 18.4;          // en données réelles, la carte descend jusqu'à l'immeuble (le fond s'agrandit au-delà du 14)
const ORIGINE = [1.4442, 43.6045];   // l'onde part de Toulouse, siège d'In'li Sud-Ouest

const couleur = ['match', ['get', 'niveau'], ...Object.entries(COULEURS_NIVEAU).flat(), '#999'];
const sombre = ['match', ['get', 'niveau'], ...Object.entries(SOMBRE_NIVEAU).flat(), '#555'];

// Rayon d'un repère : la surface suit le nombre de logements ; `f` règle l'apparition (0 → 1).
function rayon(f = 1, plus = 0) {
  const r = (a, b) => ['+', plus, ['*', f, ['+', a, ['*', b, ['get', 'rac']]]]];
  return ['interpolate', ['linear'], ['zoom'], 4, r(1.6, 0.2), 7, r(2.2, 0.36), 10, r(3, 0.55), 13, r(4.5, 0.85), 16, r(6, 1.05), 18, r(7, 1.2)];
}

const distance = ([x1, y1], [x2, y2]) => Math.hypot((x1 - x2) * Math.cos((43.6 * Math.PI) / 180), y1 - y2);

export function monterCouche(carte, { reperes = [] } = {}) {
  const map = carte.map;
  const el = carte.conteneur;
  const reduit = matchMedia('(prefers-reduced-motion: reduce)').matches || localStorage.getItem('foraine.animations') === 'reduites';
  const dMax = Math.max(0.01, ...reperes.map((r) => distance(r.position, ORIGINE)));
  const points = {
    type: 'FeatureCollection',
    features: reperes.map((r) => ({
      type: 'Feature',
      properties: {
        id: r.id, type: r.type, niveau: r.niveau, libelle: r.libelle, logements: r.logements, rac: Math.sqrt(r.logements || 1),
        tri: r.points || 0, emprise: r.emprise ? 1 : 0,
        // l'onde : de Toulouse vers les quatre autres départements, avec un léger désordre pour que la carte « pétille »
        onde: Math.min(1, (distance(r.position, ORIGINE) / dMax) * 0.86 + (Math.abs(Math.sin(r.position[0] * 913 + r.position[1] * 577)) * 0.1)),
        sous: `${r.logements} logements`,
      },
      geometry: { type: 'Point', coordinates: r.position },
    })),
  };
  const emprises = {
    type: 'FeatureCollection',
    features: reperes.filter((r) => r.emprise && r.emprise.length > 3).map((r) => ({
      type: 'Feature', properties: { id: r.id, niveau: r.niveau },
      geometry: { type: 'Polygon', coordinates: [r.emprise] },
    })),
  };

  // ── Ce qu'on change du fond de BâtIA, pour le rendre à l'identique en repartant ──
  const avant = [];
  function changer(fn, retour) { try { fn(); avant.push(retour); } catch { /* couche absente : rien à faire */ } }
  const lp = (id, k) => map.getLayoutProperty(id, k);
  const pp = (id, k) => map.getPaintProperty(id, k);
  for (const id of ['secteurs', 'secteurs-trait', 'secteurs-choisi', 'dpt-attente']) {
    if (!map.getLayer(id)) continue;
    const v = lp(id, 'visibility') || 'visible';
    changer(() => map.setLayoutProperty(id, 'visibility', 'none'), () => map.setLayoutProperty(id, 'visibility', v));
  }
  // les cinq départements sont raccordés : tous maçonnés, plus aucun « à raccorder »
  for (const id of ['dpt-raccorde', 'dpt-raccorde-trait']) {
    if (!map.getLayer(id)) continue;
    const f = map.getFilter(id);
    changer(() => map.setFilter(id, null), () => map.setFilter(id, f));
  }
  if (map.getLayer('noms-dpt')) { const t = lp('noms-dpt', 'text-field'); changer(() => map.setLayoutProperty('noms-dpt', 'text-field', ['get', 'nom']), () => map.setLayoutProperty('noms-dpt', 'text-field', t)); }
  if (map.getLayer('noms-villes')) { const o = pp('noms-villes', 'text-opacity'); changer(() => map.setPaintProperty('noms-villes', 'text-opacity', 1), () => map.setPaintProperty('noms-villes', 'text-opacity', o)); }
  const zoomMaxAvant = map.getMaxZoom();
  map.setMaxZoom(ZOOM_MAX_REEL);
  // les bornes de BâtIA (34° à 56° N) repoussent la vue vers le nord quand la feuille du téléphone oblige à centrer
  // plus au sud : levées en données réelles, rétablies au retour
  const bornesAvant = map.getMaxBounds();
  changer(() => map.setMaxBounds(null), () => map.setMaxBounds(bornesAvant));

  // ── Sources et couches ──
  map.addSource('reel-points', { type: 'geojson', data: points });
  map.addSource('reel-emprises', { type: 'geojson', data: emprises });
  const avantNoms = map.getLayer('noms-rivieres') ? 'noms-rivieres' : undefined;
  const ajoutees = [];
  const ajouter = (couche, avantId) => { map.addLayer(couche, avantId); ajoutees.push(couche.id); };

  // les bâtiments du fond (OpenStreetMap), quand l'extrait les contient : le quartier se lit autour de l'immeuble
  ajouter({ id: 'reel-batiments-fond', type: 'fill', source: 'fond', 'source-layer': 'buildings', minzoom: 14,
    paint: { 'fill-color': '#E5E5E5', 'fill-outline-color': '#CECECE', 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 14, 0, 14.6, 0.9] } }, avantNoms);
  ajouter({ id: 'reel-emprises', type: 'fill', source: 'reel-emprises', minzoom: 13.5,
    paint: { 'fill-color': couleur, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 13.5, 0, 14.5, 0.88] } }, avantNoms);
  ajouter({ id: 'reel-emprises-trait', type: 'line', source: 'reel-emprises', minzoom: 13.5,
    paint: { 'line-color': sombre, 'line-width': ['interpolate', ['linear'], ['zoom'], 14, 0.8, 18, 2.2], 'line-opacity': ['interpolate', ['linear'], ['zoom'], 13.5, 0, 14.5, 1] } }, avantNoms);
  ajouter({ id: 'reel-emprise-choisie', type: 'line', source: 'reel-emprises', minzoom: 13.5, filter: ['==', ['get', 'id'], ''],
    paint: { 'line-color': '#000091', 'line-width': ['interpolate', ['linear'], ['zoom'], 14, 2.5, 18, 5] } }, avantNoms);
  ajouter({ id: 'reel-halo', type: 'circle', source: 'reel-points', filter: ['==', ['get', 'id'], ''],
    paint: { 'circle-radius': rayon(1, 7), 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': '#000091', 'circle-stroke-width': 2.5,
      'circle-opacity': ['interpolate', ['linear'], ['zoom'], 15, 1, 16, 0], 'circle-stroke-opacity': ['interpolate', ['linear'], ['zoom'], 15, 1, 16, 0] } });
  // de près, l'emprise dessinée prend le relais du rond (le zoom ne peut être qu'au sommet d'une expression)
  const opaciteProche = ['interpolate', ['linear'], ['zoom'], 14.6, 1, 15.6, ['case', ['==', ['get', 'emprise'], 1], 0, 1]];
  const groupe = ['==', ['get', 'type'], 'groupe'];
  ajouter({ id: 'reel-points', type: 'circle', source: 'reel-points',
    layout: { 'circle-sort-key': ['get', 'tri'] },
    paint: {
      'circle-radius': rayon(reduit ? 1 : 0),
      // un groupe de petits immeubles et de maisons : un anneau, pour ne pas le confondre avec un immeuble
      'circle-color': ['case', groupe, '#FFFFFF', couleur],
      'circle-stroke-color': ['case', groupe, ['match', ['get', 'niveau'], ['surveiller', 'calme'], sombre, couleur], ['match', ['get', 'niveau'], ['surveiller', 'calme'], sombre, '#FFFFFF']],
      'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 5, ['case', groupe, 1.6, 0.6], 10, ['case', groupe, 2.6, 1.2], 12, ['case', groupe, 3, 1.5], 15, ['case', groupe, 3, 2]],
      'circle-opacity': opaciteProche, 'circle-stroke-opacity': opaciteProche,
    } });
  // de près, le mot du niveau se pose à côté de l'immeuble (« Urgent »), puis le nombre de logements
  ajouter({ id: 'reel-etiquettes', type: 'symbol', source: 'reel-points',
    filter: ['all', ['in', ['get', 'niveau'], ['literal', VIFS]], ['any', ['>=', ['zoom'], 14.2], ['all', ['>=', ['zoom'], 11.6], ['in', ['get', 'niveau'], ['literal', ['urgence', 'alerte']]], ['==', ['get', 'type'], 'immeuble']]]],
    layout: {
      'text-field': ['get', 'libelle'],
      'text-font': ['literal', ['NotoSans-Medium']],
      'text-size': ['interpolate', ['linear'], ['zoom'], 11.6, 11.5, 16, 14.5],
      'text-variable-anchor': ['left', 'right', 'top', 'bottom'], 'text-radial-offset': ['interpolate', ['linear'], ['zoom'], 11.6, 0.9, 16, 1.6],
      'text-justify': 'auto', 'text-line-height': 1.05, 'text-padding': 3, 'symbol-sort-key': ['-', 1000, ['get', 'tri']],
    },
    paint: { 'text-color': sombre, 'text-halo-color': '#FFFFFF', 'text-halo-width': 1.8, 'text-opacity': reduit ? 1 : 0 } });

  // ── Gestes ──
  let survol = null;
  const choisirIci = (e) => {
    const f = e.features?.[0];
    if (!f) return;
    e.preventDefault?.();
    el.dispatchEvent(new CustomEvent('reel:immeuble', { detail: { id: f.properties.id, type: f.properties.type }, bubbles: true }));
  };
  const entrer = () => { map.getCanvas().style.cursor = 'pointer'; };
  const sortir = () => { map.getCanvas().style.cursor = ''; survol = null; };
  for (const id of ['reel-points', 'reel-emprises']) { map.on('click', id, choisirIci); map.on('mouseenter', id, entrer); map.on('mouseleave', id, sortir); }

  // ── L'apparition : la carte se remplit en onde, depuis Toulouse ──
  let anim = null;
  function apparaitre({ duree = 2600 } = {}) {
    if (reduit || duree === 0) {
      map.setPaintProperty('reel-points', 'circle-radius', rayon(1)); map.setPaintProperty('reel-etiquettes', 'text-opacity', 1); return Promise.resolve(); }
    cancelAnimationFrame(anim);
    return new Promise((ok) => {
      const t0 = performance.now();
      const pas = (t) => {
        const p = Math.min(1.12, ((t - t0) / duree) * 1.12);
        // chaque repère éclot quand l'onde l'atteint, avec un léger rebond
        const local = ['max', 0, ['min', 1, ['/', ['-', p, ['get', 'onde']], 0.07]]];
        const rebond = ['+', local, ['*', 0.5, ['*', local, ['-', 1, local]]]];
        map.setPaintProperty('reel-points', 'circle-radius', rayon(rebond));
        if (p < 1.12) anim = requestAnimationFrame(pas);
        else {
          map.setPaintProperty('reel-points', 'circle-radius', rayon(1));
          map.setPaintProperty('reel-etiquettes', 'text-opacity', 1);
          ok();
        }
      };
      anim = requestAnimationFrame(pas);
    });
  }

  function choisir(id) {
    map.setFilter('reel-halo', ['==', ['get', 'id'], id || '']);
    map.setFilter('reel-emprise-choisie', ['==', ['get', 'id'], id || '']);
  }
  // Le fond n'est détaillé (zooms 12 à 14) qu'autour de Toulouse (carte/CARTE.md). Ailleurs, MapLibre ne peut montrer
  // que la tuile parente du zoom 11, et seulement si elle est déjà chargée : on vole d'abord au zoom 11, puis on descend.
  const DETAIL = [[0.95, 43.33], [1.9, 43.95]];
  const detaille = ([x, y]) => x >= DETAIL[0][0] && x <= DETAIL[1][0] && y >= DETAIL[0][1] && y <= DETAIL[1][1];
  let vol = 0;
  function allerVers(id, { zoom, decalage = [0, 0] } = {}) {
    const r = reperes.find((x) => x.id === id);
    if (!r) return;
    const ici = detaille(r.position);
    const z = zoom ?? (r.type === 'groupe' ? (ici ? 12.2 : 11.6) : (ici ? 16.4 : 15.2));
    const opts = { center: r.position, zoom: z, offset: decalage };
    const jeton = ++vol;
    if (ici || z <= 11.6) { if (reduit) map.jumpTo(opts); else map.flyTo({ ...opts, duration: 1600, curve: 1.4, essential: true }); return; }
    const descendre = () => {
      if (jeton !== vol) return;
      if (reduit) map.jumpTo(opts); else map.easeTo({ ...opts, duration: 1300, essential: true });
    };
    const suite = () => {
      if (jeton !== vol) return;
      const delai = setTimeout(descendre, 1500);
      map.once('idle', () => { clearTimeout(delai); descendre(); });
    };
    const etape = { ...opts, zoom: 11.2 };
    if (reduit) { map.jumpTo(etape); suite(); } else { map.flyTo({ ...etape, duration: 1300, curve: 1.4, essential: true }); map.once('moveend', suite); }
  }

  async function retirer() {
    cancelAnimationFrame(anim);
    for (const id of ['reel-points', 'reel-emprises']) { map.off('click', id, choisirIci); map.off('mouseenter', id, entrer); map.off('mouseleave', id, sortir); }
    map.getCanvas().style.cursor = '';
    ajoutees.slice().reverse().forEach((id) => map.getLayer(id) && map.removeLayer(id));
    for (const s of ['reel-points', 'reel-emprises']) if (map.getSource(s)) map.removeSource(s);
    avant.reverse().forEach((f) => { try { f(); } catch { /* */ } });
    if (map.getZoom() > zoomMaxAvant) map.jumpTo({ zoom: zoomMaxAvant });
    map.setMaxZoom(zoomMaxAvant);
  }

  return { apparaitre, choisir, allerVers, retirer, get survol() { return survol; } };
}
