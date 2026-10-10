// Live source: the crisis as it happens (backend: src/dispatch/api/live.py). The clock is the real one.
//
// The dashboard polls GET /live/state?have=n: the current snapshot plus the history entries it does not have yet
// (one every few minutes of crisis time, and one after each decision). The "timelines" given to the UI are that
// history followed by the current snapshot; in live mode the UI always shows the last one.
// Alerts and field reports do not come from here: a separate system (simulator/) sends them to the backend.

import type { CrisisMeta, Snapshot } from '../contract';
import { http, post, sharedCapabilities } from '../api/apiSource';
import type { CrisisSource, Timelines } from '../source';

type LiveState = {
  version: number;
  clock: { start: string; nowHours: number; speed: number; serverTime: string };
  label: string;
  snapshot: Snapshot;
  history: Snapshot[];
  historyLength: number;
};

export type LiveCapabilities = {
  /** Fetches the latest state. `restarted` = a new crisis was opened (reload the static description). */
  poll(): Promise<{ timelines: Timelines; restarted: boolean }>;
  /** Minutes since the start of the crisis, on the backend's clock (estimated between two polls). */
  nowMinutes(): number;
};

export function createLiveSource(baseUrl: string): CrisisSource & { live: LiveCapabilities } {
  const call = http(baseUrl);
  let history: Snapshot[] = [];
  let current: Snapshot | undefined;
  let start = '';
  let clock = { nowHours: 0, speed: 1, at: performance.now() };

  const timelines = (): Timelines => {
    const ours = current ? [...history, current] : history;
    return { ours, reference: ours };
  };

  async function poll(): Promise<{ timelines: Timelines; restarted: boolean }> {
    let st = await call<LiveState>(`/live/state?have=${history.length}`);
    const restarted = !!start && st.clock.start !== start;
    if (restarted || st.historyLength < history.length) {
      history = [];
      st = await call<LiveState>('/live/state?have=0');
    }
    start = st.clock.start;
    history.push(...st.history);
    current = st.snapshot;
    clock = { nowHours: st.clock.nowHours, speed: st.clock.speed, at: performance.now() };
    return { timelines: timelines(), restarted };
  }
  const refreshed = () => poll().then((r) => r.timelines);

  return {
    live: {
      poll,
      nowMinutes: () => 60 * clock.nowHours + (clock.speed * (performance.now() - clock.at)) / 60000,
    },
    loadMeta: () => call<CrisisMeta>('/live/meta'),
    loadTimelines: refreshed,
    accept: (d) => call('/live/plan/accept', post({ assignments: [{ incidentId: d.incidentId, teamId: d.teamId }] })).then(refreshed),
    override: (d) =>
      call('/live/plan/accept', post({ assignments: [{ incidentId: d.incidentId, teamId: d.teamId, reason: d.reason }] })).then(refreshed),
    // A live crisis is never "reset" from the dashboard: the field opens a new one (simulator: POST /live/reset).
    reset: refreshed,
    acceptPlan: (_step, overrides) => {
      const recs = current?.recommendations ?? [];
      const assignments = recs.map((r) => ({ incidentId: r.incidentId, teamId: overrides?.[r.incidentId] ?? r.teamId }));
      return call('/live/plan/accept', post({ assignments, reason: 'Plan validé' })).then(refreshed);
    },
    explainPlan: (_step, llm) => call(`/live/plan/explanation?llm=${llm}`),
    explain: (_step, incidentId) => call(`/live/explanation?incident=${encodeURIComponent(incidentId)}`),
    ask: (question, _step, recId) => call('/live/copilot', post({ question, recId })),
    reinforcement: () => call('/live/reinforcement'),
    refuse: (_step, incidentId, teamId, reasonCode, reasonText) => call('/live/refusals', post({ incidentId, teamId, reasonCode, reasonText })),
    confirmRefusal: (pid) => call(`/live/refusals/${pid}/confirm`, { method: 'POST' }).then(refreshed),
    applyRules: (_step, modifiers) => call('/live/rules', post({ modifiers })).then(refreshed),
    listRules: () => call('/live/rules'),
    removeRule: (i) => call(`/live/rules/${i}`, { method: 'DELETE' }).then(refreshed),
    ...sharedCapabilities(call),
  };
}
