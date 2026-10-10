// Road geometry for team -> incident routes, fetched once per pair from the backend (OSRM, cached server side).
// Until it arrives (or with the mock source) the caller draws its own arc.
import { useEffect } from 'react';
import { source } from '../../data/source';

type LonLat = [number, number];
const cache = new Map<string, LonLat[]>();
const pending = new Set<string>();

export const roadKey = (a: LonLat, b: LonLat) => `${a[0].toFixed(4)},${a[1].toFixed(4)};${b[0].toFixed(4)},${b[1].toFixed(4)}`;

/** Road path if known, else undefined (and the pair is queued for the next fetch). */
export function road(a: LonLat, b: LonLat, wanted: Map<string, [LonLat, LonLat]>): LonLat[] | undefined {
  const k = roadKey(a, b);
  const hit = cache.get(k);
  if (!hit && source.roads && !pending.has(k)) wanted.set(k, [a, b]);
  return hit;
}

/** Fetches the queued pairs after render; calls onLoaded when new geometry arrived. */
export function useRoadFetch(wanted: Map<string, [LonLat, LonLat]>, onLoaded: () => void): void {
  const keys = [...wanted.keys()].sort().join('|');
  useEffect(() => {
    if (!keys || !source.roads) return;
    const batch = [...wanted.entries()].filter(([k]) => !cache.has(k) && !pending.has(k)).slice(0, 40);
    if (!batch.length) return;
    batch.forEach(([k]) => pending.add(k));
    source
      .roads(batch.map(([, pair]) => pair))
      .then((res) => {
        // keep only real road geometry: a straight fallback (routing service down / rate limited) is asked again later
        res.forEach((r, i) => r.source === 'osrm' && r.coordinates.length > 2 && cache.set(batch[i][0], r.coordinates));
        onLoaded();
      })
      .catch(() => {
        /* keep the arcs */
      })
      .finally(() => batch.forEach(([k]) => pending.delete(k)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keys]);
}

if (import.meta.env.DEV) (window as unknown as { __roads?: unknown }).__roads = { cache, pending };
