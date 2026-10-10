// Le fond de carte d'Assise : un fond gris clair où seuls restent les repères utiles.
// Schéma des tuiles : Protomaps Basemap v4 (couches earth, water, landcover, landuse, roads, boundaries, places).
// Aucun bâtiment, aucun point d'intérêt, aucun numéro de route : les résidences sont à des positions fictives.

export const COULEURS = {
  mer: '#CFE3F6',
  terre: '#F4F4F4',
  foret: '#DCE9D8',
  parc: '#E3EFE0',
  ville: '#E6E6E6',
  villeDense: '#DEDEDE',
  riviere: '#A9C9E8',
  route: '#FFFFFF',
  routeBord: '#DCDCDC',
  routeLoin: '#C2C2C2',    // à petite échelle, une route blanche disparaîtrait : on la trace en gris
  frontiere: '#B5B5B5',
  texte: '#3A3A3A',
  texte2: '#666666',
  texte3: '#7A7A7A',
  eauTexte: '#3A6EA5',
  halo: '#FFFFFF',
  briqueCuite: '#000091',
  brique: '#000091',
  joint: '#929292',
};

const nom = ['coalesce', ['get', 'name:fr'], ['get', 'name']];
const R = ['NotoSans-Regular'], M = ['NotoSans-Medium'], I = ['NotoSans-Italic'];
const C = COULEURS;

export function styleFond({ base, tuiles, departements, etiquettesDpt, secteurs }) {
  return {
    version: 8,
    name: 'Assise — gris clair',
    glyphs: `${base}vendor/glyphes/{fontstack}/{range}.pbf`,
    sources: {
      fond: {
        type: 'vector', tiles: [tuiles], minzoom: 0, maxzoom: 14,
        attribution: '<a href="https://protomaps.com" target="_blank" rel="noopener">Protomaps</a> · © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">les contributeurs d’OpenStreetMap</a>',
      },
      departements: { type: 'geojson', data: departements },
      etiquettesDpt: { type: 'geojson', data: etiquettesDpt },
      secteurs: { type: 'geojson', data: secteurs },
    },
    layers: [
      { id: 'mer', type: 'background', paint: { 'background-color': C.mer } },
      { id: 'terre', type: 'fill', source: 'fond', 'source-layer': 'earth', paint: { 'fill-color': C.terre } },

      // Occupation du sol : forêts et villes seulement, ce qui donne sa forme au territoire.
      { id: 'foret-loin', type: 'fill', source: 'fond', 'source-layer': 'landcover', maxzoom: 8,
        filter: ['==', ['get', 'kind'], 'forest'],
        paint: { 'fill-color': C.foret, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0.25, 6, 0.5, 8, 0.75] } },
      { id: 'ville-loin', type: 'fill', source: 'fond', 'source-layer': 'landcover', maxzoom: 8,
        filter: ['==', ['get', 'kind'], 'urban_area'],
        paint: { 'fill-color': C.ville, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 4, 0.6, 7, 1] } },
      { id: 'foret', type: 'fill', source: 'fond', 'source-layer': 'landuse', minzoom: 8,
        filter: ['match', ['get', 'kind'], ['forest', 'wood', 'nature_reserve'], true, false],
        paint: { 'fill-color': C.foret, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 8, 0.7, 12, 0.9] } },
      { id: 'ville', type: 'fill', source: 'fond', 'source-layer': 'landuse', minzoom: 8,
        filter: ['match', ['get', 'kind'], ['residential', 'industrial', 'commercial', 'retail', 'railway', 'military', 'hospital', 'school', 'university', 'college', 'aerodrome', 'airfield'], true, false],
        paint: { 'fill-color': ['match', ['get', 'kind'], ['residential'], C.ville, C.villeDense], 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 8, 0.6, 11, 0.85, 14, 0.7] } },
      { id: 'parc', type: 'fill', source: 'fond', 'source-layer': 'landuse', minzoom: 10,
        filter: ['match', ['get', 'kind'], ['park', 'garden', 'golf_course', 'cemetery', 'grass', 'recreation_ground', 'village_green', 'allotments', 'playground', 'pitch', 'zoo'], true, false],
        paint: { 'fill-color': C.parc, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 10, 0, 11, 1] } },

      // L'eau : la mer, les lacs, la Garonne et le canal.
      { id: 'eau', type: 'fill', source: 'fond', 'source-layer': 'water', filter: ['==', ['geometry-type'], 'Polygon'],
        paint: { 'fill-color': C.mer } },
      { id: 'rivieres', type: 'line', source: 'fond', 'source-layer': 'water', minzoom: 5.5,
        filter: ['all', ['==', ['geometry-type'], 'LineString'], ['match', ['get', 'kind'], ['river', 'canal'], true, false], ['!=', ['get', 'tunnel'], true]],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': C.riviere, 'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 5.5, 0.4, 8, 0.9, 10, 1.5, 13, 2.8, 15, 5] } },
      { id: 'ruisseaux', type: 'line', source: 'fond', 'source-layer': 'water', minzoom: 13,
        filter: ['all', ['==', ['geometry-type'], 'LineString'], ['==', ['get', 'kind'], 'stream']],
        paint: { 'line-color': C.riviere, 'line-width': 0.7, 'line-opacity': 0.8 } },

      // Les cinq départements : la Haute-Garonne est raccordée, les quatre autres attendent en pointillé.
      { id: 'dpt-raccorde', type: 'fill', source: 'departements', filter: ['==', ['get', 'code'], '31'], maxzoom: 10.5,
        paint: { 'fill-color': C.brique, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 4, 0.22, 7, 0.13, 9, 0.06, 10.5, 0] } },

      // Les routes : du plus fin au plus large, pour que les grands axes passent dessus.
      ...routes(),

      { id: 'frontieres-halo', type: 'line', source: 'fond', 'source-layer': 'boundaries', maxzoom: 9,
        filter: ['all', ['==', ['get', 'kind'], 'country'], ['!=', ['get', 'disputed'], true]],
        paint: { 'line-color': C.frontiere, 'line-opacity': 0.18, 'line-width': ['interpolate', ['linear'], ['zoom'], 3, 3, 8, 6], 'line-blur': 2 } },
      { id: 'frontieres', type: 'line', source: 'fond', 'source-layer': 'boundaries', maxzoom: 11,
        filter: ['all', ['==', ['get', 'kind'], 'country'], ['!=', ['get', 'disputed'], true]],
        layout: { 'line-join': 'round' },
        paint: { 'line-color': C.frontiere, 'line-width': ['interpolate', ['linear'], ['zoom'], 3, 0.6, 8, 1.2], 'line-opacity': ['interpolate', ['linear'], ['zoom'], 9, 1, 11, 0] } },

      { id: 'dpt-attente', type: 'line', source: 'departements', filter: ['!=', ['get', 'code'], '31'], maxzoom: 10,
        layout: { 'line-join': 'round' },
        paint: { 'line-color': C.joint, 'line-width': ['interpolate', ['linear'], ['zoom'], 4, 0.9, 8, 1.6], 'line-dasharray': [2.4, 1.6], 'line-opacity': ['interpolate', ['linear'], ['zoom'], 4, 0.75, 6, 1, 9, 0.7, 10, 0] } },
      { id: 'dpt-raccorde-trait', type: 'line', source: 'departements', filter: ['==', ['get', 'code'], '31'], maxzoom: 11,
        layout: { 'line-join': 'round' },
        paint: { 'line-color': C.briqueCuite, 'line-width': ['interpolate', ['linear'], ['zoom'], 4, 1, 8, 2, 10, 1.5], 'line-opacity': ['interpolate', ['linear'], ['zoom'], 4, 0.85, 9, 0.9, 11, 0] } },

      // Les secteurs : un cercle de 400 m autour de chaque position fictive, pour ne désigner aucun immeuble.
      { id: 'secteurs', type: 'fill', source: 'secteurs', minzoom: 11,
        paint: { 'fill-color': ['get', 'couleur'], 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0, 12, 0.13, 15, 0.1] } },
      { id: 'secteurs-trait', type: 'line', source: 'secteurs', minzoom: 11,
        paint: { 'line-color': ['get', 'couleur'], 'line-width': 1.2, 'line-dasharray': [3, 2], 'line-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0, 12, 0.55] } },

      // La résidence choisie : son secteur se trace d'un trait plein de Bleu France.
      { id: 'secteurs-choisi', type: 'line', source: 'secteurs', minzoom: 10.5, filter: ['==', ['get', 'id'], ''],
        paint: { 'line-color': C.briqueCuite, 'line-width': ['interpolate', ['linear'], ['zoom'], 10.5, 1.5, 14, 2.6], 'line-opacity': 0.9 } },

      // ── Les noms ─────────────────────────────────────────────────────
      { id: 'noms-rivieres', type: 'symbol', source: 'fond', 'source-layer': 'water', minzoom: 10.5,
        filter: ['all', ['==', ['geometry-type'], 'LineString'], ['match', ['get', 'kind'], ['river', 'canal'], true, false]],
        layout: { 'symbol-placement': 'line', 'text-field': nom, 'text-font': I, 'text-size': ['interpolate', ['linear'], ['zoom'], 10.5, 11, 15, 13.5], 'text-letter-spacing': 0.08, 'symbol-spacing': 420, 'text-max-angle': 30 },
        paint: { 'text-color': C.eauTexte, 'text-halo-color': C.mer, 'text-halo-width': 1.4 } },
      { id: 'noms-mers', type: 'symbol', source: 'fond', 'source-layer': 'water', maxzoom: 9,
        filter: ['all', ['==', ['geometry-type'], 'Point'], ['match', ['get', 'kind'], ['ocean', 'sea', 'bay', 'gulf'], true, false]],
        layout: { 'text-field': nom, 'text-font': I, 'text-size': ['interpolate', ['linear'], ['zoom'], 3, 11, 7, 13.5], 'text-letter-spacing': 0.12, 'text-max-width': 7 },
        paint: { 'text-color': C.eauTexte, 'text-halo-color': C.mer, 'text-halo-width': 1 } },
      { id: 'noms-rues', type: 'symbol', source: 'fond', 'source-layer': 'roads', minzoom: 13.5,
        filter: ['all', ['has', 'name'], ['match', ['get', 'kind'], ['major_road', 'minor_road'], true, false],
          ['any', ['>=', ['zoom'], 14.3], ['==', ['get', 'kind'], 'major_road']]],
        layout: { 'symbol-placement': 'line', 'text-field': nom, 'text-font': R, 'text-size': ['interpolate', ['linear'], ['zoom'], 13.5, 10.5, 15, 12], 'symbol-spacing': 360, 'text-max-angle': 25, 'text-padding': 6 },
        paint: { 'text-color': C.texte3, 'text-halo-color': C.route, 'text-halo-width': 1.6 } },
      { id: 'noms-quartiers', type: 'symbol', source: 'fond', 'source-layer': 'places', minzoom: 12,
        filter: ['match', ['get', 'kind'], ['neighbourhood', 'macrohood'], true, false],
        layout: { 'text-field': nom, 'text-font': M, 'text-transform': 'uppercase', 'text-letter-spacing': 0.14, 'text-size': ['interpolate', ['linear'], ['zoom'], 12, 9.5, 15, 11.5], 'text-max-width': 7, 'text-padding': 8 },
        paint: { 'text-color': C.texte3, 'text-halo-color': C.halo, 'text-halo-width': 1.5 } },
      { id: 'noms-dpt', type: 'symbol', source: 'etiquettesDpt', minzoom: 5, maxzoom: 9.2,
        layout: {
          'text-field': ['format', ['get', 'nom'], {}, '\n', {}, 'à raccorder', { 'font-scale': 0.84, 'text-font': ['literal', I] }],
          'text-font': M, 'text-size': ['interpolate', ['linear'], ['zoom'], 5, 11.5, 8, 14.5], 'text-max-width': 9, 'text-line-height': 1.1,
          'text-variable-anchor': ['top', 'bottom', 'left', 'right', 'center'], 'text-radial-offset': 1.1, 'text-allow-overlap': false, 'text-padding': 3,
        },
        paint: { 'text-color': C.texte2, 'text-halo-color': C.halo, 'text-halo-width': 1.8,
          'text-opacity': ['interpolate', ['linear'], ['zoom'], 5, 0, 5.5, 1, 8.7, 1, 9.2, 0] } },
      { id: 'noms-villes', type: 'symbol', source: 'fond', 'source-layer': 'places',
        filter: ['all', ['==', ['get', 'kind'], 'locality'],
          ['<=', ['get', 'min_zoom'], ['step', ['zoom'], 5, 5.5, 6, 6.4, 7, 7.5, 9, 9.5, 10, 11, 12, 12.5, 13]]],
        layout: {
          'text-field': nom, 'text-font': ['step', ['get', 'population_rank'], ['literal', R], 11, ['literal', M]],
          'text-size': ['interpolate', ['linear'], ['zoom'],
            4, ['step', ['get', 'population_rank'], 10.5, 11, 11.5, 13, 13.5],
            8, ['step', ['get', 'population_rank'], 11, 10, 12.5, 11, 15, 13, 16],
            11, ['step', ['get', 'population_rank'], 12, 10, 14, 11, 18.5],
            14, ['step', ['get', 'population_rank'], 13, 10, 15, 11, 20]],
          'text-max-width': 8, 'text-padding': 4,
          'symbol-sort-key': ['-', 20, ['get', 'population_rank']],
        },
        // de loin, la brique de la métropole se pose sur Toulouse : son nom lui laisse la place
        paint: { 'text-color': ['step', ['get', 'population_rank'], C.texte2, 11, C.texte], 'text-halo-color': C.halo, 'text-halo-width': 1.6, 'text-halo-blur': 0.4,
          'text-opacity': ['step', ['zoom'], ['case', ['==', ['get', 'name'], 'Toulouse'], 0, 1], 8.6, 1] } },
      { id: 'noms-pays', type: 'symbol', source: 'fond', 'source-layer': 'places', maxzoom: 7,
        filter: ['all', ['==', ['get', 'kind'], 'country'], ['match', ['get', 'name:fr'], ['France', 'Espagne', 'Italie', 'Suisse', 'Allemagne', 'Belgique', 'Royaume-Uni', 'Portugal'], true, false]],
        layout: { 'text-field': nom, 'text-font': M, 'text-transform': 'uppercase', 'text-letter-spacing': 0.25, 'text-size': ['interpolate', ['linear'], ['zoom'], 3, 10, 6, 13], 'text-max-width': 6 },
        paint: { 'text-color': C.texte3, 'text-halo-color': C.halo, 'text-halo-width': 1.2, 'text-opacity': ['interpolate', ['linear'], ['zoom'], 6, 1, 7, 0] } },
    ],
  };
}

// Trois familles de routes, chacune avec son bord et son âme. Pas de chemins, pas de voies de service, pas de rails.
function routes() {
  const tunnel = ['==', ['get', 'is_tunnel'], true];
  const grandes = ['all', ['==', ['get', 'kind'], 'highway'], ['!', tunnel]];
  const majeures = ['all', ['==', ['get', 'kind'], 'major_road'], ['!', tunnel],
    ['any', ['match', ['get', 'kind_detail'], ['trunk', 'primary'], true, false], ['>=', ['zoom'], 10.5]],
    ['any', ['!=', ['get', 'kind_detail'], 'tertiary'], ['>=', ['zoom'], 11.5]]];
  const mineures = ['all', ['==', ['get', 'kind'], 'minor_road'], ['!', tunnel], ['match', ['get', 'kind_detail'], ['service', 'track'], false, true]];
  const ligne = { 'line-cap': 'round', 'line-join': 'round' };
  return [
    { id: 'rues-bord', type: 'line', source: 'fond', 'source-layer': 'roads', minzoom: 13, filter: mineures, layout: ligne,
      paint: { 'line-color': C.routeBord, 'line-opacity': ['interpolate', ['linear'], ['zoom'], 13, 0, 14, 0.7], 'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 13, 1.6, 15, 6] } },
    { id: 'rues', type: 'line', source: 'fond', 'source-layer': 'roads', minzoom: 12, filter: mineures, layout: ligne,
      paint: { 'line-color': C.route, 'line-opacity': ['interpolate', ['linear'], ['zoom'], 12, 0, 13, 1], 'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 12, 0.6, 15, 4.6] } },
    { id: 'axes-bord', type: 'line', source: 'fond', 'source-layer': 'roads', minzoom: 10, filter: majeures, layout: ligne,
      paint: { 'line-color': C.routeBord, 'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 10, 1.4, 12, 3, 15, 10] } },
    { id: 'axes', type: 'line', source: 'fond', 'source-layer': 'roads', minzoom: 8.5, filter: majeures, layout: ligne,
      paint: { 'line-color': ['interpolate', ['linear'], ['zoom'], 9, C.routeLoin, 10.5, C.route],
        'line-opacity': ['interpolate', ['linear'], ['zoom'], 8.5, 0, 9.5, 0.8],
        'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 8.5, 0.4, 10, 0.8, 12, 1.8, 15, 7.5] } },
    { id: 'voies-rapides-bord', type: 'line', source: 'fond', 'source-layer': 'roads', minzoom: 9, filter: grandes, layout: ligne,
      paint: { 'line-color': C.routeBord, 'line-opacity': ['interpolate', ['linear'], ['zoom'], 9, 0, 10, 1], 'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 9, 1.6, 12, 4, 15, 13] } },
    { id: 'voies-rapides', type: 'line', source: 'fond', 'source-layer': 'roads', minzoom: 5.5, filter: grandes, layout: ligne,
      paint: { 'line-color': ['interpolate', ['linear'], ['zoom'], 9, C.routeLoin, 10, C.route],
        'line-opacity': ['interpolate', ['linear'], ['zoom'], 5, 0, 6, 0.85, 9, 0.95],
        'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 5, 0.5, 7, 1, 8, 1.2, 10, 1.6, 12, 2.6, 15, 10] } },
  ];
}
