import type { ReactNode } from 'react'
import { CircleX, RotateCw } from 'lucide-react'
import Tchouette from '../../mascot/Tchouette'

interface VoteIntrouvableProps {
  titre: string
  children: ReactNode
  action?: ReactNode
}

/** Code inconnu (404) : Tchouette s'inquiète, on explique et on propose la suite. */
export function VoteIntrouvable({ titre, children, action }: VoteIntrouvableProps) {
  return (
    <section className="mx-auto grid w-full max-w-xl justify-items-center gap-4 rounded-box border-2 border-secondary bg-base-100 p-6 text-center shadow-[4px_4px_0_0] shadow-secondary">
      <Tchouette humeur="inquiete" taille={112} titre="" />
      <h1 className="text-2xl font-extrabold tracking-tight">{titre}</h1>
      <div className="grid gap-2 text-sm leading-relaxed lg:text-[15px]">{children}</div>
      {action}
    </section>
  )
}

interface ErreurVoteProps {
  titre: string
  message: string
  onReessayer: () => void
}

/** Erreur réseau ou serveur, avec le message de l'API et un bouton pour réessayer. */
export function ErreurVote({ titre, message, onReessayer }: ErreurVoteProps) {
  return (
    <div role="alert" className="alert alert-error alert-vertical w-full max-w-xl sm:alert-horizontal">
      <CircleX className="size-6 shrink-0" aria-hidden="true" />
      <div className="grid gap-1">
        <h1 className="font-bold">{titre}</h1>
        <p className="text-sm">{message}</p>
      </div>
      <button type="button" onClick={onReessayer} className="btn btn-sm">
        <RotateCw className="size-4" aria-hidden="true" />
        Réessayer
      </button>
    </div>
  )
}
