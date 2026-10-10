// Projet de sortie scolaire — repris de la branche codex/lio-ux-v1 (Aymeric) : le formulaire « Votre projet »
// et la recherche d'idées de sorties (aller-retour ou aller simple). Les libellés vivent dans i18n.tsx (clés ci-dessous).
import { api, ApiError, type Route } from "./api";
import { CATEGORIES, DISCOVERIES, type Category, type Discovery } from "./data/discoveries";
import { OFFER_MAX, OFFER_MIN, departuresOf, fromClock, pickDeparture, pickReturn } from "./reliability";

export type Level = "primary" | "middle" | "high";
// Thème pédagogique = catégorie de lieu (la même que les filtres de la carte), ou tous
export type Theme = Category | "all";

export type TripType = "round" | "oneway";

export type SchoolProject = {
  establishment: string; origin: string; level: Level; classIndex: number;
  theme: Theme; students: number; adults: number; date: string;
  tripType: TripType; departure: string; returnBy: string; // returnBy ignoré en aller simple
};
export const INITIAL_PROJECT: SchoolProject = {
  establishment: "Lycée Bellevue · Toulouse", origin: "Toulouse Matabiau", level: "high", classIndex: 0,
  theme: "heritage", students: 30, adults: 3, date: "2026-11-05", tripType: "round", departure: "09:00", returnBy: "16:00",
};
export const LEVELS: Level[] = ["primary", "middle", "high"];
export const THEMES: Theme[] = [...CATEGORIES, "all"];
export const TRIP_TYPES: TripType[] = ["round", "oneway"];
export type Proposal = { discovery: Discovery; outbound: Route; inbound: Route | null; project: SchoolProject }; // inbound null : aller simple // le projet sert au créneau et à la pré-réservation
// Ce qu'on pré-réserve : une idée de sortie (projet connu, formulaire prérempli) ou un trajet trouvé depuis la carte
// (pas de projet : le formulaire demande en plus le groupe ; visit = le lieu choisi sur sa fiche, s'il y en a un)
export type Booking = { outbound: Route; inbound: Route | null; visit: Discovery | null; project: SchoolProject | null };
export type SchoolError = "required" | "counts" | "tooMany" | "tooFew" | "times" | "hours";

const FEATURED = ["musee-lautrec", "cite-carcassonne", "chateau-foix"];
function candidates(theme: Theme): Discovery[] {
  const priority = (d: Discovery) => (FEATURED.includes(d.id) ? FEATURED.indexOf(d.id) : 10);
  return DISCOVERIES.filter((d) => theme === "all" || d.category === theme).sort((a, b) => priority(a) - priority(b));
}

export const travellers = (p: SchoolProject) => p.students + p.adults;

export function validateProject(p: SchoolProject): SchoolError | null {
  const round = p.tripType === "round";
  if (!p.establishment.trim() || !p.origin.trim() || !p.date || !p.departure || (round && !p.returnBy)) return "required";
  if (!Number.isInteger(p.students) || !Number.isInteger(p.adults) || p.students < 1 || p.adults < 1) return "counts";
  if (travellers(p) > 50) return "tooMany";
  if (travellers(p) < 6) return "tooFew";
  if (p.departure < OFFER_MIN || p.departure > OFFER_MAX || (round && (p.returnBy < OFFER_MIN || p.returnBy > OFFER_MAX))) return "hours";
  if (round && p.departure >= p.returnBy) return "times";
  return null;
}

const MAX_IDEAS = 8;
const clock = (v: string) => Number(v.slice(0, 2)) * 60 + Number(v.slice(3));

// /route une fois dans chaque sens, 15 min de marge de correspondance. Le moteur ne connaît ni la date ni l'effectif :
// garder une sortie dont l'aller + le retour tiennent dans le créneau est une condition nécessaire, pas une validation.
export async function searchSchoolTrips(project: SchoolProject, places: Map<string, { name: string }>, signal: AbortSignal) {
  const results: Proposal[] = [];
  const seen = new Set<string>();
  for (const discovery of candidates(project.theme)) {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    const place = places.get(discovery.stationId);
    if (!place || seen.has(discovery.stationId)) continue;
    seen.add(discovery.stationId);
    try {
      const round = project.tripType === "round";
      const [outbound, inbound] = await Promise.all([
        api.schoolRoute(project.origin, place.name, signal),
        round ? api.schoolRoute(place.name, project.origin, signal) : null,
      ]);
      if (inbound && outbound.minutes + inbound.minutes >= clock(project.returnBy) - clock(project.departure)) continue;
      results.push({ discovery, outbound, inbound, project });
      if (results.length === MAX_IDEAS) break;
    } catch (e) {
      if (signal.aborted) throw e;
      if (!(e instanceof ApiError) || e.code === "network" || e.code === "unknown_place") throw e;
    }
  }
  return results;
}

// Heures proposées par défaut : l'aller est le premier départ après l'heure du projet, le retour le dernier qui
// rentre avant l'heure limite en laissant au moins une heure sur place (pas de retour en aller simple)
export function scheduleOf(p: Proposal) {
  const out = pickDeparture(departuresOf(p.outbound), fromClock(p.project.departure));
  const back = p.inbound && pickReturn(departuresOf(p.inbound), out.arrival + 60, fromClock(p.project.returnBy));
  return { out, back };
}
