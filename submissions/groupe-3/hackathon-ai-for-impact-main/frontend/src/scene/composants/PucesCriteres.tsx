import { Info } from 'lucide-react'
import type { PuceCritere } from '../../api/types'

interface PucesCriteresProps {
  puces: PuceCritere[]
  manquants: string[]
}

/** Critères déjà recueillis en puces compactes, plus une ligne discrète pour ce qui manque encore. */
export default function PucesCriteres({ puces, manquants }: PucesCriteresProps) {
  if (puces.length === 0 && manquants.length === 0) return null
  return (
    <div className="flex flex-col gap-1.5">
      {puces.length > 0 && (
        <ul className="-mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0" aria-label="Ce que je sais de votre sortie">
          {puces.map((puce) => (
            <li key={puce.cle} className="badge badge-outline h-auto min-h-7 shrink-0 gap-1 border-secondary py-1 motion-safe:animate-pop">
              <span className="text-xs font-semibold text-base-content/70">{puce.libelle}</span>
              <span aria-hidden="true">·</span>
              <span className="text-sm font-bold tabular-nums">{puce.valeur}</span>
            </li>
          ))}
        </ul>
      )}
      {manquants.length > 0 && (
        <p className="flex min-w-0 items-center gap-1.5 text-xs text-base-content/70">
          <Info className="size-3.5 shrink-0" aria-hidden="true" />
          <span className="truncate">Il me manque : {manquants.join(', ')}</span>
        </p>
      )}
    </div>
  )
}
