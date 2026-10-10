// Naive mock engine. Stands in for the Python optimiser so the UI has something
// to play back. It is deliberately simple: greedy, step-based, no look-ahead.
//
//  - "reference": first come, first served; nearest feasible team.
//  - "ours":      greedy on clients (x2 if sensitive) per hour of travel+repair.
//
// Decisions taken by the manager (accept / override) are replayed at their step,
// before the strategy fills in the rest. Pending recommendations that nobody
// touched are executed at the step time, so playback continues on its own.

import type {
  Alternative,
  Decision,
  Incident,
  Recommendation,
  Snapshot,
  StrategyId,
  Team,
} from '../contract';
import type { Scenario, ScenarioIncident } from './scenario';

export const SHIFT_HOURS = 12;
export const REST_HOURS = 11;
const MIN_JOB_HOURS = 2; // shortest repair: below this a team is sent to rest
const SPEED_KMH = 55;
const DETOUR = 1.3;
const PREP_MINUTES = 15;
const MAX_STEPS = 200; // 100 h: long enough for degraded scenarios (half the teams)

export type UserDecision = Decision & { step: number };

type LonLat = { lon: number; lat: number };

type Job = {
  incidentId: string;
  from: LonLat;
  to: LonLat;
  dispatch: number;
  arrive: number;
  done: number;
};

type TeamState = {
  id: string;
  home: LonLat;
  pos: LonLat;
  shiftEnd: number;
  job?: Job;
  rest?: { start: number; from: LonLat; homeAt: number; until: number };
};

type IncState = { teamId?: string; arrive?: number; done?: number };

export function distanceKm(a: LonLat, b: LonLat): number {
  const R = 6371;
  const toRad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * toRad;
  const dLon = (b.lon - a.lon) * toRad;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(a.lat * toRad) * Math.cos(b.lat * toRad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function travelMinutes(a: LonLat, b: LonLat): number {
  return Math.round(PREP_MINUTES + ((distanceKm(a, b) * DETOUR) / SPEED_KMH) * 60);
}

const lerp = (a: LonLat, b: LonLat, f: number): LonLat => {
  const k = Math.max(0, Math.min(1, f));
  return { lon: a.lon + (b.lon - a.lon) * k, lat: a.lat + (b.lat - a.lat) * k };
};

const weight = (inc: ScenarioIncident) => inc.clients * (inc.sensitive ? 2 : 1);
const round1 = (x: number) => Math.round(x * 10) / 10;
const frNum = (x: number) => String(round1(x)).replace('.', ',');

export type SimResult = { snapshots: Snapshot[]; scores: number[] };

export function simulate(
  sc: Scenario,
  strategy: StrategyId,
  decisions: UserDecision[] = [],
): SimResult {
  const step = sc.stepMinutes;
  const incById = new Map(sc.incidents.map((i) => [i.id, i]));
  const teamLabel = new Map(sc.teams.map((t) => [t.id, t]));
  const teams: TeamState[] = sc.teams.map((t) => {
    const home = { lon: t.lon, lat: t.lat };
    const st: TeamState = { id: t.id, home, pos: home, shiftEnd: t.initialShiftHours * 60 };
    if (t.initialRestHours > 0) {
      const until = t.initialRestHours * 60;
      st.rest = { start: until - REST_HOURS * 60, from: home, homeAt: until - REST_HOURS * 60, until };
    }
    return st;
  });
  const inc = new Map<string, IncState>(sc.incidents.map((i) => [i.id, {}]));
  const lastReport = Math.max(...sc.incidents.map((i) => i.reportedMin));
  const iso = (min: number) => new Date(sc.startMs + min * 60000).toISOString();

  const startRest = (t: TeamState, at: number) => {
    const homeAt = at + travelMinutes(t.pos, t.home) - PREP_MINUTES;
    t.rest = { start: at, from: t.pos, homeAt, until: homeAt + REST_HOURS * 60 };
  };

  const dispatch = (t: TeamState, i: ScenarioIncident, at: number) => {
    const travel = travelMinutes(t.pos, i);
    const arrive = at + travel;
    const done = arrive + i.repairHours * 60;
    t.job = { incidentId: i.id, from: t.pos, to: { lon: i.lon, lat: i.lat }, dispatch: at, arrive, done };
    inc.set(i.id, { teamId: t.id, arrive, done });
  };

  const feasible = (t: TeamState, i: ScenarioIncident, at: number, travel: number) =>
    travel + i.repairHours * 60 <= t.shiftEnd - at;

  const snapshots: Snapshot[] = [];
  const scores: number[] = [];

  for (let k = 0; k < MAX_STEPS; k++) {
    const T = k * step;

    // 1. Advance events up to T.
    for (const t of teams) {
      if (t.job && t.job.done <= T) {
        t.pos = t.job.to;
        const freeAt = t.job.done;
        t.job = undefined;
        if (t.shiftEnd - freeAt < MIN_JOB_HOURS * 60) startRest(t, freeAt);
      }
      if (t.rest && t.rest.until <= T) {
        t.pos = t.home;
        t.shiftEnd = t.rest.until + SHIFT_HOURS * 60;
        t.rest = undefined;
      }
      if (!t.job && !t.rest && t.shiftEnd - T < MIN_JOB_HOURS * 60) startRest(t, T);
    }

    const available = () => teams.filter((t) => !t.job && !t.rest);
    const waiting = () =>
      sc.incidents.filter((i) => i.reportedMin <= T && !inc.get(i.id)!.teamId);

    // 2. Replay the manager's decisions for this step.
    const applied: Decision[] = [];
    for (const d of decisions.filter((d) => d.step === k)) {
      const t = teams.find((x) => x.id === d.teamId);
      const i = incById.get(d.incidentId);
      if (!t || !i || t.job || t.rest || inc.get(i.id)!.teamId || i.reportedMin > T) continue;
      dispatch(t, i, T);
      const { step: _s, ...rest } = d;
      void _s;
      applied.push(rest);
    }

    // 3. Strategy proposes assignments for what is left.
    const free = available();
    const open = waiting();
    const plan: { team: TeamState; incident: ScenarioIncident; travel: number }[] = [];
    const used = new Set<string>();
    const bestTeam = (i: ScenarioIncident) => {
      let best: { team: TeamState; travel: number } | null = null;
      for (const t of free) {
        if (used.has(t.id)) continue;
        const travel = travelMinutes(t.pos, i);
        if (!feasible(t, i, T, travel)) continue;
        if (!best || travel < best.travel) best = { team: t, travel };
      }
      return best;
    };

    if (strategy === 'reference') {
      for (const i of [...open].sort((a, b) => a.reportedMin - b.reportedMin || a.id.localeCompare(b.id))) {
        const b = bestTeam(i);
        if (!b) continue;
        used.add(b.team.id);
        plan.push({ team: b.team, incident: i, travel: b.travel });
      }
    } else {
      const cands = open.map((i) => ({ i, best: bestTeam(i) }));
      for (;;) {
        let pick = -1;
        let pickScore = -Infinity;
        cands.forEach((c, idx) => {
          if (!c.best) return;
          const s = weight(c.i) / (c.i.repairHours + c.best.travel / 60);
          if (s > pickScore) {
            pickScore = s;
            pick = idx;
          }
        });
        if (pick < 0) break;
        const c = cands[pick];
        const team = c.best!.team;
        used.add(team.id);
        plan.push({ team, incident: c.i, travel: c.best!.travel });
        cands.splice(pick, 1);
        for (const o of cands) if (o.best?.team === team) o.best = bestTeam(o.i);
      }
    }

    // 4. Recommendations (ours only) with alternatives among the free teams.
    const recommendations: Recommendation[] = [];
    if (strategy === 'ours') {
      const recFor = new Map(plan.map((p) => [p.team.id, p.incident.id]));
      for (const p of plan) {
        const i = p.incident;
        const shiftAfter = (p.team.shiftEnd - T - p.travel - i.repairHours * 60) / 60;
        // One candidate per location: a sibling crew parked at the same spot is not a real alternative.
        const posKey = (t: TeamState) => `${t.pos.lon.toFixed(4)}|${t.pos.lat.toFixed(4)}`;
        const seenPos = new Set([posKey(p.team)]);
        const alts: Alternative[] = free
          .filter((t) => t.id !== p.team.id)
          .map((t) => {
            const travel = travelMinutes(t.pos, i);
            const ok = feasible(t, i, T, travel);
            const after = (t.shiftEnd - T - travel - i.repairHours * 60) / 60;
            return {
              teamId: t.id,
              deltaScore: Math.round((i.clients * (travel - p.travel)) / 60),
              travelMinutes: travel,
              eta: iso(T + travel),
              shiftHoursLeftAfter: round1(Math.max(0, after)),
              feasible: ok,
              reason: ok
                ? undefined
                : `Amplitude insuffisante : ${frNum(Math.max(0, (t.shiftEnd - T) / 60))} h restantes pour ${frNum(travel / 60 + i.repairHours)} h de mission`,
              recommendedFor: recFor.get(t.id),
            };
          })
          .sort(
            (a, b) =>
              Number(b.feasible) - Number(a.feasible) ||
              a.travelMinutes - b.travelMinutes ||
              Number(!!a.recommendedFor) - Number(!!b.recommendedFor),
          )
          .filter((a) => {
            const key = posKey(free.find((t) => t.id === a.teamId)!);
            if (seenPos.has(key)) return false;
            seenPos.add(key);
            return true;
          });
        const feasibleAlts = alts.filter((a) => a.feasible).slice(0, 5);
        const infeasible = alts.filter((a) => !a.feasible).slice(0, 1);
        const alternatives = [...feasibleAlts, ...infeasible];
        recommendations.push({
          id: `REC-${k}-${i.id}`,
          teamId: p.team.id,
          incidentId: i.id,
          eta: iso(T + p.travel),
          travelMinutes: p.travel,
          priority: Math.round((weight(i) / (i.repairHours + p.travel / 60)) * 10) / 10,
          factors: {
            clients: i.clients,
            sensitive: i.sensitive,
            travelMinutes: p.travel,
            repairHours: i.repairHours,
            shiftHoursLeftAfter: round1(shiftAfter),
          },
          alternatives,
          note: noteFor(i, p.travel, shiftAfter, feasibleAlts[0]),
        });
      }
    }

    // 5. Snapshot of the situation at T (decisions applied, proposals pending).
    let score = 0;
    let clientsCut = 0;
    let clientsRestored = 0;
    let incidentsWaiting = 0;
    const incidents: Incident[] = [];
    for (const i of sc.incidents) {
      if (i.reportedMin > T) continue;
      const s = inc.get(i.id)!;
      const doneBy = s.done !== undefined && s.done <= T ? s.done : T;
      score += (i.clients * (doneBy - i.reportedMin)) / 60;
      let status: Incident['status'] = 'waiting';
      if (s.teamId) status = T < s.arrive! ? 'enroute' : T < s.done! ? 'repairing' : 'restored';
      if (status === 'restored') clientsRestored += i.clients;
      else clientsCut += i.clients;
      if (status === 'waiting') incidentsWaiting++;
      incidents.push({
        id: i.id,
        posteId: i.posteId,
        lon: i.lon,
        lat: i.lat,
        commune: i.commune,
        clients: i.clients,
        sensitive: i.sensitive,
        cause: i.cause,
        repairHours: i.repairHours,
        reportedAt: iso(i.reportedMin),
        status,
        teamId: s.teamId,
      });
    }

    let teamsAvailable = 0;
    let teamsBusy = 0;
    let teamsResting = 0;
    const teamsOut: Team[] = teams.map((t) => {
      let status: Team['status'] = 'available';
      let pos = t.pos;
      if (t.rest) {
        status = 'resting';
        pos = lerp(t.rest.from, t.home, (T - t.rest.start) / Math.max(1, t.rest.homeAt - t.rest.start));
      } else if (t.job) {
        status = T < t.job.arrive ? 'travelling' : 'repairing';
        pos = lerp(t.job.from, t.job.to, (T - t.job.dispatch) / Math.max(1, t.job.arrive - t.job.dispatch));
      }
      if (status === 'available') teamsAvailable++;
      else if (status === 'resting') teamsResting++;
      else teamsBusy++;
      const meta = teamLabel.get(t.id)!;
      return {
        id: t.id,
        label: meta.label,
        siteName: meta.siteName,
        lon: pos.lon,
        lat: pos.lat,
        status,
        shiftHoursLeft: t.rest ? 0 : round1(Math.max(0, (t.shiftEnd - T) / 60)),
        incidentId: t.job?.incidentId,
      };
    });

    scores.push(score);
    snapshots.push({
      time: iso(T),
      kpis: {
        clientsCut,
        clientsRestored,
        incidentsWaiting,
        teamsAvailable,
        teamsBusy,
        teamsResting,
        score: Math.round(score),
        scoreBaseline: 0, // filled by runCrisis
        restore90Hours: null, // filled once the plan is known, below
      },
      incidents,
      teams: teamsOut,
      recommendations: recommendations.sort((a, b) => b.priority - a.priority),
      decisions: applied,
    });

    // 6. Untouched proposals are executed at T.
    for (const p of plan) dispatch(p.team, p.incident, T);

    const allDone = sc.incidents.every((i) => {
      const s = inc.get(i.id)!;
      return s.done !== undefined && s.done <= T;
    });
    if (T >= lastReport && allDone) break;
  }

  // The mock's plan is the simulation itself: every incident reported so far gets the
  // restoration time this run schedules for it (current decisions included).
  for (const [k, snap] of snapshots.entries()) {
    const T = k * step;
    const known = sc.incidents.filter((i) => i.reportedMin <= T);
    const total = known.reduce((a, i) => a + i.clients, 0);
    if (!total) continue;
    const timeline = known
      .map((i) => ({ done: inc.get(i.id)!.done, clients: i.clients }))
      .sort((a, b) => (a.done ?? Infinity) - (b.done ?? Infinity));
    let acc = 0;
    for (const e of timeline) {
      if (e.done === undefined) break; // not scheduled: the plan does not reach 90 %
      acc += e.clients;
      if (acc >= 0.9 * total) {
        snap.kpis.restore90Hours = round1(e.done / 60);
        break;
      }
    }
  }

  return { snapshots, scores };
}

function noteFor(
  i: ScenarioIncident,
  travel: number,
  shiftAfter: number,
  next: Alternative | undefined,
): string {
  if (!next) return 'Seule équipe libre ayant l’amplitude suffisante : pas d’alternative immédiate.';
  if (shiftAfter < 1.5)
    return `Amplitude tendue : l’équipe terminera à ${frNum(shiftAfter)} h de sa limite de 12 h.`;
  if (travel > 90) return 'Trajet long : durée réelle incertaine (± 30 %), accès non vérifié.';
  if (next.deltaScore <= Math.max(5, i.clients * 0.1))
    return 'Confiance moyenne : l’alternative est presque équivalente.';
  if (i.sensitive) return 'Client sensible sur ce poste : priorité renforcée.';
  return 'Confiance élevée : nettement plus proche que l’alternative.';
}

export type CrisisRun = { ours: Snapshot[]; reference: Snapshot[] };

/** Runs both strategies and aligns them on the same timeline. */
export function runCrisis(sc: Scenario, decisions: UserDecision[] = [], reference?: SimResult): CrisisRun {
  const ref = reference ?? simulate(sc, 'reference');
  const ours = simulate(sc, 'ours', decisions);
  const n = Math.max(ours.snapshots.length, ref.snapshots.length);
  const pad = (r: SimResult) => {
    const out = [...r.snapshots];
    while (out.length < n) {
      const last = out[out.length - 1];
      const k = out.length;
      out.push({
        ...last,
        time: new Date(sc.startMs + k * sc.stepMinutes * 60000).toISOString(),
        recommendations: [],
        decisions: [],
      });
    }
    return out;
  };
  const o = pad(ours);
  const r = pad(ref);
  const withBaseline = (s: Snapshot, k: number): Snapshot => ({
    ...s,
    kpis: { ...s.kpis, scoreBaseline: r[k].kpis.score },
  });
  return { ours: o.map(withBaseline), reference: r.map(withBaseline) };
}
