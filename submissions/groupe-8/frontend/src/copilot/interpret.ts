// Plain-French interpretation of the engine's choices, from its own data (no template wording, no LLM):
// "closest free team", "the closer team is kept for a bigger outage", "only one outage waiting", ...
import type { Recommendation, Snapshot } from '../data/contract';
import { fmtInt, fmtMinutes } from '../lib/format';

const dur = (h: number) => {
  const m = Math.round(h * 60);
  return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}` : `${m} min`;
};

function names(snap: Snapshot) {
  const team = (id: string) => snap.teams.find((t) => t.id === id)?.label ?? id;
  const inc = (id: string) => snap.incidents.find((i) => i.id === id);
  return { team, inc };
}

/** True when the recommended team is the closest of the teams able to go. */
export function isClosest(rec: Recommendation): boolean {
  const others = rec.alternatives.filter((a) => a.feasible && !a.reason);
  return others.every((a) => a.travelMinutes >= rec.travelMinutes);
}

/** Why THIS team goes to THIS outage, in 2-3 concrete sentences. */
export function interpretLine(rec: Recommendation, snap: Snapshot): string[] {
  const { team, inc } = names(snap);
  const i = inc(rec.incidentId);
  const me = team(rec.teamId);
  const out: string[] = [];
  const waiting = snap.incidents.filter((x) => x.status === 'waiting');

  if (rec.factors.sensitive) out.push(`Un client sensible est concerné à ${i?.commune} : cette panne passe en priorité.`);
  if (waiting.length === 1) out.push(`C’est la seule panne en attente : il n’y a rien à arbitrer.`);
  else if (waiting.length > 1 && rec.factors.clients >= Math.max(...waiting.map((x) => x.clients)))
    out.push(`C’est la plus grosse panne en attente (${fmtInt(rec.factors.clients)} clients).`);

  // distance: the closest team, or why a closer one does not go
  const closer = rec.alternatives
    .filter((a) => a.travelMinutes < rec.travelMinutes)
    .sort((a, b) => a.travelMinutes - b.travelMinutes)[0];
  if (!closer) out.push(`${me} est l’équipe disponible la plus proche (${fmtMinutes(rec.travelMinutes)} de route).`);
  else if (closer.recommendedFor) {
    const other = inc(closer.recommendedFor);
    out.push(
      `${team(closer.teamId)} est plus proche (${fmtMinutes(closer.travelMinutes)}), mais elle part sur ${other?.commune ?? 'une autre panne'}` +
        (other ? ` (${fmtInt(other.clients)} clients), plus prioritaire.` : '.'),
    );
  } else if (closer.reason) out.push(`${team(closer.teamId)} est plus proche, mais elle est ${closer.reason.replace(/^occupée/, 'occupée')}.`);
  else if (!closer.feasible) out.push(`${team(closer.teamId)} est plus proche, mais sa fin de service tombe avant la fin de la réparation.`);
  else out.push(`${team(closer.teamId)} est plus proche, mais ${me} rétablit ces clients plus tôt au total.`);

  // what changing would cost
  const best = rec.alternatives.filter((a) => a.feasible).sort((a, b) => a.deltaScore - b.deltaScore)[0];
  if (best && best.deltaScore < 1) out.push(`${team(best.teamId)} ferait aussi bien : les deux choix se valent.`);
  else if (best && rec.factors.clients > 0)
    out.push(`Envoyer plutôt ${team(best.teamId)} laisserait ces ${fmtInt(rec.factors.clients)} clients ${dur(best.deltaScore / rec.factors.clients)} de plus sans électricité.`);

  if (rec.factors.shiftHoursLeftAfter < 1.5)
    out.push(`Attention : il ne restera que ${dur(rec.factors.shiftHoursLeftAfter)} de service à ${me} après la réparation.`);
  return out;
}

/** How to read the whole plan right now, in 2-3 sentences specific to the situation. */
export function interpretPlan(snap: Snapshot): string[] {
  const recs = snap.recommendations;
  const { team, inc } = names(snap);
  const waiting = snap.incidents.filter((x) => x.status === 'waiting');
  const free = snap.kpis.teamsAvailable;
  const n = recs.length;
  const out: string[] = [];
  if (!n) return out;

  if (waiting.length === 1 && n === 1) {
    const i = inc(recs[0].incidentId);
    out.push(
      `Une seule panne en attente (${i?.commune}, ${fmtInt(recs[0].factors.clients)} clients) et ${free} équipes libres : pas d’arbitrage, ${team(recs[0].teamId)} part car c’est la plus proche.`,
    );
    return out;
  }
  if (n >= waiting.length)
    out.push(`Assez d’équipes libres (${free}) pour les ${waiting.length} pannes en attente : toutes sont prises en charge dès maintenant.`);
  else
    out.push(
      `${waiting.length} pannes en attente pour ${n} équipes disponibles maintenant : ${waiting.length - n} attendront la prochaine équipe libérée, les pannes qui touchent le plus de clients passent d’abord.`,
    );

  const closest = recs.filter(isClosest).length;
  if (closest === n) out.push(`Chaque panne reçoit l’équipe disponible la plus proche.`);
  else
    out.push(
      `${closest} affectation${closest > 1 ? 's' : ''} sur ${n} : l’équipe la plus proche. Pour les ${n - closest} autres, une équipe plus proche existe mais elle est plus utile ailleurs ou occupée (ouvrez la ligne pour le détail).`,
    );

  const big = [...recs].sort((a, b) => b.factors.clients - a.factors.clients)[0];
  if (n > 1) out.push(`Plus grosse panne traitée : ${inc(big.incidentId)?.commune} (${fmtInt(big.factors.clients)} clients), par ${team(big.teamId)}.`);
  return out;
}
