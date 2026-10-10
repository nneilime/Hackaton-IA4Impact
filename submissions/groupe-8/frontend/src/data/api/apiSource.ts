// FastAPI-backed source (backend: src/dispatch/api/frontend.py, timeline mode).
//
//   GET  /crises/{id}/meta | /timelines        POST|DELETE /crises/{id}/decisions     GET /crises/{id}/what-if
//   GET  /crises/{id}/explanation?step&incident  POST /crises/{id}/copilot            GET /crises/{id}/reinforcement?step
//   POST /crises/{id}/refusals (+ /{pid}/confirm)  POST|GET /crises/{id}/rules  DELETE /crises/{id}/rules/{i}
//   POST /crises/{id}/plan/accept (whole plan)     POST /routes      /learning/* (expert review)
// ?equipes=50 in the page URL is passed as team_share=0.5 (stress test), like the mock.

import type { CrisisMeta } from '../contract';
import type { CrisisSource, DecisionInput, Timelines } from '../source';

/** fetch + JSON with the API's error detail; shared by the replay and the live sources. */
export function http(baseUrl: string) {
  const base = baseUrl.replace(/\/$/, '');
  return async function call<T>(path: string, init?: RequestInit): Promise<T> {
    const r = await fetch(`${base}${path}`, { headers: { 'Content-Type': 'application/json' }, ...init });
    if (!r.ok) {
      const detail = await r
        .json()
        .then((d) => d.detail)
        .catch(() => '');
      throw new Error(detail || `${init?.method ?? 'GET'} ${path} → ${r.status}`);
    }
    return r.json() as Promise<T>;
  };
}

export const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) });

/** Routes that do not depend on the mode: road geometry and the expert review (learning loop). */
export function sharedCapabilities(call: ReturnType<typeof http>): Pick<CrisisSource, 'roads' | 'learning'> {
  return {
    roads: (pairs) => call('/routes', post({ pairs })),
    learning: {
      stats: () => call('/learning/stats'),
      candidates: () => call('/learning/candidates'),
      remarks: () => call('/learning/remarks'),
      backtest: (cand) => call('/learning/candidates/backtest', post({ candidate: cand })),
      activate: (cand, approvedBy) => call('/learning/registry/activate', post({ candidate: cand, approved_by: approvedBy })),
      simulate: (crises) => call('/learning/simulate', post({ crises })),
      registry: () => call('/learning/registry'),
      retire: (id) => call(`/learning/registry/${encodeURIComponent(id)}/retire`, { method: 'POST' }),
    },
  };
}

/** The engine lists a step's recommendations as computed before the manager's decisions at that step; the contract
 *  (like the mock) lists only those still to decide. Drop the ones whose incident or team was decided. */
function pendingOnly(t: Timelines): Timelines {
  for (const snaps of [t.ours, t.reference])
    for (const s of snaps) {
      if (!s.decisions?.length) continue;
      const inc = new Set(s.decisions.map((d) => d.incidentId));
      const team = new Set(s.decisions.map((d) => d.teamId));
      s.recommendations = s.recommendations.filter((r) => !inc.has(r.incidentId) && !team.has(r.teamId));
    }
  return t;
}

export function createApiSource(baseUrl: string, crisis: string): CrisisSource {
  const call = http(baseUrl);
  const share = Number(new URLSearchParams(location.search).get('equipes') ?? 100) / 100;
  const shareQ = share > 0 && share < 1 ? `team_share=${share}` : '';
  const withShare = (p: string) => (shareQ ? `${p}${p.includes('?') ? '&' : '?'}${shareQ}` : p);

  const c = <T>(p: string, init?: RequestInit) => call<T>(withShare(`/crises/${encodeURIComponent(crisis)}${p}`), init);
  const tl = (p: string, init?: RequestInit) => c<Timelines>(p, init).then(pendingOnly);
  const decide = (d: DecisionInput, kind: 'accepted' | 'overridden') => tl('/decisions', post({ ...d, kind }));

  return {
    loadMeta: () => c<CrisisMeta>('/meta'),
    loadTimelines: () => tl('/timelines'),
    accept: (d) => decide(d, 'accepted'),
    override: (d) => decide(d, 'overridden'),
    reset: () => tl('/decisions', { method: 'DELETE' }),
    whatIfTeams: (s) => call(`/crises/${encodeURIComponent(crisis)}/what-if?team_share=${s}`),

    acceptPlan: (step, overrides) => tl('/plan/accept', post({ step, overrides: overrides ?? {} })),
    recordPlan: (step) => c('/plan/accept?replay=false', post({ step, overrides: {} })),
    explainPlan: (step, llm) => c(`/plan/explanation?step=${step}&llm=${llm}`),
    explain: (step, incidentId) => c(`/explanation?step=${step}&incident=${encodeURIComponent(incidentId)}`),
    ask: (question, step, recId) => c('/copilot', post({ question, step, recId })),
    reinforcement: (step) => c(`/reinforcement?step=${step}`),
    refuse: (step, incidentId, teamId, reasonCode, reasonText) =>
      c('/refusals', post({ step, incidentId, teamId, reasonCode, reasonText })),
    confirmRefusal: (pid) => tl(`/refusals/${pid}/confirm`, { method: 'POST' }),
    applyRules: (step, modifiers) => tl('/rules', post({ step, modifiers })),
    listRules: () => c('/rules'),
    removeRule: (i) => tl(`/rules/${i}`, { method: 'DELETE' }),
    ...sharedCapabilities(call),
  };
}
