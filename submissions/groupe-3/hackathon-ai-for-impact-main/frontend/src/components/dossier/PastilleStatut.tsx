import { CircleCheck, CircleX, Hourglass, Lock, TriangleAlert } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Statut } from '../../api/types'

interface StyleStatut {
  badge: string
  puce: string
  Icone: LucideIcon
  libelle: string
}

/** Classes écrites en entier : Tailwind et daisyUI doivent pouvoir les lire telles quelles. */
const STYLES: Record<Statut, StyleStatut> = {
  OPTION: {
    badge: 'badge badge-info badge-md h-auto min-h-7 gap-1.5 py-0.5 font-bold',
    puce: 'grid size-7 place-items-center rounded-full border-2 border-secondary bg-info text-info-content',
    Icone: Lock,
    libelle: 'Option posée',
  },
  PRE_RESERVATION: {
    badge: 'badge badge-info badge-md h-auto min-h-7 gap-1.5 py-0.5 font-bold',
    puce: 'grid size-7 place-items-center rounded-full border-2 border-secondary bg-info text-info-content',
    Icone: Hourglass,
    libelle: 'En attente de confirmation',
  },
  CONFIRMATION: {
    badge: 'badge badge-success badge-md h-auto min-h-7 gap-1.5 py-0.5 font-bold',
    puce: 'grid size-7 place-items-center rounded-full border-2 border-secondary bg-success text-success-content',
    Icone: CircleCheck,
    libelle: 'Confirmée par SNCF',
  },
  CONTRE_PROPOSITION: {
    badge: 'badge badge-warning badge-md h-auto min-h-7 gap-1.5 py-0.5 font-bold',
    puce: 'grid size-7 place-items-center rounded-full border-2 border-secondary bg-warning text-warning-content',
    Icone: TriangleAlert,
    libelle: 'Contre-proposition',
  },
  ANNULE: {
    badge: 'badge badge-error badge-md h-auto min-h-7 gap-1.5 py-0.5 font-bold',
    puce: 'grid size-7 place-items-center rounded-full border-2 border-secondary bg-error text-error-content',
    Icone: CircleX,
    libelle: 'Annulée',
  },
}

/** Pastille de statut du dossier : couleur + icône + texte. */
export default function PastilleStatut({ statut }: { statut: Statut }) {
  const { badge, Icone, libelle } = STYLES[statut]
  return (
    <span className={badge}>
      <Icone className="size-4 shrink-0" aria-hidden="true" />
      {libelle}
    </span>
  )
}

/** Puce ronde de la frise chronologique (icône seule, le texte suit à côté). */
export function PuceStatut({ statut }: { statut: Statut }) {
  const { puce, Icone } = STYLES[statut]
  return (
    <span className={puce} aria-hidden="true">
      <Icone className="size-3.5" />
    </span>
  )
}
