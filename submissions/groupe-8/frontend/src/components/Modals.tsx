// Popups for the real engine's features: the 3 best options, refusal → rule, reinforcement, expert review
// (learning loop) and active rules. Hidden with the mock source (capabilities are optional).
import { useEffect, useState, type ReactNode } from 'react';
import type { Recommendation } from '../data/contract';
import {
  source,
  type Backtest,
  type Candidate,
  type RefusalResult,
  type RegistryEntry,
  type Remark,
  type Reinforcement,
  type RuleRow,
} from '../data/source';
import { fmtHour, fmtInt, fmtMinutes } from '../lib/format';
import { stepOf, useOursSnapshot, useStore } from '../state/store';

/** Same colours as the option routes on the map (rank 1 = recommended). */
export const OPTION_COLOURS = ['var(--green)', 'var(--yellow)', 'var(--waiting)'];

const REASONS: { code: string; label: string }[] = [
  { code: 'acces', label: 'Route coupée / zone inaccessible' },
  { code: 'equipe', label: 'Équipe indisponible' },
  { code: 'duree', label: 'Durée sous-estimée' },
  { code: 'priorite', label: 'Autre incident prioritaire' },
  { code: 'competence', label: 'Compétence / habilitation' },
  { code: 'securite', label: 'Sécurité' },
  { code: 'terrain', label: 'Connaissance du terrain' },
  { code: 'autre', label: 'Autre' },
];

/** Centered popup with a scrim; `side` = panel on the right without scrim, so the map stays readable. */
function Modal({ title, subtitle, children, foot, wide, side }: { title: string; subtitle?: string; children: ReactNode; foot?: ReactNode; wide?: boolean; side?: boolean }) {
  const close = () => useStore.getState().openModal(undefined);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  return (
    <>
      {!side && <div className="scrim" onClick={close} />}
      <div className={`modal ${wide ? 'wide' : ''} ${side ? 'side' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
        <header className="drawer-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="round-close" onClick={close} aria-label="Fermer">
            ×
          </button>
        </header>
        <div className="drawer-body">{children}</div>
        {foot && <footer className="drawer-foot">{foot}</footer>}
      </div>
    </>
  );
}

export function ModalHost() {
  const modal = useStore((s) => s.modal);
  if (!modal) return null;
  if (modal.kind === 'options') return <OptionsModal recId={modal.recId!} />;
  if (modal.kind === 'refusal') return <RefusalModal recId={modal.recId} />;
  if (modal.kind === 'reinforcement') return <ReinforcementModal />;
  if (modal.kind === 'review') return <ReviewModal />;
  return <RulesModal />;
}

function useRec(recId: string): Recommendation | undefined {
  return useOursSnapshot()?.recommendations.find((r) => r.id === recId);
}

// ---------------------------------------------------------------- 3 best options
function OptionsModal({ recId }: { recId: string }) {
  const rec = useRec(recId);
  const snap = useOursSnapshot()!;
  const busy = useStore((s) => s.busy);
  const hovered = useStore((s) => s.hoveredOption);
  const { hoverOption, accept, override, openModal } = useStore.getState();
  if (!rec?.options?.length) return null;
  const inc = snap.incidents.find((i) => i.id === rec.incidentId);
  const label = (id: string) => snap.teams.find((t) => t.id === id)?.label ?? id;
  const choose = async (rank: number, team: string) => {
    openModal(undefined);
    if (rank === 1) await accept(rec);
    else await override(rec, team, 'Choix parmi les 3 meilleures options');
  };
  return (
    <Modal side title="Les 3 meilleures options" subtitle={`Poste de ${inc?.commune ?? rec.incidentId} · ${fmtInt(rec.factors.clients)} clients`}>
      <p className="modal-intro">Survolez une ligne pour voir le trajet sur la carte. Le coût est la coupure supplémentaire (clients × heures) par rapport à l’option recommandée.</p>
      <div className="opt-table" role="table">
        {rec.options.map((o) => (
          <div
            key={o.rank}
            role="row"
            className={`opt-row ${hovered === o.rank ? 'hovered' : ''}`}
            onMouseEnter={() => hoverOption(o.rank)}
            onMouseLeave={() => hoverOption(undefined)}
          >
            <i className="opt-swatch" style={{ background: OPTION_COLOURS[o.rank - 1] }} />
            <span className="opt-team">
              <b>{label(o.team)}</b>
              <span className="muted"> · {o.team_site}</span>
              {o.recommended && <span className="tag">Recommandée</span>}
            </span>
            <span className="num">{fmtMinutes(o.travel_min)}</span>
            <span className="num">{fmtHour(o.restoredAt)}</span>
            <span className={`num ${o.extra_customer_hours > 0 ? 'cost' : ''}`}>
              {o.extra_customer_hours > 0 ? `+${fmtInt(o.extra_customer_hours)} clients·h` : 'référence'}
            </span>
            <button className={`pill small ${o.recommended ? 'primary' : ''}`} disabled={busy} onClick={() => choose(o.rank, o.team)}>
              Choisir
            </button>
          </div>
        ))}
      </div>
      <div className="opt-legend muted">Colonnes : équipe · trajet · rétablissement prévu · coût</div>
    </Modal>
  );
}

// ---------------------------------------------------------------- refusal -> rule (learning loop)
function RefusalModal({ recId }: { recId?: string }) {
  const snap = useOursSnapshot()!;
  // Refusing the whole plan: the manager says which line is wrong (default: the first) and why.
  const [picked, setPicked] = useState<string | undefined>(recId ?? snap.recommendations[0]?.id);
  const rec = useRec(picked ?? '');
  const step = useStore(stepOf);
  const [code, setCode] = useState<string | undefined>();
  const [text, setText] = useState('');
  const [phase, setPhase] = useState<'input' | 'loading' | 'done'>('input');
  const [result, setResult] = useState<RefusalResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!rec) return null;
  const team = snap.teams.find((t) => t.id === rec.teamId)?.label ?? rec.teamId;
  const inc = snap.incidents.find((i) => i.id === rec.incidentId);

  const submit = async () => {
    setPhase('loading');
    setError(null);
    try {
      const r = await source.refuse!(step, rec.incidentId, rec.teamId, code, text || undefined);
      setResult(r);
      setPhase('done');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase('input');
    }
  };
  const confirm = async (pid: number, restatement: string) => {
    setPhase('loading');
    try {
      const tl = await source.confirmRefusal!(pid);
      useStore.getState().openModal(undefined);
      useStore.getState().applyTimelines(tl, { tone: 'info', title: 'Règle appliquée, plan recalculé', body: restatement });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase('done');
    }
  };

  const proposal = result && 'proposalId' in result ? result : null;
  const question = result && 'question' in result ? result.question : null;
  return (
    <Modal
      title={recId ? 'Refuser la recommandation' : 'Refuser le plan'}
      subtitle={`${team} → ${inc?.commune ?? rec.incidentId}`}
      foot={
        proposal ? (
          <>
            <button className="pill primary" disabled={phase === 'loading'} onClick={() => confirm(proposal.proposalId, proposal.restatement)}>
              Appliquer la règle
            </button>
            <button className="pill" onClick={() => (setResult(null), setPhase('input'))}>
              Corriger le motif
            </button>
          </>
        ) : (
          <button className="pill primary" disabled={phase === 'loading' || (!code && !text.trim())} onClick={submit}>
            {phase === 'loading' ? 'Analyse du motif…' : 'Envoyer le motif'}
          </button>
        )
      }
    >
      {!proposal && (
        <>
          {!recId && snap.recommendations.length > 1 && (
            <label className="refuse-line">
              Quelle affectation pose problème ?
              <select value={picked} onChange={(e) => (setPicked(e.target.value), setResult(null))}>
                {snap.recommendations.map((r, i) => (
                  <option key={r.id} value={r.id}>
                    {i + 1}. {snap.teams.find((t) => t.id === r.teamId)?.label ?? r.teamId} →{' '}
                    {snap.incidents.find((x) => x.id === r.incidentId)?.commune ?? r.incidentId}
                  </option>
                ))}
              </select>
            </label>
          )}
          <p className="modal-intro">Pourquoi refusez-vous ? Le motif est traduit en règle pour le moteur, chiffrée avant application, et enregistré pour le retour d’expérience.</p>
          <div className="chip-row" role="group" aria-label="Motif">
            {REASONS.map((r) => (
              <button key={r.code} className={`pill small ${code === r.code ? 'selected' : ''}`} onClick={() => setCode(code === r.code ? undefined : r.code)}>
                {r.label}
              </button>
            ))}
          </div>
          {question && <div className="modal-question">{question}</div>}
          <textarea
            className="modal-text"
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Précisez (ex. « la route est inondée jusqu’à 18h », « camion en panne pendant 3 h »)…"
          />
        </>
      )}
      {proposal && (
        <div className="modal-proposal">
          <p className="modal-restatement">{proposal.restatement}</p>
          {proposal.rules.length > 1 && <ul className="rule-list">
            {proposal.rules.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>}
          <p className={proposal.costDelta > 0 ? 'cost' : 'gain'}>
            Coût de la règle : {proposal.costDelta > 0 ? '+' : ''}
            {fmtInt(proposal.costDelta)} clients·h sur le plan
          </p>
        </div>
      )}
      {result && 'error' in result && <p className="modal-error">{result.error}</p>}
      {error && <p className="modal-error">{error}</p>}
    </Modal>
  );
}

// ---------------------------------------------------------------- reinforcement
/** Share as a percentage, one decimal, rounded DOWN: 89.7 % must never read "90 %" next to a missed 90 % target. */
const pct = (x: number) => (Math.floor(x * 1000) / 10).toFixed(1).replace('.', ',').replace(',0', '');
function ReinforcementModal() {
  const step = useStore(stepOf);
  const [r, setR] = useState<Reinforcement | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    source
      .reinforcement!(step)
      .then((x) => {
        if (!live) return;
        setR(x);
        useStore.getState().setHighlightSites(x.reinforcement?.sites.map((s) => s.id) ?? []);
      })
      .catch((e) => live && setError(String(e)));
    return () => {
      live = false;
    };
  }, [step]);
  const rf = r?.reinforcement;
  // The endpoint says what its shares count; the spec counts incidents.
  const unit =
    r?.basis === 'customers'
      ? { long: 'clients coupés rétablis' }
      : { long: 'incidents signalés réparés' };
  const request = () => {
    useStore.getState().toast({
      tone: 'ok',
      title: `Demande de renfort préparée : +${rf!.extra_teams} équipes`,
      body: rf!.sites.map((s) => `${s.extra} à ${s.name}`).join(', '),
    });
    useStore.getState().openModal(undefined);
  };
  return (
    <Modal
      side
      title="Objectif 48 h : renforts"
      subtitle={`Part des ${unit.long} avant 48 h selon le plan actuel (objectif 90 %)`}
      foot={rf && !r?.target_met ? <button className="pill primary" onClick={request}>Préparer la demande de renfort (FIRE)</button> : undefined}
    >
      {!r && !error && <p className="modal-intro">Simulation des renforts en cours…</p>}
      {error && <p className="modal-error">{error}</p>}
      {r && (
        <>
          <div className="reinf-figure">
            <span className={`reinf-share ${r.target_met ? 'ok' : 'over'}`}>{pct(r.projected_share)} %</span>
            <span>
              des {unit.long} à 48 h (objectif {Math.round(r.target * 100)} %)
            </span>
          </div>
          {r.target_met ? (
            <p className="gain">Objectif tenu avec les équipes actuelles : pas de renfort nécessaire.</p>
          ) : rf ? (
            <>
              <p>
                Objectif hors d’atteinte. Avec <b>{rf.extra_teams} équipe(s) en renfort</b>, le plan atteint{' '}
                <b>{pct(rf.projected_share_after)} %</b>. Sites où les placer (en surbrillance sur la carte) :
              </p>
              <ul className="reinf-sites">
                {rf.sites
                  .sort((a, b) => b.extra - a.extra)
                  .map((s) => (
                    <li key={s.id}>
                      <b>+{s.extra}</b> à {s.name}
                    </li>
                  ))}
              </ul>
              <p className="muted">Hypothèse : renforts disponibles immédiatement ; en pratique, prévoir leur délai d’arrivée.</p>
            </>
          ) : null}
        </>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------- active rules
function RulesModal() {
  const [rules, setRules] = useState<{ crisis: RuleRow[]; permanent: RuleRow[] } | null>(null);
  const busy = useStore((s) => s.busy);
  const load = () => source.listRules!().then(setRules);
  useEffect(() => {
    load();
  }, []);
  const remove = async (i: number) => {
    useStore.setState({ busy: true });
    try {
      const tl = await source.removeRule!(i);
      useStore.getState().applyTimelines(tl, { tone: 'info', title: 'Règle retirée, plan recalculé' });
      await load();
    } finally {
      useStore.setState({ busy: false });
    }
  };
  return (
    <Modal title="Règles actives" subtitle="Ce que le moteur respecte en plus des règles de sécurité">
      <h3 className="modal-h3">Pendant cette crise</h3>
      {!rules?.crisis.length && <p className="muted">Aucune règle : refusez une recommandation avec un motif pour en créer une.</p>}
      <ul className="rule-rows">
        {rules?.crisis.map((r) => (
          <li key={r.index}>
            <span>
              <b>{r.label}</b>
              {r.reason && <span className="muted"> · « {r.reason} »</span>}
            </span>
            <button className="pill small" disabled={busy} onClick={() => remove(r.index!)}>
              Retirer
            </button>
          </li>
        ))}
      </ul>
      <h3 className="modal-h3">Ajustements du calcul adoptés (retour d’expérience)</h3>
      {!rules?.permanent.length && <p className="muted">Aucun ajustement adopté.</p>}
      <ul className="rule-rows">
        {rules?.permanent.map((r) => (
          <li key={r.label}>
            <b>{r.label}</b>
          </li>
        ))}
      </ul>
    </Modal>
  );
}

// ---------------------------------------------------------------- retour d'expérience (learning loop)
// The manager's remarks are saved; the AI looks for recurring patterns and proposes to adjust ONE variable of the
// calculation (e.g. travel time towards a zone); its effect is measured on past crises; a person adopts it or not.
const REASON_LABEL: Record<string, string> = Object.fromEntries(REASONS.map((r) => [r.code, r.label]));

function ReviewModal() {
  const L = source.learning!;
  const [stats, setStats] = useState<{ total: number; rejected?: number; refusal_rate: number } | null>(null);
  const [remarks, setRemarks] = useState<Remark[]>([]);
  const [cands, setCands] = useState<Candidate[] | null>(null);
  const [adopted, setAdopted] = useState<RegistryEntry[]>([]);
  const [tests, setTests] = useState<Record<string, Backtest | 'loading'>>({});
  const [ignored, setIgnored] = useState<string[]>([]);
  const [working, setWorking] = useState<string | null>(null);
  const load = async () => {
    const [s, c, r, m] = await Promise.all([L.stats(), L.candidates(), L.registry(), L.remarks()]);
    setStats(s);
    setCands(c);
    setAdopted(r.constraints.filter((x) => x.status === 'active'));
    setRemarks(m);
  };
  useEffect(() => {
    load();
  }, []);
  const run = async (label: string, f: () => Promise<unknown>) => {
    setWorking(label);
    try {
      await f();
    } finally {
      setWorking(null);
    }
  };
  const simulate = () =>
    run('Rejeu de 2 crises avec un responsable simulé…', async () => {
      await L.simulate(['CRISE_051', 'CRISE_046']);
      await load();
    });
  const measure = async (c: Candidate) => {
    setTests((t) => ({ ...t, [c.key]: 'loading' }));
    const r = await L.backtest(c);
    setTests((t) => ({ ...t, [c.key]: r }));
  };
  const adopt = (c: Candidate) =>
    run('Ajustement adopté, recalcul de la crise…', async () => {
      await L.activate(c, 'Responsable de crise (démo)');
      await useStore.getState().reload();
      await load();
      useStore.getState().toast({ tone: 'ok', title: 'Ajustement adopté', body: `${c.variable} : ${c.before} → ${c.after}` });
    });
  const undo = (id: string) =>
    run('Annulation de l’ajustement…', async () => {
      await L.retire(id);
      await useStore.getState().reload();
      await load();
    });
  const shown = (cands ?? []).filter((c) => !ignored.includes(c.key) && !adopted.some((a) => a.description === c.description));
  return (
    <Modal wide title="Retour d’expérience" subtitle="Vos remarques sont enregistrées · l’IA repère les tendances · elle propose d’ajuster le calcul · vous décidez">
      <ol className="rex-steps">
        <li>
          <b>{fmtInt(stats?.rejected ?? 0)}</b> remarques enregistrées
        </li>
        <li>
          <b>{shown.length}</b> tendance{shown.length > 1 ? 's' : ''} repérée{shown.length > 1 ? 's' : ''}
        </li>
        <li>
          <b>{adopted.length}</b> ajustement{adopted.length > 1 ? 's' : ''} adopté{adopted.length > 1 ? 's' : ''}
        </li>
      </ol>
      {working && <p className="modal-question">{working}</p>}

      <h3 className="modal-h3">Ce que l’IA propose</h3>
      {cands && !shown.length && (
        <p className="muted">
          Pas encore de tendance : il faut au moins 3 remarques semblables (même site, même zone).{' '}
          <button className="link" disabled={!!working} onClick={simulate}>
            Générer des remarques de démonstration
          </button>
        </p>
      )}
      <div className="cand-list">
        {shown.map((c) => {
          const t = tests[c.key];
          return (
            <article key={c.key} className="rex-card">
              <div className="rex-row">
                <span className="rex-label">Observé</span>
                <p>
                  {c.observed}
                  {c.evidence.simulated_share > 0 && <span className="tag tag-quiet">démo</span>}
                </p>
              </div>
              {c.evidence.examples[0] && (
                <div className="rex-row">
                  <span className="rex-label">Exemple</span>
                  <p className="rex-quote">« {c.evidence.examples[0]} »</p>
                </div>
              )}
              <div className="rex-row">
                <span className="rex-label">Proposé</span>
                <p>{c.proposal}</p>
              </div>
              <div className="rex-variable">
                <span>{c.variable}</span>
                <b>{c.before}</b>
                <span aria-hidden>→</span>
                <b className="after">{c.after}</b>
              </div>
              <div className="rex-row">
                <span className="rex-label">Effet</span>
                {!t && <p className="muted">À mesurer sur des crises passées avant de décider.</p>}
                {t === 'loading' && <p className="muted">Rejeu de crises passées…</p>}
                {t && t !== 'loading' && (
                  <p className={t.cost_pct > 2 ? 'cost' : 'gain'}>
                    Sur {t.crises} crises passées : {t.cost_pct > 0 ? '+' : ''}
                    {t.cost_pct.toFixed(1).replace('.', ',')} % de coupure au total, objectif 48 h tenu dans {t.target_still_met_in}/{t.crises}.
                  </p>
                )}
              </div>
              <div className="cand-actions">
                <button className="pill small" disabled={t === 'loading' || !!working} onClick={() => measure(c)}>
                  {t && t !== 'loading' ? 'Mesurer à nouveau' : 'Mesurer l’effet'}
                </button>
                <button className="pill small primary" disabled={!!working} onClick={() => adopt(c)}>
                  Adopter l’ajustement
                </button>
                <button className="pill small" disabled={!!working} onClick={() => setIgnored((x) => [...x, c.key])}>
                  Ignorer
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {adopted.length > 0 && (
        <>
          <h3 className="modal-h3">Ajustements adoptés</h3>
          <ul className="rule-rows">
            {adopted.map((r) => (
              <li key={r.id}>
                <span>
                  {r.description} <span className="muted">· {r.approved_by}, {r.activated_on}</span>
                </span>
                <button className="pill small" disabled={!!working} onClick={() => undo(r.id)}>
                  Annuler
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <h3 className="modal-h3">Remarques enregistrées (les plus récentes)</h3>
      {!remarks.length && <p className="muted">Aucune remarque : refusez un plan avec un motif pour en créer une.</p>}
      <ul className="rex-remarks">
        {remarks.map((r, i) => (
          <li key={i}>
            <span className="rex-reason">{REASON_LABEL[r.reason_code ?? ''] ?? (r.reason_code === 'override' ? 'Changement d’équipe' : 'Autre')}</span>
            <span>
              Équipe de <b>{r.site}</b> → {r.commune}
              {r.reason_text && <span className="muted"> · « {r.reason_text} »</span>}
            </span>
            {r.simulated && <span className="tag tag-quiet">démo</span>}
          </li>
        ))}
      </ul>
    </Modal>
  );
}
