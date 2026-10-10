// Contract between the optimisation engine and the frontend.
// Fields marked "ADDED" are not in the original brief: the engine must provide them.

export type IncidentStatus = 'waiting' | 'enroute' | 'repairing' | 'restored';
export type TeamStatus = 'available' | 'travelling' | 'repairing' | 'resting';
export type StrategyId = 'ours' | 'reference';

export type Kpis = {
  clientsCut: number;
  clientsRestored: number;
  incidentsWaiting: number;
  teamsAvailable: number;
  teamsBusy: number;
  teamsResting: number;
  score: number; // customer-hours of outage so far, ours
  scoreBaseline: number; // same, for the reference strategy
  /** ADDED: projected hours since crisis start until 90 % of the INCIDENTS reported so far are repaired per the
   *  current plan (spec basis, config service_target.basis); null when the plan does not reach 90 %. */
  restore90Hours: number | null;
};

export type Incident = {
  id: string;
  posteId: string; // ADDED: substation code, shown to operators
  lon: number;
  lat: number;
  commune: string;
  clients: number;
  sensitive: boolean;
  cause: string;
  repairHours: number;
  reportedAt: string;
  status: IncidentStatus;
  teamId?: string;
};

export type Team = {
  id: string;
  label: string; // ADDED: human name, e.g. "Muret-3"
  siteName: string;
  lon: number;
  lat: number;
  status: TeamStatus;
  shiftHoursLeft: number; // out of 12
  incidentId?: string;
  /** ADDED (real engine): shift group of the fixed roster (A at H0, B a little later, C the relief) */
  group?: 'A' | 'B' | 'C';
  /** ADDED (real engine): current shift (or the next one when resting), ISO */
  shiftStart?: string;
  shiftEnd?: string;
};

export type Alternative = {
  teamId: string;
  deltaScore: number; // cost of choosing this team instead (customer-hours, + = worse)
  travelMinutes: number; // ADDED
  eta: string; // ADDED
  shiftHoursLeftAfter: number; // ADDED
  feasible: boolean; // ADDED: false if the team cannot legally/safely take the job
  reason?: string; // ADDED: why infeasible, or a caveat
  recommendedFor?: string; // ADDED: incidentId this team is already proposed for at this step
};

export type Recommendation = {
  id: string;
  teamId: string;
  incidentId: string;
  eta: string;
  travelMinutes: number;
  priority: number; // ADDED: engine ranking, higher = more impactful (cards sorted by it)
  factors: {
    clients: number;
    sensitive: boolean;
    travelMinutes: number;
    repairHours: number;
    shiftHoursLeftAfter: number;
  };
  alternatives: Alternative[];
  note?: string;
  /** ADDED (real engine): short deterministic headline and the 2-sentence business explanation (template). */
  headline?: string;
  details?: string;
  /** ADDED (real engine): the 3 best ways to handle this incident (recommended team + 2 best alternatives). */
  options?: RouteOption[];
  /** ADDED (real engine): similar refusals in the knowledge base, with the rule applied last time. */
  pastRefusals?: PastRefusals | null;
};

// ADDED (real engine)
export type RouteOption = {
  rank: number;
  team: string;
  team_site: string;
  travel_min: number;
  restored_h: number;
  restored_clock: string;
  restoredAt: string;
  extra_customer_hours: number;
  recommended: boolean;
  path: [number, number][]; // [lon, lat] team -> incident (straight; the map fetches the road geometry)
};

export type PastRefusals = { count: number; last_reason: string; suggested_modifiers: object[]; question: string };

// ADDED: decisions taken by the manager at this step, echoed back by the engine
export type Decision = {
  incidentId: string;
  teamId: string;
  kind: 'accepted' | 'overridden';
  recommendedTeamId: string;
  reason?: string;
};

export type Snapshot = {
  time: string; // ISO
  kpis: Kpis;
  incidents: Incident[];
  teams: Team[];
  recommendations: Recommendation[];
  decisions: Decision[]; // ADDED
};

// ADDED: static crisis description, fetched once
export type Site = { id: string; name: string; lon: number; lat: number; teams: number };

// ADDED (real engine): the fixed shift schedule, explained to the manager
export type Roster = {
  workHours: number;
  restHours: number;
  groups: { id: 'A' | 'B' | 'C'; offsetHours: number; firstShiftStart: string; teams: number }[];
};

export type CrisisMeta = {
  /** ADDED: 'live' = the crisis as it happens (real clock), 'replay' = a past crisis replayed (accelerated) */
  mode?: 'live' | 'replay';
  label?: string;
  /** ADDED (live): clock speed (1 = real time) */
  speed?: number;
  roster?: Roster;
  crisisId: string;
  start: string; // ISO, time of snapshot 0
  stepMinutes: number;
  sites: Site[];
  strategies: { id: StrategyId; label: string; description: string }[];
};
