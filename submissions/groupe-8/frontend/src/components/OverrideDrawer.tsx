import { useEffect, useRef, useState } from 'react';
import { fmtDelta, fmtHour, fmtHours, fmtInt, fmtMinutes } from '../lib/format';
import { useOursSnapshot, useStore } from '../state/store';

const REASONS = ['Connaissance terrain', 'Accès / route coupée', 'Compétence spécifique', 'Équipe déjà sur zone'];

/** "Changer d'équipe": slides in from the right over a dimmed page. */
export function OverrideDrawer() {
  const recId = useStore((s) => s.overrideRecId);
  const snapshot = useOursSnapshot()!;
  const rec = snapshot.recommendations.find((r) => r.id === recId);
  if (!rec) return null;
  return <Drawer key={rec.id} recId={rec.id} />;
}

function Drawer({ recId }: { recId: string }) {
  const snapshot = useOursSnapshot()!;
  const rec = snapshot.recommendations.find((r) => r.id === recId)!;
  const { openOverride, setPreviewTeam, override } = useStore.getState();
  const busy = useStore((s) => s.busy);
  const [selected, setSelected] = useState<string | null>(null);
  const [reason, setReason] = useState<string | undefined>();
  const panelRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLDivElement>(null);

  const team = (id: string) => snapshot.teams.find((t) => t.id === id);
  const inc = snapshot.incidents.find((i) => i.id === rec.incidentId);
  const commune = (id: string) => snapshot.incidents.find((i) => i.id === id)?.commune ?? id;
  const options = rec.alternatives;
  const feasible = options.filter((a) => a.feasible);
  const maxDelta = Math.max(1, ...feasible.map((a) => Math.abs(a.deltaScore)));
  const sel = options.find((a) => a.teamId === selected);
  const close = () => openOverride(undefined);

  useEffect(() => {
    panelRef.current?.focus();
    return () => setPreviewTeam(undefined);
  }, [setPreviewTeam]);
  useEffect(() => {
    if (selected) confirmRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selected]);

  const choose = (id: string) => {
    setSelected(id);
    setPreviewTeam(id);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      if (selected) {
        setSelected(null);
        setPreviewTeam(undefined);
      } else close();
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const ids = feasible.map((a) => a.teamId);
      if (!ids.length) return;
      const idx = selected ? ids.indexOf(selected) : -1;
      choose(ids[e.key === 'ArrowDown' ? Math.min(ids.length - 1, idx + 1) : Math.max(0, idx - 1)]);
    } else if (e.key === 'Enter' && sel && !busy && !(e.target as HTMLElement).closest('button')) {
      e.preventDefault();
      override(rec, sel.teamId, reason);
    }
  };

  return (
    <>
      <div className="scrim" onClick={close} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" ref={panelRef} tabIndex={-1} onKeyDown={onKey}>
        <header className="drawer-head">
          <div>
            <h2 id="drawer-title">Changer d’équipe</h2>
            <p>
              Poste {inc?.commune} · {fmtInt(rec.factors.clients)} clients
            </p>
          </div>
          <button className="round-close" onClick={close} aria-label="Fermer">
            ×
          </button>
        </header>

        <div className="drawer-body">

          <div className="alt-table" role="radiogroup" aria-label="Équipes alternatives">
            <div className="alt-row alt-header" aria-hidden>
              <span />
              <span>Équipe</span>
              <span className="num">Trajet</span>
              <span className="num">Arrivée</span>
              <span className="num">Ampl. après</span>
              <span className="num">Coût cl·h</span>
            </div>
            <div className="alt-row alt-current">
              <span className="radio on-rec" aria-hidden />
              <span className="alt-name">
                <span className="alt-label">{team(rec.teamId)?.label}</span>
                <span className="alt-sub">
                  <span className="tag tag-ok">Recommandée</span>
                </span>
              </span>
              <span className="num">{fmtMinutes(rec.travelMinutes)}</span>
              <span className="num">{fmtHour(rec.eta)}</span>
              <span className="num">{fmtHours(rec.factors.shiftHoursLeftAfter)}</span>
              <span className="num delta">
                <span className="delta-val">±0</span>
              </span>
            </div>
            {options.map((a) => {
              const tm = team(a.teamId);
              const isSel = a.teamId === selected;
              return (
                <div
                  key={a.teamId}
                  role="radio"
                  aria-checked={isSel}
                  aria-disabled={!a.feasible}
                  tabIndex={-1}
                  className={`alt-row ${isSel ? 'selected' : ''} ${a.feasible ? '' : 'infeasible'}`}
                  onMouseEnter={() => a.feasible && setPreviewTeam(a.teamId)}
                  onMouseLeave={() => setPreviewTeam(selected ?? undefined)}
                  onClick={() => a.feasible && choose(a.teamId)}
                  title={a.reason}
                >
                  <span className={`radio ${isSel ? 'on' : ''}`} aria-hidden />
                  <span className="alt-name">
                    <span className="alt-label">{tm?.label}</span>
                    <span className="alt-sub">
                      {a.recommendedFor ? (
                        <span className="tag">Proposée pour {commune(a.recommendedFor)}</span>
                      ) : !a.feasible ? (
                        <span className="tag tag-quiet">Amplitude insuffisante</span>
                      ) : (
                        <span className="alt-site">site {tm?.siteName.replace(' (Toulouse)', '')}</span>
                      )}
                    </span>
                  </span>
                  <span className="num">{fmtMinutes(a.travelMinutes)}</span>
                  <span className="num">{fmtHour(a.eta)}</span>
                  <span className={`num ${a.feasible && a.shiftHoursLeftAfter < 1.5 ? 'warn-text' : ''}`}>{a.feasible ? fmtHours(a.shiftHoursLeftAfter) : '—'}</span>
                  <span className="num delta">
                    {a.feasible && (
                      <span className="delta-bar">
                        <i className={a.deltaScore > 0 ? 'cost' : 'gain'} style={{ width: `${(Math.abs(a.deltaScore) / maxDelta) * 100}%` }} />
                      </span>
                    )}
                    <span className={`delta-val ${a.deltaScore > 0 ? 'cost' : 'gain'}`}>{a.feasible ? fmtDelta(a.deltaScore) : '—'}</span>
                  </span>
                </div>
              );
            })}
          </div>

          {sel && (
            <div className="override-confirm" ref={confirmRef}>
              <div className="confirm-line">
                <b>Équipe {team(sel.teamId)?.label}</b> → Poste {inc?.commune} · arrivée {fmtHour(sel.eta)} ·{' '}
                <b className={sel.deltaScore > 0 ? 'cost' : 'gain'}>{fmtDelta(sel.deltaScore)} clients·h</b>
              </div>
              {sel.recommendedFor && <div className="confirm-warn">Libère le poste {commune(sel.recommendedFor)}, qui sera réaffecté.</div>}
              <div className="reasons">
                <span>Motif</span>
                {REASONS.map((r) => (
                  <button key={r} className={`pill small ${reason === r ? 'selected' : ''}`} onClick={() => setReason(reason === r ? undefined : r)} aria-pressed={reason === r}>
                    {r}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <footer className="drawer-foot">
          <button className="pill primary" disabled={!sel || busy} onClick={() => sel && override(rec, sel.teamId, reason)}>
            Confirmer le changement
          </button>
          <button className="pill" onClick={close}>
            Annuler
          </button>
        </footer>
      </aside>
    </>
  );
}
