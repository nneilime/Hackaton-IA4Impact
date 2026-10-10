import { useEffect, useRef, useState } from 'react';
import type { Recommendation, Snapshot } from '../data/contract';
import { fmt1, fmtHour, fmtInt, fmtMinutes } from '../lib/format';
import { mode, source, type PlanExplanation } from '../data/source';
import { interpretLine, interpretPlan } from '../copilot/interpret';
import { planColour } from './MapView';
import { endMinutes, stepOf, useFocusedRec, useOursSnapshot, useStore } from '../state/store';
import { WarningIcon } from './WarningIcon';

/** One warning at most, only when something is abnormal. */
function warning(rec: Recommendation): string | null {
  if (rec.factors.shiftHoursLeftAfter < 1.5) return `Amplitude tendue : ${fmt1(rec.factors.shiftHoursLeftAfter)} h restante après l’intervention`;
  if (rec.travelMinutes > 90) return 'Trajet long : durée réelle incertaine';
  return null;
}

function FocusCard({ rec, snap }: { rec: Recommendation; snap: Snapshot }) {
  const busy = useStore((s) => s.busy);
  const { accept, openOverride, openCopilot, hoverRec, openModal } = useStore.getState();
  const past = rec.pastRefusals;
  const applyPast = async () => {
    if (!past || !source.applyRules) return;
    useStore.setState({ busy: true });
    try {
      const tl = await source.applyRules(stepOf(useStore.getState()), past.suggested_modifiers);
      useStore.getState().applyTimelines(tl, { tone: 'info', title: 'Règle déjà utilisée appliquée, plan recalculé', body: past.last_reason });
    } finally {
      useStore.setState({ busy: false });
    }
  };
  const label = (id: string) => snap.teams.find((t) => t.id === id)?.label ?? id;
  const inc = snap.incidents.find((i) => i.id === rec.incidentId);
  const f = rec.factors;
  const warn = warning(rec);

  return (
    <article className="focus" aria-label="Recommandation en cours" onMouseEnter={() => hoverRec(rec.id, 'card')} onMouseLeave={() => hoverRec(undefined)}>
      <h3 className="focus-action">
        {label(rec.teamId)} → {inc?.commune}
        <span className="focus-eta">, arrivée {fmtHour(rec.eta)}</span>
      </h3>
      {f.sensitive && <span className="tag tag-sensitive">Client sensible</span>}
      <p className="focus-facts">
        <b>{fmtInt(f.clients)}</b> clients · <b>{fmtMinutes(f.travelMinutes)}</b> de trajet · <b>{fmt1(f.repairHours).replace(',0', '')} h</b> de dépannage ·{' '}
        <b>{fmt1(f.shiftHoursLeftAfter)} h</b> d’amplitude restante
      </p>
      <ul className="focus-reading">
        {interpretLine(rec, snap).map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ul>

      {past && past.count > 0 && (
        <div className="past-refusal" role="note">
          <span>
            <b>Déjà refusé {past.count} fois</b> dans ce cas · dernier motif « {past.last_reason} »
          </span>
          {source.applyRules && past.suggested_modifiers.length > 0 && (
            <button className="pill small" disabled={busy} onClick={applyPast}>
              Appliquer la même règle
            </button>
          )}
        </div>
      )}

      {warn && (
        <p className="focus-warn">
          <WarningIcon tone="waiting" />
          {warn}
        </p>
      )}

      <div className="focus-actions">
        {!source.acceptPlan && (
          <button className="pill primary" disabled={busy} onClick={() => accept(rec)}>
            Accepter <kbd>Entrée</kbd>
          </button>
        )}
        <button className="pill" disabled={busy || rec.alternatives.length === 0} onClick={() => openOverride(rec.id)}>
          Changer d’équipe <kbd>C</kbd>
        </button>
        {source.refuse && (
          <button className="pill" disabled={busy} onClick={() => openModal({ kind: 'refusal', recId: rec.id })}>
            Refuser…
          </button>
        )}
        <button className="link" onClick={() => openCopilot('Pourquoi cette équipe ?', rec.id)}>
          Pourquoi ?
        </button>
      </div>
    </article>
  );
}

function QueueRow({ rec, rank, snap, hovered }: { rec: Recommendation; rank: number; snap: Snapshot; hovered: boolean }) {
  const { focusRec, hoverRec } = useStore.getState();
  const ref = useRef<HTMLButtonElement>(null);
  const hoverFrom = useStore((s) => s.hoverFrom);
  useEffect(() => {
    if (hovered && hoverFrom === 'map') ref.current?.scrollIntoView({ block: 'nearest' });
  }, [hovered, hoverFrom]);
  const team = snap.teams.find((t) => t.id === rec.teamId)?.label;
  const inc = snap.incidents.find((i) => i.id === rec.incidentId);
  return (
    <li>
      <button
        ref={ref}
        className={`row ${hovered ? 'hovered' : ''}`}
        onClick={() => focusRec(rec.id)}
        onMouseEnter={() => hoverRec(rec.id, 'card')}
        onMouseLeave={() => hoverRec(undefined)}
      >
        <span className="row-rank">{rank}</span>
        <span className="row-action">
          {team} → {inc?.commune}
          {rec.factors.sensitive && <span className="tag tag-sensitive">Client sensible</span>}
        </span>
        <span className="row-eta">{fmtHour(rec.eta)}</span>
        <span className="row-clients">{fmtInt(rec.factors.clients)} cl.</span>
      </button>
    </li>
  );
}

function EmptyState({ snap }: { snap: Snapshot }) {
  const k = snap.kpis;
  const done = k.clientsCut === 0 && k.clientsRestored > 0;
  return (
    <div className="empty">
      {done
        ? 'Crise terminée : tous les clients sont réalimentés.'
        : k.incidentsWaiting === 0
          ? mode === 'live' && !snap.incidents.length
            ? 'En veille : aucune alerte reçue. Le moteur proposera un plan dès qu’une panne est signalée.'
            : 'Aucun incident en attente.'
          : k.teamsAvailable === 0
            ? 'Toutes les équipes sont engagées.'
            : 'Les équipes libres n’ont pas l’amplitude nécessaire.'}
    </div>
  );
}

/** 'Pourquoi ce plan ?': the engine's facts as a short justification of the whole plan. The instant version comes
 *  first, then the plainer LLM-written one replaces it when it arrives (only if its figures match the engine's). */
function PlanWhy({ step }: { step: number }) {
  const [why, setWhy] = useState<PlanExplanation | null>(null);
  useEffect(() => {
    if (!source.explainPlan) return;
    let live = true;
    setWhy(null);
    source.explainPlan(step, false).then((x) => live && setWhy((w) => w ?? x)).catch(() => {});
    source.explainPlan(step, true).then((x) => live && setWhy(x)).catch(() => {});
    return () => {
      live = false;
    };
  }, [step]);
  if (!source.explainPlan) return null;
  return (
    <details className="plan-ai">
      <summary>Explication détaillée{why?.source === 'llm' ? ' (rédigée par l’IA)' : ''}</summary>
      {!why ? (
        <p className="plan-why-loading">Le copilote prépare l’explication…</p>
      ) : (
        <>
          <p>{why.resume}</p>
          <ul>
            {why.points.map((pt) => (
              <li key={pt}>{pt}</li>
            ))}
          </ul>
        </>
      )}
    </details>
  );
}

const DAY = new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', weekday: 'long' });
const fmtDur = (h: number) => {
  const m = Math.round(h * 60);
  return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}` : `${m} min`;
};

/** Why this plan, in 3-4 labelled lines with one figure each (computed from the engine's data, instant). */
function PlanReasons({ snap }: { snap: Snapshot }) {
  const timelines = useStore((s) => s.timelines)!;
  const start = useStore((s) => Date.parse(s.meta!.start));
  const last = timelines.ours[timelines.ours.length - 1];
  const customers = last.incidents.reduce((a, i) => a + i.clients, 0) || 1;
  const ours = last.kpis.score / customers;
  const ref = last.kpis.scoreBaseline / customers;
  const gain = ref > 0 ? Math.round((100 * (ref - ours)) / ref) : null;
  const h90 = snap.kpis.restore90Hours;
  const when = h90 === null ? null : start + h90 * 3600_000;
  const sensitive = snap.recommendations.filter((r) => r.factors.sensitive).length;
  return (
    <dl className="plan-reasons">
      <div>
        <dt>Situation</dt>
        <dd>
          <ul className="plan-reading">
            {interpretPlan(snap).map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </dd>
      </div>
      {gain !== null && (
        <div>
          <dt>Gain</dt>
          <dd>
            <b>{gain} %</b> de coupure en moins : <b>{fmtDur(ours)}</b> sans électricité en moyenne par client, contre {fmtDur(ref)} avec la
            stratégie habituelle.
          </dd>
        </div>
      )}
      {h90 !== null && when !== null && (
        <div>
          <dt>Objectif 48 h</dt>
          <dd className={h90 <= 48 ? 'ok' : 'ko'}>
            <b>{h90 <= 48 ? 'Tenu' : 'Non tenu'}</b> : 90 % des incidents réparés {DAY.format(when)} vers {fmtHour(when)}.
          </dd>
        </div>
      )}
      {sensitive > 0 && (
        <div>
          <dt>Sensibles</dt>
          <dd>
            <b>{sensitive}</b> panne{sensitive > 1 ? 's' : ''} avec client sensible traitée{sensitive > 1 ? 's' : ''} dans ce plan.
          </dd>
        </div>
      )}
    </dl>
  );
}

/** What happened since the previous plan: why a new plan exists now. */
function SinceLast({ snap }: { snap: Snapshot }) {
  const prev = useStore((s) => {
    const k = stepOf(s);
    for (let j = k - 1; j >= 0; j--) {
      const p = s.timelines!.ours[j];
      if (p.recommendations.length || p.decisions.length) return p;
    }
    return undefined;
  });
  if (!prev) return <p className="plan-since">Premier plan de la crise : les premières pannes viennent d’être signalées.</p>;
  const from = Date.parse(prev.time);
  const to = Date.parse(snap.time);
  const fresh = snap.incidents.filter((i) => {
    const r = Date.parse(i.reportedAt);
    return r > from && r <= to;
  });
  const clients = fresh.reduce((a, i) => a + i.clients, 0);
  return (
    <p className="plan-since">
      Depuis le plan de {fmtHour(prev.time)} : <b>+{fresh.length} panne{fresh.length > 1 ? 's' : ''}</b> signalée{fresh.length > 1 ? 's' : ''}
      {fresh.length > 0 && ` (${fmtInt(clients)} clients)`}, <b>{snap.kpis.teamsAvailable}</b> équipe{snap.kpis.teamsAvailable > 1 ? 's' : ''} libre
      {snap.kpis.teamsAvailable > 1 ? 's' : ''} maintenant.
    </p>
  );
}

/** The whole plan of this step as one unit: what it does, one primary action, then its lines. */
function PlanCard({ snap, focusedId, hoveredRecId }: { snap: Snapshot; focusedId?: string; hoveredRecId?: string }) {
  const busy = useStore((s) => s.busy);
  const acceptPlan = useStore((s) => s.acceptPlan);
  const recs = snap.recommendations;
  const playing = useStore((s) => s.playing);
  const atEnd = useStore((s) => s.t >= endMinutes(s));
  const step = useStore(stepOf);
  const attention = useStore((s) => s.attention);
  if (!recs.length && snap.decisions.length)
    return (
      <div className="card plan-card plan-done">
        <h2 className="card-title">
          <i className="swatch" style={{ background: `rgb(${planColour(step).join(',')})` }} aria-hidden /> Plan validé à {fmtHour(snap.time)}
        </h2>
        <p className="plan-help">
          {snap.decisions.length} équipe{snap.decisions.length > 1 ? 's' : ''} en route : leurs trajets gardent cette couleur sur la carte. Le moteur proposera le prochain plan
          dès qu’une équipe se libère ou qu’un incident arrive.
        </p>
        {!playing && mode !== 'live' && (
          <button className="pill primary plan-accept" onClick={() => useStore.getState().play()}>
            Continuer la simulation
          </button>
        )}
      </div>
    );
  if (!recs.length)
    return (
      <div className="card plan-card">
        <h2 className="card-title">Plan proposé</h2>
        <EmptyState snap={snap} />
        <p className="plan-help">
          {mode === 'live'
            ? 'Le moteur surveille les alertes en temps réel : un nouveau plan apparaîtra ici dès qu’une panne arrive ou qu’une équipe se libère.'
            : atEnd
            ? 'Fin de la simulation : « Rejouer » en bas, ou cliquez dans la chronologie pour revenir à un moment.'
            : playing
              ? 'Le moteur proposera un plan dès qu’un incident arrive ou qu’une équipe se libère.'
              : 'Appuyez sur « Lecture » en bas : le moteur propose un plan dès qu’un incident arrive.'}
        </p>
      </div>
    );
  const clients = recs.reduce((a, r) => a + r.factors.clients, 0);
  const restored = recs.map((r) => Date.parse(r.eta) + r.factors.repairHours * 3600_000);
  const n = recs.length;
  return (
    <div className={`card plan-card ${attention ? 'attention' : ''}`} key={attention}>
      <p className="plan-kicker">
        <i className="swatch" style={{ background: 'rgb(124, 58, 237)' }} aria-hidden /> Proposition du moteur · {fmtHour(snap.time)} ·{' '}
        <span className="plan-required">décision requise</span> · tracés violets sur la carte
      </p>
      <SinceLast snap={snap} />
      <h2 className="plan-what">
        Envoyer <b>{n} équipe{n > 1 ? 's' : ''}</b> maintenant
      </h2>
      <p className="plan-result">
        → <b>{fmtInt(clients)} clients</b> retrouvent l’électricité d’ici <b>{fmtHour(Math.max(...restored))}</b>
      </p>

      <h3 className="plan-sub">Pourquoi ce plan</h3>
      <PlanReasons snap={snap} />
      <PlanWhy step={step} />

      <div className="plan-decision">
        <button className="pill primary plan-accept" disabled={busy} onClick={() => acceptPlan(true)}>
          {busy ? 'Validation…' : mode === 'live' ? 'Valider le plan : envoyer les équipes' : 'Valider le plan et continuer'}
        </button>
        {source.refuse && (
          <button className="pill plan-refuse" disabled={busy} onClick={() => useStore.getState().openModal({ kind: 'refusal' })}>
            Refuser…
          </button>
        )}
      </div>

      <h3 className="plan-sub">
        Les {n} affectations <span className="plan-sub-note">(numéros = carte)</span>
      </h3>
      <div className="plan-table-head" aria-hidden>
        <span>#</span>
        <span>Équipe → panne</span>
        <span>Arrivée</span>
        <span>Clients</span>
      </div>
      <ol className="plan-list" aria-label="Affectations du plan">
        {recs.map((r, i) =>
          r.id === focusedId ? (
            <li key={r.id} className="plan-open">
              <span className="plan-open-rank" aria-hidden>
                {i + 1}
              </span>
              <FocusCard rec={r} snap={snap} />
            </li>
          ) : (
            <QueueRow key={r.id} rec={r} rank={i + 1} snap={snap} hovered={hoveredRecId === r.id} />
          ),
        )}
      </ol>
    </div>
  );
}

/** Every plan validated so far in the crisis (the "Journal" tab), most recent first, one block per plan. */
export function Journal({ snap }: { snap: Snapshot }) {
  const busy = useStore((s) => s.busy);
  const resetDecisions = useStore((s) => s.resetDecisions);
  const k = useStore(stepOf);
  const ours = useStore((s) => s.timelines!.ours);
  const plans = ours
    .slice(0, k + 1)
    .map((p, j) => ({ j, time: p.time, decisions: p.decisions, teams: p.teams, incidents: p.incidents }))
    .filter((p) => p.decisions.length)
    .reverse();
  const total = plans.reduce((a, p) => a + p.decisions.length, 0);
  void snap;
  return (
    <section className="card journal">
      <div className="journal-head">
        <h2 className="card-title">
          Décisions prises <span className="count">{total}</span>
        </h2>
        {total > 0 && mode !== 'live' && (
          <button className="pill small" disabled={busy} onClick={() => resetDecisions()}>
            Tout annuler
          </button>
        )}
      </div>
      {!total ? (
        <p className="plan-help">Aucune décision pour l’instant. Validez un plan dans l’onglet « Plan ».</p>
      ) : (
        plans.map((p) => {
          const label = (id: string) => p.teams.find((t) => t.id === id)?.label ?? id;
          const commune = (id: string) => p.incidents.find((i) => i.id === id)?.commune ?? id;
          return (
            <div key={p.j} className="journal-plan">
              <h3 className="journal-plan-head">
                <i className="swatch" style={{ background: `rgb(${planColour(p.j).join(',')})` }} aria-hidden /> Plan de {fmtHour(p.time)}
                <span className="muted">
                  {' '}
                  · {p.decisions.length} équipe{p.decisions.length > 1 ? 's' : ''}
                </span>
              </h3>
              <ul className="journal-list">
                {p.decisions.map((d) => (
                  <li key={d.incidentId} className={d.kind}>
                    <span className={`journal-kind ${d.kind}`}>{d.kind === 'accepted' ? 'Validée' : 'Modifiée'}</span>
                    <span>
                      <b>{label(d.teamId)}</b> → {commune(d.incidentId)}
                      {d.kind === 'overridden' && <span className="muted"> (au lieu de {label(d.recommendedTeamId)})</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })
      )}
    </section>
  );
}

export function RecPanel() {
  const snap = useOursSnapshot()!;
  const view = useStore((s) => s.view);
  const hoveredRecId = useStore((s) => s.hoveredRecId);
  const focused = useFocusedRec();

  if (view === 'reference')
    return (
      <section className="recs">
        <div className="card">
          <h2 className="card-title">À décider</h2>
          <div className="empty">Vue référence : aucune décision à prendre.</div>
        </div>
      </section>
    );

  const recs = snap.recommendations;
  const queue = recs.map((r, i) => ({ r, rank: i + 1 })).filter(({ r }) => r.id !== focused?.id);

  if (source.acceptPlan)
    return (
      <section className="recs">
        <PlanCard snap={snap} focusedId={focused?.id} hoveredRecId={hoveredRecId} />
      </section>
    );

  return (
    <section className="recs">
      <div className="card decide-card">
        <h2 className="card-title">
          À décider {recs.length > 0 && <span className="count">{recs.length}</span>}
        </h2>
        {focused ? <FocusCard key={focused.id} rec={focused} snap={snap} /> : <EmptyState snap={snap} />}

        {queue.length > 0 && (
          <>
            <h3 className="card-subtitle">Ensuite</h3>
            <ol className="queue" aria-label="File d’attente">
              {queue.map(({ r, rank }) => (
                <QueueRow key={r.id} rec={r} rank={rank} snap={snap} hovered={hoveredRecId === r.id} />
              ))}
            </ol>
          </>
        )}
      </div>
    </section>
  );
}
