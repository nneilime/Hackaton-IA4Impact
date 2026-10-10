import type { Niveau } from '../../api/types'
import { INFOS_NIVEAU } from './niveaux'

const CLASSES_PASTILLE: Record<Niveau, string> = {
  vert: 'badge badge-success badge-sm h-auto min-h-5 gap-1 py-0.5 text-left font-semibold',
  orange: 'badge badge-warning badge-sm h-auto min-h-5 gap-1 py-0.5 text-left font-semibold',
  rouge: 'badge badge-error badge-sm h-auto min-h-5 gap-1 py-0.5 text-left font-semibold',
}

const CLASSES_PUCE: Record<Niveau, string> = {
  vert: 'grid size-5 shrink-0 place-items-center rounded-full bg-success text-success-content',
  orange: 'grid size-5 shrink-0 place-items-center rounded-full bg-warning text-warning-content',
  rouge: 'grid size-5 shrink-0 place-items-center rounded-full bg-error text-error-content',
}

interface PastilleNiveauProps {
  niveau: Niveau
  /** Remplace le libellé par défaut (« Fiable », « Point de vigilance », « Pas adapté à votre groupe »). */
  libelle?: string
}

/** Pastille de statut : couleur + icône + texte, jamais la couleur seule. */
export default function PastilleNiveau({ niveau, libelle }: PastilleNiveauProps) {
  const { Icone, libelle: libelleParDefaut } = INFOS_NIVEAU[niveau]
  return (
    <span className={CLASSES_PASTILLE[niveau]}>
      <Icone className="size-3.5 shrink-0" aria-hidden="true" />
      {libelle ?? libelleParDefaut}
    </span>
  )
}

/** Rond plein avec l'icône du statut ; le texte qui l'accompagne porte le sens. */
export function PuceNiveau({ niveau }: { niveau: Niveau }) {
  const { Icone } = INFOS_NIVEAU[niveau]
  return (
    <span className={CLASSES_PUCE[niveau]} aria-hidden="true">
      <Icone className="size-3.5" />
    </span>
  )
}
