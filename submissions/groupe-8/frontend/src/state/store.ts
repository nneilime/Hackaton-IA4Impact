import { create } from 'zustand';
import type { CrisisMeta, Decision, Recommendation, Snapshot, StrategyId } from '../data/contract';
import { mode, source, type DecisionInput, type Timelines } from '../data/source';
import { fmtDelta, fmtInt } from '../lib/format';

export type Toast = { id: number; tone: 'ok' | 'info' | 'warn'; title: string; body?: string };

/** Playback speeds: ×1 = one minute of crisis per second. */
export const SPEEDS = [
  { label: '×1', minPerSec: 1, title: '1 s = 1 min de crise' },
  { label: '×10', minPerSec: 10, title: '1 s = 10 min de crise' },
  { label: '×60', minPerSec: 60, title: '1 s = 1 h de crise' },
] as const;

export type CopilotRequest = { id: number; question: string; recId?: string };

/** Popups of the real engine's features (3 options, refusal → rule, reinforcement, expert review, rules). */
export type Modal = { kind: 'options' | 'refusal' | 'reinforcement' | 'review' | 'rules'; recId?: string };

type State = {
  modal?: Modal;
  /** Sites highlighted on the map (reinforcement request). */
  highlightSites: string[];
  /** Option (1-3) hovered in the "3 options" popup: highlighted on the map. */
  hoveredOption?: number;
  /** Number of operator rules active in this crisis (header pill). */
  rulesCount: number;
  openModal(m: Modal | undefined): void;
  setHighlightSites(ids: string[]): void;
  hoverOption(rank: number | undefined): void;
  /** Install timelines returned by the engine after a rule / refusal, keep the focus, refresh the rules count. */
  applyTimelines(timelines: Timelines, toast?: Omit<Toast, 'id'>): void;
  refreshRules(): Promise<void>;
  reload(): Promise<void>;
  status: 'loading' | 'ready' | 'error';
  error?: string;
  meta?: CrisisMeta;
  timelines?: Timelines;

  t: number; // minutes since snapshot 0 (continuous)
  playing: boolean;
  speedIdx: number;
  view: StrategyId;

  hoveredRecId?: string;
  hoverFrom?: 'card' | 'map';
  /** The one recommendation in focus (defaults to the first of the queue). */
  focusedRecId?: string;
  copilotOpen: boolean;
  copilotRequest?: CopilotRequest;
  overrideRecId?: string;
  previewTeamId?: string;
  busy: boolean;
  toasts: Toast[];

  init(): Promise<void>;
  setT(t: number): void;
  play(): void;
  pause(): void;
  togglePlay(): void;
  stepBy(n: number): void;
  setSpeed(i: number): void;
  setView(v: StrategyId): void;
  hoverRec(id: string | undefined, from?: 'card' | 'map'): void;
  focusRec(id: string | undefined): void;
  moveFocus(delta: number): void;
  openCopilot(question?: string, recId?: string): void;
  closeCopilot(): void;
  openOverride(id: string | undefined): void;
  setPreviewTeam(id: string | undefined): void;
  accept(rec: Recommendation): Promise<void>;
  override(rec: Recommendation, teamId: string, reason?: string): Promise<void>;
  /** Validates every recommendation of the current step in one action (the engine's whole plan). */
  acceptPlan(andContinue?: boolean): Promise<void>;
  /** Bumped when the manager must decide (the plan card flashes). */
  attention: number;
  /** True when the current step has a plan waiting for the manager's decision (play is blocked). */
  needsDecision(): boolean;
  resetDecisions(): Promise<void>;
  toast(t: Omit<Toast, 'id'>): void;
  dismissToast(id: number): void;
};

let toastSeq = 1;

/** Plans validated in the browser (step -> decisions). Validating the engine's own plan is not replayed on the server,
 *  so every timeline that comes back from the server (after a refusal, a team change, a reload) gets them re-applied:
 *  otherwise the earlier plans would vanish (journal empty, routes losing their plan colour, old plans asked again). */
const acceptedLocal: Record<number, Decision[]> = {};

function withLocal(tl: Timelines): Timelines {
  const steps = Object.keys(acceptedLocal).map(Number);
  if (!steps.length) return tl;
  const ours = tl.ours.slice();
  for (const j of steps) {
    const snap = ours[j];
    if (!snap) continue;
    const have = new Set(snap.decisions.map((d) => d.incidentId));
    const add = acceptedLocal[j].filter((d) => !have.has(d.incidentId));
    const decisions = [...snap.decisions, ...add];
    const incs = new Set(decisions.map((d) => d.incidentId));
    const teams = new Set(decisions.map((d) => d.teamId));
    ours[j] = { ...snap, decisions, recommendations: snap.recommendations.filter((r) => !incs.has(r.incidentId) && !teams.has(r.teamId)) };
  }
  return { ...tl, ours };
}

export const useStore = create<State>((set, get) => ({
  status: 'loading',
  t: 0,
  playing: false,
  speedIdx: 1, // ×10: 30 min of crisis in 3 s, teams and new outages visibly move between two plans
  view: 'ours',
  busy: false,
  toasts: [],
  copilotOpen: false,
  highlightSites: [],
  attention: 0,
  rulesCount: 0,

  openModal(m) {
    if (m) get().pause();
    set({ modal: m, hoveredOption: undefined, ...(m ? {} : { highlightSites: [] }) });
  },
  setHighlightSites(ids) {
    set({ highlightSites: ids });
  },
  hoverOption(rank) {
    if (get().hoveredOption !== rank) set({ hoveredOption: rank });
  },
  applyTimelines(timelines, toast) {
    const idx = currentRecs(get()).findIndex((r) => r.id === focusedRec(get())?.id);
    set({ timelines: withLocal(timelines) });
    keepFocusAt(idx);
    if (toast) get().toast(toast);
    get().refreshRules();
  },
  async refreshRules() {
    if (!source.listRules) return;
    try {
      const r = await source.listRules();
      set({ rulesCount: r.crisis.length + r.permanent.length });
    } catch {
      /* rules panel stays as is */
    }
  },
  async reload() {
    set({ busy: true });
    try {
      const [meta, timelines] = await Promise.all([source.loadMeta(), source.loadTimelines()]);
      set({ meta, timelines: withLocal(timelines) });
      get().refreshRules();
    } finally {
      set({ busy: false });
    }
  },

  async init() {
    if (source.live) return initLive();
    try {
      // Every page load is a fresh demo: the server forgets earlier decisions and crisis rules (instant when clean).
      const [meta, timelines] = await Promise.all([source.loadMeta(), source.acceptPlan ? source.reset() : source.loadTimelines()]);
      // Start on the first step with incidents, so the screen is never empty.
      const first = timelines.ours.findIndex((s) => s.incidents.length > 0);
      set({ meta, timelines, status: "ready", t: Math.max(0, first) * meta.stepMinutes });
      get().refreshRules();
    } catch (e) {
      set({ status: 'error', error: e instanceof Error ? e.message : String(e) });
    }
  },

  setT(t) {
    if (source.live) return; // live: the clock is the real one
    set({ t: Math.max(0, Math.min(endMinutes(get()), t)) });
  },
  needsDecision() {
    const s = get();
    return !source.live && !!source.acceptPlan && s.view === 'ours' && currentRecs(s).length > 0;
  },
  play() {
    if (source.live) return;
    const s = get();
    // The manager decides before the crisis goes on: a waiting plan must be validated or refused first.
    if (s.needsDecision()) {
      set({ attention: s.attention + 1 });
      s.toast({ tone: 'warn', title: 'Décision requise', body: 'Validez ou refusez le plan proposé avant de continuer la simulation.' });
      return;
    }
    if (s.t >= endMinutes(s)) set({ t: 0 });
    set({ playing: true, overrideRecId: undefined, previewTeamId: undefined });
  },
  pause() {
    if (source.live) return;
    const s = get();
    const step = s.meta?.stepMinutes ?? 30;
    // Snap to the step so the recommendations on screen match the clock.
    set({ playing: false, t: Math.floor(s.t / step + 1e-6) * step });
  },
  togglePlay() {
    if (get().playing) get().pause();
    else get().play();
  },
  stepBy(n) {
    if (source.live) return;
    const s = get();
    const step = s.meta?.stepMinutes ?? 30;
    const k = Math.floor(s.t / step + 1e-6) + n;
    set({ playing: false, t: Math.max(0, Math.min(endMinutes(s), k * step)) });
  },
  setSpeed(i) {
    set({ speedIdx: i });
  },
  setView(v) {
    set({ view: v, overrideRecId: undefined, previewTeamId: undefined, hoveredRecId: undefined });
  },
  hoverRec(id, from) {
    if (get().hoveredRecId !== id) set({ hoveredRecId: id, hoverFrom: from });
  },
  focusRec(id) {
    if (get().focusedRecId !== id) set({ focusedRecId: id });
  },
  moveFocus(delta) {
    const s = get();
    const recs = currentRecs(s);
    if (!recs.length) return;
    const i = Math.max(0, recs.findIndex((r) => r.id === focusedRec(s)?.id));
    const next = recs[Math.max(0, Math.min(recs.length - 1, i + delta))];
    set({ focusedRecId: next.id });
  },
  openCopilot(question, recId) {
    set({ copilotOpen: true, copilotRequest: question ? { id: copilotSeq++, question, recId } : get().copilotRequest });
  },
  closeCopilot() {
    set({ copilotOpen: false });
  },
  openOverride(id) {
    if (id) get().pause();
    set({ overrideRecId: id, previewTeamId: undefined });
  },
  setPreviewTeam(id) {
    if (get().previewTeamId !== id) set({ previewTeamId: id });
  },

  async accept(rec) {
    const s = get();
    if (s.busy) return;
    set({ busy: true });
    try {
      const idx = currentRecs(s).findIndex((r) => r.id === rec.id);
      const timelines = await source.accept(decisionInput(s, rec, rec.teamId));
      set({ timelines: withLocal(timelines) });
      keepFocusAt(idx);
      const team = teamLabel(s, rec.teamId);
      s.toast({ tone: 'ok', title: `Validée : ${team} → Poste ${incidentName(s, rec.incidentId)}` });
    } finally {
      set({ busy: false, hoveredRecId: undefined });
    }
  },

  async override(rec, teamId, reason) {
    const s = get();
    if (s.busy) return;
    set({ busy: true });
    try {
      const est = rec.alternatives.find((a) => a.teamId === teamId)?.deltaScore ?? 0;
      const idx = currentRecs(s).findIndex((r) => r.id === rec.id);
      const timelines = await source.override({ ...decisionInput(s, rec, teamId), reason });
      set({ timelines: withLocal(timelines), overrideRecId: undefined, previewTeamId: undefined, hoveredRecId: undefined });
      keepFocusAt(idx);
      get().toast({
        tone: 'info',
        title: `Modifiée : ${teamLabel(s, teamId)} → Poste ${incidentName(s, rec.incidentId)}`,
        body: `Coût estimé ${fmtDelta(est)} clients·h`,
      });
    } finally {
      set({ busy: false });
    }
  },

  async acceptPlan(andContinue) {
    const s = get();
    if (s.busy || !source.acceptPlan || !s.timelines) return;
    const recs = currentRecs(s);
    if (!recs.length) return;
    const k = stepOf(s);
    if (source.live) {
      // Live: the backend dispatches the teams now; the field reports their arrival and the end of the repairs.
      set({ busy: true });
      try {
        const timelines = await source.acceptPlan(k);
        set({ timelines, hoveredRecId: undefined, overrideRecId: undefined, focusedRecId: undefined });
        const clients = recs.reduce((a, r) => a + r.factors.clients, 0);
        get().toast({
          tone: 'ok',
          title: `Plan validé : ${recs.length} équipe${recs.length > 1 ? 's' : ''} en route`,
          body: `${fmtInt(clients)} clients concernés. Le moteur proposera le prochain plan dès qu’une alerte arrive ou qu’une équipe se libère.`,
        });
      } finally {
        set({ busy: false });
      }
      return;
    }
    // The engine's own plan is what the precomputed crisis already assumes: validating it changes nothing in the
    // projection, so it is applied here at once (no server recomputation) and only recorded on the server.
    acceptedLocal[k] = [
      ...(acceptedLocal[k] ?? []),
      ...recs.map((r) => ({ incidentId: r.incidentId, teamId: r.teamId, kind: 'accepted' as const, recommendedTeamId: r.teamId })),
    ];
    const ours = s.timelines.ours.slice();
    ours[k] = {
      ...ours[k],
      recommendations: [],
      decisions: [
        ...ours[k].decisions,
        ...recs.map((r) => ({ incidentId: r.incidentId, teamId: r.teamId, kind: 'accepted' as const, recommendedTeamId: r.teamId })),
      ],
    };
    set({ timelines: { ...s.timelines, ours }, hoveredRecId: undefined, overrideRecId: undefined, focusedRecId: undefined });
    source.recordPlan?.(k).catch(() => {});
    const clients = recs.reduce((a, r) => a + r.factors.clients, 0);
    get().toast({
      tone: 'ok',
      title: `Plan validé : ${recs.length} équipe${recs.length > 1 ? 's' : ''} en route`,
      body: `${fmtInt(clients)} clients concernés. La simulation reprend jusqu’au prochain plan.`,
    });
    if (andContinue) setTimeout(() => get().play(), 0);
  },

  async resetDecisions() {
    set({ busy: true });
    try {
      const timelines = await source.reset();
      for (const key of Object.keys(acceptedLocal)) delete acceptedLocal[Number(key)];
      set({ timelines, overrideRecId: undefined });
      get().toast({ tone: 'info', title: 'Décisions annulées' });
    } finally {
      set({ busy: false });
    }
  },

  toast(t) {
    const id = toastSeq++;
    set({ toasts: [...get().toasts.slice(-2), { ...t, id }] });
    setTimeout(() => get().dismissToast(id), 6000);
  },
  dismissToast(id) {
    set({ toasts: get().toasts.filter((x) => x.id !== id) });
  },
}));

// ---- selectors & helpers ------------------------------------------------

export function endMinutes(s: Pick<State, 'timelines' | 'meta'>): number {
  if (!s.timelines || !s.meta) return 0;
  if (s.meta.mode === 'live') return Math.max(0, (Date.parse(s.timelines.ours[s.timelines.ours.length - 1].time) - Date.parse(s.meta.start)) / 60000);
  return (s.timelines.ours.length - 1) * s.meta.stepMinutes;
}

export const stepOf = (s: Pick<State, 't' | 'meta' | 'timelines'>) => {
  if (!s.meta || !s.timelines) return 0;
  if (s.meta.mode === 'live') return Math.max(0, s.timelines.ours.length - 1); // live: always the current state
  return Math.min(s.timelines.ours.length - 1, Math.floor(s.t / s.meta.stepMinutes + 1e-6));
};

/** Snapshot currently displayed (strategy shown on the map). */
export function useSnapshot(): Snapshot | undefined {
  return useStore((s) => (s.timelines ? s.timelines[s.view][stepOf(s)] : undefined));
}

/** Snapshot of our strategy (decisions apply to it). */
export function useOursSnapshot(): Snapshot | undefined {
  return useStore((s) => (s.timelines ? s.timelines.ours[stepOf(s)] : undefined));
}

export const useStep = () => useStore(stepOf);

let copilotSeq = 1;

const currentRecs = (s: State) => (s.timelines ? s.timelines.ours[stepOf(s)].recommendations : []);

/** The focused recommendation, or the first of the queue when the focus is gone. */
export function focusedRec(s: State): Recommendation | undefined {
  const recs = currentRecs(s);
  return recs.find((r) => r.id === s.focusedRecId) ?? recs[0];
}
export const useFocusedRec = () => useStore((s) => (s.view === 'ours' ? focusedRec(s) : undefined));

/** After a decision, the recommendation that slid into the same place takes the focus. */
function keepFocusAt(idx: number) {
  const recs = currentRecs(useStore.getState());
  const next = recs[Math.min(Math.max(0, idx), recs.length - 1)];
  useStore.setState({ focusedRecId: next?.id });
}

function decisionInput(s: State, rec: Recommendation, teamId: string): DecisionInput {
  return {
    step: stepOf(s),
    recommendationId: rec.id,
    incidentId: rec.incidentId,
    teamId,
    recommendedTeamId: rec.teamId,
  };
}

function teamLabel(s: State, id: string) {
  return s.timelines?.ours[stepOf(s)].teams.find((t) => t.id === id)?.label ?? id;
}
function incidentName(s: State, id: string) {
  return s.timelines?.ours[stepOf(s)].incidents.find((i) => i.id === id)?.commune ?? id;
}

/** Live mode: load the crisis, then poll the backend every second (alerts, field reports, new plans). */
async function initLive() {
  const live = source.live!;
  const load = async () => {
    const [meta, timelines] = await Promise.all([source.loadMeta(), source.loadTimelines()]);
    useStore.setState({ meta, timelines, status: 'ready', t: live.nowMinutes() });
    useStore.getState().refreshRules();
  };
  try {
    await load();
  } catch (e) {
    useStore.setState({ status: 'error', error: e instanceof Error ? e.message : String(e) });
    return;
  }
  let polling = false;
  setInterval(async () => {
    const s = useStore.getState();
    if (polling || s.busy) return;
    polling = true;
    try {
      const { timelines, restarted } = await live.poll();
      if (restarted) {
        useStore.setState({ meta: await source.loadMeta(), focusedRecId: undefined });
        useStore.getState().toast({ tone: 'info', title: 'Nouvelle crise ouverte', body: 'Le terrain a ouvert une nouvelle crise : le tableau de bord repart de zéro.' });
      }
      const idx = currentRecs(useStore.getState()).findIndex((r) => r.id === focusedRec(useStore.getState())?.id);
      useStore.setState({ timelines, t: live.nowMinutes(), status: 'ready' });
      keepFocusAt(idx);
    } catch {
      /* backend restarting: keep the last state, try again */
    } finally {
      polling = false;
    }
  }, 1000);
}

/** The display mode of this page (live = real time, replay = a past crisis). */
export const pageMode = mode;

if (import.meta.env.DEV) (window as unknown as { __store?: unknown }).__store = useStore;
