import { useEffect, useRef, useState } from 'react';
import { fmtClock, fmtDay, fmtInt } from '../lib/format';
import { liveAvailable, mode, source } from '../data/source';
import { stepOf, useStore } from '../state/store';
import { WarningIcon } from './WarningIcon';

const TARGET_HOURS = 48;
const CLOSE_HOURS = 42;
const HOUR = 3600_000;
const weekdayFmt = new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', weekday: 'long' });
const hourFmt = new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', hour: 'numeric', hourCycle: 'h23' });
const hourOnly = (ms: number) => `${Number(hourFmt.formatToParts(ms).find((p) => p.type === 'hour')?.value ?? 0)} h`;
const signedHours = (d: number) => {
  const a = Math.abs(d);
  return `${d < 0 ? '−' : '+'}${a >= 1 ? Math.round(a) : a.toFixed(1).replace('.', ',')} h`;
};

function Clock() {
  const t = useStore((s) => s.t);
  const start = useStore((s) => Date.parse(s.meta!.start));
  const now = start + t * 60000;
  return (
    <div className="clock">
      <div className="clock-time">{fmtClock(now)}</div>
      <div className="clock-date">{fmtDay(now)}</div>
    </div>
  );
}

/** Critical state only flips when the estimate crosses 48 h; an unknown estimate keeps it. */
function useOverTarget(hours: number | null) {
  const state = useRef(false);
  if (hours !== null) {
    if (!state.current && hours > TARGET_HOURS) state.current = true;
    else if (state.current && hours <= TARGET_HOURS) state.current = false;
  }
  return state.current;
}

/** Shows how much the estimate moved (decision or new incidents), for a few seconds. */
function useRecentChange(hours: number | null, step: number) {
  const prev = useRef<{ hours: number | null; step: number } | null>(null);
  const [change, setChange] = useState<{ d: number; id: number } | null>(null);
  useEffect(() => {
    const p = prev.current;
    prev.current = { hours, step };
    // Ignore jumps of the playhead (scrubbing): only same or next step.
    if (!p || p.hours === null || hours === null || Math.abs(step - p.step) > 1) return;
    const d = hours - p.hours;
    if (Math.abs(d) < 0.5) return;
    const id = Date.now();
    setChange({ d, id });
    const timer = setTimeout(() => setChange((c) => (c?.id === id ? null : c)), 4000);
    return () => clearTimeout(timer);
  }, [hours, step]);
  return change;
}

/**
 * The 90 % / 48 h service target (90 % of the incidents reported so far repaired within 48 h of the crisis start,
 * per the current plan). Quiet chip while it holds; red alert card with the reinforcement action when it does not.
 */
function Restore90() {
  const k = useStore(stepOf);
  const hours = useStore((s) => s.timelines!.ours[k].kpis.restore90Hours);
  const open = useStore((s) => s.timelines!.ours[k].incidents.some((i) => i.status !== 'restored'));
  const start = useStore((s) => Date.parse(s.meta!.start));
  const t = useStore((s) => s.t);
  const critical = useOverTarget(hours);
  const change = useRecentChange(hours, k);
  const [pinned, setPinned] = useState(false);

  const h = hours === null ? null : Math.ceil(hours);
  const when = h === null ? null : Math.ceil((start + (hours as number) * HOUR) / HOUR) * HOUR;
  const whenText = when === null ? '' : `${weekdayFmt.format(when)} vers ${hourOnly(when)}`;
  // Once the moment has passed it is a fact, not an estimate.
  const reached = hours !== null && hours * 60 <= t;
  const missed = critical || (h === null && open);

  if (!missed) {
    const tip =
      h === null
        ? 'Objectif : 90 % des incidents signalés réparés dans les 48 h suivant le début de la crise.'
        : reached
          ? `90 % des incidents signalés ont été réparés en ${h} h (objectif 48 h).`
          : `90 % des incidents signalés seront réparés avant 48 h selon le plan actuel (prévu ${whenText}, ${TARGET_HOURS - h} h d’avance).`;
    return (
      <div className="target-chip" role="status" title={tip} aria-label={tip}>
        <span className="target-ok" aria-hidden>
          ✓
        </span>
        <span>
          <b>Objectif 48 h tenu</b>
          <small>{h === null ? '90 % des incidents en 48 h' : reached ? `90 % réparés en ${h} h` : `90 % réparés ${whenText}`}</small>
        </span>
        {h !== null && !reached && h > CLOSE_HOURS && <span className="target-warn">marge faible</span>}
      </div>
    );
  }

  const late = h === null ? null : h - TARGET_HOURS;
  return (
    <section className="target-alert" role="alert" aria-label="Objectif 48 h menacé">
      <div className="target-alert-text">
        <b>
          <WarningIcon tone="critical" /> Objectif 48 h menacé
        </b>
        <span>
          {h === null
            ? 'Le plan actuel n’atteint pas 90 % des incidents réparés.'
            : `90 % des incidents réparés seulement ${reached ? `en ${h} h` : whenText} (+${late} h)`}
          {change && (
            <span key={change.id} className={`r90-delta ${change.d < 0 ? 'better' : 'worse'}`}>
              {' '}
              {signedHours(change.d)}
            </span>
          )}
        </span>
      </div>
      <span className={`fire ${pinned ? 'pinned' : ''}`}>
        <button
          className="fire-pill"
          onClick={() => (source.reinforcement ? useStore.getState().openModal({ kind: 'reinforcement' }) : setPinned(!pinned))}
          aria-describedby="fire-tip"
        >
          {source.reinforcement ? 'Chiffrer les renforts' : 'FIRE'}
        </button>
        <span className="fire-tip" id="fire-tip" role="tooltip">
          Renfort FIRE : combien d’équipes en plus, et sur quels sites, pour revenir sous 48 h.
        </span>
      </span>
    </section>
  );
}

function Stat({ value, label, sub, abnormal }: { value: string | number; label: string; sub?: string; abnormal?: boolean }) {
  return (
    <div className={`stat ${abnormal ? 'abnormal' : ''}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">
        {value}
        {sub && <small>{sub}</small>}
      </span>
    </div>
  );
}

const ICONS = {
  rules: 'M5 6h14M5 12h14M5 18h9',
  review: 'M4 12a8 8 0 0 1 14-5.3M20 12a8 8 0 0 1-14 5.3M18 3v4h-4M6 21v-4h4',
};
const Icon = ({ d }: { d: string }) => (
  <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

/** Slim top bar: product, which crisis (live or a past one), engine status, switch between the two modes. */
export function TopBar() {
  const view = useStore((s) => s.view);
  const meta = useStore((s) => s.meta!);
  const started = useStore((s) => s.timelines!.ours.some((x) => x.incidents.length > 0));
  const speed = meta.speed ?? 1;
  const goto = (q: string) => (location.search = q);
  return (
    <header className="topbar">
      <img className="logo" src={`${import.meta.env.BASE_URL}logo-enedispo.png`} alt="EnedisPO" />
      <span className="topbar-sep" aria-hidden />
      <div className="topbar-title">
        <b>Pilotage de crise</b>
        {mode === 'live' ? (
          <span>
            {started ? `Crise en cours depuis ${fmtClock(Date.parse(meta.start))}, ${fmtDay(Date.parse(meta.start))}` : 'En veille : aucune alerte pour le moment'}
            {' '}· Ariège, Haute-Garonne, Gers
          </span>
        ) : (
          <span>
            {meta.crisisId === 'CRISE_DEMO'
              ? `Scénario de démonstration : une tempête qui s’intensifie · ${fmtDay(Date.parse(meta.start))} (temps accéléré) · Gers, Haute-Garonne, Ariège`
              : `Revue de la crise ${meta.crisisId.replace('CRISE_', 'n° ')} du ${fmtDay(Date.parse(meta.start))} (temps accéléré) · Ariège, Haute-Garonne, Gers`}
          </span>
        )}
      </div>
      <div className="topbar-right">
        {view === 'reference' && <span className="badge">Vue stratégie de référence</span>}
        {mode === 'live' ? (
          <span className="live-badge" title={speed > 1 ? `Horloge accélérée ×${speed} pour la démonstration` : 'Horloge réelle'}>
            <i aria-hidden /> En direct{speed > 1 ? ` · ×${speed}` : ''}
          </span>
        ) : (
          <span className="engine-status">
            <i aria-hidden /> {source.explainPlan ? 'Moteur et IA connectés' : 'Données de démonstration'}
          </span>
        )}
        {liveAvailable &&
          (mode === 'live' ? (
            <button className="pill small" onClick={() => goto('?mode=replay')} title="Rejouer une crise passée en temps accéléré et voir ce qui a été fait">
              Revoir une crise passée
            </button>
          ) : (
            <button className="pill small primary" onClick={() => goto('')}>
              Revenir au direct
            </button>
          ))}
      </div>
    </header>
  );
}

/** Dark left rail: the clock, the situation in figures, the 48 h target, the learning tools. */
export function Rail() {
  const k = useStore(stepOf);
  const kp = useStore((s) => s.timelines![s.view][k].kpis);
  const rulesCount = useStore((s) => s.rulesCount);
  const { openModal } = useStore.getState();
  const teamsTotal = kp.teamsAvailable + kp.teamsBusy + kp.teamsResting;
  const noTeam = kp.teamsAvailable === 0 && kp.incidentsWaiting > 0;
  return (
    <nav className="rail" aria-label="Situation">
      <section className="rail-block">
        <h2 className="rail-h">Heure de la crise</h2>
        <Clock />
      </section>
      <section className="rail-block">
        <h2 className="rail-h">Situation</h2>
        <Stat value={fmtInt(kp.clientsCut)} label="Clients coupés" sub={`${fmtInt(kp.clientsRestored)} réalimentés`} />
        <Stat value={fmtInt(kp.incidentsWaiting)} label="Incidents en attente" />
        <Stat value={kp.teamsAvailable} label="Équipes disponibles" sub={`sur ${teamsTotal}`} abnormal={noTeam} />
      </section>
      <section className="rail-block">
        <h2 className="rail-h">Objectif de service</h2>
        <Restore90 />
      </section>
      <section className="rail-block rail-tools">
        <h2 className="rail-h">Apprentissage</h2>
        {source.listRules && (
          <button className="rail-item" onClick={() => openModal({ kind: 'rules' })}>
            <Icon d={ICONS.rules} />
            <span>Consignes de la crise</span>
            <span className="rail-count">{rulesCount}</span>
          </button>
        )}
        {source.learning && (
          <button className="rail-item" onClick={() => openModal({ kind: 'review' })}>
            <Icon d={ICONS.review} />
            <span>Retour d’expérience</span>
          </button>
        )}
      </section>
    </nav>
  );
}
