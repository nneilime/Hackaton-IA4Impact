import { CircleCheck, CircleX, TriangleAlert } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Niveau } from '../../api/types'

type Taille = 'sm' | 'md'

/** Classes écrites en entier : Tailwind et daisyUI doivent pouvoir les lire telles quelles. */
const STYLES: Record<Niveau, { classes: Record<Taille, string>; Icone: LucideIcon; libelle: string }> = {
  vert: {
    classes: {
      sm: 'badge badge-success badge-sm h-auto min-h-6 gap-1.5 py-0.5 font-bold',
      md: 'badge badge-success badge-md h-auto min-h-7 gap-1.5 py-0.5 font-bold',
    },
    Icone: CircleCheck,
    libelle: 'Favorable',
  },
  orange: {
    classes: {
      sm: 'badge badge-warning badge-sm h-auto min-h-6 gap-1.5 py-0.5 font-bold',
      md: 'badge badge-warning badge-md h-auto min-h-7 gap-1.5 py-0.5 font-bold',
    },
    Icone: TriangleAlert,
    libelle: 'À vérifier',
  },
  rouge: {
    classes: {
      sm: 'badge badge-error badge-sm h-auto min-h-6 gap-1.5 py-0.5 font-bold',
      md: 'badge badge-error badge-md h-auto min-h-7 gap-1.5 py-0.5 font-bold',
    },
    Icone: CircleX,
    libelle: 'Défavorable',
  },
}

interface PastilleNiveauProps {
  niveau: Niveau
  /** Texte affiché à côté de l'icône ; la couleur n'est jamais le seul signal. */
  libelle?: string
  taille?: Taille
}

/** Pastille de niveau vert / orange / rouge : couleur + icône + texte. */
export default function PastilleNiveau({ niveau, libelle, taille = 'md' }: PastilleNiveauProps) {
  const { classes, Icone, libelle: libelleParDefaut } = STYLES[niveau]
  return (
    <span className={classes[taille]}>
      <Icone className="size-4 shrink-0" aria-hidden="true" />
      {libelle ?? libelleParDefaut}
    </span>
  )
}
