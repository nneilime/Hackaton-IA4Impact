import { ArrowRight, MapPin, TrainFront, Trophy } from 'lucide-react'
import type { OptionSondage } from '../../api/types'
import Confettis from './Confettis'
import { libelleVotes, part } from './vote'

interface BilletGagnantProps {
  option: OptionSondage
  total: number
  onVoirTrains: () => void
}

/**
 * Célébration de fin de vote : un billet (talon or, bord perforé, ombre dure bleu nuit) annonce la
 * destination choisie, entouré de confettis Memphis, avec l'étape suivante du parcours.
 */
export default function BilletGagnant({ option, total, onVoirTrains }: BilletGagnantProps) {
  return (
    <div className="relative px-7 py-9">
      <Confettis />
      <article
        aria-live="polite"
        className="relative grid grid-cols-[auto_minmax(0,1fr)] overflow-hidden rounded-box border-2 border-secondary bg-base-100 shadow-[6px_6px_0_0] shadow-secondary motion-safe:animate-pop"
      >
        <div className="relative grid place-items-center border-r-2 border-dashed border-secondary bg-accent px-5 text-accent-content before:absolute before:-right-3.5 before:-top-3.5 before:size-7 before:rounded-full before:border-2 before:border-secondary before:bg-base-200 after:absolute after:-bottom-3.5 after:-right-3.5 after:size-7 after:rounded-full after:border-2 after:border-secondary after:bg-base-200">
          <Trophy className="size-12" aria-hidden="true" />
        </div>
        <div className="flex flex-wrap items-end justify-between gap-4 p-4 lg:p-5">
          <div className="grid min-w-0 gap-1">
            <p className="text-lg font-bold lg:text-xl">Destination choisie par la classe :</p>
            <h2 className="text-4xl font-extrabold tracking-tight lg:text-5xl">{option.nom}</h2>
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-base font-semibold">
              <span className="flex items-center gap-1">
                <MapPin className="size-4 shrink-0" aria-hidden="true" />
                {option.commune}
              </span>
              <span className="tabular-nums">
                {libelleVotes(option.votes)} sur {total} · {part(option, total)} %
              </span>
            </p>
          </div>
          <button type="button" onClick={onVoirTrains} className="btn btn-primary btn-md text-base">
            <TrainFront className="size-5" aria-hidden="true" />
            Voir les trains pour {option.nom}
            <ArrowRight className="size-5" aria-hidden="true" />
          </button>
        </div>
      </article>
    </div>
  )
}
