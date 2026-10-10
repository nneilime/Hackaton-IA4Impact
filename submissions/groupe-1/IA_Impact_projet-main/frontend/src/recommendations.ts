// Recommandations de lieux : une seule liste à la fois, quelle que soit sa source. Elle s'affiche dans le bandeau
// du bas (tant qu'aucune simulation ne l'occupe) et met ses lieux en avant sur la carte.
// Sources : le projet de sortie scolaire aujourd'hui ; l'assistant IA demain — il n'aura qu'à appeler
// `recommend({ source: "ai", items: [{ discovery, reason }] })` depuis App, sans rien changer d'autre.
import type { Discovery } from "./data/discoveries";
import type { Proposal } from "./school";

export type Recommendation = {
  discovery: Discovery;
  proposal?: Proposal; // aller-retour calculé (projet scolaire) : un clic l'affiche comme itinéraire
  reason?: string; // pourquoi ce lieu (texte libre, ex. réponse de l'IA)
};
export type Recommendations = { source: "school" | "ai"; items: Recommendation[] };
