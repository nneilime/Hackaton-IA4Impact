import type { ReactNode } from 'react'
import Tchouette from '../../mascot/Tchouette'
import type { HumeurTchouette } from '../../mascot/Tchouette'

interface IntroEcranProps {
  titre: ReactNode
  /** Une phrase, 15 mots au plus. */
  phrase: ReactNode
  humeur?: HumeurTchouette
  /** Colonne de droite (bulle de Tchouette, chargement…). */
  aside?: ReactNode
}

/**
 * Intro d'étape sur une seule rangée (120 px au plus) : Tchouette, le titre et une phrase.
 * Deux décorations seulement : le disque or derrière la mascotte et les traverses après le titre.
 */
export default function IntroEcran({ titre, phrase, humeur = 'parle', aside }: IntroEcranProps) {
  return (
    <header className="grid items-center gap-x-6 gap-y-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,30rem)]">
      <div className="flex min-w-0 items-center gap-3 motion-safe:animate-entree">
        <div className="relative shrink-0">
          <span aria-hidden="true" className="absolute -left-1.5 -top-1 size-10 rounded-full bg-accent" />
          <Tchouette humeur={humeur} taille={64} titre="" className="relative" />
        </div>
        <div className="grid min-w-0 gap-1">
          <h1 className="flex items-center gap-3 text-2xl font-extrabold leading-tight tracking-tight lg:text-3xl">
            {titre}
            <span
              aria-hidden="true"
              className="hidden h-2.5 w-12 shrink-0 border-y-2 border-secondary bg-[repeating-linear-gradient(90deg,var(--color-secondary)_0_3px,transparent_3px_8px)] sm:block"
            />
          </h1>
          <p className="text-sm lg:text-[15px]">{phrase}</p>
        </div>
      </div>
      {aside && <div className="min-w-0">{aside}</div>}
    </header>
  )
}
