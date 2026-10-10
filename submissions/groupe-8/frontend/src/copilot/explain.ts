// Plain-language explanation of a recommendation. Keep this the only entry point.
// Real engine: headline + 2 business sentences from the backend (LLM-written when compliant, checked against the
// engine's figures). Mock / failure: the local template below.
import type { Recommendation, Snapshot } from '../data/contract';
import { source } from '../data/source';
import { fmtHour, fmtHours, fmtInt, fmtMinutes } from '../lib/format';

export type Explanation = { paragraphs: string[]; limits: string; source?: string };

export async function explainRecommendation(rec: Recommendation, snapshot: Snapshot): Promise<Explanation> {
  if (source.explain) {
    try {
      const step = Number(rec.id.split('-')[0]);
      const e = await source.explain(step, rec.incidentId);
      return { paragraphs: [`${e.headline}.`, ...e.paragraphs], limits: e.limits, source: e.source };
    } catch {
      /* fall back to the template */
    }
  }
  return templateExplanation(rec, snapshot);
}

function templateExplanation(rec: Recommendation, snapshot: Snapshot): Explanation {
  const team = snapshot.teams.find((t) => t.id === rec.teamId);
  const inc = snapshot.incidents.find((i) => i.id === rec.incidentId);
  const f = rec.factors;
  const label = (id: string) => snapshot.teams.find((t) => t.id === id)?.label ?? id;
  const restoreAt = Date.parse(rec.eta) + f.repairHours * 3600_000;
  const perHour = f.clients / (f.repairHours + f.travelMinutes / 60);
  const next = rec.alternatives.find((a) => a.feasible);
  const waiting = snapshot.incidents.filter((i) => i.status === 'waiting').length;

  const p1 =
    `L’équipe ${team?.label ?? rec.teamId} (site de ${team?.siteName ?? '—'}) est proposée pour le poste de ${inc?.commune ?? '—'}, ` +
    `qui prive ${fmtInt(f.clients)} clients d’électricité${f.sensitive ? ', dont au moins un client sensible' : ''}. ` +
    `Elle peut y être à ${fmtHour(rec.eta)}, après ${fmtMinutes(f.travelMinutes)} de route, ` +
    `et le dépannage estimé à ${fmtHours(f.repairHours)} permettrait une réalimentation vers ${fmtHour(restoreAt)}.`;

  const p2 =
    `Parmi les ${waiting} incidents en attente, celui-ci passe en priorité car il rétablit environ ${fmtInt(perHour)} clients par heure d’intervention` +
    `${f.sensitive ? ', et le poids des clients sensibles est doublé' : ''}. ` +
    `Il restera ${fmtHours(f.shiftHoursLeftAfter)} d’amplitude à l’équipe à la fin de l’intervention, dans la limite des 12 h.`;

  const p3 = next
    ? `Envoyer plutôt ${label(next.teamId)} (${fmtMinutes(next.travelMinutes)} de route) retarderait la réalimentation de ` +
      `${fmtMinutes(next.travelMinutes - f.travelMinutes)} et coûterait environ ${fmtInt(Math.max(0, next.deltaScore))} clients·h de coupure en plus.`
    : 'Aucune autre équipe libre n’a l’amplitude suffisante pour cette intervention à cet instant.';

  return {
    paragraphs: [p1, p2, p3],
    limits:
      'Limites : temps de trajet estimé à vol d’oiseau (+30 %), durée de dépannage issue de la gamme, effets indirects sur les autres incidents non comptés dans le coût.',
  };
}
