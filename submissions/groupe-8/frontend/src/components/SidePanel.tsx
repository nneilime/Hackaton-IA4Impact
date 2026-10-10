// Right column: one panel, four tabs. "Plan" = what the engine proposes now (validated as a whole),
// "Équipes" = every team, what it does and its shift, "Copilote" = questions in plain French,
// "Journal" = the decisions already taken.
// The copilot stays mounted while hidden so the conversation survives a tab switch.
import { useState } from 'react';
import { Copilot } from './Copilot';
import { Journal, RecPanel } from './RecPanel';
import { TeamsPanel } from './TeamsPanel';
import { stepOf, useOursSnapshot, useStore } from '../state/store';

type Tab = 'plan' | 'teams' | 'copilot' | 'journal';

export function SidePanel() {
  const snap = useOursSnapshot()!;
  const copilotOpen = useStore((s) => s.copilotOpen);
  const { openCopilot, closeCopilot } = useStore.getState();
  const [tab, setTab] = useState<Exclude<Tab, 'copilot'>>('plan');
  const active: Tab = copilotOpen ? 'copilot' : tab;
  const go = (t: Tab) => {
    if (t === 'copilot') openCopilot();
    else {
      closeCopilot();
      setTab(t);
    }
  };
  const nPlan = snap.recommendations.length;
  const nFree = snap.teams.filter((t) => t.status === 'available').length;
  const nDone = useStore((s) => s.timelines!.ours.slice(0, stepOf(s) + 1).reduce((a, p) => a + p.decisions.length, 0));

  return (
    <aside className="side panel">
      <div className="panel-tabs" role="tablist" aria-label="Panneau de décision">
        <button role="tab" aria-selected={active === 'plan'} className={active === 'plan' ? 'on' : ''} onClick={() => go('plan')}>
          Plan
          {nPlan > 0 && <span className="count live">{nPlan}</span>}
        </button>
        <button role="tab" aria-selected={active === 'teams'} className={active === 'teams' ? 'on' : ''} onClick={() => go('teams')}>
          Équipes
          <span className="count" title="équipes disponibles">{nFree}</span>
        </button>
        <button role="tab" aria-selected={active === 'copilot'} className={active === 'copilot' ? 'on' : ''} onClick={() => go('copilot')}>
          Copilote
        </button>
        <button role="tab" aria-selected={active === 'journal'} className={active === 'journal' ? 'on' : ''} onClick={() => go('journal')}>
          Journal
          {nDone > 0 && <span className="count">{nDone}</span>}
        </button>
      </div>
      <div className="panel-body" role="tabpanel">
        {active === 'plan' && <RecPanel />}
        {active === 'teams' && <TeamsPanel />}
        {active === 'journal' && <Journal snap={snap} />}
        <div className="panel-copilot" hidden={active !== 'copilot'}>
          <Copilot />
        </div>
      </div>
    </aside>
  );
}
