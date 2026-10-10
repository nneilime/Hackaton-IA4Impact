import { lazy, memo, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import maplibregl, { type GeoJSONSource, type LngLatLike, type Map as MlMap } from "maplibre-gl";
import { Protocol } from "pmtiles";
import { layers, namedFlavor } from "@protomaps/basemaps";
import { OCCITANIE, OCCITANIE_BOUNDS, OUTSIDE_MASK } from "../occitanie";
import { COACH_MODES, WALK, type Edge, type Place, type Route } from "../api";
import { useI18n } from "../i18n";
import { CATEGORIES, DISCOVERIES, DISCOVERIES_BY_STATION, imageOf, type Category, type Discovery } from "../data/discoveries";
import { CATEGORY_PATHS, CategoryIcon } from "./CategoryIcon";
import { DiscoveryImage } from "./Discovery";
import type { TrainSim } from "../sim";
import { createTrain3D } from "../train3d";
import { MOBILE_QUERY } from "./MobileNav";

// Intérieur du wagon en 3D, chargé seulement quand on monte à bord
const WagonInterior = lazy(() => import("./WagonInterior"));

type Props = {
  places: Place[];
  edges: Edge[];
  byId: Map<string, Place>;
  route: Route | null;
  // Départ / arrivée choisis avant tout itinéraire (« Partir de cette gare », « Y aller en train ») : déjà colorés
  fromId: string | null;
  toId: string | null;
  sim: TrainSim | null;
  // Bandes de l'écran cachées par l'interface (mobile : en-tête flottant en haut, panneau + navigation en bas) :
  // la carte cadre ce qu'elle montre dans ce qui reste visible
  inset?: { top: number; bottom: number };
  highlight: ReadonlySet<string>; // lieux recommandés (projet scolaire, assistant IA), mis en avant
  selected: string | null;
  onSelect: (id: string) => void;
  onPick: (which: "from" | "to", name: string) => void;
  onOpenDiscovery: (d: Discovery) => void;
};

// Moteur cartographique : MapLibre GL (rendu WebGL) sur un fond vectoriel de l'Occitanie seule, servi par le
// site (public/basemap, voir scripts/fetch-basemap.sh). Réseau, gares et itinéraire sont des couches de la
// carte, pas des éléments HTML : le GPU les dessine, et MapLibre gère seul le chevauchement des noms.
maplibregl.addProtocol("pmtiles", new Protocol().tile);

const NAVY = "#0f2149";
const RED = "#c90c0f";
const YELLOW = "#ffd500";
const RAIL = "#7d879c";
const WHITE = "#ffffff";

// Les gares apparaissent par ordre d'importance (fréquentation, puis lieu à découvrir à côté) à mesure qu'on zoome,
// plus petites quand on dézoome ; la taille dit aussi la fréquentation. Les noms se masquent : les couches sont
// empilées par importance, MapLibre place d'abord celles du dessus et cache le nom de toute gare qui chevaucherait
// une gare ou un nom déjà placé. Sur ordinateur, le tri reste léger : seules les petites gares attendent un peu de
// zoom, et les haltes sans lieu un peu plus. Sur téléphone l'écran est trop petit : la vue de toute la région ne
// montre presque plus rien, et les petites haltes sans lieu n'arrivent qu'une fois bien zoomé.
type Tier = "major" | "medium" | "minor";
const TIERS: Tier[] = ["minor", "medium", "major"]; // du dessous au dessus
const tierOf = (p: Place): Tier => (p.trips_per_day >= 60 ? "major" : p.trips_per_day >= 20 ? "medium" : "minor");
type Reveal = { icon: number; label: number }; // zooms d'apparition de la pastille et du nom
const REVEAL: Record<"desktop" | "mobile", Record<Tier, { place: Reveal; bare: Reveal }>> = {
  desktop: {
    major: { place: { icon: 0, label: 6 }, bare: { icon: 0, label: 6 } },
    medium: { place: { icon: 0, label: 10 }, bare: { icon: 7, label: 10 } },
    minor: { place: { icon: 7.5, label: 12 }, bare: { icon: 8.5, label: 12 } },
  },
  mobile: {
    major: { place: { icon: 6.5, label: 7.5 }, bare: { icon: 7.5, label: 8.5 } },
    medium: { place: { icon: 8, label: 10 }, bare: { icon: 9.5, label: 11 } },
    minor: { place: { icon: 9.5, label: 12 }, bare: { icon: 11, label: 12.5 } },
  },
};
// Paliers de zoom où l'affichage change (MapLibre n'accepte le zoom qu'en tête d'expression : un palier par seuil)
const STEPS = [...new Set(Object.values(REVEAL).flatMap((d) => Object.values(d).flatMap((t) => [t.place, t.bare]).flatMap((r) => [r.icon, r.label])))]
  .filter((z) => z > 0)
  .sort((a, b) => a - b);
const byZoom = (at: (z: number) => unknown) =>
  ["step", ["zoom"], at(0), ...STEPS.flatMap((z) => [z, at(z)])] as unknown as maplibregl.ExpressionSpecification;
const BADGE_PX: Record<Tier | "important", number> = { important: 30, major: 26, medium: 22, minor: 18 };
const TEXT_PX: Record<Tier | "important", number> = { important: 14, major: 13.5, medium: 12, minor: 11 };
// Échelle des pastilles selon le zoom : minuscules sur la vue de toute la région, pleine taille à partir du zoom 12
const SHRINK: [zoom: number, scale: number][] = [[6, 0.38], [9, 0.65], [12, 1]];
// Train 3D : rétrécit à chaque cran de dézoom, de TRAIN_MAX (zoom ≥ 14, en ville) à TRAIN_MIN (zoom 6, toute la
// région) — bornes qui gardent la rame lisible sans qu'elle mange l'écran
const TRAIN_ZOOM_OUT = 6;
const TRAIN_ZOOM_IN = 14;
const TRAIN_MIN = 1.4;
const TRAIN_MAX = 2;
const trainScale = (z: number, base: number) => {
  const t = Math.min(1, Math.max(0, (z - TRAIN_ZOOM_OUT) / (TRAIN_ZOOM_IN - TRAIN_ZOOM_OUT)));
  return base * (TRAIN_MIN + (TRAIN_MAX - TRAIN_MIN) * t);
};

// Pastilles de gare : dessinées une fois sur un canvas, une par état
const BADGE = 30; // taille de référence, réduite par icon-size
const BADGES = {
  default: { bg: NAVY, fg: WHITE, border: WHITE },
  start: { bg: YELLOW, fg: NAVY, border: WHITE },
  end: { bg: RED, fg: WHITE, border: WHITE },
  change: { bg: WHITE, fg: NAVY, border: NAVY },
  route: { bg: WHITE, fg: RED, border: RED },
};
type Badge = keyof typeof BADGES;
// Pictogramme « train » (Material Icons, Apache 2.0)
const TRAIN_PATH =
  "M12 2c-4 0-8 .5-8 4v9.5C4 17.43 5.57 19 7.5 19L6 20.5v.5h2.23l2-2H14l2 2h2v-.5L16.5 19c1.93 0 3.5-1.57 3.5-3.5V6c0-3.5-3.58-4-8-4zM7.5 17c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm3.5-7H6V6h5v4zm2 0V6h5v4h-5zm3.5 7c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z";

function badgeImage({ bg, fg, border }: (typeof BADGES)[Badge]) {
  const ratio = 2, pad = 4, size = (BADGE + pad * 2) * ratio;
  const ctx = Object.assign(document.createElement("canvas"), { width: size, height: size }).getContext("2d")!;
  ctx.scale(ratio, ratio);
  ctx.translate(pad, pad);
  ctx.shadowColor = "rgba(15, 33, 73, .45)";
  ctx.shadowBlur = 3;
  ctx.shadowOffsetY = 1;
  ctx.fillStyle = bg;
  ctx.beginPath();
  ctx.roundRect(0, 0, BADGE, BADGE, 8);
  ctx.fill();
  ctx.shadowColor = "transparent";
  ctx.strokeStyle = border;
  ctx.lineWidth = 2.3;
  ctx.beginPath();
  ctx.roundRect(1.15, 1.15, BADGE - 2.3, BADGE - 2.3, 7);
  ctx.stroke();
  const glyph = 19;
  ctx.translate((BADGE - glyph) / 2, (BADGE - glyph) / 2);
  ctx.scale(glyph / 24, glyph / 24);
  ctx.fillStyle = fg;
  ctx.fill(new Path2D(TRAIN_PATH));
  return { image: ctx.getImageData(0, 0, size, size), pixelRatio: ratio };
}

type State = "" | "is-dimmed" | "is-start" | "is-end" | "is-change" | "is-selected" | "is-on-route";
const badgeOf: Record<State, Badge> = {
  "": "default", "is-dimmed": "default", "is-start": "start", "is-end": "end", "is-selected": "end", "is-change": "change", "is-on-route": "route",
};

// Nom affiché : toujours pour les gares importantes (sauf les simples arrêts du trajet), sinon à partir de
// labelZoom ; pastille à partir de iconZoom (0 pour les gares du trajet, toujours visibles)
const nameField = () => byZoom((z) => ["case", ["any", ["get", "alwaysName"], [">=", z, ["get", "labelZoom"]]], ["get", "name"], ""]);
const iconField = () => byZoom((z) => ["case", [">=", z, ["get", "iconZoom"]], ["concat", "badge-", ["get", "badge"]], ""]);

const offsets = (size: number, scale: number) =>
  ["match", ["get", "badgePx"], ...Object.values(BADGE_PX).flatMap((px) => [px, ["literal", [((px * scale) / 2 + 3) / size, 0]]]), ["literal", [1, 0]]];

const fc = <G extends GeoJSON.Geometry>(features: GeoJSON.Feature<G>[]): GeoJSON.FeatureCollection<G> => ({ type: "FeatureCollection", features });
const line = (coords: [number, number][], properties: Record<string, unknown>): GeoJSON.Feature<GeoJSON.LineString> => ({
  type: "Feature", properties, geometry: { type: "LineString", coordinates: coords },
});
const lonLat = (p: Place): [number, number] => [p.lon, p.lat];

// Zone à 20 min à pied autour de chaque gare : 1,5 km à 75 m/min, la vitesse de marche du backend
const WALK_RADIUS_M = 20 * 75;
const WALK_DLAT = WALK_RADIUS_M / 111_320;
function walkZone(p: Place, properties: Record<string, unknown>): GeoJSON.Feature<GeoJSON.Polygon> {
  const n = 72, dLon = WALK_DLAT / Math.cos((p.lat * Math.PI) / 180);
  const ring = Array.from({ length: n + 1 }, (_, i) => {
    const a = (i / n) * 2 * Math.PI;
    return [p.lon + dLon * Math.cos(a), p.lat + WALK_DLAT * Math.sin(a)];
  });
  return { type: "Feature", properties, geometry: { type: "Polygon", coordinates: [ring] } };
}
// Point le plus au nord du cercle, où s'écrit « 20 min à pied »
const walkLabel = (p: Place, properties: Record<string, unknown>): GeoJSON.Feature<GeoJSON.Point> => ({
  type: "Feature", properties, geometry: { type: "Point", coordinates: [p.lon, p.lat + WALK_DLAT] },
});

const BASE = `${location.origin}${import.meta.env.BASE_URL}basemap`;
const STATION_LAYERS = ["lio-stops", ...TIERS.map((t) => `st-${t}`), "st-route", "st-important"];

function buildStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    glyphs: `${BASE}/fonts/{fontstack}/{range}.pbf`,
    sprite: `${BASE}/sprites/light`,
    sources: {
      protomaps: {
        type: "vector",
        url: `pmtiles://${BASE}/occitanie.pmtiles`,
        attribution: '<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap</a> · <a href="https://protomaps.com">Protomaps</a>',
      },
    },
    // Fond très épuré : les points d'intérêt et les bâtiments ne servent à rien ici et coûtent au rendu
    layers: layers("protomaps", namedFlavor("light"), { lang: "fr" }).filter((l) => !/^(pois|buildings)/.test(l.id)),
  };
}

function addOverlays(map: MlMap) {
  for (const [name, colors] of Object.entries(BADGES)) map.addImage(`badge-${name}`, ...Object.values(badgeImage(colors)) as [ImageData, { pixelRatio: number }]);
  const empty = fc([]);
  for (const id of ["walk-zones", "walk-labels", "network", "route", "stations", "stops"]) map.addSource(id, { type: "geojson", data: empty });
  map.addSource("mask", { type: "geojson", data: { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: OUTSIDE_MASK } } });

  // Hors région : grisé, frontière en pointillés
  map.addLayer({ id: "mask", type: "fill", source: "mask", paint: { "fill-color": "#e9ebf0", "fill-opacity": 0.85 } });
  map.addLayer({
    id: "border", type: "line", source: { type: "geojson", data: line(OCCITANIE, {}) },
    paint: { "line-color": NAVY, "line-width": 1.5, "line-opacity": 0.5, "line-dasharray": [4, 3.3] },
  });

  // Zones à 20 min à pied : un voile à peine teinté et un fin pointillé, sous le réseau. Elles n'apparaissent
  // qu'en zoomant (inutiles et illisibles sur la vue de la région) ; celle de la gare choisie ressort davantage.
  const fadeIn = (from: number, to: number, value: number | maplibregl.ExpressionSpecification) =>
    ["interpolate", ["linear"], ["zoom"], from, 0, to, value] as unknown as maplibregl.ExpressionSpecification;
  const zoneLevel = (focus: number, normal: number, dimmed: number) =>
    ["case", ["get", "focus"], focus, ["get", "dim"], dimmed, normal] as maplibregl.ExpressionSpecification;
  map.addLayer({ id: "walk-fill", type: "fill", source: "walk-zones", paint: { "fill-color": NAVY, "fill-opacity": fadeIn(8.5, 11, zoneLevel(0.06, 0.018, 0.008)) } });
  map.addLayer({
    id: "walk-edge", type: "line", source: "walk-zones",
    paint: {
      "line-color": NAVY, "line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.8, 14, 1.4],
      "line-dasharray": [3, 3], "line-opacity": fadeIn(8.5, 11, zoneLevel(0.6, 0.3, 0.12)),
    },
  });
  // « 20 min à pied » posé sur le haut du cercle, quand on est assez près pour le lire ; masqué s'il gêne un autre nom
  map.addLayer({
    id: "walk-label", type: "symbol", source: "walk-labels", minzoom: 12,
    layout: { "text-field": "", "text-font": ["Noto Sans Medium"], "text-size": 11, "text-letter-spacing": 0.04, "text-padding": 4 },
    paint: { "text-color": NAVY, "text-halo-color": WHITE, "text-halo-width": 1.4, "text-opacity": zoneLevel(0.85, 0.55, 0.3) },
  });

  // Voies : un trait gris bordé de blanc, comme les lignes ferroviaires de Google Maps. Les cars dessous, les trains par-dessus
  const round = { "line-cap": "round", "line-join": "round" } as const;
  map.addLayer({ id: "net-casing", type: "line", source: "network", filter: ["==", ["get", "kind"], "train"], layout: round, paint: { "line-color": WHITE, "line-width": 6, "line-opacity": 0.9 } });
  map.addLayer({ id: "net-lio", type: "line", source: "network", filter: ["==", ["get", "kind"], "lio"], layout: round, paint: { "line-color": NAVY, "line-width": 1, "line-opacity": 0.35 } });
  map.addLayer({ id: "net-coach", type: "line", source: "network", filter: ["==", ["get", "kind"], "coach"], layout: round, paint: { "line-color": NAVY, "line-width": 1.5, "line-opacity": 0.6, "line-dasharray": [1.3, 4] } });
  map.addLayer({ id: "net-train", type: "line", source: "network", filter: ["==", ["get", "kind"], "train"], layout: round, paint: { "line-color": RAIL, "line-width": 3, "line-opacity": 0.75 } });

  // Itinéraire : rouge (pointillés marine pour la marche) sur un liseré blanc
  map.addLayer({ id: "route-casing", type: "line", source: "route", layout: round, paint: { "line-color": WHITE, "line-width": 11 } });
  map.addLayer({ id: "route-ride", type: "line", source: "route", filter: ["!", ["get", "walk"]], layout: round, paint: { "line-color": RED, "line-width": 6 } });
  map.addLayer({ id: "route-walk", type: "line", source: "route", filter: ["get", "walk"], layout: round, paint: { "line-color": NAVY, "line-width": 4, "line-dasharray": [0, 2] } });

  const dim = ["case", ["get", "dim"], 0.45, 1] as maplibregl.ExpressionSpecification;
  // Arrêts de car (base complète seulement) : un simple point, ils sont des milliers
  map.addLayer({
    id: "lio-stops", type: "circle", source: "stops",
    paint: { "circle-radius": ["case", ["get", "on"], 4.5, 2], "circle-color": WHITE, "circle-stroke-color": NAVY, "circle-stroke-width": 1, "circle-stroke-opacity": ["case", ["get", "on"], 1, 0.5] },
  });
  const symbol = (id: string, filter: maplibregl.FilterSpecification, size: number, important: boolean): maplibregl.LayerSpecification => ({
    id, type: "symbol", source: "stations", filter,
    layout: {
      "icon-image": iconField(),
      "icon-size": ["interpolate", ["linear"], ["zoom"], ...SHRINK.flatMap(([z, k]) => [z, ["*", k / BADGE, ["get", "badgePx"]]])] as unknown as maplibregl.ExpressionSpecification,
      "icon-allow-overlap": true,
      "icon-ignore-placement": false,
      "text-field": nameField(),
      "text-font": ["Noto Sans Medium"],
      "text-size": size,
      "text-anchor": "left",
      // Nom à droite de la pastille, 3 px après son bord (en em de la taille du texte), qui suit la pastille quand elle rétrécit
      "text-offset": ["interpolate", ["linear"], ["zoom"], ...SHRINK.flatMap(([z, k]) => [z, offsets(size, k)])] as unknown as maplibregl.ExpressionSpecification,
      "text-optional": true,
      "text-allow-overlap": important,
      "symbol-sort-key": ["-", ["get", "trips"]],
    },
    paint: { "text-color": NAVY, "text-halo-color": WHITE, "text-halo-width": 1.6, "icon-opacity": dim, "text-opacity": dim },
  });
  const plain = ["!", ["get", "important"]] as maplibregl.ExpressionSpecification;
  for (const t of TIERS) map.addLayer(symbol(`st-${t}`, ["all", plain, ["==", ["get", "tier"], t]], TEXT_PX[t], false));
  map.addLayer(symbol("st-route", ["==", ["get", "state"], "is-on-route"], TEXT_PX.major, false));
  map.addLayer(symbol("st-important", ["all", ["get", "important"], ["!=", ["get", "state"], "is-on-route"]], TEXT_PX.important, true));

}

// Fiche de gare : contenu React rendu dans la bulle MapLibre
function StationCard({ card, onPick, onOpenDiscovery, close }: { card: Place; onPick: Props["onPick"]; onOpenDiscovery: Props["onOpenDiscovery"]; close: () => void }) {
  const { t, locale } = useI18n();
  const discoveries = DISCOVERIES_BY_STATION.get(card.id) ?? [];
  return (
    <div className="popup">
      <span className="popup-kind">
        {card.network === "lio" ? t.modes["Car liO"] : t.station} · {card.department}
      </span>
      <strong>{card.name}</strong>
      {card.trips_per_day > 0 && <span className="popup-freq">{t.trainsPerDay(card.trips_per_day)}</span>}
      {card.lines.length > 0 && (
        <ul className="popup-lines">
          {card.lines.slice(0, 4).map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}
      {discoveries.length > 0 && (
        <div className="popup-disc">
          <span>{t.discoverCount(discoveries.length)}</span>
          {discoveries.map((d) => (
            <button key={d.id} onClick={() => { onOpenDiscovery(d); close(); }}>
              <DiscoveryImage d={d} />
              <span className="popup-disc-name">
                {d.title[locale]}
                <span className={`popup-disc-cat cat-text-${d.category}`}>
                  <CategoryIcon category={d.category} />
                  {t.categories[d.category]}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
      <div className="popup-actions">
        <button onClick={() => { onPick("from", card.name); close(); }}>{t.leaveFrom}</button>
        <button onClick={() => { onPick("to", card.name); close(); }}>{t.goTo}</button>
      </div>
    </div>
  );
}

const NO_INSET = { top: 0, bottom: 0 };

export default memo(function MapView({ places, edges, byId, route, fromId, toId, sim, inset = NO_INSET, highlight, selected, onSelect, onPick, onOpenDiscovery }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<MlMap | null>(null);
  const [card, setCard] = useState<Place | null>(null);
  const [mobile, setMobile] = useState(() => window.matchMedia(MOBILE_QUERY).matches);
  useEffect(() => {
    const mq = window.matchMedia(MOBILE_QUERY);
    const sync = () => setMobile(mq.matches);
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  const { t, locale } = useI18n();
  const popup = useRef<maplibregl.Popup | null>(null);
  const popupBody = useMemo(() => document.createElement("div"), []);
  const pins = useRef(new Map<string, HTMLElement>());
  // Thèmes affichés sur la carte (tous par défaut) ; le choix est retenu d'une visite à l'autre
  const [shown, setShown] = useState<Set<Category>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("place-themes") ?? "null");
      if (Array.isArray(saved)) return new Set(saved.filter((c): c is Category => CATEGORIES.includes(c)));
    } catch {
      /* stockage indisponible */
    }
    return new Set(CATEGORIES);
  });
  const showAll = shown.size === CATEGORIES.length;
  const toggleTheme = (c: Category) =>
    setShown((prev) => {
      // Depuis « Tous », un clic isole le thème ; décocher le dernier thème revient à « Tous »
      const next = prev.size === CATEGORIES.length ? new Set([c]) : new Set(prev);
      if (prev.size !== CATEGORIES.length) next.has(c) ? next.delete(c) : next.add(c);
      return next.size ? next : new Set(CATEGORIES);
    });

  // La molette verticale fait défiler les pastilles horizontalement (sinon inaccessible à la souris)
  const filterBar = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = filterBar.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (el.scrollWidth <= el.clientWidth || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      e.preventDefault();
      el.scrollLeft += e.deltaY;
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("place-themes", JSON.stringify([...shown]));
    } catch {
      /* stockage indisponible */
    }
  }, [shown]);
  // Les gestionnaires d'événements de la carte sont posés une fois : ils lisent les données via des refs
  const latest = useRef({ byId, onSelect, onOpenDiscovery });
  latest.current = { byId, onSelect, onOpenDiscovery };
  // Marges de cadrage et décalage du centre qui tiennent compte des bandes cachées (lus au moment du mouvement)
  const insetRef = useRef(inset);
  insetRef.current = inset;
  // Sur mobile, le bandeau de simulation / d'idées flotte sur la carte : sa hauteur réelle (--sim-h, publiée par le
  // bandeau, change quand on le déplie) s'ajoute à ce qui est caché en bas
  const bottomInset = () => {
    const { bottom } = insetRef.current;
    return bottom ? bottom + 6 + (parseFloat(document.documentElement.style.getPropertyValue("--sim-h")) || 0) : 0;
  };
  const pad = (p: number) => ({ top: p + insetRef.current.top, bottom: p + bottomInset(), left: p, right: p });
  const offset = (): [number, number] => [0, (insetRef.current.top - bottomInset()) / 2];

  useEffect(() => {
    const m = new maplibregl.Map({
      container: box.current!,
      style: buildStyle(),
      bounds: OCCITANIE_BOUNDS,
      maxBounds: OCCITANIE_BOUNDS,
      minZoom: 6,
      maxZoom: 17,
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
    });
    m.touchZoomRotate.disableRotation();
    m.on("load", () => {
      addOverlays(m);
      setMap(m);
    });
    m.on("click", STATION_LAYERS, (e) => {
      const p = latest.current.byId.get(e.features?.[0]?.properties.id);
      if (!p) return;
      latest.current.onSelect(p.id);
      setCard(p);
    });
    m.on("mouseenter", STATION_LAYERS, () => (m.getCanvas().style.cursor = "pointer"));
    m.on("mouseleave", STATION_LAYERS, () => (m.getCanvas().style.cursor = ""));
    // Taille des épingles de lieux selon le zoom (variable CSS lue par .disc-pin), noms à partir du zoom 11
    const scalePins = () => {
      const z = m.getZoom();
      box.current!.style.setProperty("--pin", `${Math.round(Math.min(46, Math.max(24, 24 + (z - 6) * 3.7)))}px`);
      box.current!.classList.toggle("pins-named", z >= 11);
    };
    m.on("zoom", scalePins);
    scalePins();
    return () => m.remove();
  }, []);

  // Les bandes qui flottent sur la carte (en-tête, filtres, bandeau du bas sur mobile) en cachent les bords : la
  // limite de déplacement est élargie d'autant, pour pouvoir amener le sud ou le nord de la région dans la partie
  // visible. Elle est aussi toujours un peu plus grande que l'écran, sinon MapLibre bloque le dézoom dès que la
  // région ne remplit plus la vue (sur un téléphone en portrait, c'est avant même qu'elle y tienne en entier).
  // Une marge en pixels vaut moins de degrés quand on zoome : la limite se recalcule avec le zoom.
  useEffect(() => {
    if (!map) return;
    // Sur mobile, assez bas pour voir toute la région dans la partie laissée libre par les bandeaux
    map.setMinZoom(inset.top || inset.bottom ? 5 : 6);
    let last = "";
    const fit = () => {
      const deg = 360 / (512 * 2 ** map.getZoom()); // degrés de longitude par pixel
      const lat = deg * Math.cos((43.7 * Math.PI) / 180); // et de latitude, à hauteur de l'Occitanie
      const side = 40;
      const { clientWidth: W, clientHeight: H } = map.getContainer();
      const [[w, s], [e, n]] = OCCITANIE_BOUNDS;
      const top = insetRef.current.top, bottom = bottomInset();
      // Ce qui manque à la région pour couvrir l'écran (en pixels), réparti des deux côtés
      const spareX = Math.max(0, W - (e - w) / deg) / 2;
      const spareY = Math.max(0, H - top - bottom - (n - s) / lat) / 2;
      const next: [LngLatLike, LngLatLike] = [
        [w - (side + spareX) * deg, s - (bottom + side + spareY) * lat],
        [e + (side + spareX) * deg, n + (top + side + spareY) * lat],
      ];
      const key = JSON.stringify(next.map((p) => (p as number[]).map((v) => v.toFixed(3))));
      if (key !== last) map.setMaxBounds((last = key, next));
    };
    fit();
    map.on("zoom", fit);
    // Le bandeau du bas change de hauteur quand on le déplie (--sim-h)
    const watch = new MutationObserver(fit);
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ["style"] });
    return () => {
      map.off("zoom", fit);
      watch.disconnect();
    };
  }, [map, inset.top, inset.bottom]);

  // Une seule ligne par paire de gares et par type de service (A→B et B→A confondus)
  const network = useMemo(() => {
    const seen = new Set<string>();
    const out: GeoJSON.Feature<GeoJSON.LineString>[] = [];
    for (const e of edges) {
      const kind = e.mode === "Car liO" ? "lio" : COACH_MODES.has(e.mode) ? "coach" : "train";
      const key = [e.from_id, e.to_id].sort().join("-") + kind;
      const a = byId.get(e.from_id), b = byId.get(e.to_id);
      if (seen.has(key) || !a || !b) continue;
      seen.add(key);
      out.push(line([lonLat(a), lonLat(b)], { kind }));
    }
    return fc(out);
  }, [edges, byId]);

  useEffect(() => {
    (map?.getSource("network") as GeoJSONSource | undefined)?.setData(network);
  }, [map, network]);

  // Lieux à découvrir : une épingle avec la photo du lieu, nommée dans la langue de l'interface. Des marqueurs
  // HTML plutôt qu'une couche : ils ne sont que 32, et une photo ronde s'y fait en CSS.
  useEffect(() => {
    if (!map) return;
    const markers = DISCOVERIES.map((d) => {
      const pin = document.createElement("button");
      pin.className = `disc-pin cat-${d.category}`;
      pin.setAttribute("aria-label", d.title[locale]);
      const img = Object.assign(document.createElement("img"), { src: imageOf(d), alt: "", loading: "lazy" });
      // Pas de photo : pixel transparent, il reste un rond marine bordé de jaune
      img.onerror = () => (img.src = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==");
      const name = Object.assign(document.createElement("span"), { textContent: d.title[locale] });
      // Pastille du thème au coin de la photo
      const badge = document.createElement("i");
      badge.className = `disc-pin-cat cat-${d.category}`;
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 24 24");
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", CATEGORY_PATHS[d.category]);
      svg.append(path);
      badge.append(svg);
      pin.append(img, badge, name);
      pins.current.set(d.id, pin);
      pin.addEventListener("click", (e) => {
        e.stopPropagation();
        latest.current.onOpenDiscovery(d);
      });
      return new maplibregl.Marker({ element: pin, anchor: "bottom", offset: [0, -9] }).setLngLat([d.lon, d.lat]).addTo(map);
    });
    return () => markers.forEach((mk) => mk.remove());
  }, [map, locale]);

  // Lieux recommandés : épingle agrandie, bordée de rouge et nommée, les autres en retrait ; la carte se cadre
  // sur eux quand la liste change (pas quand on referme un trajet) et qu'aucun itinéraire n'est affiché
  useEffect(() => {
    if (!map) return;
    box.current?.classList.toggle("has-reco", highlight.size > 0);
    for (const [id, pin] of pins.current) pin.classList.toggle("is-reco", highlight.has(id));
  }, [map, locale, highlight]);

  // Filtre par thème : les épingles hors thème disparaissent, sauf un lieu recommandé (il reste visible)
  useEffect(() => {
    if (!map) return;
    for (const d of DISCOVERIES) pins.current.get(d.id)?.classList.toggle("is-filtered", !shown.has(d.category) && !highlight.has(d.id));
  }, [map, locale, shown, highlight]);
  useEffect(() => {
    if (!map || !highlight.size || route) return;
    const bounds = new maplibregl.LngLatBounds();
    for (const d of DISCOVERIES) if (highlight.has(d.id)) bounds.extend([d.lon, d.lat]);
    map.fitBounds(bounds, { padding: pad(window.innerWidth < 760 ? 40 : 90), maxZoom: 10, duration: 800 });
  }, [map, highlight, inset.bottom]);

  useEffect(() => {
    map?.setLayoutProperty("walk-label", "text-field", t.walkZone);
  }, [map, t]);

  // Épingles en retrait quand un itinéraire est affiché
  useEffect(() => {
    box.current?.classList.toggle("pins-dimmed", route !== null);
  }, [route]);

  // Réseau estompé quand un itinéraire est affiché
  useEffect(() => {
    if (!map) return;
    const dimmed = route !== null;
    map.setPaintProperty("net-casing", "line-opacity", dimmed ? 0.4 : 0.9);
    map.setPaintProperty("net-train", "line-opacity", dimmed ? 0.3 : 0.75);
    map.setPaintProperty("net-coach", "line-opacity", dimmed ? 0.3 : 0.6);
    map.setPaintProperty("net-lio", "line-opacity", dimmed ? 0.3 : 0.35);
  }, [map, route]);

  // Itinéraire + état de chaque gare (départ, arrivée, correspondance, desservie, estompée)
  useEffect(() => {
    if (!map) return;
    const legs = (route?.legs ?? []).map((l) =>
      line(l.stops.map((id) => byId.get(id)).filter((p): p is Place => !!p).map(lonLat), { walk: l.mode === WALK }),
    );
    (map.getSource("route") as GeoJSONSource).setData(fc(legs));

    const onRoute = new Set(route?.legs.flatMap((l) => l.stops) ?? []);
    const changes = new Set(route?.legs.slice(1).map((l) => l.from_id) ?? []);
    // Sans itinéraire, les extrémités déjà choisies prennent leurs couleurs de départ (jaune) et d'arrivée (rouge)
    const startId = route ? route.legs[0]?.from_id : fromId;
    const endId = route ? route.legs[route.legs.length - 1]?.to_id : toId;
    const stations: GeoJSON.Feature<GeoJSON.Point>[] = [];
    const stops: GeoJSON.Feature<GeoJSON.Point>[] = [];
    const zones: GeoJSON.Feature<GeoJSON.Polygon>[] = [];
    const zoneLabels: GeoJSON.Feature<GeoJSON.Point>[] = [];
    for (const p of places) {
      const geometry: GeoJSON.Point = { type: "Point", coordinates: lonLat(p) };
      if (p.network === "lio") {
        stops.push({ type: "Feature", geometry, properties: { id: p.id, on: onRoute.has(p.id) } });
        continue;
      }
      const tier = tierOf(p);
      const state: State =
        p.id === startId ? "is-start" : p.id === endId ? "is-end" : changes.has(p.id) ? "is-change"
          : p.id === selected ? "is-selected" : onRoute.has(p.id) ? "is-on-route" : route ? "is-dimmed" : "";
      const important = state !== "" && state !== "is-dimmed";
      const big = important && state !== "is-on-route";
      const zone = { focus: big, dim: state === "is-dimmed" };
      const reveal = REVEAL[mobile ? "mobile" : "desktop"][tier][DISCOVERIES_BY_STATION.has(p.id) ? "place" : "bare"];
      zones.push(walkZone(p, zone));
      zoneLabels.push(walkLabel(p, zone));
      stations.push({
        type: "Feature",
        geometry,
        properties: {
          id: p.id, name: p.name, tier, state, important, trips: p.trips_per_day,
          badge: badgeOf[state], badgePx: big ? BADGE_PX.important : BADGE_PX[tier],
          dim: state === "is-dimmed", alwaysName: big, iconZoom: important ? 0 : reveal.icon, labelZoom: reveal.label,
        },
      });
    }
    (map.getSource("stations") as GeoJSONSource).setData(fc(stations));
    (map.getSource("stops") as GeoJSONSource).setData(fc(stops));
    (map.getSource("walk-zones") as GeoJSONSource).setData(fc(zones));
    (map.getSource("walk-labels") as GeoJSONSource).setData(fc(zoneLabels));
  }, [map, places, byId, route, selected, fromId, toId, mobile]);

  // Recadre la carte sur l'itinéraire, vole vers le lieu sélectionné, ou recule autour de lui quand on le quitte
  const lastSelected = useRef<string | null>(null);
  useEffect(() => {
    if (!map) return;
    const previous = lastSelected.current;
    lastSelected.current = selected;
    if (selected) {
      const p = byId.get(selected);
      if (p) map.flyTo({ center: lonLat(p), zoom: Math.max(map.getZoom(), 12), offset: offset(), duration: 800 });
    } else if (!route && previous) {
      const p = byId.get(previous);
      if (p) map.flyTo({ center: lonLat(p), zoom: Math.min(map.getZoom(), 9), offset: offset(), duration: 800 });
    } else if (route && route.legs.length) {
      const bounds = new maplibregl.LngLatBounds();
      for (const l of route.legs) for (const id of l.stops) {
        const p = byId.get(id);
        if (p) bounds.extend(lonLat(p));
      }
      if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: pad(window.innerWidth < 760 ? 44 : 60), duration: 800 });
    }
    // Le panneau du bas qui change de cran recadre aussi : le trajet reste entier dans la partie visible
  }, [map, route, selected, byId, inset.bottom]);

  const [wagon, setWagon] = useState(false);
  useEffect(() => {
    if (!sim) setWagon(false);
  }, [sim]);

  // Train simulé : un marqueur HTML (au-dessus des épingles de lieux, qui sont elles aussi en HTML), déplacé à
  // chaque image ; la caméra le suit jusqu'à ce qu'on fasse glisser la carte
  useEffect(() => {
    if (!map || !sim) return;
    // Rame qui suit le zoom entre deux bornes, un peu plus petite sur téléphone (elle y couvre vite la carte)
    const base = window.matchMedia(MOBILE_QUERY).matches ? 0.8 : 1;
    let scale = trainScale(map.getZoom(), base);
    const train = createTrain3D(scale, t.wagonDoor);
    const marker = new maplibregl.Marker({ element: train.el }).setLngLat(sim.position()).addTo(map);
    // Un clic sur la rame fait apparaître une porte au-dessus ; un clic ailleurs la range ; la porte fait monter à bord
    let doorOn = false;
    const clickTrain = (e: maplibregl.MapMouseEvent) => {
      const { clientX, clientY } = e.originalEvent;
      doorOn = train.hit(clientX, clientY) ? !doorOn : false;
      train.showDoor(doorOn);
    };
    const hoverTrain = (e: maplibregl.MapMouseEvent) => {
      map.getCanvas().style.cursor = train.hit(e.originalEvent.clientX, e.originalEvent.clientY) ? "pointer" : "";
    };
    map.on("click", clickTrain);
    map.on("mousemove", hoverTrain);
    train.onDoor = () => {
      doorOn = false;
      train.showDoor(false);
      setWagon(true);
    };
    map.flyTo({ center: sim.position(), zoom: Math.max(map.getZoom(), 10), offset: offset(), duration: 900 });
    let flying = true;
    const landed = () => (flying = false);
    map.once("moveend", landed);
    // Doigt ou souris posé sur la carte : on ne recentre plus (chaque easeTo couperait le geste avant qu'il démarre),
    // et dès que la carte bouge sous la main, la caméra lâche le train — jusqu'à « lecture » ou un saut dans le trajet
    let holding = false;
    const hold = () => (holding = true);
    const release = () => (holding = false);
    const canvas = map.getCanvasContainer();
    canvas.addEventListener("pointerdown", hold);
    window.addEventListener("pointerup", release);
    window.addEventListener("pointercancel", release);
    const stopFollow = (e: { originalEvent?: unknown }) => {
      if (e.originalEvent) sim.follow = false;
    };
    map.on("dragstart", stopFollow);
    map.on("zoomstart", stopFollow);
    let lastFollow = 0;
    let lastPos: [number, number] | null = null;
    const draw = () => {
      const pos = sim.position();
      marker.setLngLat(pos);
      scale = trainScale(map.getZoom(), base);
      train.setScale(scale);
      const reach = 400 * scale; // bord du canvas affiché, en pixels écran
      // Voie parcourue projetée à l'écran, relative au train : la rame s'y plie voiture par voiture.
      // Le canvas (400 px, moins sur téléphone) suffit largement à couvrir les deux voitures.
      const o = map.project(pos);
      const track: [number, number][] = [];
      let run = 0;
      for (const ll of sim.trail()) {
        const p = map.project(ll);
        let pt: [number, number] = [p.x - o.x, p.y - o.y];
        const last = track[track.length - 1];
        if (last) {
          const len = Math.hypot(pt[0] - last[0], pt[1] - last[1]);
          // Section coupée à 400 px : un point très loin passerait au-delà de l'horizon de la caméra 3D
          if (run + len > reach) pt = [last[0] + ((pt[0] - last[0]) * (reach - run)) / len, last[1] + ((pt[1] - last[1]) * (reach - run)) / len];
          run += len;
        }
        track.push(pt);
        if (run >= reach) break;
      }
      train.setTrack(track);
      const { state } = sim.getSnapshot();
      train.setMode(state.kind === "moving" && sim.playing ? "moving" : state.kind === "arrived" ? "arrived" : "stopped", sim.speed);
      train.frame(performance.now());
      return pos;
    };
    // Train à l'arrêt : le simulateur ne notifie plus, c'est le zoom qui redessine la rame à sa nouvelle taille
    map.on("zoom", draw);
    const unsubscribe = sim.subscribe(() => {
      const pos = draw();
      // Recentrer ~10 fois par seconde suffit et laisse la carte respirer. Train immobile (pause, quai,
      // arrivée) : on ne recentre plus, sinon chaque easeTo couperait le glisser et le zoom de l'utilisateur
      const now = performance.now();
      const moved = !lastPos || pos[0] !== lastPos[0] || pos[1] !== lastPos[1];
      if (sim.follow && !flying && !holding && moved && now - lastFollow > 100) {
        lastFollow = now;
        lastPos = pos;
        map.easeTo({ center: pos, offset: offset(), duration: 120, easing: (k) => k });
      }
    });
    return () => {
      unsubscribe();
      map.off("zoom", draw);
      map.off("dragstart", stopFollow);
      map.off("zoomstart", stopFollow);
      canvas.removeEventListener("pointerdown", hold);
      window.removeEventListener("pointerup", release);
      window.removeEventListener("pointercancel", release);
      map.off("moveend", landed);
      map.off("click", clickTrain);
      map.off("mousemove", hoverTrain);
      map.getCanvas().style.cursor = "";
      marker.remove();
      train.dispose();
    };
  }, [map, sim]);

  // Une seule fiche partagée, ouverte sur la gare cliquée
  useEffect(() => {
    popup.current?.remove();
    popup.current = null;
    if (!map || !card) return;
    const p = new maplibregl.Popup({ offset: card.network === "lio" ? 6 : 16, className: "station-card", maxWidth: "280px" })
      .setLngLat(lonLat(card) as LngLatLike)
      .setDOMContent(popupBody)
      .addTo(map);
    p.on("close", () => setCard((c) => (c === card ? null : c)));
    popup.current = p;
  }, [map, card, popupBody]);

  return (
    <div className="map">
      <div ref={box} className="map-canvas" />
      <div ref={filterBar} className="theme-filter" role="group" aria-label={t.themeFilter} style={inset.top ? { top: inset.top + 8 } : undefined}>
        <button className={showAll ? "is-on" : ""} aria-pressed={showAll} onClick={() => setShown(new Set(CATEGORIES))}>
          {t.allThemes}
        </button>
        {CATEGORIES.map((c) => {
          const on = !showAll && shown.has(c);
          return (
            <button key={c} className={`cat-chip-${c}${on ? " is-on" : ""}`} aria-pressed={on} onClick={() => toggleTheme(c)}>
              <CategoryIcon category={c} />
              {t.categories[c]}
            </button>
          );
        })}
      </div>
      {wagon && sim && createPortal(
        <Suspense fallback={null}>
          <WagonInterior sim={sim} byId={byId} onClose={() => setWagon(false)} />
        </Suspense>,
        document.body,
      )}
      {card && createPortal(<StationCard card={card} onPick={onPick} onOpenDiscovery={onOpenDiscovery} close={() => setCard(null)} />, popupBody)}
    </div>
  );
});
