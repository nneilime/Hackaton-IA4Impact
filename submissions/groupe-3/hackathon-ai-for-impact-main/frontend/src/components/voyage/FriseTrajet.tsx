import { Fragment } from 'react'
import type { Trajet } from '../../api/types'
import { formaterDuree, libelleCorrespondances, minutesEntre } from './format'

type TypeArret = 'depart' | 'correspondance' | 'arrivee'

interface Arret {
  type: TypeArret
  gare: string
  /** Heure de passage principale (départ, ou arrivée au terminus). */
  heure: string
  /** Train pris à cet arrêt. */
  train?: string
  /** Pour une correspondance : heure d'arrivée du train précédent. */
  arriveePrecedente?: string
}

/** Morceau de voie : deux rails et leurs traverses, en bleu nuit. */
const VOIE =
  'h-2 min-w-1 flex-1 border-y-2 border-secondary bg-[repeating-linear-gradient(90deg,var(--color-secondary)_0_2px,transparent_2px_6px)]'

const POINTS: Record<TypeArret, string> = {
  depart: 'size-3.5 shrink-0 rounded-full border-2 border-secondary bg-primary',
  correspondance: 'size-3.5 shrink-0 rounded-full border-2 border-secondary bg-accent',
  arrivee: 'size-3.5 shrink-0 rounded-full border-2 border-secondary bg-secondary',
}

const ALIGNEMENTS: Record<TypeArret, string> = {
  depart: 'flex min-w-0 shrink flex-col items-start text-left',
  correspondance: 'flex min-w-0 shrink flex-col items-center text-center',
  arrivee: 'flex min-w-0 shrink flex-col items-end text-right',
}

function arretsDuTrajet(trajet: Trajet): Arret[] {
  const { segments } = trajet
  if (segments.length === 0) return []
  const arrets: Arret[] = [
    { type: 'depart', gare: segments[0].gare_depart, heure: segments[0].depart, train: segments[0].train },
  ]
  for (let i = 1; i < segments.length; i += 1) {
    arrets.push({
      type: 'correspondance',
      gare: segments[i].gare_depart,
      heure: segments[i].depart,
      train: segments[i].train,
      arriveePrecedente: segments[i - 1].arrivee,
    })
  }
  const dernier = segments[segments.length - 1]
  arrets.push({ type: 'arrivee', gare: dernier.gare_arrivee, heure: dernier.arrivee })
  return arrets
}

/** Phrase complète pour les lecteurs d'écran (la frise visuelle est masquée). */
function description(titre: string, trajet: Trajet, arrets: Arret[]): string {
  const etapes = arrets.map((arret) => {
    if (arret.type === 'depart') return `départ de ${arret.gare} à ${arret.heure}, train liO ${arret.train}`
    if (arret.type === 'correspondance') {
      return `correspondance à ${arret.gare} : arrivée ${arret.arriveePrecedente ?? ''}, départ ${arret.heure}, train liO ${arret.train}`
    }
    return `arrivée à ${arret.gare} à ${arret.heure}`
  })
  return `${titre} : ${etapes.join(' ; ')}. Durée ${formaterDuree(trajet.duree_min)}, ${libelleCorrespondances(trajet.correspondances).toLowerCase()}.`
}

interface FriseTrajetProps {
  trajet: Trajet
  /** « Aller » ou « Retour ». */
  titre: string
}

/** Frise compacte d'un trajet, de gare en gare, sur une voie horizontale. */
export default function FriseTrajet({ trajet, titre }: FriseTrajetProps) {
  const arrets = arretsDuTrajet(trajet)

  return (
    <div className="grid grid-cols-[3.75rem_minmax(0,1fr)] items-start gap-x-3">
      <div className="grid gap-0.5">
        <p className="text-xs font-semibold uppercase tracking-wide">{titre}</p>
        <p className="text-xs font-bold tabular-nums">{formaterDuree(trajet.duree_min)}</p>
        <p className="text-xs">{libelleCorrespondances(trajet.correspondances)}</p>
      </div>

      {arrets.length > 0 ? (
        <>
          <p className="sr-only">{description(titre, trajet, arrets)}</p>
          <div aria-hidden="true" className="flex min-w-0 items-start">
            {arrets.map((arret, index) => {
              const attente =
                arret.type === 'correspondance' && arret.arriveePrecedente
                  ? minutesEntre(arret.arriveePrecedente, arret.heure)
                  : null
              const trainPrecedent = index > 0 ? arrets[index - 1].train : undefined
              return (
                <Fragment key={`${arret.gare}-${arret.heure}-${index}`}>
                  {index > 0 && (
                    <div className="flex min-w-6 flex-1 flex-col">
                      <span className="h-5 truncate text-center text-xs font-semibold leading-5 tabular-nums">
                        {trainPrecedent}
                      </span>
                      <span className="flex h-4 items-center">
                        <span className={VOIE} />
                      </span>
                    </div>
                  )}
                  <div className={ALIGNEMENTS[arret.type]}>
                    <time className="h-5 text-sm font-bold leading-5 tabular-nums">{arret.heure}</time>
                    <span className="flex h-4 w-full items-center">
                      {arret.type !== 'depart' && <span className={VOIE} />}
                      <span className={POINTS[arret.type]} />
                      {arret.type !== 'arrivee' && <span className={VOIE} />}
                    </span>
                    <span className="text-xs font-semibold leading-tight break-words">{arret.gare}</span>
                    {attente !== null && <span className="text-xs tabular-nums">corresp. {attente} min</span>}
                  </div>
                </Fragment>
              )
            })}
          </div>
        </>
      ) : (
        <p className="text-sm">Le détail des trains n'est pas disponible pour ce trajet.</p>
      )}
    </div>
  )
}
