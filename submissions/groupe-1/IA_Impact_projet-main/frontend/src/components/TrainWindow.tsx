import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";
import type { Place } from "../api";
import { useI18n } from "../i18n";
import type { TrainSim } from "../sim";
import { DISCOVERIES, creditOf, distanceKm, imageOf, type Credit, type Discovery, type Text } from "../data/discoveries";
import { SCENERY, sceneryCredit, sceneryImage } from "../data/scenery";
import { bearing, hasStreetView, streetShot } from "../streetview";
import { loadTrackside, photosNear } from "../commons";
import { FILLERS, fillerImage, zonePhotosOf } from "../data/filler";
import { MOBILE_QUERY } from "./MobileNav";

type Props = {
  sim: TrainSim;
  byId: Map<string, Place>;
  onOpenDiscovery: (d: Discovery) => void;
};

// `generic` : pas une photo de l'endroit exact, juste du coin — « region » (photo de la région) ou « illustration »
// (image générée) ; utilisées quand il n'y a rien de réel à montrer
type View = { id: string; src: string; title: Text; credit?: Credit; discovery?: Discovery; km: number; generic?: "region" | "illustration" };
// Une vue Street View prise le long du trajet : sa position, et l'ordre dans lequel elle a été prise
type Shot = View & { lat: number; lon: number; at: number };
// Une fenêtre du carrousel ; sans vue (le temps que les données arrivent), un hublot sur le ciel
type Car = { key: number; view?: View };

// Rayons autour du train : un lieu à visiter doit être tout près pour « se voir », un paysage peut être plus loin
const PLACE_KM = 8;
const PHOTO_KM = 10; // photos Commons géolocalisées
const STREET_KM = 5; // vues Street View
const SCENERY_KM = 15; // paysages choisis à la main (des endroits précis : Pont du Gard, étang de Thau…)

// Largeur visée d'une fenêtre, et du montant de caisse entre deux fenêtres (même valeur que .tws-track { gap })
const WINDOW_W = 250;
const WINDOW_W_MOBILE = 96;
const PILLAR = 22;
// À ×1, une fenêtre entière passe en tant de secondes
const SECONDS_PER_WINDOW = 3;

// Ce qu'on peut voir depuis la position du train : les lieux tout proches, en alternance avec le paysage réel
// (Street View, puis photos Commons prises dans le coin, puis paysages de la région choisis à la main)
function viewsAround(sim: TrainSim, shots: Shot[]): View[] {
  const [lon, lat] = sim.position();
  const here = { lon, lat };
  const places = DISCOVERIES.map((d) => ({ d, km: distanceKm(here, d) }))
    .filter((x) => x.km <= PLACE_KM)
    .sort((a, b) => a.km - b.km)
    .slice(0, 3)
    .map(({ d, km }): View => ({ id: d.id, src: imageOf(d), title: d.title, credit: creditOf(d), discovery: d, km }));
  const street = shots
    .map((v) => ({ ...v, km: distanceKm(here, v) }))
    .filter((v) => v.km <= STREET_KM)
    .sort((a, b) => b.at - a.at); // la plus récente d'abord : c'est ce qu'on a sous les yeux
  const photos = photosNear(lon, lat, PHOTO_KM)
    .slice(0, 10)
    .map(({ p, km }): View => ({ id: p.id, src: p.src, title: { en: p.title, fr: p.title }, credit: { author: p.author, license: p.license, source: p.source }, km }));
  const scenery = SCENERY.map((s) => ({ s, km: distanceKm(here, s) }))
    .filter((x) => x.km <= SCENERY_KM)
    .sort((a, b) => a.km - b.km)
    .map(({ s, km }): View => ({ id: s.id, src: sceneryImage(s), title: s.title, credit: sceneryCredit(s), km }));
  const land = [...street, ...photos, ...scenery];
  // Un lieu, un paysage, un lieu… : la fenêtre ne montre pas que des monuments
  const mixed: View[] = [];
  for (let i = 0; i < Math.max(places.length, land.length); i++) {
    if (places[i]) mixed.push(places[i]);
    if (land[i]) mixed.push(land[i]);
  }
  return mixed;
}

// Prochaine vue pour une fenêtre qui entre. Une vue réelle (lieu, photo de l'endroit) ne passe qu'une fois par
// trajet : une fois vue, elle ne revient plus, même si le train est encore dans le coin. Quand il n'y a plus rien de
// réel, une vue de la nature du coin (zones les plus proches) : d'abord les photos de la région pas encore montrées,
// puis l'illustration générée, puis la moins récemment montrée — jamais deux fois la même à l'écran.
function pickView(pool: View[], cars: Car[], seen: Map<string, number>, [lon, lat]: [number, number]): View {
  const onScreen = (id: string) => cars.some((c) => c.view?.id === id);
  const real = pool.find((v) => !seen.has(v.id) && !onScreen(v.id));
  if (real) return real;
  const zones = FILLERS.map((f) => ({ f, km: distanceKm({ lon, lat }, f) })).sort((a, b) => a.km - b.km);
  // Photos des deux zones les plus proches en alternance (le train est souvent entre deux paysages), puis les
  // illustrations générées, puis des zones un peu plus loin si tout est déjà à l'écran
  const photos = zones.slice(0, 2).map(({ f, km }) => zonePhotosOf(f).map((z): View => ({ ...z, title: f.title, km, generic: "region" })));
  const alternated = Array.from({ length: Math.max(0, ...photos.map((x) => x.length)) }, (_, i) => photos.map((x) => x[i])).flat().filter(Boolean);
  const generic = [
    ...alternated,
    ...zones.slice(0, 5).map(({ f, km }): View => ({ id: `fill-${f.id}`, src: fillerImage(f), title: f.title, km, generic: "illustration" })),
    ...zones.slice(2, 5).flatMap(({ f, km }) => zonePhotosOf(f).map((z): View => ({ ...z, title: f.title, km, generic: "region" }))),
  ].filter((v) => !onScreen(v.id));
  const fresh = generic.find((v) => !seen.has(v.id));
  if (fresh) return fresh;
  const last = (v: View) => seen.get(v.id) ?? -1;
  return generic.reduce((a, b) => (last(b) < last(a) ? b : a), generic[0] ?? { id: `fill-${FILLERS[0].id}`, src: fillerImage(FILLERS[0]), title: FILLERS[0].title, km: 0, generic: "illustration" });
}

// La paroi du wagon et sa rangée de fenêtres, qui défile tout entière vers la gauche comme si le train avançait :
// une fenêtre sort à gauche, une nouvelle entre à droite avec ce qu'il y a à voir à cet endroit. Le défilement suit
// la marche du train (démarre en douceur, plus vite en ×2 et ×4, s'arrête à quai). Animé hors de React.
export default function TrainWindows({ sim, byId, onOpenDiscovery }: Props) {
  const { t, locale } = useI18n();
  const snap = useSyncExternalStore(sim.subscribe, sim.getSnapshot);
  const root = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);

  // Largeur des fenêtres : un nombre entier en tient dans le bandeau
  const [geo, setGeo] = useState({ n: 1, w: WINDOW_W, width: WINDOW_W });
  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const width = el.clientWidth;
      if (!width) return;
      // Sur téléphone, de petits hublots : trois ou quatre côte à côte qui défilent, plutôt qu'une grande vitre
      const target = window.matchMedia(MOBILE_QUERY).matches ? WINDOW_W_MOBILE : WINDOW_W;
      const n = Math.max(1, Math.round((width + PILLAR) / (target + PILLAR)));
      const w = Math.floor((width - (n - 1) * PILLAR) / n);
      setGeo((g) => (g.n === n && g.w === w ? g : { n, w, width }));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const period = geo.w + PILLAR;

  const seen = useRef(new Map<string, number>()); // vues déjà montrées pendant ce trajet, et dans quel ordre
  const counter = useRef(0);
  const shots = useRef<Shot[]>([]);
  const fill = (from: Car[], size: number) => {
    const pool = viewsAround(sim, shots.current);
    const cars = [...from];
    while (cars.length < size) cars.push({ key: counter.current++, view: pickView(pool, cars, seen.current, sim.position()) });
    return cars;
  };
  const [cars, setCars] = useState<Car[]>(() => fill([], geo.n + 1));
  const latest = useRef({ cars, n: geo.n, byId });
  latest.current = { cars, n: geo.n, byId };
  // Ce qui vient d'entrer à l'écran est noté « vu » (ici plutôt qu'à la pioche, que React peut appeler deux fois)
  useEffect(() => {
    for (const c of cars) if (c.view && !seen.current.has(c.view.id)) seen.current.set(c.view.id, counter.current++);
  }, [cars]);

  // Nouveau trajet, ou plus de fenêtres : on recompose la rangée depuis la position du train
  const motion = useRef({ offset: 0, v: 0, pending: false });
  useEffect(() => {
    seen.current.clear();
    shots.current = [];
    motion.current.offset = 0;
    setCars(fill([], geo.n + 1));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sim, geo.n]);

  const paint = () => {
    if (track.current) track.current.style.transform = `translate3d(${-motion.current.offset}px,0,0)`;
  };

  useEffect(() => {
    const m = motion.current;
    const clock = { last: 0, check: 1, minute: sim.minute, shotAcc: 0, shooting: false, retryAt: 0 };
    let alive = true;
    loadTrackside();

    // Vue Street View à la position du train, côté droit de la voie (cap de la marche + 90°)
    const shoot = () => {
      clock.shooting = true;
      clock.shotAcc = 0;
      const pos = sim.position();
      const a = sim.positionAt(Math.max(0, sim.minute - 3));
      const b = sim.positionAt(Math.min(sim.total, sim.minute + 3));
      const here = { lon: pos[0], lat: pos[1] };
      const near = sim.frames.reduce((x, f) => (distanceKm(here, f) < distanceKm(here, x) ? f : x));
      const name = latest.current.byId.get(near.stopId)?.name ?? near.stopId;
      streetShot(pos, bearing(a, b) + 90).then((s) => {
        clock.shooting = false;
        if (!s) clock.retryAt = performance.now() + 4000; // rien par ici (ou refus de Google) : on patiente
        if (!alive || !s || shots.current.some((x) => x.id === `sv-${s.pano}`)) return;
        shots.current = [
          ...shots.current.slice(-19),
          {
            id: `sv-${s.pano}`, src: s.src, lat: s.lat, lon: s.lon, at: performance.now(), km: 0,
            title: { en: `Near ${name}`, fr: `Près de ${name}` },
            credit: { author: "Google Street View", license: s.date ?? "", source: `https://www.google.com/maps/@?api=1&map_action=pano&pano=${s.pano}` },
          },
        ];
      });
    };

    const unsubscribe = sim.subscribe(() => {
      const now = performance.now();
      const dt = clock.last ? Math.min(0.1, (now - clock.last) / 1000) : 0;
      clock.last = now;
      const moving = sim.getSnapshot().state.kind === "moving" && sim.playing;
      const { cars: c, n } = latest.current;

      // Saut dans la barre de progression : le train est ailleurs, toute la rangée est à refaire
      if (Math.abs(sim.minute - clock.minute) > Math.max(2, sim.total * 0.04)) {
        seen.current.clear();
        m.offset = 0;
        m.pending = false;
        setCars(fill([], n + 1));
      }
      clock.minute = sim.minute;

      // Défilement : vitesse lissée pour démarrer et freiner en douceur
      const target = moving ? (period / SECONDS_PER_WINDOW) * sim.speed : 0;
      m.v += (target - m.v) * Math.min(1, dt * 1.8);
      if (m.v < 0.5 && target === 0) m.v = 0;
      m.offset += m.v * dt;
      // La première fenêtre est sortie à gauche : elle quitte la rangée, une nouvelle entre à droite. Le décalage
      // n'est rattrapé qu'au rendu de la nouvelle rangée (effet plus bas), sinon tout reculerait d'un cran.
      if (m.offset >= period && !m.pending) {
        m.pending = true;
        const rest = c.slice(1);
        const view = pickView(viewsAround(sim, shots.current), rest, seen.current, sim.position());
        setCars([...rest, { key: counter.current++, view }]);
      }
      paint();

      // Street View (si une clé est configurée) : une vue réelle de plus à chaque fenêtre qui passe
      if (moving) clock.shotAcc += dt * sim.speed;
      if (hasStreetView && !clock.shooting && now >= clock.retryAt) {
        const [lon, lat] = sim.position();
        const none = !shots.current.some((v) => distanceKm({ lon, lat }, v) <= STREET_KM);
        if (none || clock.shotAcc >= SECONDS_PER_WINDOW * 0.8) shoot();
      }
    });
    return () => {
      alive = false;
      unsubscribe();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sim, period]);

  useLayoutEffect(() => {
    const m = motion.current;
    if (m.pending) {
      m.pending = false;
      m.offset = Math.max(0, m.offset - period);
    }
    paint();
  }, [cars, period]);

  const { state } = snap;
  const atPlatform = state.kind !== "moving" ? byId.get(state.stopId)?.name ?? state.stopId : null;
  // Le panneau de gare se pose sur la fenêtre au milieu du bandeau
  const signAt = Math.floor((motion.current.offset + geo.width / 2) / period);

  return (
    <div ref={root} className="tws" aria-label={t.simWindow}>
      <div ref={track} className="tws-track">
        {cars.map((car, i) => {
          const view = car.view;
          const d = view?.discovery;
          return (
            <figure key={car.key} className="tws-win" style={{ width: geo.w }}>
              <div className="tws-frame">
                <div className="tws-pane">
                  {view && <WindowImage view={view} alt={view.title[locale]} />}
                  {atPlatform && i === signAt && <div className="tws-sign">{atPlatform}</div>}
                  {d && !atPlatform && <span className="tws-badge">{t.simWindowPlace}</span>}
                  <div className="tws-glass" aria-hidden="true" />
                  {d && <button className="tws-open" onClick={() => onOpenDiscovery(d)} aria-label={d.title[locale]} />}
                </div>
                {/* Habillage intérieur du wagon : rideaux noués, cantonnière, tablette */}
                <span className="tws-curtain tws-curtain-l" aria-hidden="true" />
                <span className="tws-curtain tws-curtain-r" aria-hidden="true" />
                <span className="tws-valance" aria-hidden="true" />
              </div>
              <figcaption>
                {view && (
                  <>
                    <strong title={view.title[locale]}>{view.title[locale]}</strong>
                    <span className="tws-meta">
                      {d && <span className="sim-km">{t.simKm(view.km.toLocaleString(locale, { maximumFractionDigits: view.km < 10 ? 1 : 0 }))}</span>}
                      {view.generic ? (
                        <small>{view.generic === "region" ? t.simWindowRegion : t.simWindowIllustration}</small>
                      ) : (
                        view.credit && <small title={view.credit.source}>© {[view.credit.author, view.credit.license].filter(Boolean).join(" · ")}</small>
                      )}
                    </span>
                  </>
                )}
              </figcaption>
            </figure>
          );
        })}
      </div>
    </div>
  );
}

// La photo d'une fenêtre ; si elle ne se charge pas, un aplat ciel et champs
function WindowImage({ view, alt }: { view: View; alt: string }) {
  const [failed, setFailed] = useState(false);
  return failed ? (
    <span className="tws-img tws-img-empty" />
  ) : (
    <img className="tws-img" src={view.src} alt={alt} draggable={false} onError={() => setFailed(true)} />
  );
}
