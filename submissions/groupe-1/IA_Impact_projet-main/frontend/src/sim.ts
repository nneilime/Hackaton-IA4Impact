// Simulation d'un trajet : une horloge qui fait défiler les minutes de l'itinéraire et place le train entre
// ses arrêts. Hors de React exprès : la carte lit la position à chaque image (60 fois par seconde) sans faire
// redessiner l'interface ; le panneau, lui, ne se met à jour que quand la minute affichée change.
import { WALK, type Place, type Route } from "./api";

type Frame = { t: number; lon: number; lat: number; stopId: string; leg: number };

export type SimState =
  | { kind: "stopped"; stopId: string; leg: number } // à quai : départ, arrêt intermédiaire, correspondance
  | { kind: "moving"; fromId: string; toId: string; leg: number; walk: boolean }
  | { kind: "arrived"; stopId: string; leg: number };

export type SimSnapshot = { minute: number; playing: boolean; speed: number; state: SimState };

// Le trajet entier défile en ~2 min à la vitesse ×1, quelle que soit sa durée réelle
const BASE_SECONDS = 120;
export const SPEEDS = [1.5, 2, 4];

export class TrainSim {
  readonly total: number;
  readonly frames: Frame[];
  minute = 0;
  playing = true;
  speed = 1.5;
  follow = true; // la caméra suit le train tant que l'utilisateur ne fait pas glisser la carte
  private listeners = new Set<() => void>();
  private raf = 0;
  private last = 0;
  private snap: SimSnapshot;

  constructor(readonly route: Route, byId: Map<string, Place>) {
    // Une image clé par arrêt desservi ; la correspondance garde le train immobile pendant l'attente
    const frames: Frame[] = [];
    let start = 0;
    route.legs.forEach((leg, i) => {
      start += leg.wait_minutes;
      leg.stops.forEach((id, k) => {
        const p = byId.get(id);
        const t = start + (leg.times[k] ?? (k === 0 ? 0 : leg.minutes));
        if (p) frames.push({ t, lon: p.lon, lat: p.lat, stopId: id, leg: i });
      });
      start += leg.minutes;
    });
    this.frames = frames;
    this.total = Math.max(1, frames[frames.length - 1]?.t ?? 1);
    this.snap = this.makeSnap();
    this.tick = this.tick.bind(this);
  }

  // Position interpolée entre les deux arrêts qui encadrent la minute courante
  position(): [number, number] {
    return this.positionAt(this.minute);
  }

  // Même calcul à une minute quelconque du trajet (la fenêtre du train regarde un peu devant)
  positionAt(minute: number): [number, number] {
    const f = this.frames;
    if (!f.length) return [0, 0];
    const i = this.segment(minute);
    if (i < 0) return [f[0].lon, f[0].lat];
    if (i >= f.length - 1) return [f[f.length - 1].lon, f[f.length - 1].lat];
    const a = f[i], b = f[i + 1];
    const k = b.t > a.t ? (minute - a.t) / (b.t - a.t) : 0;
    return [a.lon + (b.lon - a.lon) * k, a.lat + (b.lat - a.lat) * k];
  }

  // Voie déjà parcourue, du train vers l'arrière (pour poser les voitures en courbe). Au départ, rien derrière :
  // on prolonge la première section vers l'arrière pour que la rame soit déjà dans l'axe.
  trail(): [number, number][] {
    const f = this.frames;
    const pts: [number, number][] = [this.position()];
    for (let i = this.segment(); i >= 0; i--) {
      const [x, y] = pts[pts.length - 1];
      if (f[i].lon !== x || f[i].lat !== y) pts.push([f[i].lon, f[i].lat]);
    }
    if (pts.length === 1) {
      const [x, y] = pts[0];
      const next = f.find((p) => p.lon !== x || p.lat !== y);
      if (next) pts.push([2 * x - next.lon, 2 * y - next.lat]);
    }
    return pts;
  }

  // Indice de la dernière image clé déjà atteinte
  private segment(minute = this.minute) {
    let i = -1;
    while (i + 1 < this.frames.length && this.frames[i + 1].t <= minute) i++;
    return i;
  }

  private state(): SimState {
    const f = this.frames;
    const i = Math.max(0, this.segment());
    if (this.minute >= this.total) return { kind: "arrived", stopId: f[f.length - 1].stopId, leg: f[f.length - 1].leg };
    const a = f[i], b = f[i + 1];
    // À quai si on est pile sur l'arrêt, ou si l'image suivante est la même gare (attente de correspondance)
    if (!b || a.stopId === b.stopId || Math.abs(this.minute - a.t) < 0.25) return { kind: "stopped", stopId: a.stopId, leg: b?.leg ?? a.leg };
    return { kind: "moving", fromId: a.stopId, toId: b.stopId, leg: b.leg, walk: this.route.legs[b.leg]?.mode === WALK };
  }

  private makeSnap(): SimSnapshot {
    return { minute: Math.floor(this.minute), playing: this.playing, speed: this.speed, state: this.state() };
  }

  private tick(now: number) {
    this.raf = requestAnimationFrame(this.tick);
    const dt = this.last ? Math.min(0.1, (now - this.last) / 1000) : 0;
    this.last = now;
    if (this.playing) {
      this.minute = Math.min(this.total, this.minute + (dt * this.speed * this.total) / BASE_SECONDS);
      if (this.minute >= this.total) this.playing = false;
    }
    this.emit();
  }

  private emit() {
    const s = this.makeSnap(), p = this.snap;
    const same = s.minute === p.minute && s.playing === p.playing && s.speed === p.speed && JSON.stringify(s.state) === JSON.stringify(p.state);
    if (!same) this.snap = s;
    this.listeners.forEach((l) => l());
  }

  // Abonnement : appelé à chaque image ; getSnapshot ne change que quand ce qui s'affiche change.
  // L'horloge ne tourne que tant que quelqu'un écoute (la carte ou le panneau) : rien à libérer à la main.
  subscribe = (l: () => void) => {
    this.listeners.add(l);
    if (!this.raf) {
      this.last = 0;
      this.raf = requestAnimationFrame(this.tick);
    }
    return () => {
      this.listeners.delete(l);
      if (!this.listeners.size) {
        cancelAnimationFrame(this.raf);
        this.raf = 0;
      }
    };
  };
  getSnapshot = () => this.snap;

  toggle() {
    if (this.minute >= this.total) this.minute = 0;
    this.playing = !this.playing;
    if (this.playing) this.follow = true; // relancer le trajet recadre sur le train
    this.emit();
  }
  setSpeed(s: number) {
    this.speed = s;
    this.emit();
  }
  seek(fraction: number) {
    this.minute = Math.max(0, Math.min(1, fraction)) * this.total;
    this.follow = true;
    this.emit();
  }
}
