import { CircleCheck, CircleX, TriangleAlert } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Niveau } from '../../api/types'

interface InfosNiveau {
  /** Libellé par défaut, toujours affiché à côté de la couleur. */
  libelle: string
  Icone: LucideIcon
}

// Les classes de couleur vivent dans chaque composant, en chaînes complètes et statiques.
export const INFOS_NIVEAU: Record<Niveau, InfosNiveau> = {
  vert: { libelle: 'Fiable', Icone: CircleCheck },
  orange: { libelle: 'Point de vigilance', Icone: TriangleAlert },
  rouge: { libelle: 'Pas adapté à votre groupe', Icone: CircleX },
}

/** Libellés selon ce que l'on qualifie : la couleur n'est jamais le seul signal. */
export const LIBELLES_CONTROLE: Record<Niveau, string> = {
  vert: 'Conforme',
  orange: 'Vigilance',
  rouge: 'Bloquant',
}

export const LIBELLES_ACCES: Record<Niveau, string> = {
  vert: 'Accès facile',
  orange: 'Accès à anticiper',
  rouge: 'Accès difficile',
}

export const LIBELLES_JAUGE: Record<Niveau, string> = {
  vert: 'Places suffisantes',
  orange: 'Places tout juste suffisantes',
  rouge: 'Places insuffisantes',
}
