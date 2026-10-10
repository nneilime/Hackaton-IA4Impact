import type { CSSProperties } from 'react'
import { Flag, Trophy } from 'lucide-react'
import type { Sondage } from '../../api/types'
import TrainLio from './TrainLio'
import { libelleVotes, meneurs, part } from './vote'

const CLASSES_PISTE = {
  enCourse:
    'grid grid-cols-[minmax(0,1fr)_5.5rem] items-center gap-3 sm:grid-cols-[minmax(0,1fr)_9rem] sm:gap-4 xl:grid-cols-[minmax(0,1fr)_11rem]',
  /** Vote clos : les trains battus s'effacent derrière le gagnant. */
  distancee:
    'grid grid-cols-[minmax(0,1fr)_5.5rem] items-center gap-3 opacity-55 sm:grid-cols-[minmax(0,1fr)_9rem] sm:gap-4 xl:grid-cols-[minmax(0,1fr)_11rem]',
} as const

interface CourseTrainsProps {
  sondage: Sondage
}

/**
 * La course des trains : une piste par destination, chaque train avance selon sa part des votes.
 * La zone de déplacement s'arrête juste avant la ligne d'arrivée ; à la fermeture du vote,
 * seul le train gagnant la franchit.
 */
export default function CourseTrains({ sondage }: CourseTrainsProps) {
  const ferme = sondage.statut === 'ferme'
  const tete = meneurs(sondage)
  const meneurUnique = tete.length === 1 ? tete[0].site_id : null

  return (
    <ol className="grid gap-3" aria-label="Course des trains : part des votes par destination">
      {sondage.options.map((option, index) => {
        const pourcentage = part(option, sondage.total_votes)
        const gagnant = ferme && option.site_id === sondage.gagnant
        const enTete = !ferme && option.site_id === meneurUnique
        // Le gagnant dépasse la zone de course de 2,75 rem : il franchit la ligne d'arrivée.
        const avance = gagnant ? 'calc(100% + 2.75rem)' : `${pourcentage}%`
        return (
          <li
            key={option.site_id}
            className={ferme && !gagnant ? CLASSES_PISTE.distancee : CLASSES_PISTE.enCourse}
          >
            <div className="relative h-24 overflow-x-clip rounded-box border border-base-300 bg-base-200">
              <p className="absolute left-3 top-1.5 flex max-w-[calc(100%-4rem)] items-baseline gap-2 truncate leading-tight">
                <span className="truncate text-xl font-extrabold lg:text-2xl">{option.nom}</span>
                <span className="hidden truncate text-sm font-semibold opacity-70 xl:inline">{option.commune}</span>
              </p>
              {/* Traverses et rail, vus de profil */}
              <div
                aria-hidden="true"
                className="absolute inset-x-3 bottom-1.5 h-2 bg-[repeating-linear-gradient(90deg,var(--color-secondary)_0_7px,transparent_7px_20px)] opacity-35"
              />
              <div aria-hidden="true" className="absolute inset-x-3 bottom-3.5 h-1 rounded-full bg-secondary" />
              {/* Ligne d'arrivée en damier */}
              <div
                aria-hidden="true"
                className="absolute inset-y-2 right-3 w-5 border border-secondary bg-[repeating-conic-gradient(var(--color-secondary)_0_25%,var(--color-base-100)_0_50%)] bg-size-[10px_10px]"
              />
              {/* Zone de course : largeur de la piste moins le train et la ligne d'arrivée */}
              <div aria-hidden="true" className="absolute bottom-4 left-3 right-[8.75rem]">
                <div
                  className="w-full translate-x-(--avance) motion-safe:transition-transform motion-safe:duration-1000 motion-safe:ease-out"
                  style={{ '--avance': avance } as CSSProperties}
                >
                  <TrainLio numero={index + 1} className="h-auto w-24" />
                </div>
              </div>
            </div>
            <div className="grid justify-items-end gap-0.5 text-right">
              <p className="text-3xl font-extrabold tabular-nums leading-none sm:text-4xl lg:text-5xl">
                {pourcentage}
                <span className="text-xl sm:text-2xl lg:text-3xl"> %</span>
              </p>
              <p className="text-base font-semibold tabular-nums">{libelleVotes(option.votes)}</p>
              {gagnant && (
                <span className="badge badge-accent badge-sm font-bold motion-safe:animate-pop">
                  <Trophy className="size-3.5" aria-hidden="true" />
                  Choisie
                </span>
              )}
              {enTete && (
                <span className="badge badge-ghost badge-sm font-bold">
                  <Flag className="size-3.5" aria-hidden="true" />
                  En tête
                </span>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
