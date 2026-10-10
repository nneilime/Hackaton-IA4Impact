// Navigation du diapo : une slide à la fois, une transition entre deux, l'entrée de la nouvelle slide,
// puis l'arrêt de tout ce qui tournait sur l'ancienne. L'état (slide courante) est exposé à React par un store.
import { enterBlocks, leaveSlide } from "./enter";
import { SlideRun, type SlideCtx } from "./loop";
import { TRANSITIONS, type TransEnv, type TransKind } from "./transitions";
import { reduceMotion } from "./util";

export type Tone = "dark" | "light" | "red-bg";

/** Une slide : son contenu (React) et son comportement à l'entrée et à la sortie */
export interface SlideDef {
  id: string;
  tone: Tone;
  /** classe de style de la slide (s-cover, s-route…) */
  cls: string;
  /** transition utilisée pour arriver sur cette slide (et en repartir en arrière) */
  trans?: TransKind;
  Body: () => JSX.Element;
  enter?: (ctx: SlideCtx) => void;
  leave?: (el: HTMLElement) => void;
}

export interface DeckState { cur: number; total: number; dir: 1 | -1 }

export class DeckEngine {
  private state: DeckState;
  private listeners = new Set<() => void>();
  private runs = new Map<HTMLElement, SlideRun>();
  private busy = false;
  private queued: number | null = null;
  private env: TransEnv;

  constructor(private slides: { el: HTMLElement; def: SlideDef }[], stage: HTMLElement, layer: HTMLElement) {
    this.state = { cur: -1, total: slides.length, dir: 1 };
    this.env = { stage, layer, enter: (el, delay) => this.enter(el, delay) };
  }

  // ── Store pour React (useSyncExternalStore) ──
  subscribe = (f: () => void) => { this.listeners.add(f); return () => this.listeners.delete(f); };
  getState = () => this.state;
  private set(s: Partial<DeckState>) { this.state = { ...this.state, ...s }; this.listeners.forEach((f) => f()); }

  private defOf(el: HTMLElement) { return this.slides.find((s) => s.el === el)!.def; }

  private enter(el: HTMLElement, t0: number) {
    this.runs.get(el)?.stop();
    const run = new SlideRun();
    this.runs.set(el, run);
    enterBlocks(el, t0, run);
    this.defOf(el).enter?.({ el, t0: reduceMotion ? 0 : t0, run });
  }

  private leave(el: HTMLElement) {
    const run = this.runs.get(el);
    if (run) leaveSlide(el, run);
    else el.classList.remove("on", "shown");
    this.defOf(el).leave?.(el);
  }

  go = (n: number, fast = false) => {
    if (!this.slides.length) return; // diapo vide (slides retirées le temps de les remettre)
    n = Math.max(0, Math.min(this.slides.length - 1, n));
    const { cur } = this.state;
    if (n === cur) return;
    if (this.busy) { this.queued = n; return; }
    const prev = this.slides[cur]?.el, next = this.slides[n].el, dir = n > cur ? 1 : -1;
    this.set({ cur: n, dir });
    history.replaceState(null, "", `#${n + 1}`); // l'URL garde ?lite / ?story
    const tone = this.slides[n].def.tone;
    document.body.classList.toggle("bg-light", tone === "light");
    document.body.classList.toggle("bg-red", tone === "red-bg");
    if (!prev || reduceMotion) {
      if (prev) this.leave(prev);
      next.classList.add("shown");
      next.style.zIndex = "2";
      this.enter(next, prev ? 0 : 300);
      return;
    }
    this.busy = true;
    prev.style.zIndex = "1";
    next.style.zIndex = "2";
    next.classList.add("shown");
    const kind = this.slides[dir > 0 ? n : cur].def.trans ?? "train";
    TRANSITIONS[kind](this.env, prev, next, dir, () => {
      this.leave(prev);
      prev.style.zIndex = "";
      this.busy = false;
      if (this.queued != null) { const q = this.queued; this.queued = null; this.go(q, true); }
    }, fast);
  };

  next = () => this.go(this.state.cur + 1);
  prev = () => this.go(this.state.cur - 1);

  /** Démontage (rechargement à chaud) : la slide courante s'arrête proprement */
  destroy() {
    const el = this.slides[this.state.cur]?.el;
    if (el) this.leave(el);
    this.listeners.clear();
  }
}
