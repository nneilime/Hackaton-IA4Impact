// Photos réelles prises le long des voies, pour la fenêtre du train simulé : public/trackside.json, préparé par
// scripts/fetch-trackside.py à partir de Wikimedia Commons (photos géolocalisées sous licence libre, déjà triées).
// Le fichier est chargé une fois, au premier trajet simulé ; les images restent chez Wikimedia.
import { distanceKm } from "./data/discoveries";

export type CommonsPhoto = { id: string; src: string; lat: number; lon: number; title: string; author: string; license: string; source: string };

let photos: CommonsPhoto[] = [];
let loading: Promise<void> | null = null;

// Charge le fichier (une seule fois ; sans lui, la fenêtre se contente des lieux et des paysages choisis)
export function loadTrackside() {
  loading ??= fetch(`${import.meta.env.BASE_URL}trackside.json`)
    .then((r) => (r.ok ? r.json() : []))
    .then((list: CommonsPhoto[]) => {
      photos = list;
    })
    .catch(() => {
      loading = null; // hors ligne : on retentera au prochain trajet
    });
  return loading;
}

// Photos à moins de `km` du point, la plus proche d'abord
export function photosNear(lon: number, lat: number, km: number) {
  return photos
    .map((p) => ({ p, km: distanceKm({ lon, lat }, p) }))
    .filter((x) => x.km <= km)
    .sort((a, b) => a.km - b.km);
}
