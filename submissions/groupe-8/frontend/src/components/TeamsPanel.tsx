// "Équipes" tab: every team and what it is doing now, and how the shifts are organised (fixed roster, groups A/B/C),
// explained so the manager can tell at a glance who can leave now and who comes back when.
import { useState } from 'react';
import type { Roster, Snapshot, Team } from '../data/contract';
import { fmtHour, fmtMinutes } from '../lib/format';
import { useOursSnapshot, useStore } from '../state/store';

const STATUS: Record<Team['status'], { label: string; plural: string }> = {
  available: { label: 'Disponible', plural: 'Disponibles' },
  travelling: { label: 'En route', plural: 'En route' },
  repairing: { label: 'Sur intervention', plural: 'Sur intervention' },
  resting: { label: 'Au repos', plural: 'Au repos' },
};
const ORDER: Team['status'][] = ['available', 'travelling', 'repairing', 'resting'];
const GROUP_TEXT: Record<string, string> = {
  A: 'commence au début de la crise',
  B: 'décalé pour étaler les fins de poste',
  C: 'la relève : en service pendant le repos des groupes A et B',
};

/** On-duty bands of a group over the next `hours`, as [start, end] fractions of the bar. */
function bands(r: Roster, offset: number, from: number, hours: number): [number, number][] {
  const cycle = r.workHours + r.restHours;
  const out: [number, number][] = [];
  let s = offset + Math.floor((from - offset) / cycle) * cycle;
  for (; s < from + hours; s += cycle) {
    const a = Math.max(s, from);
    const b = Math.min(s + r.workHours, from + hours);
    if (b > a) out.push([(a - from) / hours, (b - from) / hours]);
  }
  return out;
}

function RosterExplainer({ roster, startMs, nowMs }: { roster: Roster; startMs: number; nowMs: number }) {
  const H = 48;
  const nowH = (nowMs - startMs) / 3600_000;
  const from = Math.max(0, Math.floor(nowH) - 6);
  const ticks = [0, 12, 24, 36, 48];
  return (
    <section className="roster">
      <h3 className="plan-sub">Comment les postes sont organisés</h3>
      <p className="roster-help">
        Chaque équipe travaille <b>{roster.workHours} h</b>, puis se repose <b>{roster.restHours} h</b> (plus que les 11 h légales). Les horaires sont
        fixés au début de la crise et ne changent plus : chacun connaît ses heures à l’avance. Les équipes sont réparties en {roster.groups.length} groupes
        décalés, pour qu’il y ait toujours des équipes en service. Un dépannage n’est jamais proposé s’il ne tient pas avant la fin du poste.
      </p>
      <div className="roster-chart" role="img" aria-label="Postes de travail des groupes sur 48 h">
        {roster.groups.map((g) => (
          <div key={g.id} className="roster-row">
            <span className="roster-name">
              <b>Groupe {g.id}</b> · {g.teams} éq.
            </span>
            <span className="roster-bar">
              {bands(roster, g.offsetHours, from, H).map(([a, b]) => (
                <i key={a} style={{ left: `${a * 100}%`, width: `${(b - a) * 100}%` }} />
              ))}
              <span className="roster-now" style={{ left: `${((nowH - from) / H) * 100}%` }} />
            </span>
          </div>
        ))}
        <div className="roster-row roster-axis">
          <span />
          <span className="roster-bar">
            {ticks.map((h) => (
              <small key={h} style={{ left: `${(h / H) * 100}%` }}>
                {fmtHour(startMs + (from + h) * 3600_000)}
              </small>
            ))}
          </span>
        </div>
      </div>
      <ul className="roster-groups">
        {roster.groups.map((g) => {
          const first = Date.parse(g.firstShiftStart);
          return (
            <li key={g.id}>
              <b>Groupe {g.id}</b> ({GROUP_TEXT[g.id] ?? ''}) : 1er poste {fmtHour(first)} → {fmtHour(first + roster.workHours * 3600_000)}, puis repos
              jusqu’à {fmtHour(first + (roster.workHours + roster.restHours) * 3600_000)}.
            </li>
          );
        })}
      </ul>
      <p className="roster-legend">
        <i className="on" /> en service <i className="off" /> repos <span className="roster-now-key" /> maintenant
      </p>
    </section>
  );
}

function detail(t: Team, snap: Snapshot, nowMs: number): string {
  const commune = (id?: string) => snap.incidents.find((i) => i.id === id)?.commune ?? '';
  const end = t.shiftEnd ? Date.parse(t.shiftEnd) : null;
  switch (t.status) {
    case 'available':
      return end ? `jusqu’à ${fmtHour(end)} · reste ${fmtMinutes((end - nowMs) / 60000)}` : 'en service';
    case 'travelling':
      return `→ ${commune(t.incidentId)}`;
    case 'repairing':
      return `à ${commune(t.incidentId)}${end ? ` · poste jusqu’à ${fmtHour(end)}` : ''}`;
    case 'resting':
      return t.shiftStart ? `reprend à ${fmtHour(t.shiftStart)}` : 'au repos';
  }
}

export function TeamsPanel() {
  const snap = useOursSnapshot()!;
  const meta = useStore((s) => s.meta!);
  const [filter, setFilter] = useState<Team['status'] | 'all'>('all');
  const nowMs = Date.parse(snap.time);
  const count = (st: Team['status']) => snap.teams.filter((t) => t.status === st).length;
  const shown = snap.teams
    .filter((t) => filter === 'all' || t.status === filter)
    .sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status) || a.label.localeCompare(b.label, 'fr'));
  return (
    <section className="card teams-panel">
      <h2 className="card-title">
        Équipes <span className="count">{snap.teams.length}</span>
      </h2>
      <div className="team-filters" role="radiogroup" aria-label="Filtrer les équipes">
        <button role="radio" aria-checked={filter === 'all'} className={`pill small ${filter === 'all' ? 'selected' : ''}`} onClick={() => setFilter('all')}>
          Toutes
        </button>
        {ORDER.map((st) => (
          <button key={st} role="radio" aria-checked={filter === st} className={`pill small ${filter === st ? 'selected' : ''}`} onClick={() => setFilter(st)}>
            <i className={`team-dot ${st}`} aria-hidden /> {STATUS[st].plural} <b>{count(st)}</b>
          </button>
        ))}
      </div>
      <ul className="team-list">
        {shown.map((t) => (
          <li key={t.id} className={`team-row ${t.status}`}>
            <i className={`team-dot ${t.status}`} aria-hidden />
            <span className="team-name">
              <b>{t.label}</b>
              {t.group && <span className="team-group" title={`Groupe ${t.group} : ${GROUP_TEXT[t.group]}`}>{t.group}</span>}
            </span>
            <span className="team-status">{STATUS[t.status].label}</span>
            <span className="team-detail">{detail(t, snap, nowMs)}</span>
          </li>
        ))}
      </ul>
      {meta.roster && <RosterExplainer roster={meta.roster} startMs={Date.parse(meta.start)} nowMs={nowMs} />}
    </section>
  );
}
