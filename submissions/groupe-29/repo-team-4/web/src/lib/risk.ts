// Seuils de statut partagés avec le reste de l'application (Dashboard,
// StatusBadge) : > 15 % => signalée, > 10 % => surveillance, sinon conforme.
export const FLAG_THRESHOLD = 15
export const WATCH_THRESHOLD = 10

export type RiskTone = "rose" | "amber" | "emerald"

export function riskTone(errorRate: number): RiskTone {
  if (errorRate > FLAG_THRESHOLD) return "rose"
  if (errorRate > WATCH_THRESHOLD) return "amber"
  return "emerald"
}

export function riskLabel(errorRate: number): string {
  if (errorRate > FLAG_THRESHOLD) return "Risque élevé · suspicion de fraude"
  if (errorRate > WATCH_THRESHOLD) return "Risque modéré"
  return "Risque faible"
}
