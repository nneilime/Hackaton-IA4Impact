// Indice de fiabilité et avis d'enseignants d'un trajet — données de démonstration (mock), pas encore servies par l'API.
// Tout est tiré d'un générateur pseudo-aléatoire semé par le trajet lui-même : le même trajet donne toujours les
// mêmes chiffres et les mêmes avis, d'une recherche à l'autre. Les correspondances et les cars font baisser l'indice.
import { COACH_MODES, WALK, type Route } from "./api";
import { REVIEW_BANK, TEACHERS, slotOf } from "./data/teacher-reviews";
import type { Text } from "./data/discoveries";

export type Level = "high" | "medium" | "low";

export type Reliability = {
  score: number; // 0-100
  level: Level;
  punctuality: number; // % de trains à l'heure (moins de 5 min de retard)
  avgDelay: number; // minutes
  cancelRate: number; // % de suppressions
  missedTransfers: number; // % de correspondances manquées, 0 sans correspondance
  observed: number; // trajets observés sur 90 jours
};

export type Review = {
  author: string;
  role: Text; // niveau enseigné
  school: string; // ville de l'établissement
  rating: number; // 1-5
  monthsAgo: number;
  group: number; // élèves emmenés
  text: Text;
  train?: number; // heure du départ emprunté (minutes), quand les avis portent sur un horaire précis
};

// mulberry32 : petit générateur déterministe, suffisant pour de la démo
function rng(seed: string) {
  let a = 0;
  for (let i = 0; i < seed.length; i++) a = (Math.imul(a ^ seed.charCodeAt(i), 2654435761) + i) | 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const seedOf = (route: Route) => route.legs.map((l) => `${l.from_id}>${l.to_id}:${l.line}`).join("|");
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

// Horloge « HH:MM » <-> minutes depuis minuit
export const toClock = (m: number) => {
  const r = ((Math.round(m) % 1440) + 1440) % 1440;
  return `${String(Math.floor(r / 60)).padStart(2, "0")}:${String(r % 60).padStart(2, "0")}`;
};
export const fromClock = (v: string) => Number(v.slice(0, 2)) * 60 + Number(v.slice(3, 5));

// Plage de l'offre groupes scolaires : départs acceptés de 8 h à 16 h seulement
export const OFFER_START = 480, OFFER_END = 960;
export const OFFER_MIN = "08:00", OFFER_MAX = "16:00";

const RUSH = (m: number) => (m >= 420 && m < 540) || (m >= 1020 && m < 1140);

// Sans `minute`, l'indice moyen du trajet ; avec, celui du départ de cette heure-là (heures de pointe et soirée plus fragiles)
export function reliabilityOf(route: Route, minute?: number): Reliability {
  const r = rng("rel:" + seedOf(route) + (minute ?? ""));
  const peak = minute === undefined ? 0 : RUSH(minute) ? 7 : minute >= 1230 ? 4 : 0;
  const rides = route.legs.filter((l) => l.mode !== WALK);
  const coaches = rides.filter((l) => COACH_MODES.has(l.mode)).length;
  const tightest = Math.min(...route.legs.slice(1).map((l) => l.wait_minutes), Infinity);

  const punctuality = clamp(Math.round(93 - coaches * 4 - route.ride_minutes / 30 - r() * 9 - peak), 62, 98);
  const cancelRate = clamp(+(0.6 + r() * 2.4 + coaches * 0.8 + peak / 4).toFixed(1), 0.3, 8);
  const avgDelay = clamp(+(1.5 + (100 - punctuality) / 6 + r() * 2).toFixed(1), 1, 12);
  const missedTransfers = route.transfers ? clamp(Math.round(3 + route.transfers * 3 + (tightest < 15 ? 6 : 0) + r() * 5), 2, 30) : 0;

  const score = clamp(Math.round(punctuality - cancelRate * 2 - missedTransfers * 0.6 + 6), 30, 98);
  const level: Level = score >= 85 ? "high" : score >= 70 ? "medium" : "low";
  const observed = minute === undefined ? 180 + Math.floor(r() * 900) : 40 + Math.floor(r() * 50);
  return { score, level, punctuality, avgDelay, cancelRate, missedTransfers, observed };
}

export type Departure = { minute: number; arrival: number; rel: Reliability };

// Départs de la journée, limités à la plage de l'offre (8 h - 16 h) : la part des trains quotidiens du premier tronçon
// roulant qui tombe dans ces huit heures (sur une journée de service d'environ 16 h).
// Le moteur ne connaît pas les horaires réels : ce sont des heures de démonstration, stables pour un même trajet.
export function departuresOf(route: Route): Departure[] {
  const r = rng("dep:" + seedOf(route));
  const firstRide = route.legs.find((l) => l.mode !== WALK);
  const n = clamp(Math.round((firstRide?.trips_per_day ?? 8) / 2), 3, 12);
  const start = OFFER_START, end = OFFER_END, step = (end - start) / (n - 1);
  const minutes = Array.from({ length: n }, (_, i) => clamp(Math.round(start + i * step + (r() - 0.5) * step * 0.5), start, end));
  return [...new Set(minutes)].sort((a, b) => a - b).map((minute) => ({ minute, arrival: minute + route.minutes, rel: reliabilityOf(route, minute) }));
}

// Premier départ à partir de l'heure voulue, sinon le dernier de la journée
export const pickDeparture = (deps: Departure[], after: number) => deps.find((d) => d.minute >= after) ?? deps[deps.length - 1];

// Avec `minute`, les avis portent sur ce départ-là : notes calées sur son indice, et au moins deux avis propres à sa
// tranche horaire (train bondé à 8 h, calme à midi, lycéens l'après-midi…) — changer d'horaire change les avis.
export function reviewsOf(route: Route, rel: Reliability, minute?: number): Review[] {
  const r = rng("rev:" + seedOf(route) + (minute ?? ""));
  const pick = <T,>(xs: T[]) => xs[Math.floor(r() * xs.length)];
  const towns = [...new Set(route.legs.flatMap((l) => [l.from, l.to]))];
  const teachers = [...TEACHERS];
  const used = new Set<number>();
  const count = 3 + Math.floor(r() * 3);
  const slot = minute === undefined ? undefined : slotOf(minute);

  return Array.from({ length: count }, (_, k) => {
    // La note suit l'indice : un trajet fiable reçoit surtout des 4-5, un trajet fragile plus de 2-3
    const rating = clamp(Math.round(rel.score / 20 + (r() - 0.55) * 2.4), 1, 5);
    const fits = REVIEW_BANK.map((c, i) => ({ c, i })).filter(
      ({ c, i }) =>
        !used.has(i) && (!c.needsTransfer || route.transfers > 0) && (!c.direct || route.transfers === 0) && (!c.slot || c.slot === slot),
    );
    const inSlot = k < 2 && slot ? fits.filter(({ c }) => c.slot === slot) : [];
    const rated = fits.filter(({ c }) => c.rating.includes(rating));
    const pool = inSlot.length ? inSlot : rated.length ? rated : fits.length ? fits : REVIEW_BANK.map((c, i) => ({ c, i }));
    const { c, i } = pick(pool);
    used.add(i);
    const teacher = teachers.splice(Math.floor(r() * teachers.length), 1)[0];
    return {
      author: teacher.name,
      role: teacher.role,
      school: pick(towns),
      // Un avis propre à la tranche garde une note cohérente avec son texte
      rating: c.rating.includes(rating) ? rating : c.rating.reduce((b, x) => (Math.abs(x - rating) < Math.abs(b - rating) ? x : b)),
      monthsAgo: 1 + Math.floor(r() * 14),
      group: 12 + Math.floor(r() * 10) * 2,
      text: c.text,
      train: minute,
    };
  }).sort((a, b) => a.monthsAgo - b.monthsAgo);
}

// Retour : le dernier départ qui arrive avant l'heure limite, sans repartir avant d'être arrivé ; à défaut le premier possible
export const pickReturn = (deps: Departure[], notBefore: number, arriveBy: number) =>
  [...deps].reverse().find((d) => d.minute >= notBefore && d.arrival <= arriveBy) ?? deps.find((d) => d.minute >= notBefore) ?? deps[deps.length - 1];
