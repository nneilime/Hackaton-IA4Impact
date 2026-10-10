import type { CSSProperties } from 'react'
import type { Indice, Niveau } from '../../api/types'
import { formaterPoints } from './format'

const TAILLES_ANNEAU = {
  sm: { taille: '3.5rem', epaisseur: '0.35rem', texte: 'text-base font-extrabold leading-none tabular-nums text-base-content' },
  md: { taille: '4.25rem', epaisseur: '0.45rem', texte: 'text-xl font-extrabold leading-none tabular-nums text-base-content' },
} as const

const CLASSES_ANNEAU: Record<Niveau, string> = {
  vert: 'radial-progress shrink-0 bg-base-200 text-success',
  orange: 'radial-progress shrink-0 bg-base-200 text-warning',
  rouge: 'radial-progress shrink-0 bg-base-200 text-error',
}

interface AnneauScoreProps {
  score: number
  niveau: Niveau
  taille?: keyof typeof TAILLES_ANNEAU
}

/** Le score sur 100 dans un anneau : le « O » de la ligne. */
export function AnneauScore({ score, niveau, taille = 'sm' }: AnneauScoreProps) {
  const valeur = Math.max(0, Math.min(100, Math.round(score)))
  const dimensions = TAILLES_ANNEAU[taille]
  // Variables imposées par le composant radial-progress de daisyUI.
  const style = {
    '--value': valeur,
    '--size': dimensions.taille,
    '--thickness': dimensions.epaisseur,
  } as CSSProperties
  return (
    <div
      className={CLASSES_ANNEAU[niveau]}
      style={style}
      role="progressbar"
      aria-valuenow={valeur}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Indice de confiance : ${valeur} sur 100`}
    >
      <span className={dimensions.texte}>{valeur}</span>
    </div>
  )
}

/** Détail de l'Indice Confiance Voyageur Scolaire, critère par critère (contenu d'un collapse). */
export default function DetailIndice({ indice }: { indice: Indice }) {
  if (indice.details.length === 0) {
    return <p className="text-sm">Le détail des critères n'est pas disponible pour cette proposition.</p>
  }
  return (
    <ul className="grid gap-2.5">
      {indice.details.map((critere) => (
        <li key={critere.critere} className="grid gap-1">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="font-semibold">{critere.critere}</span>
            <span className="shrink-0 font-bold tabular-nums">
              {formaterPoints(critere.points)}/{formaterPoints(critere.max)}
            </span>
          </div>
          <progress
            className="progress h-1.5"
            value={critere.points}
            max={Math.max(1, critere.max)}
            aria-label={`${critere.critere} : ${formaterPoints(critere.points)} points sur ${formaterPoints(critere.max)}`}
          />
          <p className="text-xs leading-snug">{critere.explication}</p>
        </li>
      ))}
    </ul>
  )
}
