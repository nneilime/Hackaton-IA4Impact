import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import MapGL, { NavigationControl, ScaleControl, useControl, useMap, type MapRef } from 'react-map-gl/maplibre';
import { MapboxOverlay, type MapboxOverlayProps } from '@deck.gl/mapbox';
import { IconLayer, PathLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';
import { PathStyleExtension } from '@deck.gl/extensions';
import type { PickingInfo } from '@deck.gl/core';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

import type { Incident, Recommendation, Team } from '../data/contract';
import { incidentIcon, sensitiveBadgeIcon, siteIcon, teamIcon } from '../lib/icons';
import { palette, rgba, type RGBA } from '../lib/theme';
import { stepOf, useFocusedRec, useStore } from '../state/store';
import { fmtHour } from '../lib/format';
import { MapLegend } from './MapLegend';
import { MapTooltip, type HoverTarget } from './MapTooltip';
import {
  BASEMAP,
  CLUSTER_MAX_ZOOM,
  HG_BOUNDS,
  MAJOR_SITES,
  MIN_ZOOM,
  TERRITORY_BOUNDS,
  communeCodes,
  communeKey,
  setupTerritory,
  siteShortName,
} from './map/territory';
import { road, useRoadFetch } from './map/roads';
import { placeLabels, type LabelSpec, type PlacedLine, type Rect } from './map/labels';

// Untouched copy of the worker, see scripts/copy-maplibre-worker.mjs
maplibregl.setWorkerUrl(`${import.meta.env.BASE_URL}vendor/maplibre/maplibre-gl-worker.mjs`);

const PULSE_MS = 1400;
// Fixed glyph set: avoids deck.gl rebuilding its font atlas mid-playback.
const CHARSET = Array.from(new Set(
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,;:·-–()/\'’éèêëàâäîïôöûüùçÉÈÊÀÂÎÔÛÇœ',
)).join('');
const FIT_PADDING = { top: 60, bottom: 40, left: 40, right: 40 };
/** Fit padding scaled to the map's size: fixed 60 px margins swallow a short map (laptop / display scaling). */
function fitPadding(map: maplibregl.Map | null) {
  const el = map?.getContainer();
  if (!el) return FIT_PADDING;
  const v = Math.min(1, el.clientHeight / 600);
  const h = Math.min(1, el.clientWidth / 900);
  return { top: Math.round(56 * v), bottom: Math.round(16 * v), left: Math.round(40 * h), right: Math.round(40 * h) };
}
const dashExt = [new PathStyleExtension({ dash: true })];
/** Colour of the plan being proposed (routes + numbered badges): distinct from the blue UI, the grey borders and the orange outages. */
const PLAN_RGB: [number, number, number] = [124, 58, 237];
/** Validated plans: one colour per plan (by the step that produced it), cycling. Violet stays for the pending plan. */
const PLAN_COLOURS: [number, number, number][] = [
  [14, 165, 233], // sky
  [16, 185, 129], // emerald
  [245, 158, 11], // amber
  [236, 72, 153], // pink
  [20, 184, 166], // teal
  [99, 102, 241], // indigo
];
export const planColour = (step: number) => PLAN_COLOURS[step % PLAN_COLOURS.length];
/** Below this zoom (France view) site labels are hidden and markers shrink. */
const DETAIL_ZOOM = 8;
/** Site names are shown permanently from this zoom (counts only below it). */
const SITE_NAME_ZOOM = 10;
/** Site squares show their number of available teams from this zoom (small plain squares below). */
const SITE_COUNT_ZOOM = 8.5;
/** Sensitive incidents get a label from this zoom. */
const SENSITIVE_LABEL_ZOOM = 9;



function DeckOverlay(props: MapboxOverlayProps) {
  const overlay = useControl<MapboxOverlay>(() => new MapboxOverlay(props));
  overlay.setProps(props);
  return null;
}

/**
 * Sets up the territory as soon as the basemap style is parsed. The map 'load' event waits for
 * every tile (relief included) and can take seconds on a slow network.
 */
function TerritorySetup({ onReady }: { onReady: (map: maplibregl.Map) => void }) {
  const { current } = useMap();
  useEffect(() => {
    if (!current) return;
    const map = current.getMap();
    let done = false;
    const go = () => {
      if (done) return;
      done = true;
      onReady(map);
    };
    if ((map as unknown as { style?: { _loaded?: boolean } }).style?._loaded) go();
    else map.once('style.load', go);
    return () => {
      map.off('style.load', go);
    };
  }, [current, onReady]);
  return null;
}

type TeamView = Team & { offset: [number, number]; atHome: boolean };
export type Cluster = { key: string; commune: string; lon: number; lat: number; count: number; clients: number; sensitive: boolean };
type Route = { id: string; recId?: string; kind: 'pending' | 'decided' | 'travel' | 'preview' | 'option'; rank?: number; path: [number, number][]; color: RGBA; width: number };

const incidentSize = (i: Incident) =>
  (i.status === 'restored' ? 9 : 13 + Math.sqrt(i.clients / 150) * 17) * (i.sensitive && i.status !== 'restored' ? 1.35 : 1);
const clusterRadius = (c: Cluster) => 13 + Math.sqrt(c.clients / 500) * 10;

/** Gentle arc from a to b (quadratic Bézier), in lon/lat with latitude correction. */
function arc(a: [number, number], b: [number, number], n = 28): [number, number][] {
  const k = Math.cos((a[1] * Math.PI) / 180);
  const dx = (b[0] - a[0]) * k;
  const dy = b[1] - a[1];
  const cx = ((a[0] + b[0]) * k) / 2 - dy * 0.18;
  const cy = (a[1] + b[1]) / 2 + dx * 0.18;
  const pts: [number, number][] = [];
  for (let i = 0; i <= n; i++) {
    const u = i / n;
    const x = (1 - u) ** 2 * a[0] * k + 2 * (1 - u) * u * cx + u * u * b[0] * k;
    const y = (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * cy + u * u * b[1];
    pts.push([x / k, y]);
  }
  return pts;
}

export function MapView() {
  const mapRef = useRef<MapRef>(null);
  // The live map instance (from the map context). Under StrictMode the ref can briefly
  // point at a discarded instance with a different camera, so projections use this one.
  const liveMap = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [zoom, setZoom] = useState(8);
  const clustered = zoom < CLUSTER_MAX_ZOOM;
  const [saturation, setSaturation] = useState(false);
  const [hover, setHover] = useState<HoverTarget | null>(null);
  /** Card pinned by a click: stays until a click on empty map, Esc or the next step. */
  const [pinned, setPinned] = useState<{ target: HoverTarget; lon: number; lat: number } | null>(null);
  const [, setTick] = useState(0);

  const timelines = useStore((s) => s.timelines)!;
  const meta = useStore((s) => s.meta)!;
  const view = useStore((s) => s.view);
  const t = useStore((s) => s.t);
  const playing = useStore((s) => s.playing);
  const hoveredRecId = useStore((s) => s.hoveredRecId);
  const overrideRecId = useStore((s) => s.overrideRecId);
  const previewTeamId = useStore((s) => s.previewTeamId);
  const hoverRec = useStore((s) => s.hoverRec);
  const modal = useStore((s) => s.modal);
  const hoveredOption = useStore((s) => s.hoveredOption);
  const highlightSites = useStore((s) => s.highlightSites);

  const step = meta.stepMinutes;
  const snaps = timelines[view];
  const k = stepOf({ t, meta, timelines });
  const snap = snaps[k];
  const next = snaps[Math.min(k + 1, snaps.length - 1)];
  const frac = Math.max(0, Math.min(1, t / step - k));
  const nowMs = Date.parse(meta.start) + t * 60000;
  const p = palette();

  // ---- incidents (new ones appear between steps as they are reported)
  const upcoming = useMemo(() => {
    const known = new Set(snap.incidents.map((i) => i.id));
    return next.incidents
      .filter((i) => !known.has(i.id))
      .map((i) => ({ inc: { ...i, status: 'waiting' as const, teamId: undefined }, at: Date.parse(i.reportedAt) }));
  }, [snap, next]);
  const arrived = upcoming.filter((u) => u.at <= nowMs).length;
  const incidents = useMemo(() => {
    const extra = upcoming.filter((u) => u.at <= nowMs).map((u) => u.inc);
    const all = extra.length ? [...snap.incidents, ...extra] : snap.incidents;
    const rank = { restored: 0, repairing: 1, enroute: 2, waiting: 3 } as const;
    return [...all].sort((a, b) => rank[a.status] - rank[b.status] || b.clients - a.clients);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snap, upcoming, arrived]);
  const incById = useMemo(() => new Map(incidents.map((i) => [i.id, i])), [incidents]);

  // ---- per-commune clusters of waiting incidents at territory zoom
  const { clusters, clusteredIds } = useMemo(() => {
    const out: Cluster[] = [];
    const ids = new Set<string>();
    if (!clustered) return { clusters: out, clusteredIds: ids };
    const by = new Map<string, Incident[]>();
    for (const i of incidents) {
      if (i.status !== 'waiting') continue;
      by.set(i.commune, [...(by.get(i.commune) ?? []), i]);
    }
    for (const [commune, g] of by) {
      if (g.length < 2) continue;
      g.forEach((i) => ids.add(i.id));
      out.push({
        key: commune,
        commune,
        lon: g.reduce((s, i) => s + i.lon, 0) / g.length,
        lat: g.reduce((s, i) => s + i.lat, 0) / g.length,
        count: g.length,
        clients: g.reduce((s, i) => s + i.clients, 0),
        sensitive: g.some((i) => i.sensitive),
      });
    }
    return { clusters: out.sort((a, b) => b.clients - a.clients), clusteredIds: ids };
  }, [incidents, clustered]);

  // ---- teams: interpolate between snapshots; teams parked at their site are shown by the site marker
  const siteByName = useMemo(() => new Map(meta.sites.map((s) => [s.name, s])), [meta.sites]);
  const nextTeams = useMemo(() => new Map(next.teams.map((tm) => [tm.id, tm])), [next]);
  const teams: TeamView[] = useMemo(() => {
    const out = snap.teams.map((tm) => {
      const n = nextTeams.get(tm.id);
      const lon = n ? tm.lon + (n.lon - tm.lon) * frac : tm.lon;
      const lat = n ? tm.lat + (n.lat - tm.lat) * frac : tm.lat;
      const site = siteByName.get(tm.siteName);
      const atHome = !!site && Math.abs(site.lon - lon) < 1e-3 && Math.abs(site.lat - lat) < 1e-3;
      return { ...tm, lon, lat, atHome, offset: [0, 0] as [number, number] };
    });
    // Teams on a repair sit beside the incident; teams waiting at the same spot fan out.
    const groups = new Map<string, TeamView[]>();
    for (const tm of out) {
      if (tm.status === 'repairing') tm.offset = [14, -14];
      else if (tm.status !== 'travelling') {
        const key = `${tm.lon.toFixed(3)}|${tm.lat.toFixed(3)}`;
        groups.set(key, [...(groups.get(key) ?? []), tm]);
      }
    }
    for (const g of groups.values()) {
      if (g.length < 2) continue;
      g.forEach((tm, i) => (tm.offset = [(i - (g.length - 1) / 2) * 16, -16]));
    }
    return out;
  }, [snap, nextTeams, frac, siteByName]);
  const teamById = useMemo(() => new Map(teams.map((tm) => [tm.id, tm])), [teams]);

  // ---- site labels: teams available at home, per site
  const siteAvail = useMemo(() => {
    const m = new Map<string, number>();
    for (const tm of snap.teams) {
      const s = siteByName.get(tm.siteName);
      if (tm.status === 'available' && s && Math.abs(s.lon - tm.lon) < 1e-3 && Math.abs(s.lat - tm.lat) < 1e-3)
        m.set(tm.siteName, (m.get(tm.siteName) ?? 0) + 1);
    }
    return m;
  }, [snap, siteByName]);
  const siteAvailKey = [...siteAvail.entries()].join();
  // ---- optional saturation layer: customer-hours waiting per commune
  useEffect(() => {
    const map = liveMap.current;
    if (!ready || !map) return;
    map.setLayoutProperty('communes-sat', 'visibility', saturation ? 'visible' : 'none');
    if (!saturation) return;
    map.removeFeatureState({ source: 'communes' });
    const T = Date.parse(snap.time);
    const ch = new Map<string, number>();
    for (const i of snap.incidents) {
      if (i.status !== 'waiting') continue;
      const key = communeKey(i.commune);
      ch.set(key, (ch.get(key) ?? 0) + (i.clients * Math.max(0, T - Date.parse(i.reportedAt))) / 3600000);
    }
    for (const [key, v] of ch) for (const code of communeCodes.get(key) ?? []) map.setFeatureState({ source: 'communes', id: code }, { ch: v });
  }, [ready, saturation, snap]);

  // ---- pulse once for incidents that appear during playback
  const seen = useRef<Set<string> | null>(null);
  const pulses = useRef(new Map<string, number>());
  const realNow = performance.now();
  {
    const visible = new Set(incidents.map((i) => i.id));
    if (!seen.current) seen.current = visible;
    else {
      for (const id of visible)
        if (!seen.current.has(id)) {
          seen.current.add(id);
          if (playing) pulses.current.set(id, realNow);
        }
      for (const id of seen.current) if (!visible.has(id)) seen.current.delete(id);
    }
    for (const [id, at] of pulses.current) if (realNow - at > PULSE_MS || !visible.has(id)) pulses.current.delete(id);
  }
  const pulseCount = pulses.current.size;
  useEffect(() => {
    if (playing || pulseCount === 0) return;
    const raf = requestAnimationFrame(() => setTick((x) => x + 1));
    return () => cancelAnimationFrame(raf);
  });

  // ---- routes
  const recs: Recommendation[] = view === 'ours' ? snap.recommendations : [];
  const recTeamIds = useMemo(() => new Map(recs.map((r) => [r.teamId, r.id])), [recs]);
  const recIncIds = useMemo(() => new Map(recs.map((r) => [r.incidentId, r.id])), [recs]);
  const focused = useFocusedRec();
  const focusId = overrideRecId ?? focused?.id;
  const focusRec = recs.find((r) => r.id === focusId);

  const [roadsVersion, setRoadsVersion] = useState(0);
  const bumpRoads = useCallback(() => setRoadsVersion((v) => v + 1), []);
  // Road geometry (OSRM via the backend) for routes from a team standing still; arcs until it arrives.
  const snapTeams = useMemo(() => new Map(snap.teams.map((tm) => [tm.id, tm])), [snap]);
  const optionRec = modal?.kind === 'options' ? recs.find((r) => r.id === modal.recId) : undefined;
  // validated plans: which step's plan sent the team now heading to each incident (for the route colour)
  const planOfIncident = useMemo(() => {
    const m = new Map<string, { step: number; from: [number, number] }>();
    if (view !== 'ours') return m;
    for (let j = 0; j <= k; j++)
      for (const d of timelines.ours[j].decisions) {
        const tm = timelines.ours[j].teams.find((t) => t.id === d.teamId);
        if (tm) m.set(d.incidentId, { step: j, from: [tm.lon, tm.lat] });
      }
    return m;
  }, [timelines, k, view]);
  const { routes, wanted } = useMemo(() => {
    const out: Route[] = [];
    // Pairs still missing a road geometry, fetched after render (kept in the memo's result: StrictMode-safe).
    const wanted = new Map<string, [[number, number], [number, number]]>();
    const ends = (teamId: string, incId: string, roads = true) => {
      const tm = teamById.get(teamId);
      const inc = incById.get(incId);
      if (!tm || !inc) return null;
      const st = snapTeams.get(teamId);
      if (roads && st && st.status !== 'travelling') {
        const r = road([st.lon, st.lat], [inc.lon, inc.lat], wanted);
        if (r && r.length > 1) return r;
      }
      return arc([tm.lon, tm.lat], [inc.lon, inc.lat]);
    };
    const decidedNow = new Set(view === 'ours' ? snap.decisions.map((d) => d.teamId) : []);
    for (const tm of teams) {
      if (tm.status !== 'travelling' || !tm.incidentId || decidedNow.has(tm.id)) continue;
      // a team on the road keeps its whole road route, in the colour of the plan that sent it, until it arrives
      const sent = planOfIncident.get(tm.incidentId);
      const inc = incById.get(tm.incidentId);
      const roadPath = sent && inc ? road(sent.from, [inc.lon, inc.lat], wanted) : undefined;
      const path = roadPath && roadPath.length > 1 ? roadPath : ends(tm.id, tm.incidentId, false);
      if (path)
        out.push(
          sent === undefined
            ? { id: `tr-${tm.id}`, kind: 'travel', path, color: rgba(p.blue, 120), width: 1.5 }
            : { id: `tr-${tm.id}`, kind: 'travel', path, color: [...planColour(sent.step), 235] as RGBA, width: 4 },
        );
    }
    if (view === 'ours') {
      for (const d of snap.decisions) {
        const path = ends(d.teamId, d.incidentId);
        if (path) out.push({ id: `dec-${d.incidentId}`, kind: 'decided', path, color: [...planColour(k), 255] as RGBA, width: 4.5 });
      }
    }
    for (const r of recs) {
      const path = ends(r.teamId, r.incidentId);
      if (!path) continue;
      // The whole proposed plan is visible as one set of numbered routes; the line in focus is the strongest.
      const isFocus = r.id === focusId;
      const isHover = r.id === hoveredRecId;
      const muted = r.id === overrideRecId && !!previewTeamId;
      const alpha = muted ? 90 : isFocus || isHover ? 255 : 215;
      out.push({ id: r.id, recId: r.id, kind: 'pending', path, color: [...PLAN_RGB, alpha] as RGBA, width: muted ? 2 : isFocus ? 7 : isHover ? 6 : 4.5 });
    }
    const orec = recs.find((r) => r.id === overrideRecId);
    if (orec && previewTeamId) {
      const path = ends(previewTeamId, orec.incidentId);
      if (path) out.push({ id: 'preview', kind: 'preview', path, color: rgba(p.teal), width: 4.5 });
    }
    // The 3 best options of the recommendation under study, in the popup's colours (rank 1 drawn last, on top).
    if (optionRec?.options) {
      const colours = [p.green, p.yellow, p.waiting];
      for (const o of [...optionRec.options].reverse()) {
        const path = ends(o.team, optionRec.incidentId);
        if (!path) continue;
        const dim = hoveredOption !== undefined && hoveredOption !== o.rank;
        const strong = hoveredOption === o.rank;
        out.push({ id: `opt-${o.rank}`, recId: optionRec.id, rank: o.rank, kind: 'option', path, color: rgba(colours[o.rank - 1], dim ? 70 : 255), width: strong ? 7 : 4.5 });
      }
    }
    return { routes: out, wanted };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teams, incById, recs, snap.decisions, view, focusId, hoveredRecId, overrideRecId, previewTeamId, optionRec, hoveredOption, roadsVersion, planOfIncident, k]);

  useRoadFetch(wanted, bumpRoads);

  // Zoom on the 3 options when their popup opens (once per recommendation).
  const optionKey = optionRec?.id;
  useEffect(() => {
    const map = liveMap.current;
    if (!ready || !map || !optionRec?.options) return;
    const inc = incById.get(optionRec.incidentId);
    if (!inc) return;
    const pts: [number, number][] = [[inc.lon, inc.lat], ...optionRec.options.map((o) => o.path[0])];
    const lons = pts.map((q) => q[0]);
    const lats = pts.map((q) => q[1]);
    map.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      { padding: 90, maxZoom: 11, duration: 600 },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, optionKey]);

  // ---- plan badges: the line number of each assignment, at its incident (same numbers as the panel)
  const planBadges = useMemo(
    () =>
      recs
        .map((r, i) => ({ recId: r.id, rank: i + 1, inc: incById.get(r.incidentId) }))
        .filter((b): b is { recId: string; rank: number; inc: Incident } => !!b.inc)
        .map((b) => ({ recId: b.recId, rank: b.rank, lon: b.inc.lon, lat: b.inc.lat })),
    [recs, incById],
  );

  // ---- a new plan appears: frame all its routes (teams and outages) so the whole proposal is visible
  // live: re-frame only when the set of proposed outages changes (not at every re-plan or history entry)
  const planKey = view === 'ours' && recs.length ? `${meta.mode === 'live' ? '' : k}:${recs.map((r) => r.incidentId).sort().join()}` : '';
  useEffect(() => {
    const map = liveMap.current;
    if (!ready || !map || !planKey) return;
    const pts: [number, number][] = [];
    for (const r of recs) {
      const tm = snap.teams.find((t) => t.id === r.teamId);
      const inc = incById.get(r.incidentId);
      if (tm) pts.push([tm.lon, tm.lat]);
      if (inc) pts.push([inc.lon, inc.lat]);
    }
    if (!pts.length) return;
    const lons = pts.map((q) => q[0]);
    const lats = pts.map((q) => q[1]);
    const pad = 0.04;
    map.fitBounds(
      [
        [Math.min(...lons) - pad, Math.min(...lats) - pad],
        [Math.max(...lons) + pad, Math.max(...lats) + pad],
      ],
      { padding: fitPadding(map), maxZoom: 10.5, duration: 700 },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, planKey]);

  // ---- labels: placed in screen space, recomputed when the view moves
  const [viewTick, setViewTick] = useState(0);
  const detail = zoom >= DETAIL_ZOOM;
  // Town, river and road names come from the basemap. Our labels, by priority:
  // focused recommendation > sensitive incidents > site names. (Cluster totals: in the tooltip.)
  const sensitiveZoom = zoom >= SENSITIVE_LABEL_ZOOM;
  const siteNames = zoom >= SITE_NAME_ZOOM;
  const focusLabelKey = focusRec ? `${focusRec.id}` : '';
  const labelSpecs: LabelSpec[] = useMemo(() => {
    if (!detail) return [];
    const line = (text: string, size: number, bold: boolean, color: RGBA) => ({ text, size, bold, color });
    const specs: LabelSpec[] = [];
    const finc = focusRec && incById.get(focusRec.incidentId);
    if (focusRec && finc)
      specs.push({
        id: 'focus',
        lon: finc.lon,
        lat: finc.lat,
        lines: [line(`${finc.commune} · arrivée ${fmtHour(focusRec.eta)}`, 14, true, rgba(p.blue))],
        priority: 1000,
        anchors: ['right', 'left', 'above', 'below'],
        gap: 16,
        force: true,
      });
    if (sensitiveZoom)
      for (const i of incidents)
        if (i.sensitive && i.status === 'waiting' && i.id !== finc?.id)
          specs.push({
            id: `s-${i.id}`,
            lon: i.lon,
            lat: i.lat,
            lines: [line(`${i.commune} · client sensible`, 12, true, rgba(p.critical))],
            priority: 900,
            anchors: ['right', 'left', 'above', 'below'],
            gap: 14,
          });
    if (siteNames)
      for (const st of meta.sites)
        specs.push({
          id: st.id,
          lon: st.lon,
          lat: st.lat,
          lines: [line(siteShortName(st.name), 12, true, rgba(p.blue))],
          priority: (MAJOR_SITES.includes(st.name) ? 550 : 500) + st.teams,
          anchors: ['below', 'above', 'right', 'left'],
          gap: 12,
        });
    return specs;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta.sites, detail, sensitiveZoom, siteNames, focusLabelKey, incidents.length]);

  const placed: PlacedLine[] = useMemo(() => {
    const map = liveMap.current;
    if (!ready || !map) return [];
    const box = map.getContainer().getBoundingClientRect();
    // Overlaid UI and site squares are obstacles.
    const obstacles: Rect[] = [...map.getContainer().parentElement!.querySelectorAll('.legend, .legend-open, .map-tools, .maplibregl-ctrl-top-right, .maplibregl-ctrl-bottom-right')].map((el) => {
      const r = el.getBoundingClientRect();
      return { x0: r.left - box.left - 4, y0: r.top - box.top - 4, x1: r.right - box.left + 4, y1: r.bottom - box.top + 4 };
    });
    for (const st of meta.sites) {
      const q = map.project([st.lon, st.lat]);
      obstacles.push({ x0: q.x - 11, y0: q.y - 11, x1: q.x + 11, y1: q.y + 11 });
    }
    // Basemap city and town names win: our site labels move around them.
    const placeLayers = ['label_city_capital', 'label_city', 'label_town'].filter((id) => map.getLayer(id));
    for (const f of placeLayers.length ? map.queryRenderedFeatures({ layers: placeLayers }) : []) {
      if (f.geometry.type !== 'Point') continue;
      const q = map.project(f.geometry.coordinates as [number, number]);
      const name = String(f.properties['name:fr'] ?? f.properties['name'] ?? '');
      const size = f.layer.id === 'label_town' ? 13 : 16;
      const w = name.length * size * 0.6;
      obstacles.push({ x0: q.x - w / 2, y0: q.y - size, x1: q.x + w / 2, y1: q.y + size });
    }
    return placeLabels(labelSpecs, (lon, lat) => map.project([lon, lat]), { width: box.width, height: box.height }, obstacles);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, labelSpecs, viewTick]);

  // ---- deck layers (interleaved below the MapLibre labels)
  const layers = useMemo(() => {
    if (!ready) return [];
    const restored = incidents.filter((i) => i.status === 'restored');
    const active = incidents.filter((i) => i.status !== 'restored' && !clusteredIds.has(i.id));
    const pulseData = [...pulses.current.entries()].map(([id, at]) => ({ inc: incById.get(id)!, age: (realNow - at) / PULSE_MS })).filter((d) => d.inc);
    const shownTeams = teams.filter(
      (tm) => !(tm.atHome && (tm.status === 'available' || tm.status === 'resting')) || tm.id === focusRec?.teamId || tm.id === previewTeamId,
    );
    const focusInc = focusRec?.incidentId;
    const sc = zoom < DETAIL_ZOOM ? 0.6 : 1; // smaller markers at France / Occitanie zoom
    const labelProps = {
      getPosition: (d: PlacedLine) => [d.lon, d.lat] as [number, number],
      getText: (d: PlacedLine) => d.text,
      getSize: (d: PlacedLine) => d.size,
      getColor: (d: PlacedLine) => d.color,
      getPixelOffset: (d: PlacedLine) => d.offset,
      getTextAnchor: 'middle' as const,
      getAlignmentBaseline: 'top' as const,
      characterSet: CHARSET,
      fontSettings: { sdf: true, fontSize: 64, buffer: 6 },
      outlineWidth: 3,
      outlineColor: rgba(p.surface),
    };
    const pathProps = {
      getPath: (d: Route) => d.path,
      getColor: (d: Route) => d.color,
      getWidth: (d: Route) => d.width,
      widthUnits: 'pixels' as const,
      capRounded: true,
      jointRounded: true,
    };
    return [
      // Routes first: markers sit on top of their ends (and win the mouse there).
      // White casing so routes separate from roads of similar colour.
      new PathLayer({
        id: 'routes-casing',
        ...pathProps,
        data: routes.filter((r) => r.kind !== 'travel' || r.width > 2),
        getColor: rgba(p.surface, 230),
        getWidth: (d: Route) => d.width + 3,
      }),
      new PathLayer({
        id: 'routes-solid',
        ...pathProps,
        data: routes.filter((r) => r.kind === 'travel' || r.kind === 'decided'),
      }),
      new PathLayer({
        id: 'routes-dashed',
        ...pathProps,
        data: routes.filter((r) => r.kind === 'pending' || r.kind === 'preview'),
        // the proposal is drawn solid (it must read at a glance); only the "Changer d'équipe" preview is dashed
        getDashArray: (d: Route) => (d.kind === 'preview' ? [2.2, 1.6] : [0, 0]),
        dashJustified: true,
        extensions: dashExt,
        pickable: true,
      }),
      new PathLayer({
        id: 'routes-options',
        ...pathProps,
        data: routes.filter((r) => r.kind === 'option'),
        pickable: true,
      }),
      new IconLayer({
        id: 'incidents-restored',
        data: restored,
        getPosition: (d: Incident) => [d.lon, d.lat],
        getIcon: () => incidentIcon('restored', false),
        getSize: 9,
        sizeUnits: 'pixels',
        getColor: [255, 255, 255, 102], // 40 %
        pickable: true,
      }),
      new IconLayer({
        id: 'incidents',
        data: active,
        getPosition: (d: Incident) => [d.lon, d.lat],
        getIcon: (d: Incident) => incidentIcon(d.status, d.sensitive),
        getSize: (d: Incident) => incidentSize(d) * (d.id === focusInc ? 1.3 : 1) * sc,
        sizeUnits: 'pixels',
        pickable: true,
        updateTriggers: { getSize: [focusInc, sc] },
      }),
      new ScatterplotLayer({
        id: 'clusters',
        data: clusters,
        getPosition: (d: Cluster) => [d.lon, d.lat],
        getRadius: (d: Cluster) => clusterRadius(d) * sc,
        radiusUnits: 'pixels',
        updateTriggers: { getRadius: sc },
        stroked: true,
        lineWidthUnits: 'pixels',
        getLineWidth: (d: Cluster) => (d.sensitive ? 3.5 : 2),
        getFillColor: rgba(p.waiting),
        getLineColor: (d: Cluster) => (d.sensitive ? rgba(p.critical) : rgba(p.surface)),
        pickable: true,
      }),
      new IconLayer({
        id: 'cluster-sensitive',
        data: clusters.filter((c) => c.sensitive),
        getPosition: (d: Cluster) => [d.lon, d.lat],
        getPixelOffset: (d: Cluster) => [clusterRadius(d) * 0.75, -clusterRadius(d) * 0.75],
        getIcon: () => sensitiveBadgeIcon(),
        getSize: 13,
        sizeUnits: 'pixels',
      }),
      new ScatterplotLayer({
        id: 'pulses',
        data: pulseData,
        getPosition: (d) => [d.inc.lon, d.inc.lat],
        getRadius: (d) => incidentSize(d.inc) / 2 + d.age * 26,
        radiusUnits: 'pixels',
        filled: false,
        stroked: true,
        lineWidthUnits: 'pixels',
        getLineWidth: 2.5,
        getLineColor: (d) => rgba(d.inc.sensitive ? p.critical : p.waiting, Math.round(230 * (1 - d.age))),
        updateTriggers: { getRadius: realNow, getLineColor: realNow },
      }),
      new ScatterplotLayer({
        id: 'reinforcement-rings',
        data: meta.sites.filter((st) => highlightSites.includes(st.id)),
        getPosition: (d) => [d.lon, d.lat],
        getRadius: 22,
        radiusUnits: 'pixels',
        filled: false,
        stroked: true,
        lineWidthUnits: 'pixels',
        getLineWidth: 4,
        getLineColor: rgba(p.green),
      }),
      new IconLayer({
        id: 'teams',
        data: shownTeams,
        getPosition: (d: TeamView) => [d.lon, d.lat],
        getPixelOffset: (d: TeamView) => d.offset,
        getIcon: (d: TeamView) => teamIcon(d.status),
        getSize: (d: TeamView) => (d.id === focusRec?.teamId || d.id === previewTeamId ? 24 : 17) * sc,
        sizeUnits: 'pixels',
        pickable: true,
        updateTriggers: { getSize: [focusRec?.teamId, previewTeamId, sc] },
      }),
      // Team sites: a square holding the number of available teams (name on hover / close zoom).
      new IconLayer({
        id: 'sites',
        data: meta.sites,
        getPosition: (d) => [d.lon, d.lat],
        getIcon: () => siteIcon(),
        // Territory zoom: small squares without numbers (less clutter); full size with counts from SITE_COUNT_ZOOM.
        getSize: zoom < SITE_COUNT_ZOOM ? 11 : 22,
        updateTriggers: { getSize: zoom < SITE_COUNT_ZOOM },
        sizeUnits: 'pixels',
        pickable: true,
      }),
      new TextLayer({
        id: 'site-counts',
        data: zoom < SITE_COUNT_ZOOM ? [] : meta.sites,
        getPosition: (d) => [d.lon, d.lat],
        getText: (d) => String(siteAvail.get(d.name) ?? 0),
        getSize: 12,
        getColor: rgba(p.surface),
        fontFamily: 'Sora Variable, sans-serif',
        fontWeight: 700,
        characterSet: CHARSET,
        updateTriggers: { getText: siteAvailKey },
      }),
      new TextLayer({ id: 'labels-regular', data: placed.filter((l) => !l.bold), ...labelProps, fontFamily: 'Sora Variable, sans-serif', fontWeight: 500 }),
      new TextLayer({ id: 'labels-bold', data: placed.filter((l) => l.bold), ...labelProps, fontFamily: 'Sora Variable, sans-serif', fontWeight: 700 }),
      new TextLayer({
        id: 'cluster-count',
        data: clusters,
        getPosition: (d: Cluster) => [d.lon, d.lat],
        getText: (d: Cluster) => String(d.count),
        getSize: 14 * sc,
        getColor: rgba(p.text),
        fontFamily: 'Sora Variable, sans-serif',
        fontWeight: 700,
        characterSet: CHARSET,
      }),
      // Plan badges: the line number of each assignment, drawn as a pin label above its incident.
      new TextLayer({
        id: 'plan-badges',
        data: planBadges,
        getPosition: (d: { lon: number; lat: number }) => [d.lon, d.lat],
        getPixelOffset: [0, -26],
        getText: (d: { rank: number }) => String(d.rank),
        getSize: (d: { recId: string }) => (d.recId === focusRec?.id || d.recId === hoveredRecId ? 15 : 13),
        getColor: (d: { recId: string }) => (d.recId === focusRec?.id || d.recId === hoveredRecId ? rgba(p.surface) : ([...PLAN_RGB, 255] as RGBA)),
        background: true,
        getBackgroundColor: (d: { recId: string }) => (d.recId === focusRec?.id || d.recId === hoveredRecId ? ([...PLAN_RGB, 255] as RGBA) : rgba(p.surface)),
        getBorderColor: [...PLAN_RGB, 255] as RGBA,
        getBorderWidth: 2,
        backgroundPadding: [7, 3, 7, 3],
        backgroundBorderRadius: 11,
        fontFamily: 'Sora Variable, sans-serif',
        fontWeight: 800,
        characterSet: CHARSET,
        pickable: true,
        updateTriggers: {
          getSize: [focusRec?.id, hoveredRecId],
          getColor: [focusRec?.id, hoveredRecId],
          getBackgroundColor: [focusRec?.id, hoveredRecId],
        },
      }),
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, incidents, clusters, clusteredIds, teams, routes, focusRec, previewTeamId, placed, siteAvailKey, highlightSites, planBadges, hoveredRecId, zoom < DETAIL_ZOOM, zoom < SITE_COUNT_ZOOM, pulseCount ? realNow : 0]);

  /** The card for a picked object (incident, team, cluster, site), or null for routes and decorations. */
  const cardFor = (info: PickingInfo): HoverTarget | null => {
    const id = info.layer?.id;
    if (!info.object || !id) return null;
    if (id === 'clusters') return { kind: 'cluster', object: info.object as Cluster, x: info.x, y: info.y };
    if (id === 'sites') {
      const st = info.object as (typeof meta.sites)[number];
      return { kind: 'site', object: { name: st.name, available: siteAvail.get(st.name) ?? 0, teams: st.teams }, x: info.x, y: info.y };
    }
    if (id === 'teams') return { kind: 'team', object: info.object as Team, x: info.x, y: info.y };
    if (id === 'incidents' || id === 'incidents-restored') return { kind: 'incident', object: info.object as Incident, x: info.x, y: info.y };
    return null;
  };

  const onHover = (info: PickingInfo) => {
    const id = info.layer?.id;
    const card = cardFor(info);
    setHover(card);
    const rid =
      id === 'routes-dashed' || id === 'routes-options'
        ? (info.object as Route).recId
        : id === 'plan-badges'
          ? (info.object as { recId: string }).recId
        : card?.kind === 'team'
          ? recTeamIds.get(card.object.id)
          : card?.kind === 'incident'
            ? recIncIds.get(card.object.id)
            : undefined;
    if (rid) hoverRec(rid, 'map');
    else if (useStore.getState().hoverFrom === 'map') hoverRec(undefined);
  };

  // Clicking an incident, a team or a route of a recommendation puts it in focus; a cluster or a site
  // zooms in; anything with a card keeps its card pinned.
  const onClick = (info: PickingInfo) => {
    const id = info.layer?.id;
    const map = liveMap.current;
    if (!info.object || !id || !map) {
      setPinned(null);
      return;
    }
    const o = info.object as { lon?: number; lat?: number };
    const at: [number, number] = o.lon !== undefined && o.lat !== undefined ? [o.lon, o.lat] : ((info.coordinate ?? [0, 0]) as [number, number]);
    userMoved.current = true;
    if (id === 'clusters') {
      setPinned(null);
      setHover(null); // the cluster splits as the map zooms: its card would point at nothing
      map.flyTo({ center: at, zoom: Math.max(map.getZoom() + 2, CLUSTER_MAX_ZOOM + 0.3), duration: 700 });
      return;
    }
    if (id === 'sites') map.flyTo({ center: at, zoom: Math.max(map.getZoom(), 10), duration: 700 });
    const card = cardFor(info);
    if (card) setPinned({ target: card, lon: at[0], lat: at[1] });
    const rid =
      id === 'routes-dashed'
        ? (info.object as Route).recId
        : id === 'plan-badges'
          ? (info.object as { recId: string }).recId
          : id === 'teams'
          ? recTeamIds.get((info.object as Team).id)
          : id === 'incidents'
            ? recIncIds.get((info.object as Incident).id)
            : undefined;
    if (rid) useStore.getState().focusRec(rid);
  };

  const onStyleReady = useCallback(async (map: maplibregl.Map) => {
    liveMap.current = map;
    if (import.meta.env.DEV) (window as unknown as { __map?: unknown }).__map = map;
    try {
      await setupTerritory(map);
    } catch (err) {
      console.error('Fond de carte : chargement incomplet', err);
    }
    // deck.gl rasterises label fonts once: wait for the web fonts first.
    await Promise.all([document.fonts.load('700 16px "Sora Variable"'), document.fonts.load('500 16px "Sora Variable"')]).catch(() => {});
    setZoom(map.getZoom());
    setReady(true);
  }, []);

  const fit = useCallback((b: [[number, number], [number, number]]) => {
    liveMap.current?.fitBounds(b, { padding: fitPadding(liveMap.current), duration: 900 });
  }, []);

  // Until the user pans or zooms, keep the whole territory framed when the panel size changes
  // (window resize, display scaling): otherwise a short first layout leaves the map on Spain.
  const userMoved = useRef(false);

  // The pinned card follows the map; it is dropped on Esc and when the step changes (its data would be stale).
  useEffect(() => setPinned(null), [meta.mode === 'live' ? 0 : k]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setPinned(null);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  const pinnedAt = pinned && ready && liveMap.current ? liveMap.current.project([pinned.lon, pinned.lat]) : null;
  const shownCard: HoverTarget | null = hover ?? (pinned && pinnedAt ? ({ ...pinned.target, x: pinnedAt.x, y: pinnedAt.y } as HoverTarget) : null);
  const onResize = useCallback(() => {
    setViewTick((x) => x + 1);
    if (!userMoved.current) liveMap.current?.fitBounds(TERRITORY_BOUNDS, { padding: fitPadding(liveMap.current), duration: 0 });
  }, []);
  useEffect(() => {
    if (ready && !userMoved.current) liveMap.current?.fitBounds(TERRITORY_BOUNDS, { padding: fitPadding(liveMap.current), duration: 0 });
  }, [ready]);

  return (
    <div className="map-wrap">
      <MapGL
        mapLib={maplibregl}
        ref={mapRef}
        initialViewState={{ bounds: TERRITORY_BOUNDS, fitBoundsOptions: { padding: FIT_PADDING } }}
        mapStyle={BASEMAP}
        attributionControl={{ compact: true }}
        dragRotate={false}
        pitchWithRotate={false}
        touchPitch={false}
        minZoom={MIN_ZOOM}
        maxZoom={13}
        onMoveStart={(e) => {
          if ((e as { originalEvent?: unknown }).originalEvent) userMoved.current = true;
        }}
        onMove={(e) => {
          setZoom(Math.round(e.viewState.zoom * 20) / 20);
          setViewTick((x) => x + 1);
        }}
        // Basemap labels are known only once tiles are rendered: re-place site labels then.
        onIdle={() => setViewTick((x) => x + 1)}
        onMoveEnd={(e) => {
          setZoom(Math.round(e.target.getZoom() * 20) / 20);
          setViewTick((x) => x + 1);
        }}
        onResize={onResize}
        onError={(e) => console.warn('Carte :', e.error?.message ?? e)}
        style={{ position: 'absolute', inset: 0 }}
      >
        {ready && <DeckOverlay layers={layers} onHover={onHover} onClick={onClick} getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')} />}
        <NavigationControl position="top-right" showCompass={false} />
        <ScaleControl position="bottom-right" unit="metric" maxWidth={120} />
        <TerritorySetup onReady={onStyleReady} />
      </MapGL>

      <div className="map-tools segmented" role="group" aria-label="Vue de la carte">
        <button onClick={() => fit(TERRITORY_BOUNDS)}>Recentrer</button>
        <button onClick={() => fit(HG_BOUNDS)}>Haute-Garonne</button>
        <button className={saturation ? 'selected' : ''} aria-pressed={saturation} onClick={() => setSaturation(!saturation)}>
          Saturation
        </button>
      </div>

      {view === 'reference' && <div className="map-banner">Vue : stratégie de référence</div>}
      <MapLegend saturation={saturation} />
      {shownCard && <MapTooltip
          target={shownCard}
          snapshot={snap}
          nowMs={nowMs}
          pinned={!hover}
          box={liveMap.current ? { width: liveMap.current.getContainer().clientWidth, height: liveMap.current.getContainer().clientHeight } : undefined}
        />}
    </div>
  );
}
