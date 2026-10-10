import { useEffect } from 'react';
import { source } from '../data/source';
import { fmtHour } from '../lib/format';
import { SPEEDS, endMinutes, focusedRec, useStore } from './store';

/** Drives the crisis clock while playing, and the keyboard shortcuts. */
export function useClock() {
  const playing = useStore((s) => s.playing);

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    // The clock advances with real elapsed time, but the store (hence the map, the timeline and the panel) is updated
    // at most ~20 times a second: per-frame updates made heavy frames crawl at ×60. Elapsed time is capped at 0.5 s
    // so a background tab does not jump hours ahead when it comes back.
    const tick = (now: number) => {
      if (now - last >= 50) {
        const dt = Math.min(0.5, (now - last) / 1000);
        last = now;
        const s = useStore.getState();
        if (!s.playing) return;
        const end = endMinutes(s);
        const next = s.t + dt * SPEEDS[s.speedIdx].minPerSec;
        if (next >= end) {
          useStore.setState({ t: end });
          s.pause();
          return;
        }
        // A new plan proposed on the way: stop there, the manager decides before the crisis goes on.
        const step = s.meta?.stepMinutes ?? 30;
        const k0 = Math.floor(s.t / step + 1e-6);
        const k1 = Math.floor(next / step + 1e-6);
        for (let k = k0 + 1; k <= k1 && s.timelines; k++) {
          if (s.view === 'ours' && source.acceptPlan && s.timelines.ours[k]?.recommendations.length) {
            useStore.setState({ t: k * step, playing: false, attention: s.attention + 1 });
            s.toast({ tone: 'info', title: `Nouveau plan proposé à ${fmtHour(s.timelines.ours[k].time)}`, body: 'Validez-le ou refusez-le pour continuer.' });
            return;
          }
        }
        useStore.setState({ t: next });
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest('input, textarea, [contenteditable]')) return;
      const s = useStore.getState();
      if (s.overrideRecId) return; // the "Changer d'équipe" panel has its own keys
      if (e.key === 'Escape' && s.copilotOpen) {
        s.closeCopilot();
      } else if (e.code === 'Space') {
        e.preventDefault();
        s.togglePlay();
      } else if (e.key === 'ArrowRight') {
        s.stepBy(1);
      } else if (e.key === 'ArrowLeft') {
        s.stepBy(-1);
      } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        s.moveFocus(e.key === 'ArrowDown' ? 1 : -1);
      } else if (e.key === 'Enter' && !el.closest('button, a, [role=radio], [role=tab]')) {
        const rec = focusedRec(s);
        if (rec && s.view === 'ours') {
          e.preventDefault();
          // plan mode: Enter validates the whole plan (instant), like the main button
          if (source.acceptPlan) s.acceptPlan(true);
          else s.accept(rec);
        }
      } else if ((e.key === 'c' || e.key === 'C') && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const rec = focusedRec(s);
        if (rec && s.view === 'ours' && rec.alternatives.length) s.openOverride(rec.id);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
}
