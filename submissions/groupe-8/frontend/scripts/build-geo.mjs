// Builds the map geography from the public france-geojson dataset
// (https://github.com/gregoiredavid/france-geojson, Licence Ouverte / Etalab).
//
//   node scripts/build-geo.mjs <dir with d09/d31/d32.geojson (full-resolution departments)
//                                    and c09/c31/c32.geojson (communes)>
//
// Output: public/geo/territory.json
//   departments  the three department polygons (full resolution, for the 8 % fill)
//   borders      their outline split into 'outer' and 'shared' lines (shared edges drawn thinner)
//   communes     for the optional saturation layer
// The outputs are committed: the app needs no network access for its geography.

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const src = process.argv[2];
if (!src) throw new Error('usage: node scripts/build-geo.mjs <download dir>');
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (f) => JSON.parse(readFileSync(join(src, f), 'utf8'));
const CODES = ['09', '31', '32'];

// Ramer–Douglas–Peucker on [lon, lat] rings
function rdp(pts, eps) {
  if (pts.length < 4) return pts;
  const [a, b] = [pts[0], pts[pts.length - 1]];
  let idx = -1;
  let max = 0;
  for (let i = 1; i < pts.length - 1; i++) {
    const p = pts[i];
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const len = Math.hypot(dx, dy) || 1e-12;
    const d = Math.abs(dy * p[0] - dx * p[1] + b[0] * a[1] - b[1] * a[0]) / len;
    if (d > max) {
      max = d;
      idx = i;
    }
  }
  if (max <= eps) return [a, b];
  return [...rdp(pts.slice(0, idx + 1), eps).slice(0, -1), ...rdp(pts.slice(idx), eps)];
}
// Closed rings start and end on the same point: split at the farthest vertex first.
function rdpRing(r, eps) {
  let far = 1;
  let best = -1;
  for (let i = 1; i < r.length - 1; i++) {
    const d = Math.hypot(r[i][0] - r[0][0], r[i][1] - r[0][1]);
    if (d > best) {
      best = d;
      far = i;
    }
  }
  return [...rdp(r.slice(0, far + 1), eps).slice(0, -1), ...rdp(r.slice(far), eps)];
}
const round = (r) => r.map(([x, y]) => [Math.round(x * 1e4) / 1e4, Math.round(y * 1e4) / 1e4]);
const simplifyRing = (r, eps) => {
  const s = round(rdpRing(r, eps));
  return s.length >= 4 ? s : round(r);
};
const polygons = (g) => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates);
const simplifyGeom = (g, eps) => ({
  type: 'MultiPolygon',
  coordinates: polygons(g).map((poly) => poly.map((r) => simplifyRing(r, eps))),
});

const departments = {
  type: 'FeatureCollection',
  features: CODES.map((code) => {
    const raw = read(`d${code}.geojson`);
    const f = raw.features ? raw.features[0] : raw;
    return { type: 'Feature', properties: { code, nom: f.properties.nom }, geometry: f.geometry };
  }),
};

// Edges used by one department are outer borders; edges used by two are shared borders.
// The source polygons share exact vertices along common borders.
const key = (p) => `${p[0]},${p[1]}`;
const edges = new Map();
for (const f of departments.features)
  for (const poly of polygons(f.geometry))
    for (const ring of poly)
      for (let i = 0; i < ring.length - 1; i++) {
        const [a, b] = [ring[i], ring[i + 1]];
        const k = key(a) < key(b) ? `${key(a)}|${key(b)}` : `${key(b)}|${key(a)}`;
        const e = edges.get(k);
        if (e) e.count++;
        else edges.set(k, { a, b, count: 1 });
      }

/** Chains loose segments into polylines. */
function chain(segs) {
  const byPoint = new Map();
  const add = (p, s) => byPoint.set(key(p), [...(byPoint.get(key(p)) ?? []), s]);
  for (const s of segs) {
    add(s.a, s);
    add(s.b, s);
  }
  const used = new Set();
  const lines = [];
  const extend = (line, end) => {
    for (;;) {
      const next = (byPoint.get(key(end)) ?? []).find((s) => !used.has(s));
      if (!next) return line;
      used.add(next);
      end = key(next.a) === key(end) ? next.b : next.a;
      line.push(end);
    }
  };
  for (const s of segs) {
    if (used.has(s)) continue;
    used.add(s);
    const fwd = extend([s.a, s.b], s.b);
    const back = extend([s.a], s.a);
    lines.push([...back.reverse().slice(0, -1), ...fwd]);
  }
  return lines;
}
const all = [...edges.values()];
const borders = {
  type: 'FeatureCollection',
  features: [
    { type: 'Feature', properties: { kind: 'outer' }, geometry: { type: 'MultiLineString', coordinates: chain(all.filter((e) => e.count === 1)) } },
    { type: 'Feature', properties: { kind: 'shared' }, geometry: { type: 'MultiLineString', coordinates: chain(all.filter((e) => e.count > 1)) } },
  ],
};

const communes = {
  type: 'FeatureCollection',
  features: ['c09', 'c31', 'c32'].flatMap((c) =>
    read(`${c}.geojson`).features.map((f) => ({
      type: 'Feature',
      properties: { code: f.properties.code, nom: f.properties.nom },
      geometry: simplifyGeom(f.geometry, 0.0008),
    })),
  ),
};

mkdirSync(join(root, 'public', 'geo'), { recursive: true });
writeFileSync(join(root, 'public', 'geo', 'territory.json'), JSON.stringify({ departments, borders, communes }));

const size = (o) => (JSON.stringify(o).length / 1024).toFixed(0);
console.log(
  `departments ${size(departments)} kB, borders ${borders.features.map((f) => f.geometry.coordinates.length).join('/')} lines, communes ${communes.features.length} (${size(communes)} kB)`,
);
