// Boucle d'animation partagée : chaque slide y inscrit ses « tickers » (une fonction appelée à chaque image)
// et ses minuteurs, et les retire tous d'un coup en partant.

/** Appelée à chaque image ; renvoyer `false` la retire de la boucle */
export type Ticker = (now: number) => boolean | void;

const tickers = new Set<Ticker>();
(function loop(now: number) {
  for (const f of tickers) if (f(now) === false) tickers.delete(f);
  requestAnimationFrame(loop);
})(performance.now());

/** Ce qui tourne pour une slide pendant qu'elle est à l'écran */
export class SlideRun {
  private tickers: Ticker[] = [];
  private timers: number[] = [];

  tick(f: Ticker) {
    tickers.add(f);
    this.tickers.push(f);
  }

  later(ms: number, f: () => void) {
    this.timers.push(window.setTimeout(f, ms));
  }

  stop() {
    this.tickers.forEach((f) => tickers.delete(f));
    this.timers.forEach(clearTimeout);
    this.tickers = [];
    this.timers = [];
  }
}

/** Ce que reçoit le comportement propre à une slide à son entrée */
export interface SlideCtx {
  el: HTMLElement;
  /** délai (ms) avant que les blocs commencent à entrer */
  t0: number;
  run: SlideRun;
}
