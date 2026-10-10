import type { ReactNode } from 'react'
import { CircleX, RotateCw } from 'lucide-react'
import Tchouette from '../../mascot/Tchouette'
import type { HumeurTchouette } from '../../mascot/Tchouette'

interface EtatVideProps {
  titre: string
  humeur?: HumeurTchouette
  children: ReactNode
  actions?: ReactNode
}

/** Écran sans contenu, en largeur : Tchouette à gauche, la cause et la suite à droite. */
export function EtatVide({ titre, humeur = 'inquiete', children, actions }: EtatVideProps) {
  return (
    <section className="grid items-center gap-4 rounded-box border-2 border-secondary bg-base-100 p-5 shadow-[4px_4px_0_0] shadow-secondary motion-safe:animate-entree sm:grid-cols-[auto_minmax(0,1fr)] lg:max-w-4xl">
      <Tchouette humeur={humeur} taille={88} titre="" className="justify-self-center" />
      <div className="grid gap-2">
        <h2 className="text-lg font-bold leading-tight lg:text-xl">{titre}</h2>
        <div className="grid gap-1.5 text-sm leading-relaxed">{children}</div>
        {actions && <div className="flex flex-wrap gap-2 pt-1">{actions}</div>}
      </div>
    </section>
  )
}

interface EtatErreurProps {
  titre: string
  message: string
  onReessayer: () => void
}

/** Erreur de l'API : le message est affiché tel quel, avec un bouton pour réessayer. */
export function EtatErreur({ titre, message, onReessayer }: EtatErreurProps) {
  return (
    <div role="alert" className="alert alert-error alert-vertical text-sm sm:alert-horizontal">
      <CircleX className="size-5 shrink-0" aria-hidden="true" />
      <div className="grid gap-0.5">
        <h2 className="font-bold">{titre}</h2>
        <p>{message}</p>
      </div>
      <button type="button" onClick={onReessayer} className="btn btn-sm">
        <RotateCw className="size-4" aria-hidden="true" />
        Réessayer
      </button>
    </div>
  )
}

/** Tchouette réfléchit (la mascotte de l'intro passe en « reflexion ») pendant l'appel à l'API. */
export function ChargementTchouette({ texte }: { texte: string }) {
  return (
    <p role="status" className="flex items-center gap-2 text-sm font-semibold">
      <span className="loading loading-dots loading-sm shrink-0" aria-hidden="true" />
      {texte}
    </p>
  )
}
