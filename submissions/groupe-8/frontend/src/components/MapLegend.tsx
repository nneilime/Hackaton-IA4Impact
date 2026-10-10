import { useState } from 'react';
import { incidentIcon, teamIcon } from '../lib/icons';

const Item = ({ src, label, size = 16 }: { src: string; label: string; size?: number }) => (
  <li>
    <span className="lg-sym">
      <img src={src} width={size} height={size} alt="" />
    </span>
    {label}
  </li>
);

export function MapLegend({ saturation }: { saturation: boolean }) {
  const [open, setOpen] = useState(false);
  if (!open)
    return (
      <button className="pill legend-open" onClick={() => setOpen(true)}>
        Légende
      </button>
    );
  return (
    <div className="legend">
      <button className="round-close small" onClick={() => setOpen(false)} aria-label="Masquer la légende">
        ×
      </button>
      <div className="legend-col">
        <h4>Incidents (taille = clients)</h4>
        <ul>
          <Item src={incidentIcon('waiting', false).url} label="En attente" />
          <li>
            <span className="lg-sym">
              <i className="lg-cluster">3</i>
            </span>
            Plusieurs dans la commune
          </li>
          <Item src={incidentIcon('enroute', false).url} label="Équipe en route" />
          <Item src={incidentIcon('repairing', false).url} label="Dépannage en cours" />
          <Item src={incidentIcon('restored', false).url} label="Réalimenté" size={10} />
          <Item src={incidentIcon('waiting', true).url} label="Client sensible" size={19} />
        </ul>
        <h4>Équipes</h4>
        <ul>
          <li>
            <span className="lg-sym">
              <i className="lg-site">3</i>
            </span>
            Site · équipes disponibles
          </li>
          <Item src={teamIcon('travelling').url} label="En route" />
          <Item src={teamIcon('repairing').url} label="Sur intervention" />
          <Item src={teamIcon('available').url} label="Disponible hors site" />
          <Item src={teamIcon('resting').url} label="Au repos" />
        </ul>
        <h4>Affectations</h4>
        <ul>
          <li>
            <span className="lg-sym">
              <svg width="24" height="8">
                <line className="lg-dash" x1="2" y1="4" x2="22" y2="4" />
              </svg>
            </span>
            Recommandée
          </li>
          <li>
            <span className="lg-sym">
              <svg width="24" height="8">
                <line className="lg-seg s1" x1="2" y1="4" x2="7" y2="4" />
                <line className="lg-seg s2" x1="7" y1="4" x2="12" y2="4" />
                <line className="lg-seg s3" x1="12" y1="4" x2="17" y2="4" />
                <line className="lg-seg s4" x1="17" y1="4" x2="22" y2="4" />
              </svg>
            </span>
            Validée
          </li>
        </ul>
        {saturation && (
          <>
            <h4>Saturation</h4>
            <div className="lg-ramp" aria-hidden />
            <div className="lg-ramp-labels">
              <span>faible</span>
              <span>clients·h en attente</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
