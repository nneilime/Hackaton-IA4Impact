// Client du backend FastAPI. En dev, Vite relaie /api vers uvicorn (voir vite.config.ts) ;
// en prod, VITE_API_URL pointe vers l'API déployée.
const BASE = import.meta.env.VITE_API_URL ?? "/api";

export type Place = {
  id: string;
  name: string;
  lat: number;
  lon: number;
  department: string;
  commune: string;
  network: "sncf" | "lio";
  trips_per_day: number; // passages par jour (jour de référence), sert à la taille de l'icône
  lines: string[]; // lignes qui s'y arrêtent, les plus fréquentes d'abord
};
export type Edge = { from_id: string; to_id: string; mode: string; network: string; minutes: number };

// Un leg = un trajet direct (même train ou même car), stops = toutes les gares desservies, extrémités comprises
export type Leg = {
  mode: string;
  network: string; // réseau liO (« liO 34 »), vide pour la SNCF et la marche
  line: string;
  from: string;
  to: string;
  from_id: string;
  to_id: string;
  minutes: number;
  wait_minutes: number; // changement + attente estimée avant ce leg (0 pour le premier)
  stops: string[];
  times: number[]; // minutes depuis le départ du leg, à chaque arrêt de `stops`
  trips_per_day: number | null; // null pour la marche
};
export type Route = {
  from: string;
  to: string;
  minutes: number;
  ride_minutes: number;
  access_minutes: number; // pour rejoindre le premier arrêt quand on a demandé une ville
  egress_minutes: number;
  transfers: number;
  legs: Leg[];
};
export const WALK = "Marche";
export const COACH_MODES = new Set(["Car TER", "Car liO", "Car à réservation"]);
export type ErrorCode = "unknown_place" | "no_route" | "same_place" | "network";

export class ApiError extends Error {
  constructor(public code: ErrorCode) {
    super(code);
  }
}

async function get<T>(path: string, params?: URLSearchParams, signal?: AbortSignal): Promise<T> {
  const qs = params ? "?" + params : "";
  let res: Response;
  try {
    res = await fetch(BASE + path + qs, { signal });
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new ApiError("network");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(body?.detail?.code ?? "network");
  return body as T;
}

// Trajets qu'un groupe scolaire peut pré-réserver (TER seulement, marges de 15 min) : ceux sortis de schoolRoute
const GROUP_OK = new WeakSet<Route>();
export const isGroupRoute = (r: Route) => GROUP_OK.has(r);

// Assistant (POST /chat) : sa réponse, et ce qu'il demande au site d'afficher
export type ChatTurn = { role: "user" | "assistant"; content: string };
export type CatalogPlace = { id: string; title: string; category: string; station: string; summary: string };
export type ChatAction =
  | { type: "route"; from: string; to: string }
  | { type: "places"; items: { id: string; reason: string }[] };
export type ChatError = "chat_unavailable" | "chat_rate_limit" | "network";
export class ChatFailure extends Error {
  constructor(public code: ChatError) {
    super(code);
  }
}

async function chat(messages: ChatTurn[], catalog: CatalogPlace[]) {
  let res: Response;
  try {
    res = await fetch(BASE + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, catalog }),
    });
  } catch {
    throw new ChatFailure("network");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ChatFailure(body?.detail?.code === "chat_rate_limit" ? "chat_rate_limit" : res.status === 503 ? "chat_unavailable" : "network");
  return body as { reply: string; actions: ChatAction[] };
}

// Dictée (POST /transcribe) : l'enregistrement part tel quel, le texte revient pour être relu avant envoi
export type DictationError = ChatError | "audio_empty" | "audio_too_large" | "audio_format";
export class DictationFailure extends Error {
  constructor(public code: DictationError) {
    super(code);
  }
}
const DICTATION_CODES: DictationError[] = ["chat_unavailable", "chat_rate_limit", "audio_empty", "audio_too_large", "audio_format"];

async function transcribe(audio: Blob) {
  let res: Response;
  try {
    res = await fetch(BASE + "/transcribe", {
      method: "POST",
      // Sans paramètre de codec : le serveur ne regarde que le type principal
      headers: { "Content-Type": audio.type.split(";")[0] || "audio/webm" },
      body: audio,
    });
  } catch {
    throw new DictationFailure("network");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const code = body?.detail?.code;
    throw new DictationFailure(DICTATION_CODES.includes(code) ? code : res.status === 503 ? "chat_unavailable" : "network");
  }
  return (body as { text: string }).text;
}

export const api = {
  chat,
  transcribe,
  places: () => get<{ places: Place[] }>("/places").then((r) => r.places),
  network: () => get<{ edges: Edge[] }>("/network").then((r) => r.edges),
  // Sortie scolaire : 15 min de marge aux correspondances, et jamais de TGV, d'Intercités ni de car (même avec la base complète)
  schoolRoute: async (from: string, to: string, signal?: AbortSignal) => {
    const route = await get<Route>("/route", new URLSearchParams({ from, to, transfer_min: "15" }), signal);
    if (route.legs.some((leg) => leg.mode !== "Train TER" && leg.mode !== WALK)) throw new ApiError("no_route");
    GROUP_OK.add(route);
    return route;
  },
  // Recherche libre (carte, champs départ / arrivée) : le même trajet qu'une idée de sortie quand il existe, pour
  // pouvoir le pré-réserver ; sinon le trajet le plus rapide, affiché mais pas pré-réservable (car, TGV…)
  trip: (from: string, to: string) =>
    api.schoolRoute(from, to).catch((e) => {
      if (e instanceof ApiError && e.code === "no_route") return get<Route>("/route", new URLSearchParams({ from, to }));
      throw e;
    }),
};
