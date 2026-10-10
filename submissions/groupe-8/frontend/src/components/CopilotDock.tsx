import { useStore } from '../state/store';
import { Copilot } from './Copilot';

/** Opened from the header ("Demander au copilote") or from "Pourquoi ?"; slides over the
 *  recommendations so the map stays free. Always mounted: the conversation survives closing. */
export function CopilotDock() {
  const open = useStore((s) => s.copilotOpen);
  return (
    <div className={`copilot-dock ${open ? 'open' : ''}`} aria-hidden={!open} inert={!open}>
      <Copilot />
    </div>
  );
}
