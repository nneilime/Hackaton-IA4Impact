// Grands types de paysage d'Occitanie, pour la fenêtre du train entre deux villes, quand il n'y a ni lieu ni photo
// prise à l'endroit même. Pour chaque zone : des photos de la région trouvées sur Google Images (public/zones/,
// liste dans zone-photos.json — pas libres de droits, à remplacer avant une diffusion publique) et une image
// générée par IA (public/filler/<id>.jpg) en dernier recours. Ni l'une ni l'autre n'est une photo de l'endroit
// exact : la légende le dit. Chaque zone est posée en son centre ; la fenêtre prend les zones les plus proches.
import type { Text } from "./discoveries";
import zonePhotos from "./zone-photos.json";

export type Filler = { id: string; lat: number; lon: number; title: Text };

export const fillerImage = (f: Filler) => `${import.meta.env.BASE_URL}filler/${f.id}.jpg`;
export const zonePhotosOf = (f: Filler) =>
  ((zonePhotos as Record<string, string[]>)[f.id] ?? []).map((file) => ({ id: `zone-${file}`, src: `${import.meta.env.BASE_URL}zones/${file}` }));

export const FILLERS: Filler[] = [
  { id: "lauragais", lat: 43.42, lon: 1.75, title: { en: "Lauragais wheat fields", fr: "Champs du Lauragais" } },
  { id: "gers-tournesols", lat: 43.6, lon: 0.95, title: { en: "Sunflowers of Gascony", fr: "Tournesols de Gascogne" } },
  { id: "garonne", lat: 43.85, lon: 1.25, title: { en: "Garonne plain", fr: "Plaine de la Garonne" } },
  { id: "quercy", lat: 44.45, lon: 1.6, title: { en: "Quercy causse", fr: "Causse du Quercy" } },
  { id: "aveyron", lat: 44.3, lon: 2.35, title: { en: "Aveyron valley", fr: "Vallée de l'Aveyron" } },
  { id: "larzac", lat: 43.95, lon: 3.1, title: { en: "Larzac plateau", fr: "Plateau du Larzac" } },
  { id: "montagne-noire", lat: 43.42, lon: 2.25, title: { en: "Montagne Noire forests", fr: "Forêts de la Montagne Noire" } },
  { id: "vignes", lat: 43.28, lon: 2.75, title: { en: "Vineyards", fr: "Vignes" } },
  { id: "garrigue", lat: 42.98, lon: 2.7, title: { en: "Corbières garrigue", fr: "Garrigue des Corbières" } },
  { id: "etangs", lat: 43.3, lon: 3.35, title: { en: "Coastal lagoons", fr: "Étangs du littoral" } },
  { id: "plaine-herault", lat: 43.55, lon: 3.55, title: { en: "Hérault plain", fr: "Plaine de l'Hérault" } },
  { id: "oliviers", lat: 43.9, lon: 4.3, title: { en: "Olive groves of the Gard", fr: "Oliveraies du Gard" } },
  { id: "roussillon", lat: 42.65, lon: 2.75, title: { en: "Roussillon orchards", fr: "Vergers du Roussillon" } },
  { id: "piemont", lat: 43.05, lon: 1.35, title: { en: "Pyrenean foothills", fr: "Piémont pyrénéen" } },
  { id: "cevennes", lat: 44.15, lon: 3.8, title: { en: "Cévennes chestnut woods", fr: "Châtaigneraies des Cévennes" } },
  { id: "bigorre", lat: 43.1, lon: 0.1, title: { en: "Bigorre meadows", fr: "Prairies de Bigorre" } },
  { id: "albigeois", lat: 43.9, lon: 2.05, title: { en: "Albigeois hills", fr: "Collines de l'Albigeois" } },
  { id: "lozere", lat: 44.55, lon: 3.5, title: { en: "Lozère granite plateau", fr: "Plateau granitique de Lozère" } },
];
