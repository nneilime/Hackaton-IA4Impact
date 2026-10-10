import type { ReactNode, Ref } from 'react'
import type { HumeurTchouette } from '../../mascot/Tchouette'
import TchouetteEnScene from './TchouetteEnScene'

interface IntroEtapeProps {
  humeur: HumeurTchouette
  titreTchouette: string
  titre: ReactNode
  /** Une phrase de 15 mots au plus. */
  phrase?: ReactNode
  /** Éléments posés à côté du titre, sur la même ligne (bouton Copier, pastille de statut…). */
  aCote?: ReactNode
  /** Ligne de métadonnées sous la phrase (lieu, date, dossier). */
  meta?: ReactNode
  idTitre?: string
  /** Pour placer le focus sur le titre après une transition d'écran. */
  refTitre?: Ref<HTMLHeadingElement>
  rebond?: boolean
  etoiles?: boolean
  rail?: boolean
}

/**
 * Intro d'étape sur une seule rangée (120 px au plus) : Tchouette + titre + une phrase.
 * Remplace les grands héros de la v1 (frontend/DESIGN.md §3).
 */
export default function IntroEtape({
  humeur,
  titreTchouette,
  titre,
  phrase,
  aCote,
  meta,
  idTitre,
  refTitre,
  rebond,
  etoiles,
  rail,
}: IntroEtapeProps) {
  return (
    <header className="flex items-center gap-3 motion-safe:animate-entree lg:gap-4">
      <TchouetteEnScene humeur={humeur} titre={titreTchouette} rebond={rebond} etoiles={etoiles} rail={rail} />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h1
            ref={refTitre}
            id={idTitre}
            tabIndex={refTitre ? -1 : undefined}
            className="min-w-0 text-2xl font-extrabold leading-tight tracking-tight text-balance focus:outline-none lg:text-3xl"
          >
            {titre}
          </h1>
          {aCote}
        </div>
        {phrase && <p className="max-w-3xl text-sm text-base-content/80 lg:text-[15px]">{phrase}</p>}
        {meta}
      </div>
    </header>
  )
}
