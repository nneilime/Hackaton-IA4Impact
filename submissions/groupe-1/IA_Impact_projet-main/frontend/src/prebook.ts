// Pré-réservation d'une sortie scolaire — envoi simulé (mock) : pas encore d'API côté backend. La demande est gardée
// dans ce navigateur et reçoit une référence ; brancher ici un POST le jour où le guichet groupes liO a son endpoint.
export type Prebooking = {
  teacher: string;
  email: string;
  phone: string;
  establishment: string;
  level: string; // niveau et classe en clair (« Lycée · Seconde »)
  students: number;
  adults: number;
  date: string; // AAAA-MM-JJ
  destination: string;
  fromProject: boolean; // false : réservé depuis la carte, sans passer par le projet de sortie
  outbound: { from: string; to: string; departure: string; arrival: string };
  inbound: { from: string; to: string; departure: string; arrival: string } | null; // null : aller simple
  needs: string;
  message: string;
};

const KEY = "prebookings";

export async function sendPrebooking(b: Prebooking): Promise<string> {
  await new Promise((r) => setTimeout(r, 900));
  const ref = "LIO-" + Math.random().toString(36).slice(2, 8).toUpperCase();
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    localStorage.setItem(KEY, JSON.stringify([...saved, { ref, sentAt: new Date().toISOString(), ...b }]));
  } catch {
    /* stockage indisponible : la référence reste affichée */
  }
  return ref;
}
