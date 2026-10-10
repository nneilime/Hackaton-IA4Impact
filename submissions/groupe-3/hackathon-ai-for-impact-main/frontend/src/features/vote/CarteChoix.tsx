import { Check, MapPin, Trophy } from 'lucide-react'
import type { OptionSondage } from '../../api/types'
import { IconeDestination } from './icones'
import { interetCourt, part } from './vote'

interface CarteChoixProps {
  option: OptionSondage
  total: number
  /** Le vote de l'élève (ou son vote final quand le vote est clos). */
  choisie: boolean
  /** Destination désignée à la fermeture du vote. */
  gagnante: boolean
  ferme: boolean
  /** Les pourcentages ne s'affichent qu'une fois que l'élève a voté (ou à la fin). */
  montrerResultats: boolean
  envoi: boolean
  onVoter: () => void
}

const CLASSES_CARTE = {
  /** Vote ouvert, carte non choisie. */
  libre:
    'card min-h-[72px] w-full cursor-pointer flex-row items-center gap-3 border-2 border-base-300 bg-base-100 p-3 text-left hover:border-secondary focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-secondary active:scale-[0.98] motion-safe:transition-transform',
  /** Vote ouvert, le choix de l'élève : contour et ombre dure bleu nuit, petit rebond. */
  choisie:
    'card min-h-[72px] w-full cursor-pointer flex-row items-center gap-3 border-2 border-secondary bg-base-100 p-3 text-left shadow-[4px_4px_0_0] shadow-secondary focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-secondary active:scale-[0.98] motion-safe:transition-transform motion-safe:animate-pop',
  /** Vote clos. */
  gagnante: 'card flex-row items-center gap-3 border-2 border-secondary bg-base-100 p-3 shadow-[4px_4px_0_0] shadow-secondary',
  perdante: 'card flex-row items-center gap-3 border-2 border-base-300 bg-base-100 p-3 opacity-75',
} as const

/** Grande carte tactile d'une destination sur le téléphone de l'élève : un appui = un vote. */
export default function CarteChoix(props: CarteChoixProps) {
  const { option, total, choisie, gagnante, ferme, montrerResultats, envoi, onVoter } = props
  const pourcentage = part(option, total)

  const contenu = (
    <>
      <span className="grid size-12 shrink-0 place-items-center rounded-full bg-secondary text-secondary-content">
        <IconeDestination option={option} className="size-6" />
      </span>
      <span className="grid min-w-0 flex-1 gap-0.5">
        <span className="text-base font-bold leading-tight break-words">{option.nom}</span>
        <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide opacity-70">
          <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
          {option.commune}
        </span>
        <span className="line-clamp-2 text-sm leading-snug">{interetCourt(option.interet_pedagogique)}</span>
        {montrerResultats && (
          <span className="mt-1 flex items-center gap-2">
            <progress
              className={choisie || gagnante ? 'progress progress-primary h-2.5 flex-1' : 'progress h-2.5 flex-1'}
              value={pourcentage}
              max={100}
              aria-label={`${option.nom} : ${pourcentage} % des votes`}
            />
            <span className="w-11 text-right text-sm font-extrabold tabular-nums">{pourcentage} %</span>
          </span>
        )}
        {gagnante && (
          <span className="flex items-center gap-1 text-xs font-bold">
            <Trophy className="size-3.5 shrink-0" aria-hidden="true" />
            Choisie par la classe
          </span>
        )}
        {choisie && (
          <span className="flex items-center gap-1 text-xs font-bold">
            <Check className="size-3.5 shrink-0" aria-hidden="true" />
            Ton vote
          </span>
        )}
      </span>
    </>
  )

  if (ferme) {
    return (
      <div className={gagnante ? CLASSES_CARTE.gagnante : CLASSES_CARTE.perdante}>
        {contenu}
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={onVoter}
      aria-pressed={choisie}
      aria-busy={envoi}
      className={choisie ? CLASSES_CARTE.choisie : CLASSES_CARTE.libre}
    >
      {contenu}
      <span className="grid size-8 shrink-0 place-items-center" aria-hidden="true">
        {envoi ? (
          <span className="loading loading-spinner loading-sm" />
        ) : choisie ? (
          <span className="grid size-8 place-items-center rounded-full bg-primary text-primary-content motion-safe:animate-pop">
            <Check className="size-5" />
          </span>
        ) : (
          <span className="size-7 rounded-full border-2 border-base-300" />
        )}
      </span>
    </button>
  )
}
