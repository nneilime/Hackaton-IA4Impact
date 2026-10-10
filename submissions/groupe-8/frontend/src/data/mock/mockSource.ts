import type { CrisisMeta } from '../contract';
import type { CrisisSource, DecisionInput, Timelines } from '../source';
import { runCrisis, simulate, type SimResult, type UserDecision } from './engine';
import type { Scenario } from './scenario';

export function createMockSource(crisis: string): CrisisSource {
  let scenarioP: Promise<Scenario> | null = null;
  let reference: SimResult | null = null;
  let decisions: UserDecision[] = [];

  // Demo lever: ?equipes=50 keeps only that share of each site's teams (stress test).
  const share = Number(new URLSearchParams(location.search).get('equipes') ?? 100) / 100;
  const scenario = () =>
    (scenarioP ??= fetch(`${import.meta.env.BASE_URL}mock/${crisis.toLowerCase()}/scenario.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`Scénario ${crisis} introuvable (npm run generate)`);
        return r.json() as Promise<Scenario>;
      })
      .then((sc) => (share > 0 && share < 1 ? keepShare(sc, share) : sc)));

  // Test lever: ?r90=30|45|54|null forces the 90 % estimate to check each display state.
  const r90 = new URLSearchParams(location.search).get('r90');
  const forced = r90 === null ? undefined : r90 === 'null' ? null : Number(r90);

  const run = async (): Promise<Timelines> => {
    const sc = await scenario();
    reference ??= simulate(sc, 'reference');
    const t = runCrisis(sc, decisions, reference);
    if (forced !== undefined) for (const snap of t.ours) snap.kpis = { ...snap.kpis, restore90Hours: forced };
    return t;
  };

  const record = (d: DecisionInput, kind: 'accepted' | 'overridden') => {
    decisions = decisions.filter((x) => !(x.step === d.step && x.incidentId === d.incidentId));
    // A team can only be committed once per step: drop an earlier decision using it.
    decisions = decisions.filter((x) => !(x.step === d.step && x.teamId === d.teamId));
    decisions.push({
      step: d.step,
      kind,
      incidentId: d.incidentId,
      teamId: d.teamId,
      recommendedTeamId: d.recommendedTeamId,
      reason: d.reason,
    });
    return run();
  };

  return {
    async loadMeta(): Promise<CrisisMeta> {
      const sc = await scenario();
      return {
        crisisId: sc.crisisId,
        start: new Date(sc.startMs).toISOString(),
        stepMinutes: sc.stepMinutes,
        sites: sc.sites,
        strategies: [
          { id: 'ours', label: 'Copilote', description: 'Priorité clients (×2 sensibles) par heure d’intervention' },
          { id: 'reference', label: 'Référence', description: 'Premier signalé, équipe la plus proche' },
        ],
      };
    },
    loadTimelines: run,
    accept: (d) => record(d, 'accepted'),
    override: (d) => record(d, 'overridden'),
    async reset() {
      decisions = [];
      return run();
    },
    async whatIfTeams(share: number) {
      const reduced = keepShare(await scenario(), share);
      const ours = simulate(reduced, 'ours').scores;
      const ref = simulate(reduced, 'reference').scores;
      return { score: Math.round(ours[ours.length - 1]), baseline: Math.round(ref[ref.length - 1]) };
    },
  };
}

/** Keeps a share of each site's teams (at least one per site). */
function keepShare(sc: Scenario, share: number): Scenario {
  const teams = sc.teams.filter((t) => {
    const n = Number(t.id.split('-').pop());
    const siteSize = sc.sites.find((s) => s.id === t.siteId)?.teams ?? 1;
    return n <= Math.max(1, Math.ceil(siteSize * share));
  });
  const sites = sc.sites.map((s) => ({ ...s, teams: teams.filter((t) => t.siteId === s.id).length }));
  return { ...sc, teams, sites };
}
