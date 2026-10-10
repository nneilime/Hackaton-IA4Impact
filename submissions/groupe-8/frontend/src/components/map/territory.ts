// Geography drawn by MapLibre over a full street basemap (OpenFreeMap "liberty"):
// French labels, relief, and the highlight of the three departments. The deck.gl
// operational layer (incidents, teams, sites, routes) draws above all of it.
import type { Map as MLMap } from 'maplibre-gl';
import { palette } from '../../lib/theme';

/** Full-detail OSM street style, no API key. Fallback to test: CARTO Voyager
 *  https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json */
export const BASEMAP = 'https://tiles.openfreemap.org/styles/liberty';
export const TERRITORY_BOUNDS: [[number, number], [number, number]] = [
  [-0.29, 42.57],
  [2.18, 44.12],
];
export const HG_BOUNDS: [[number, number], [number, number]] = [
  [0.44, 42.69],
  [2.05, 43.92],
];
/** Cannot zoom out further than the whole of France. */
export const MIN_ZOOM = 4.8;
/** Below this zoom, waiting incidents are grouped per commune. */
export const CLUSTER_MAX_ZOOM = 9.3;
/** Department labels are hidden at street level. */
const DEPT_LABEL_MAX_ZOOM = 11;

const DEPT_LABELS = [
  { code: '32', name: 'GERS', lon: 0.55, lat: 43.42 },
  { code: '31', name: 'HAUTE-GARONNE', lon: 1.13, lat: 43.3 },
  { code: '09', name: 'ARIÈGE', lon: 1.4, lat: 42.79 },
];
export const MAJOR_SITES = ['Auch', 'Foix'];

// Insertion points in the liberty style: the fill goes under the roads, the outline
// above roads but under every label.
const FIRST_ROAD_LAYER = 'tunnel_motorway_link_casing';
const FIRST_LABEL_LAYER = 'waterway_line_label';
const FIRST_PLACE_LABEL = 'label_other';

export const siteShortName = (name: string) =>
  name.replace(/\s*\(Toulouse\)/, '').replace('Bagnères de Luchon', 'Luchon').replace('Villefranche-de-Lauragais', 'Villefranche');

/** Accent-, case- and article-insensitive commune key (france-geojson drops "Le", "La", "L'"). */
export const communeKey = (s: string) =>
  s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/^(le |la |les |l')/, '')
    .replace(/[^a-z]/g, '');

type Territory = {
  departments: GeoJSON.FeatureCollection;
  borders: GeoJSON.FeatureCollection;
  communes: GeoJSON.FeatureCollection;
};

/** Commune key -> feature codes (several communes can share a name). */
export const communeCodes = new Map<string, string[]>();

const setups = new WeakMap<MLMap, Promise<void>>();

/** Idempotent: React StrictMode and hot reload may ask twice for the same map. */
export function setupTerritory(map: MLMap): Promise<void> {
  let p = setups.get(map);
  if (!p) {
    p = addTerritory(map);
    setups.set(map, p);
  }
  return p;
}

async function addTerritory(map: MLMap) {
  const p = palette();
  const geo: Territory = await fetch(`${import.meta.env.BASE_URL}geo/territory.json`).then((r) => r.json());
  for (const f of geo.communes.features) {
    const k = communeKey(String(f.properties!.nom));
    communeCodes.set(k, [...(communeCodes.get(k) ?? []), String(f.properties!.code)]);
  }
  const before = (id: string) => (map.getLayer(id) ? id : undefined);

  // --- labels in French: prefer name:fr wherever the style shows a name (road refs untouched)
  for (const l of map.getStyle().layers) {
    if (l.type !== 'symbol') continue;
    const tf = map.getLayoutProperty(l.id, 'text-field');
    if (tf && JSON.stringify(tf).includes('name:latin'))
      map.setLayoutProperty(l.id, 'text-field', ['coalesce', ['get', 'name:fr'], ['get', 'name:latin'], ['get', 'name']]);
  }

  // --- relief, so the Pyrenees read as mountains at medium zoom
  map.addSource('terrain', {
    type: 'raster-dem',
    tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
    encoding: 'terrarium',
    tileSize: 256,
    maxzoom: 12,
    attribution: 'Relief © Mapzen / AWS Terrain Tiles',
  });
  map.addLayer(
    {
      id: 'hillshade',
      type: 'hillshade',
      source: 'terrain',
      paint: {
        'hillshade-shadow-color': p.text,
        'hillshade-highlight-color': p.surface,
        'hillshade-accent-color': p.text,
        'hillshade-exaggeration': 0.22,
      },
    },
    before('waterway_tunnel'),
  );

  map.addSource('departments', { type: 'geojson', data: geo.departments });
  map.addSource('borders', { type: 'geojson', data: geo.borders });
  map.addSource('communes', { type: 'geojson', data: geo.communes, promoteId: 'code' });

  // --- fill under the roads: roads and labels stay fully readable
  map.addLayer({ id: 'dept-fill', type: 'fill', source: 'departments', paint: { 'fill-color': p.blue, 'fill-opacity': 0.04 } }, before(FIRST_ROAD_LAYER));
  map.addLayer(
    {
      id: 'communes-sat',
      type: 'fill',
      source: 'communes',
      layout: { visibility: 'none' },
      paint: {
        'fill-color': p.blue,
        'fill-opacity': ['interpolate', ['linear'], ['coalesce', ['feature-state', 'ch'], 0], 0, 0, 50, 0.12, 400, 0.3, 1500, 0.5, 4000, 0.68],
      },
    },
    before(FIRST_ROAD_LAYER),
  );

  // --- outline above the roads, below every label; white casing keeps it visible on any colour
  const line = (id: string, kind: 'outer' | 'shared', color: string, width: number) =>
    map.addLayer(
      {
        id,
        type: 'line',
        source: 'borders',
        filter: ['==', ['get', 'kind'], kind],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': color, 'line-width': width },
      },
      before(FIRST_LABEL_LAYER),
    );
  line('dept-shared-casing', 'shared', p.surface, 3.5);
  line('dept-outer-casing', 'outer', p.surface, 5);
  // grey, not blue: the proposed routes must be the strongest lines on the map
  line('dept-shared', 'shared', '#8a94a8', 1.2);
  line('dept-outer', 'outer', '#6b7590', 1.8);

  // --- department names: under the place labels so a town name always wins the collision
  map.addSource('dept-labels', {
    type: 'geojson',
    data: {
      type: 'FeatureCollection',
      features: DEPT_LABELS.map((d) => ({ type: 'Feature', properties: d, geometry: { type: 'Point', coordinates: [d.lon, d.lat] } })),
    },
  });
  map.addLayer(
    {
      id: 'dept-labels',
      type: 'symbol',
      source: 'dept-labels',
      maxzoom: DEPT_LABEL_MAX_ZOOM,
      layout: {
        'text-field': ['format', ['get', 'name'], {}, '\n', {}, ['get', 'code'], { 'font-scale': 0.85 }],
        'text-font': ['Noto Sans Bold'],
        'text-size': ['step', ['zoom'], 12, 7, 14, 9.5, 18],
        'text-letter-spacing': 0.08,
        'text-line-height': 1.1,
      },
      paint: { 'text-color': p.blue, 'text-halo-color': p.surface, 'text-halo-width': 2.2 },
    },
    before(FIRST_PLACE_LABEL),
  );
}
