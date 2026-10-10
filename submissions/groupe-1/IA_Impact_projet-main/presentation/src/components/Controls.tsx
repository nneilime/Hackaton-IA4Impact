// Commandes du diapo : plein écran, précédente / suivante, ligne de train (une gare par slide) et compteur.
// Elles se cachent quand la souris ne bouge plus.
import { useEffect, useState, useSyncExternalStore, type MouseEvent } from "react";
import type { DeckEngine } from "../engine/deck";
import { T } from "../textes";

const pad = (n: number) => String(n).padStart(2, "0");

export function useFullscreen() {
  const get = () => !!document.fullscreenElement;
  const [isFs, setFs] = useState(get);
  useEffect(() => {
    const on = () => { setFs(get()); document.body.classList.toggle("is-fs", get()); };
    document.addEventListener("fullscreenchange", on);
    return () => document.removeEventListener("fullscreenchange", on);
  }, []);
  const toggle = () => (get() ? document.exitFullscreen() : document.documentElement.requestFullscreen()).catch(() => {});
  return { isFs, toggle, supported: !!document.documentElement.requestFullscreen };
}

export function Controls({ engine, fs }: { engine: DeckEngine; fs: ReturnType<typeof useFullscreen> }) {
  const { cur, total, dir } = useSyncExternalStore(engine.subscribe, engine.getState);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    let timer = 0;
    const wake = () => {
      setHidden(false);
      document.body.style.cursor = "";
      clearTimeout(timer);
      timer = window.setTimeout(() => { setHidden(true); document.body.style.cursor = "none"; }, 2600);
    };
    const evs = ["mousemove", "pointerdown", "keydown"] as const;
    evs.forEach((e) => addEventListener(e, wake));
    wake();
    return () => { evs.forEach((e) => removeEventListener(e, wake)); clearTimeout(timer); };
  }, []);

  const f = total > 1 ? Math.max(0, cur) / (total - 1) : 0;
  const at = (k: number) => `calc(6px + (100% - 12px) * ${k})`;
  const stop = (fn: () => void) => (e: MouseEvent) => { e.stopPropagation(); fn(); };

  return (
    <div className={`ui${hidden ? " hide" : ""}`}>
      <div className="ui-top">
        {fs.supported && (
          <button className="btn" type="button" onClick={stop(fs.toggle)}>
            <svg viewBox="0 0 24 24" className="fs-open"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></svg>
            <svg viewBox="0 0 24 24" className="fs-close"><path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" /></svg>
            <span>{fs.isFs ? T.exitFullscreen : T.fullscreen}</span>
          </button>
        )}
      </div>
      <div className="ui-bottom">
        <button className="btn round" type="button" onClick={stop(engine.prev)}>
          <svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7" /></svg><span className="sr-only">{T.prev}</span>
        </button>
        <div className="progress">
          <i />
          <i className="fill" style={{ width: `calc((100% - 12px) * ${f})` }} />
          {Array.from({ length: total }, (_, i) => (
            <button key={i} className={`stn${i <= cur ? " done" : ""}`} type="button" title={`${i + 1}`} style={{ left: at(total > 1 ? i / (total - 1) : 0) }} onClick={stop(() => engine.go(i))} />
          ))}
          <i className={`loco${dir < 0 ? " back" : ""}`} style={{ left: at(f) }} />
        </div>
        <span className="count">{`${pad(cur + 1)} / ${pad(total)}`}</span>
        <button className="btn round" type="button" onClick={stop(engine.next)}>
          <svg viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" /></svg><span className="sr-only">{T.next}</span>
        </button>
      </div>
    </div>
  );
}
