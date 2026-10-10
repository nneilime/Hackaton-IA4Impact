// THE single entry point for crisis data. Swap the implementation here.
//
//   VITE_DATA_SOURCE=mock (default) -> mock engine running in the browser on
//                                      public/mock/<crisis>/scenario.json (replay only)
//   VITE_DATA_SOURCE=api            -> FastAPI service at VITE_API_URL:
//        live mode (default page)    -> the crisis in real time (live/liveSource.ts)
//        ?mode=replay                -> "Revoir une crise passée": a past crisis, accelerated (api/apiSource.ts)
//
// Every call returns the full, aligned timelines of both strategies so the UI can
// scrub freely. Decisions are idempotent per (step, incident).
// Optional capabilities (real engine only) are undefined with the mock: the UI hides those features.

import type { CrisisMeta, Snapshot } from './contract';
import { createApiSource } from './api/apiSource';
import { createLiveSource, type LiveCapabilities } from './live/liveSource';
import { createMockSource } from './mock/mockSource';

export type Timelines = { ours: Snapshot[]; reference: Snapshot[] };

export type DecisionInput = {
  step: number; // snapshot index the decision applies to
  recommendationId: string;
  incidentId: string;
  teamId: string; // team finally chosen by the manager
  recommendedTeamId: string;
  reason?: string; // free label for audit ("Connaissance terrain", …)
};

export type PlanExplanation = { resume: string; points: string[]; source: 'llm' | 'template' };
export type ServerExplanation = { headline: string; paragraphs: string[]; limits: string; source: 'llm' | 'template' };
export type Reinforcement = {
  projected_share: number;
  /** What the shares count: incidents (the spec) or customers. */
  basis?: 'incidents' | 'customers';
  target: number;
  target_met: boolean;
  known_incidents: number;
  reinforcement?: {
    extra_teams: number;
    by_site: Record<string, number>;
    sites: { id: string; name: string; lon: number; lat: number; extra: number }[];
    projected_share_after: number;
    target_met: boolean;
  };
};
export type RefusalResult =
  | { question: string }
  | { error: string }
  | { proposalId: number; restatement: string; costDelta: number; rules: string[] };
export type RuleRow = { index?: number; step?: number; label: string; rule: Record<string, unknown>; reason: string };
export type Candidate = {
  key: string;
  description: string;
  /** what the AI saw in the manager's remarks / what it proposes / the variable of the calculation it changes */
  observed: string;
  proposal: string;
  variable: string;
  before: string;
  after: string;
  modifier: Record<string, unknown>;
  evidence: { refusals: number; crises: number; main_reason: string; examples: string[]; simulated_share: number };
  safety_alert: boolean;
  level: string;
};
export type Remark = { crisis: string; team: string; site: string; commune: string; departement: string; reason_code: string | null; reason_text: string | null; simulated: boolean };
export type Backtest = { crises: number; cost_pct: number; target_still_met_in: number; share_by_deadline_with: number };
export type RoadRoute = { coordinates: [number, number][]; source: 'osrm' | 'straight'; duration_min: number | null };
export type RegistryEntry = { id: string; description: string; status: string; approved_by: string; activated_on: string };

export interface CrisisSource {
  loadMeta(): Promise<CrisisMeta>;
  loadTimelines(): Promise<Timelines>;
  /** Accept the recommendation as is. */
  accept(d: DecisionInput): Promise<Timelines>;
  /** Assign a different team than the recommended one. */
  override(d: DecisionInput): Promise<Timelines>;
  /** Cancels every decision (demo reset). */
  reset(): Promise<Timelines>;
  /** What-if: final score if only `teamShare` of the teams were available. Optional. */
  whatIfTeams?(teamShare: number): Promise<{ score: number; baseline: number }>;

  // ---- real engine only (optional)
  /** Validates the engine's whole plan of a step at once; `overrides` = incidents sent to another team. */
  acceptPlan?(step: number, overrides?: Record<string, string>): Promise<Timelines>;
  /** Record the validation of the engine's own plan (journal + knowledge base) without recomputing the crisis. */
  recordPlan?(step: number): Promise<unknown>;
  explain?(step: number, incidentId: string): Promise<ServerExplanation>;
  /** 'Pourquoi ce plan ?': justification of the whole plan of a step (llm=false: instant template). */
  explainPlan?(step: number, llm: boolean): Promise<PlanExplanation>;
  ask?(question: string, step: number, recId?: string): Promise<{ answer: string; source: string }>;
  reinforcement?(step: number): Promise<Reinforcement>;
  refuse?(step: number, incidentId: string, teamId: string, reasonCode?: string, reasonText?: string): Promise<RefusalResult>;
  confirmRefusal?(proposalId: number): Promise<Timelines>;
  applyRules?(step: number, modifiers: object[]): Promise<Timelines>;
  listRules?(): Promise<{ crisis: RuleRow[]; permanent: RuleRow[] }>;
  removeRule?(index: number): Promise<Timelines>;
  roads?(pairs: [number, number][][]): Promise<RoadRoute[]>;
  /** Live mode only: polling and the real clock. */
  live?: LiveCapabilities;
  learning?: {
    stats(): Promise<{ total: number; accepted?: number; rejected?: number; refusal_rate: number }>;
    candidates(): Promise<Candidate[]>;
    remarks(): Promise<Remark[]>;
    backtest(c: Candidate): Promise<Backtest>;
    activate(c: Candidate, approvedBy: string): Promise<unknown>;
    simulate(crises: string[]): Promise<unknown>;
    registry(): Promise<{ version: number; constraints: RegistryEntry[] }>;
    retire(id: string): Promise<unknown>;
  };
}

const kind = (import.meta.env.VITE_DATA_SOURCE ?? 'mock') as 'mock' | 'api';
const crisis = (new URLSearchParams(location.search).get('crise') ?? import.meta.env.VITE_CRISIS ?? 'CRISE_DEMO') as string;
const apiUrl = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000') as string;

/** True when the live mode exists (real engine); the mock only replays. */
export const liveAvailable = kind === 'api';
export const mode: 'live' | 'replay' = liveAvailable && new URLSearchParams(location.search).get('mode') !== 'replay' ? 'live' : 'replay';

export const source: CrisisSource =
  mode === 'live' ? createLiveSource(apiUrl) : kind === 'api' ? createApiSource(apiUrl, crisis) : createMockSource(crisis);
