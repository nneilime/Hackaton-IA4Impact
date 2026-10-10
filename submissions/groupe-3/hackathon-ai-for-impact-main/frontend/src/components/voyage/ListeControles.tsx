import type { Controle } from '../../api/types'
import { PuceNiveau } from './PastilleNiveau'
import { LIBELLES_CONTROLE } from './niveaux'
import { RANG_NIVEAU } from './format'

/** Les contrôles de la fiche (R1 à R10), les points bloquants d'abord. */
export default function ListeControles({ controles }: { controles: Controle[] }) {
  if (controles.length === 0) {
    return <p className="text-sm">Aucun contrôle n'a été transmis pour cette proposition.</p>
  }
  const tries = [...controles].sort((a, b) => RANG_NIVEAU[b.niveau] - RANG_NIVEAU[a.niveau])
  return (
    <ul className="list">
      {tries.map((controle, index) => (
        <li key={`${controle.regle}-${index}`} className="list-row items-start gap-2.5 px-0 py-2">
          <PuceNiveau niveau={controle.niveau} />
          <div className="grid gap-0.5">
            <p className="text-sm font-semibold leading-snug">
              {controle.libelle}
              <span className="font-bold"> · {LIBELLES_CONTROLE[controle.niveau]}</span>
            </p>
            <p className="text-xs leading-snug">{controle.message}</p>
          </div>
          <span className="text-xs font-semibold tabular-nums">{controle.regle}</span>
        </li>
      ))}
    </ul>
  )
}
