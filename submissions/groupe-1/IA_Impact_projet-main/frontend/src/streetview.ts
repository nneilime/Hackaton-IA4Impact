// Google Street View pour la fenêtre du train simulé : la vraie vue photographiée là où passe le train.
// API Street View Static : la requête de métadonnées est gratuite et dit s'il existe une photo à moins de `radius`
// mètres ; seule l'image est facturée (crédit gratuit mensuel de Google). La clé est publique par nature (elle part
// dans le navigateur) : elle doit être restreinte au domaine du site et à cette seule API dans Google Cloud.
const KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY;
const API = "https://maps.googleapis.com/maps/api/streetview";

export const hasStreetView = Boolean(KEY);

export type StreetShot = { pano: string; lat: number; lon: number; src: string; date?: string };

// Cap en degrés (0 = nord, sens horaire) pour aller de a vers b, coordonnées [lon, lat]
export function bearing(a: [number, number], b: [number, number]) {
  const rad = Math.PI / 180;
  const [lon1, lat1] = [a[0] * rad, a[1] * rad];
  const [lon2, lat2] = [b[0] * rad, b[1] * rad];
  const y = Math.sin(lon2 - lon1) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
  return (Math.atan2(y, x) / rad + 360) % 360;
}

// Photo Street View la plus proche du point (à moins de 1,5 km), regardant vers `heading`. L'image est déjà chargée
// quand la promesse se résout : elle apparaît d'un coup dans le hublot, sans aplat gris le temps du téléchargement.
// null s'il n'y a rien par ici (rase campagne loin des routes) ou si Google refuse (clé, quota).
export async function streetShot([lon, lat]: [number, number], heading: number): Promise<StreetShot | null> {
  if (!KEY) return null;
  try {
    const q = new URLSearchParams({ location: `${lat},${lon}`, radius: "1500", source: "outdoor", key: KEY });
    const meta = await fetch(`${API}/metadata?${q}`).then((r) => r.json());
    if (meta.status !== "OK") return null;
    const img = new URLSearchParams({ size: "640x480", pano: meta.pano_id, heading: String(Math.round(heading)), fov: "80", pitch: "2", key: KEY });
    const src = `${API}?${img}`;
    await new Promise<void>((ok, ko) => {
      const im = new Image();
      im.onload = () => ok();
      im.onerror = () => ko(new Error("street view image"));
      im.src = src;
    });
    return { pano: meta.pano_id, lat: meta.location.lat, lon: meta.location.lng, src, date: meta.date };
  } catch {
    return null;
  }
}
