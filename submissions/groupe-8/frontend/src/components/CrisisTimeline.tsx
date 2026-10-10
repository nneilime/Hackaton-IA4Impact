import { useMemo, useRef, useState } from 'react';
import type { Snapshot } from '../data/contract';
import { fmtHour, fmtInt, fmtMinutes, parisHour } from '../lib/format';
import { mode } from '../data/source';
import { SPEEDS, endMinutes, stepOf, useStore } from '../state/store';
import { useSize } from './useWidth';

/*
 * The course of the crisis on one axis: what happened (solid, left of the cursor),
 * what the current plan projects (light, dashed, right of it), new incidents, team
 * capacity, and the milestones written on the axis. Our strategy only.
 */

const TARGET_H = 48;
const G = { left: 76, right: 16, flags: 36, arrivals: 14, capacity: 30, gap: 6, axis: 18 };
const FLAG_FONT = 12;
const HOUR = 3600_000;

const weekdayFmt = new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', weekday: 'long' });
const dayShortFmt = new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', weekday: 'short' });
/** "lun. 06 h" */
const axisLabel = (ms: number) => `${dayShortFmt.format(ms)} ${String(parisHour(ms)).padStart(2, '0')} h`;
/** "lundi à 2 h" (rounded up to the hour, like the 48 h target status) */
const whenLabel = (ms: number) => {
  const up = Math.ceil(ms / HOUR) * HOUR;
  return `${weekdayFmt.format(up)} à ${parisHour(up)} h`;
};
const niceStep = (max: number) => [500, 1000, 2000, 2500, 5000, 10000, 20000, 50000].find((s) => max / s <= 4) ?? 100000;

type Series = {
  minutes: number[]; // time of each step since snapshot 0
  cut: number[];
  arrivals: number[];
  busy: number[];
  resting: number[];
  waiting: number[];
  teams: number;
  firstMin: number; // first incident
  endMin: number; // last restoration (end of crisis)
  endIdx: number;
  peakIdx: number;
  restoredAt: Map<string, number>; // incident -> minutes of first snapshot showing it restored
};

function buildSeries(snaps: Snapshot[], start: number): Series {
  const n = snaps.length;
  // Snapshots are placed by their own time: regular steps in a replay, irregular in live mode (one every few minutes
  // plus one after each decision).
  const minutes = snaps.map((x) => (Date.parse(x.time) - start) / 60000);
  const reportedMin = (iso: string) => (Date.parse(iso) - start) / 60000;
  const all = snaps[n - 1].incidents;
  const firstMin = all.length ? Math.min(...all.map((i) => reportedMin(i.reportedAt))) : 0;
  const arrivals = new Array(n).fill(0);
  for (const i of all) arrivals[nearestIdx(minutes, reportedMin(i.reportedAt), true)]++;
  const lastReport = all.length ? Math.max(...all.map((i) => reportedMin(i.reportedAt))) : 0;
  let endIdx = n - 1;
  for (let i = 0; i < n; i++)
    if (minutes[i] >= lastReport && snaps[i].kpis.clientsCut === 0) {
      endIdx = i;
      break;
    }
  const cut = snaps.map((s) => s.kpis.clientsCut);
  let peakIdx = 0;
  cut.forEach((v, i) => v > cut[peakIdx] && (peakIdx = i));
  const restoredAt = new Map<string, number>();
  snaps.forEach((s, i) => {
    for (const inc of s.incidents) if (inc.status === 'restored' && !restoredAt.has(inc.id)) restoredAt.set(inc.id, minutes[i]);
  });
  const k0 = snaps[0].kpis;
  return {
    minutes,
    cut,
    arrivals,
    busy: snaps.map((s) => s.kpis.teamsBusy),
    resting: snaps.map((s) => s.kpis.teamsResting),
    waiting: snaps.map((s) => s.kpis.incidentsWaiting),
    teams: k0.teamsAvailable + k0.teamsBusy + k0.teamsResting,
    firstMin,
    endMin: minutes[endIdx],
    endIdx,
    peakIdx,
    restoredAt,
  };
}

/** Index of the snapshot at minute m (the first at or after it when `ceil`, else the closest). */
function nearestIdx(minutes: number[], m: number, ceil = false): number {
  let lo = 0;
  let hi = minutes.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (minutes[mid] < m) lo = mid + 1;
    else hi = mid;
  }
  if (!ceil && lo > 0 && Math.abs(minutes[lo - 1] - m) < Math.abs(minutes[lo] - m)) return lo - 1;
  return lo;
}

/** When the plan repairs `share` of the incidents reported so far (minutes since start), or null.
 *  Counted in incidents, like the 90 % / 48 h service target (restore90Hours). */
function shareRestoredAt(snap: Snapshot, s: Series, share: number): number | null {
  const known = snap.incidents.map((i) => ({ c: 1, at: s.restoredAt.get(i.id) ?? Infinity })).sort((a, b) => a.at - b.at);
  const total = known.reduce((a, x) => a + x.c, 0);
  if (!total) return null;
  let acc = 0;
  for (const x of known) {
    acc += x.c;
    if (acc >= share * total) return Number.isFinite(x.at) ? x.at : null;
  }
  return null;
}

type Flag = { id: string; x: number; y: number; label: string; projected: boolean; tone?: 'critical' };

/** Two rows of flags; a label goes down a row when it would overlap one already placed. Flags are placed by
 *  priority (array order) and one that fits in neither row is dropped rather than drawn over another. */
function placeFlags(flags: Flag[], minX: number, maxX: number, reserved: [number, number][] = [], nRows = 2) {
  // With a single row the unit label (top left) shares it, so it is reserved there.
  const rows: [number, number][][] = nRows === 1 ? [[...reserved]] : [[], [...reserved]];
  const out: (Flag & { row: number; x0: number; w: number })[] = [];
  for (const f of flags) {
    const w = f.label.length * FLAG_FONT * 0.56 + 8;
    let x0 = f.x - w / 2;
    x0 = Math.max(minX, Math.min(maxX - w, x0));
    const fits = (r: number) => rows[r].every(([a, b]) => x0 + w < a || x0 > b);
    const row = fits(0) ? 0 : nRows > 1 && fits(1) ? 1 : -1;
    if (row < 0) continue;
    rows[row].push([x0, x0 + w]);
    out.push({ ...f, row, x0, w });
  }
  return out;
}

export function CrisisTimeline() {
  const [ref, { width, height }] = useSize<HTMLDivElement>();
  // Short band (laptops): one row of milestone labels and thinner strips.
  const compact = height < 150;
  const g = compact ? { ...G, flags: 18, arrivals: 10, capacity: 24, gap: 4, axis: 16 } : G;
  const timelines = useStore((s) => s.timelines)!;
  const meta = useStore((s) => s.meta)!;
  const t = useStore((s) => s.t);
  const k = useStore(stepOf);
  const playing = useStore((s) => s.playing);
  const speedIdx = useStore((s) => s.speedIdx);
  const lastMin = useStore(endMinutes);
  const { togglePlay, setSpeed, setT, pause, stepBy } = useStore.getState();
  const dragging = useRef(false);
  const [hoverX, setHoverX] = useState<number | null>(null);

  const step = meta.stepMinutes;
  const start = Date.parse(meta.start);
  const snaps = timelines.ours;
  const s = useMemo(() => buildSeries(snaps, start), [snaps, start]);
  const snapNow = snaps[k];

  // ---- geometry
  const x0 = Math.floor(s.firstMin / step) * step; // axis starts at the first incident's step
  // live: the axis runs to now (at least one hour wide); replay: to the end of the crisis
  const x1 = mode === 'live' ? Math.max(x0 + 60, t) : Math.min(lastMin, s.endMin + step * 2);
  const W = Math.max(0, width - g.left - g.right);
  const mainTop = g.flags;
  const mainH = Math.max(40, height - g.flags - g.gap - g.arrivals - g.gap - g.capacity - g.axis - 4);
  const mainBottom = mainTop + mainH;
  const arrTop = mainBottom + g.gap;
  const capTop = arrTop + g.arrivals + g.gap;
  const axisY = capTop + g.capacity + 14;
  const X = (min: number) => g.left + ((Math.max(x0, Math.min(x1, min)) - x0) / Math.max(1, x1 - x0)) * W;
  const yStep = niceStep(Math.max(...s.cut));
  const yMax = Math.ceil(Math.max(...s.cut) / yStep) * yStep || yStep;
  const Y = (v: number) => mainBottom - (v / yMax) * mainH;
  const cursorMin = Math.max(x0, Math.min(x1, t));
  const cx = X(cursorMin);

  const idx = useMemo(() => s.minutes.map((_, i) => i).filter((i) => s.minutes[i] >= x0 - step && s.minutes[i] <= x1), [s, x0, x1, step]);
  const area = useMemo(() => {
    const pts = idx.map((i) => `${X(s.minutes[i]).toFixed(1)},${Y(s.cut[i]).toFixed(1)}`);
    return {
      line: `M${pts.join('L')}`,
      fill: `M${X(s.minutes[idx[0]])},${mainBottom}L${pts.join('L')}L${X(s.minutes[idx[idx.length - 1]])},${mainBottom}Z`,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idx, s, width, height]);
  const cap = useMemo(() => {
    const yb = (v: number) => capTop + g.capacity - (v / s.teams) * g.capacity;
    const busyPts = idx.map((i) => `${X(s.minutes[i]).toFixed(1)},${yb(s.busy[i]).toFixed(1)}`);
    const restPts = idx.map((i) => `${X(s.minutes[i]).toFixed(1)},${yb(s.busy[i] + s.resting[i]).toFixed(1)}`);
    const xa = X(s.minutes[idx[0]]);
    const xb = X(s.minutes[idx[idx.length - 1]]);
    return {
      busy: `M${xa},${capTop + g.capacity}L${busyPts.join('L')}L${xb},${capTop + g.capacity}Z`,
      resting: `M${busyPts[0]}L${restPts.join('L')}L${[...busyPts].reverse().join('L')}Z`,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idx, s, width, height]);

  // ---- milestones (share of the incidents reported so far, like the 90 % / 48 h target)
  const r90 = snapNow.kpis.restore90Hours;
  const m90 = r90 === null ? null : r90 * 60;
  const m50 = useMemo(() => shareRestoredAt(snapNow, s, 0.5), [snapNow, s]);
  const targetMin = TARGET_H * 60;
  const late = m90 !== null && m90 > targetMin;
  const peak = s.cut[s.peakIdx];
  const peakMin = s.minutes[s.peakIdx];

  // Live: the axis ends now; milestones beyond it (48 h target, projected 90 %) are not drawn.
  const onAxis = (min: number) => mode !== 'live' || min <= x1 + 1e-6;
  // Priority order: the target and the 90 % milestone first, the 50 % milestone dropped first when crowded.
  const flags = placeFlags(
    [
      ...(onAxis(targetMin) ? [{ id: 'target', x: X(targetMin), y: mainBottom, label: 'Objectif 48 h', projected: targetMin > t }] : []),
      ...(m90 !== null && onAxis(m90)
        ? [{ id: 'm90', x: X(m90), y: Y(cutAt(s, m90)), label: '90 % des incidents réparés', projected: m90 > t, tone: late ? ('critical' as const) : undefined }]
        : []),
      { id: 'peak', x: X(peakMin), y: Y(peak), label: `Pic : ${fmtInt(peak)} clients coupés`, projected: peakMin > t },
      ...(mode !== 'live' || snapNow.kpis.clientsCut === 0 ? [{ id: 'end', x: X(s.endMin), y: mainBottom, label: 'Fin de crise', projected: s.endMin > t }] : []),
      ...(m50 !== null && onAxis(m50) ? [{ id: 'm50', x: X(m50), y: Y(cutAt(s, m50)), label: '50 % réparés', projected: m50 > t }] : []),
    ],
    2,
    width - 2,
    [[0, g.left + 20]], // the "clients coupés" unit label sits at the left of the lower row
    compact ? 1 : 2,
  );

  // ---- axis ticks every 6, 12 or 24 h (Paris time): labels at least ~80 px apart on long crises
  const ticks = useMemo(() => {
    const hours = (x1 - x0) / 60;
    const every = [6, 12, 24].find((e) => (W / Math.max(1, hours)) * e >= 80) ?? 24;
    const out: number[] = [];
    for (let ms = Math.ceil((start + x0 * 60000) / HOUR) * HOUR; ms <= start + x1 * 60000; ms += HOUR) if (parisHour(ms) % every === 0) out.push(ms);
    return out;
  }, [start, x0, x1, W]);

  // ---- text
  const elapsed = Math.max(0, t - s.firstMin);
  const over = t >= s.endMin;
  const peakPast = peakMin <= t;
  const summary = [
    mode === 'live'
      ? `Pic jusqu’ici : ${fmtInt(peak)} clients coupés (${fmtHour(start + peakMin * 60000)}).`
      : `Pic ${peakPast ? 'atteint' : 'prévu'} ${whenLabel(start + peakMin * 60000)} avec ${fmtInt(peak)} clients coupés.`,
    m90 === null
      ? '90 % des incidents réparés : estimation en cours.'
      : `90 % des incidents réparés ${m90 <= t ? '' : 'prévus '}${whenLabel(start + m90 * 60000)}, soit ${gapWords(Math.ceil(m90 / 60))}.`,
  ].join(' ');

  // ---- interaction
  const toMin = (clientX: number, el: Element) => {
    const r = el.getBoundingClientRect();
    return x0 + ((clientX - r.left - g.left) / W) * (x1 - x0);
  };
  const hoverMin = hoverX === null ? null : x0 + ((hoverX - g.left) / W) * (x1 - x0);
  const hoverIdx = hoverMin === null ? null : nearestIdx(s.minutes, hoverMin);
  const cursorLabel = `${fmtHour(start + cursorMin * 60000)} · ${fmtInt(snapNow.kpis.clientsCut)} clients coupés`;
  const cursorLabelW = cursorLabel.length * FLAG_FONT * 0.56 + 12;
  const cursorLeft = cx + 8 + cursorLabelW > width - g.right;

  const waitingForAlerts = !snaps[snaps.length - 1].incidents.length;
  return (
    <footer className="band">
      {mode === 'live' ? (
        <div className="transport live" role="status">
          <span className="live-badge">
            <i aria-hidden /> En direct
          </span>
          <p className="elapsed">
            {waitingForAlerts ? 'En veille : le moteur attend les alertes du terrain.' : `Crise en cours depuis ${fmtMinutes(elapsed)}`}
          </p>
          <p className="elapsed muted">Temps réel : pas de lecture ni de retour arrière. Pour rejouer, « Revoir une crise passée ».</p>
        </div>
      ) : (
      <div className="transport" role="group" aria-label="Lecture de la crise">
        <div className="transport-row">
          <button className="round-btn" onClick={() => stepBy(-1)} aria-label="Reculer de 30 min" title="Reculer de 30 min (←)">
            ‹
          </button>
          <button className={`play ${playing ? 'on' : ''}`} onClick={togglePlay} aria-label={playing ? 'Pause' : 'Lecture'} title="Lecture / pause (Espace)">
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden>
              {playing ? <path d="M7 5h4v14H7zM13 5h4v14h-4z" fill="currentColor" /> : <path d="M8 5v14l11-7z" fill="currentColor" />}
            </svg>
            <span className="play-label">{playing ? 'Pause' : t >= lastMin ? 'Rejouer' : 'Lecture'}</span>
          </button>
          <button className="round-btn" onClick={() => stepBy(1)} aria-label="Avancer de 30 min" title="Avancer de 30 min (→)">
            ›
          </button>
        </div>
        <div className="speeds" role="radiogroup" aria-label="Vitesse de lecture">
          {SPEEDS.map((sp, i) => (
            <button key={sp.label} role="radio" aria-checked={i === speedIdx} title={sp.title} className={`pill small ${i === speedIdx ? 'selected' : ''}`} onClick={() => setSpeed(i)}>
              {sp.label}
            </button>
          ))}
        </div>
        <p className="elapsed">{over ? `Crise terminée en ${fmtMinutes(s.endMin - s.firstMin)}` : `Crise en cours depuis ${fmtMinutes(elapsed)}`}</p>
      </div>
      )}

      <div className="timeline">
        <p className="timeline-summary">{waitingForAlerts ? 'Aucune panne signalée pour le moment.' : summary}</p>
        <div className="timeline-chart" ref={ref}>
          {width > 0 && !waitingForAlerts && idx.length > 0 && (
            <svg
              width={width}
              height={height}
              onPointerDown={(e) => {
                dragging.current = true;
                (e.target as Element).setPointerCapture?.(e.pointerId);
                useStore.setState({ playing: false });
                setT(toMin(e.clientX, e.currentTarget));
              }}
              onPointerMove={(e) => {
                const r = e.currentTarget.getBoundingClientRect();
                setHoverX(e.clientX - r.left >= g.left ? e.clientX - r.left : null);
                if (dragging.current) setT(toMin(e.clientX, e.currentTarget));
              }}
              onPointerLeave={() => setHoverX(null)}
              onPointerUp={() => {
                dragging.current = false;
                pause();
              }}
            >
              <defs>
                <clipPath id="tl-past">
                  <rect x={0} y={0} width={cx} height={height} />
                </clipPath>
                <clipPath id="tl-future">
                  <rect x={cx} y={0} width={Math.max(0, width - cx)} height={height} />
                </clipPath>
              </defs>

              {/* y axis: faint gridlines, round values, unit */}
              {Array.from({ length: Math.round(yMax / yStep) + 1 }, (_, i) => i * yStep)
                // short band: keep the labels at least 14 px apart (0 and the top always shown)
                .filter((_, i, all) => (compact ? i === 0 || i === all.length - 1 : i % Math.max(1, Math.ceil(14 / (mainH / Math.max(1, all.length - 1)))) === 0 || i === all.length - 1))
                .map((v) => (
                <g key={v}>
                  <line className="tl-grid" x1={g.left} x2={g.left + W} y1={Y(v)} y2={Y(v)} />
                  <text className="tl-ytick" x={g.left - 8} y={Y(v) + 4}>
                    {fmtInt(v)}
                  </text>
                </g>
              ))}
              {!compact && (
                <text className="tl-unit" x={0} y={mainTop - 6}>
                  clients coupés
                </text>
              )}

              {/* late stretch: from the 48 h target to the 90 % milestone */}
              {late && <rect className="tl-late" x={X(targetMin)} y={mainTop} width={Math.max(0, X(m90!) - X(targetMin))} height={mainH} />}

              {/* customers cut: past solid, projection light and dashed */}
              <path className="tl-area past" d={area.fill} clipPath="url(#tl-past)" />
              <path className="tl-line past" d={area.line} clipPath="url(#tl-past)" />
              <path className="tl-area future" d={area.fill} clipPath="url(#tl-future)" />
              <path className="tl-line future" d={area.line} clipPath="url(#tl-future)" />

              {/* 48 h target line */}
              {onAxis(targetMin) && <line className="tl-target" x1={X(targetMin)} x2={X(targetMin)} y1={mainTop - 4} y2={capTop + g.capacity} />}

              {/* new incidents */}
              <text className="tl-strip-label incidents" x={g.left - 8} y={arrTop + g.arrivals - 2}>
                incidents
              </text>
              {idx.map((i) =>
                s.arrivals[i] ? (
                  <rect
                    key={i}
                    className={`tl-arrival ${s.minutes[i] > t ? 'future' : ''}`}
                    x={X(s.minutes[i]) - Math.max(1, W / (x1 - x0) * step * 0.35)}
                    width={Math.max(2, (W / (x1 - x0)) * step * 0.7)}
                    y={arrTop + g.arrivals - (s.arrivals[i] / Math.max(...s.arrivals)) * g.arrivals}
                    height={(s.arrivals[i] / Math.max(...s.arrivals)) * g.arrivals}
                  />
                ) : null,
              )}

              {/* team capacity: working (bottom) and resting (above) */}
              {compact ? (
                <text className="tl-strip-label working" x={g.left - 8} y={capTop + g.capacity - 6}>
                  équipes
                </text>
              ) : (
                <>
                  <text className="tl-strip-label working" x={g.left - 8} y={capTop + g.capacity - 1}>
                    au travail
                  </text>
                  <text className="tl-strip-label resting" x={g.left - 8} y={capTop + 11}>
                    au repos
                  </text>
                </>
              )}
              <path className="tl-cap busy" d={cap.busy} />
              <path className="tl-cap resting" d={cap.resting} />
              <rect className="tl-veil" x={cx} y={arrTop} width={Math.max(0, g.left + W - cx)} height={capTop + g.capacity - arrTop} />

              {/* time axis */}
              <line className="tl-axis" x1={g.left} x2={g.left + W} y1={capTop + g.capacity + 2} y2={capTop + g.capacity + 2} />
              {ticks.map((ms) => {
                const tx = X((ms - start) / 60000);
                return (
                  <g key={ms}>
                    <line className="tl-tick" x1={tx} x2={tx} y1={capTop + g.capacity + 2} y2={capTop + g.capacity + 6} />
                    <text className="tl-xtick" x={tx} y={axisY}>
                      {axisLabel(ms)}
                    </text>
                  </g>
                );
              })}

              {/* milestones written on the axis */}
              {flags.map((f) => {
                const labelY = compact ? 13 : f.row === 0 ? 13 : 28;
                return (
                  <g key={f.id} className={`tl-flag ${f.projected ? 'projected' : ''} ${f.tone ?? ''}`}>
                    <line x1={f.x} x2={f.x} y1={labelY + 4} y2={f.y} />
                    <circle cx={f.x} cy={f.y} r={3} />
                    <text x={f.x0 + f.w / 2} y={labelY}>
                      {f.label}
                    </text>
                  </g>
                );
              })}

              {/* now */}
              <line className="tl-now" x1={cx} x2={cx} y1={mainTop - 2} y2={capTop + g.capacity + 2} />
              <g className="tl-now-label" transform={`translate(${cursorLeft ? cx - 8 - cursorLabelW : cx + 8},${mainTop + 4})`}>
                <rect width={cursorLabelW} height={20} rx={4} />
                <text x={cursorLabelW / 2} y={14}>
                  {cursorLabel}
                </text>
              </g>

              {/* hover guide */}
              {hoverX !== null && !dragging.current && <line className="tl-hover" x1={hoverX} x2={hoverX} y1={mainTop} y2={capTop + g.capacity} />}
            </svg>
          )}
          {hoverIdx !== null && hoverX !== null && !dragging.current && (
            <div className="tl-tooltip" style={hoverX > width - 220 ? { right: width - hoverX + 12 } : { left: hoverX + 12 }}>
              <b>
                {dayShortFmt.format(start + s.minutes[hoverIdx] * 60000)} {fmtHour(start + s.minutes[hoverIdx] * 60000)}
              </b>
              <span>{fmtInt(s.cut[hoverIdx])} clients coupés</span>
              <span>{fmtInt(s.waiting[hoverIdx])} incidents en attente</span>
              <span>{s.busy[hoverIdx]} équipes au travail</span>
            </div>
          )}
        </div>
      </div>
    </footer>
  );
}

/** Customers cut at a given minute (linear between snapshots). */
function cutAt(s: Series, min: number) {
  if (s.minutes.length < 2) return s.cut[0] ?? 0;
  const i = Math.min(s.minutes.length - 2, Math.max(0, nearestIdx(s.minutes, min, true) - 1));
  const f = (min - s.minutes[i]) / ((s.minutes[i + 1] - s.minutes[i]) || 1);
  return s.cut[i] + (s.cut[i + 1] - s.cut[i]) * Math.max(0, Math.min(1, f));
}

function gapWords(h90: number) {
  if (h90 === TARGET_H) return 'pile à l’objectif';
  return h90 < TARGET_H ? `${TARGET_H - h90} h avant l’objectif` : `${h90 - TARGET_H} h après l’objectif`;
}
