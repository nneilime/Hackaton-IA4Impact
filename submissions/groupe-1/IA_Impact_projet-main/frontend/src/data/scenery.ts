// Paysages qu'on aperçoit par la fenêtre du train simulé : pas des lieux à visiter, mais ce qui défile le long des
// voies (vignes, étangs, Pyrénées…). Chaque paysage est posé à peu près au centre de sa région ; la fenêtre montre
// ceux qui sont les plus proches du train. Photos : public/scenery/<id>.jpg, téléchargées depuis Wikimedia Commons
// par scripts/fetch-scenery.py, crédits dans scenery-credits.json.
import credits from "./scenery-credits.json";
import type { Credit, Text } from "./discoveries";

export type Scenery = { id: string; lat: number; lon: number; title: Text };

export const sceneryImage = (s: Scenery) => `${import.meta.env.BASE_URL}scenery/${s.id}.jpg`;
export const sceneryCredit = (s: Scenery) => (credits as Record<string, Credit>)[s.id];

export const SCENERY: Scenery[] = [
  { id: "garonne", lat: 43.6, lon: 1.44, title: { en: "The Garonne in Toulouse", fr: "La Garonne à Toulouse" } },
  { id: "tournesols", lat: 43.55, lon: 1.15, title: { en: "Sunflower fields", fr: "Champs de tournesols" } },
  { id: "montagne-noire", lat: 43.45, lon: 2.15, title: { en: "Montagne Noire", fr: "Montagne Noire" } },
  { id: "vignes", lat: 43.3, lon: 2.75, title: { en: "Minervois vineyards", fr: "Vignes du Minervois" } },
  { id: "clape", lat: 43.15, lon: 3.1, title: { en: "La Clape hills", fr: "Massif de la Clape" } },
  { id: "leucate", lat: 42.88, lon: 2.99, title: { en: "Leucate lagoon, along the tracks", fr: "Étang de Leucate, au bord des voies" } },
  { id: "canigou", lat: 42.52, lon: 2.46, title: { en: "Snowy Canigou", fr: "Le Canigou enneigé" } },
  { id: "cote-vermeille", lat: 42.53, lon: 3.08, title: { en: "Côte Vermeille", fr: "Côte Vermeille" } },
  { id: "etang-thau", lat: 43.42, lon: 3.62, title: { en: "Thau lagoon", fr: "Étang de Thau" } },
  { id: "flamants", lat: 43.5, lon: 3.83, title: { en: "Pink flamingos on the lagoons", fr: "Flamants roses sur les étangs" } },
  { id: "maguelone", lat: 43.51, lon: 3.88, title: { en: "Maguelone, between lagoon and sea", fr: "Maguelone, entre étang et mer" } },
  { id: "garrigue", lat: 43.72, lon: 3.6, title: { en: "Garrigue scrubland", fr: "La garrigue" } },
  { id: "pic-saint-loup", lat: 43.78, lon: 3.81, title: { en: "Pic Saint-Loup", fr: "Pic Saint-Loup" } },
  { id: "oliviers", lat: 43.98, lon: 4.69, title: { en: "Olive groves", fr: "Oliveraies" } },
  { id: "pont-du-gard", lat: 43.947, lon: 4.535, title: { en: "Pont du Gard", fr: "Pont du Gard" } },
  { id: "cevennes", lat: 44.15, lon: 3.75, title: { en: "Cévennes ridges", fr: "Corniche des Cévennes" } },
  { id: "gorges-tarn", lat: 44.33, lon: 3.3, title: { en: "Tarn gorges", fr: "Gorges du Tarn" } },
  { id: "larzac", lat: 43.95, lon: 3.2, title: { en: "Larzac plateau", fr: "Causse du Larzac" } },
  { id: "tarn", lat: 44.0, lon: 2.85, title: { en: "The Tarn valley", fr: "La vallée du Tarn" } },
  { id: "aubrac", lat: 44.62, lon: 2.98, title: { en: "Aubrac pastures", fr: "Plateau de l'Aubrac" } },
  { id: "quercy", lat: 44.7, lon: 1.6, title: { en: "Quercy causses", fr: "Causses du Quercy" } },
  { id: "pyrenees-ariegeoises", lat: 42.85, lon: 1.45, title: { en: "Ariège Pyrenees", fr: "Pyrénées ariégeoises" } },
  { id: "gavarnie", lat: 42.73, lon: -0.01, title: { en: "Cirque de Gavarnie", fr: "Cirque de Gavarnie" } },
];
