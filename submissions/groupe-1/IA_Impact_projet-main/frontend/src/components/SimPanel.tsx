import { useEffect, useRef, useState, useSyncExternalStore, type RefObject } from "react";
import type { Place } from "../api";
import { formatMinutes, useI18n } from "../i18n";
import { SPEEDS, type TrainSim } from "../sim";
import type { Discovery } from "../data/discoveries";
import TrainWindows from "./TrainWindow";

type Props = {
  sim: TrainSim;
  byId: Map<string, Place>;
  onStop: () => void;
  onOpenDiscovery: (d: Discovery) => void;
};

// Pictogrammes Material Icons (Apache 2.0) : les glyphes ❚❚ / ▶ ne s'affichent pas dans la police du site
const ICON = {
  play: "M8 5v14l11-7z",
  pause: "M6 19h4V5H6v14zm8-14v14h4V5h-4z",
  replay: "M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z",
};

// Hauteur d'un bandeau du bas (simulation, recommandations) publiée en variable CSS : la bulle de l'assistant se pose juste au-dessus
export function useBottomHeight(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const html = document.documentElement.style;
    const ro = new ResizeObserver(() => html.setProperty("--sim-h", `${el.offsetHeight}px`));
    ro.observe(el);
    return () => {
      ro.disconnect();
      html.removeProperty("--sim-h");
    };
  }, [root]);
}

// Bandeau de la simulation, en bas de la page : où en est le train, et ce qu'il y a à voir autour de lui. Le corps se replie.
export default function SimPanel({ sim, byId, onStop, onOpenDiscovery }: Props) {
  const { t } = useI18n();
  const snap = useSyncExternalStore(sim.subscribe, sim.getSnapshot);
  // Ouvert d'office, y compris sur téléphone où les hublots sont assez petits pour ne pas manger la carte
  const [open, setOpen] = useState(true);
  const bar = useRef<HTMLDivElement>(null);
  const root = useRef<HTMLElement>(null);
  const name = (id: string) => byId.get(id)?.name ?? id;

  // Barre de progression mise à jour à chaque image, sans repasser par React
  useEffect(
    () =>
      sim.subscribe(() => {
        bar.current?.style.setProperty("--p", String(sim.minute / sim.total));
      }),
    [sim],
  );

  useBottomHeight(root);

  const { state } = snap;
  const status =
    state.kind === "arrived" ? t.simArrived(name(state.stopId))
      : state.kind === "stopped" ? (state.leg > 0 && sim.route.legs[state.leg].from_id === state.stopId && snap.minute > 0 ? t.simChange(name(state.stopId)) : t.simAt(name(state.stopId)))
        : t.simBetween(name(state.fromId), name(state.toId));


  return (
    <section ref={root} className={open ? "sim open" : "sim"} aria-label={t.simTitle}>
      <div className="sim-head">
        <button className="sim-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          <span className="sim-live" aria-hidden="true" />
          <span className="sim-title">{t.simTitle}</span>
          <span className="sim-clock">
            {formatMinutes(snap.minute)} / {formatMinutes(Math.round(sim.total))}
          </span>
          <span className="sim-chevron" aria-hidden="true">▾</span>
        </button>
        <button className="sim-close" onClick={onStop} aria-label={t.simStop} title={t.simStop}>
          ×
        </button>
      </div>

      <div
        ref={bar}
        className="sim-bar"
        role="slider"
        aria-label={t.simProgress}
        aria-valuemin={0}
        aria-valuemax={Math.round(sim.total)}
        aria-valuenow={snap.minute}
        tabIndex={0}
        onPointerDown={(e) => {
          // React remet currentTarget à null après l'événement : on garde l'élément pour le glissé
          const el = e.currentTarget;
          const seek = (x: number) => {
            const r = el.getBoundingClientRect();
            sim.seek((x - r.left) / r.width);
          };
          e.preventDefault();
          el.setPointerCapture(e.pointerId);
          seek(e.clientX);
          const move = (ev: PointerEvent) => seek(ev.clientX);
          const end = () => {
            el.removeEventListener("pointermove", move);
            el.removeEventListener("pointerup", end);
            el.removeEventListener("pointercancel", end);
          };
          el.addEventListener("pointermove", move);
          el.addEventListener("pointerup", end);
          el.addEventListener("pointercancel", end);
        }}
        onKeyDown={(e) => {
          const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
          if (step) sim.seek((sim.minute + step) / sim.total);
        }}
      >
        <span />
      </div>

      <div className="sim-controls">
        <button className="sim-play" onClick={() => sim.toggle()} aria-label={snap.playing ? t.simPause : t.simPlay}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d={snap.playing ? ICON.pause : state.kind === "arrived" ? ICON.replay : ICON.play} />
          </svg>
        </button>
        <p className="sim-status">{status}</p>
        <div className="sim-speed" role="group" aria-label={t.simSpeed}>
          {SPEEDS.map((s) => (
            <button key={s} aria-pressed={snap.speed === s} onClick={() => sim.setSpeed(s)}>
              ×{s}
            </button>
          ))}
        </div>
      </div>

      <div className="sim-body">
        <div className="sim-inner">
          <TrainWindows sim={sim} byId={byId} onOpenDiscovery={onOpenDiscovery} />
        </div>
      </div>
    </section>
  );
}
