import { useLayoutEffect, useRef, useState } from 'react';
import type { Incident, Snapshot, Team } from '../data/contract';
import { fmtHours, fmtInt, fmtMinutes } from '../lib/format';
import type { Cluster } from './MapView';

export type HoverTarget =
  | { kind: 'incident'; object: Incident; x: number; y: number }
  | { kind: 'team'; object: Team; x: number; y: number }
  | { kind: 'cluster'; object: Cluster; x: number; y: number }
  | { kind: 'site'; object: { name: string; available: number; teams: number }; x: number; y: number };

const TEAM_STATUS: Record<Team['status'], string> = {
  available: 'Disponible',
  travelling: 'En route',
  repairing: 'Sur intervention',
  resting: 'Au repos (11 h)',
};

export function MapTooltip({ target, snapshot, nowMs, pinned, box }: { target: HoverTarget; snapshot: Snapshot; nowMs: number; pinned?: boolean; box?: { width: number; height: number } }) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 260, h: 140 });
  // Measured after each render: the card is then placed fully inside the map (short maps on laptops).
  useLayoutEffect(() => {
    const el = ref.current;
    if (el && (Math.abs(el.offsetWidth - size.w) > 1 || Math.abs(el.offsetHeight - size.h) > 1)) setSize({ w: el.offsetWidth, h: el.offsetHeight });
  });
  const team = (id?: string) => snapshot.teams.find((t) => t.id === id);
  const inc = (id?: string) => snapshot.incidents.find((i) => i.id === id);
  let body: React.ReactNode;
  if (target.kind === 'site') {
    const st = target.object;
    body = (
      <>
        <div className="tt-title">Site {st.name}</div>
        <div className="tt-row">
          <b>{st.available}</b> équipes disponibles sur {st.teams}
        </div>
      </>
    );
  } else if (target.kind === 'cluster') {
    const c = target.object;
    body = (
      <>
        <div className="tt-title">{c.commune}</div>
        <div className="tt-row">
          <b>{c.count}</b> incidents en attente · <b>{fmtInt(c.clients)}</b> clients coupés
        </div>
        {c.sensitive && <span className="tag tag-sensitive">
            <i className="dot-sensitive" aria-hidden />
            Client sensible
          </span>}
      </>
    );
  } else if (target.kind === 'incident') {
    const i = target.object;
    const since = Math.max(0, (nowMs - Date.parse(i.reportedAt)) / 60000);
    const tm = team(i.teamId);
    const status =
      i.status === 'waiting'
        ? `En attente depuis ${fmtMinutes(since)}`
        : i.status === 'enroute'
          ? `Équipe ${tm?.label ?? ''} en route`
          : i.status === 'repairing'
            ? `Dépannage en cours · équipe ${tm?.label ?? ''}`
            : 'Réalimenté';
    body = (
      <>
        <div className="tt-title">Poste {i.commune}</div>
        <div className="tt-row">
          {i.posteId} · <b>{fmtInt(i.clients)}</b> clients
        </div>
        <div className="tt-tags">
          <span className="tag">{i.cause}</span>
          {i.sensitive && <span className="tag tag-sensitive">
            <i className="dot-sensitive" aria-hidden />
            Client sensible
          </span>}
        </div>
        <div className="tt-row">Dépannage estimé {fmtHours(i.repairHours)}</div>
        <div className={`tt-status s-${i.status}`}>{status}</div>
      </>
    );
  } else {
    const t = target.object;
    const dest = inc(t.incidentId);
    body = (
      <>
        <div className="tt-title">Équipe {t.label}</div>
        <div className="tt-row">Site {t.siteName}</div>
        <div className="tt-tags">
          <span className="tag">{TEAM_STATUS[t.status]}</span>
        </div>
        {dest && <div className="tt-row">Vers poste {dest.commune}</div>}
        {t.status !== 'resting' && <div className="tt-row">Amplitude restante {fmtHours(t.shiftHoursLeft)} / 12 h</div>}
      </>
    );
  }
  // Keep the card inside the map on the right/bottom edges.
  const w = box?.width ?? 1000;
  const h = box?.height ?? 800;
  const GAP = 14;
  // Right of the pointer if it fits, else left; below if it fits, else above; finally clamped inside the map.
  const left = target.x + GAP + size.w <= w - 4 ? target.x + GAP : target.x - GAP - size.w;
  const top = target.y + GAP + size.h <= h - 4 ? target.y + GAP : target.y - GAP - size.h;
  const style: React.CSSProperties = {
    left: Math.max(4, Math.min(w - size.w - 4, left)),
    top: Math.max(4, Math.min(h - size.h - 4, top)),
    maxHeight: h - 8,
    overflowY: 'auto',
  };
  return (
    <div ref={ref} className={`map-tooltip ${pinned ? 'pinned' : ''}`} style={style}>
      {body}
    </div>
  );
}
