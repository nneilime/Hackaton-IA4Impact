import { useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, History, RotateCcw } from 'lucide-react'
import type { Replique } from '../../api/types'
import TrainLio from '../../layout/TrainLio'
import CarnetVoyage from './CarnetVoyage'

interface BarreHauteProps {
  carnet: Replique[]
  /** Le parcours a dépassé l'accueil : « Recommencer » demande d'abord confirmation. */
  parcoursAvance: boolean
  onRecommencer: () => void
}

/** Même style que le bandeau classique : bouton carré 40 px sur mobile, libellé visible ensuite. */
const BOUTON =
  'btn btn-secondary btn-square btn-md border-secondary-content/25 sm:btn-sm sm:w-auto sm:px-3 focus-visible:outline-accent'

/** Barre du haut discrète : titre, train liO qui passe, carnet de voyage, recommencer, version classique. */
export default function BarreHaute({ carnet, parcoursAvance, onRecommencer }: BarreHauteProps) {
  const [carnetOuvert, setCarnetOuvert] = useState(false)
  const refConfirmation = useRef<HTMLDialogElement>(null)
  const idConfirmation = useId()

  function demanderRecommencer() {
    if (parcoursAvance) refConfirmation.current?.showModal()
    else onRecommencer()
  }

  function confirmerRecommencer() {
    refConfirmation.current?.close()
    onRecommencer()
  }

  return (
    <header className="relative isolate bg-secondary text-secondary-content">
      <TrainLio />
      <nav className="navbar relative z-10 mx-auto min-h-12 max-w-4xl gap-2 px-4 py-0" aria-label="Tchouette">
        <div className="navbar-start min-w-0">
          <p className="rounded-field bg-secondary py-0.5 pr-2 text-base font-extrabold tracking-tight">Tchouette · liO</p>
        </div>
        <div className="navbar-end gap-1.5">
          <button type="button" onClick={() => setCarnetOuvert(true)} aria-haspopup="dialog" className={BOUTON}>
            <BookOpen className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Carnet de voyage</span>
            <span className="sr-only sm:hidden">Carnet de voyage</span>
          </button>
          <button type="button" onClick={demanderRecommencer} aria-haspopup={parcoursAvance ? 'dialog' : undefined} className={BOUTON}>
            <RotateCcw className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Recommencer</span>
            <span className="sr-only sm:hidden">Recommencer</span>
          </button>
          <Link to="/classique" className={BOUTON}>
            <History className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Version classique</span>
            <span className="sr-only sm:hidden">Version classique</span>
          </Link>
        </div>
      </nav>

      <CarnetVoyage repliques={carnet} ouvert={carnetOuvert} onFermer={() => setCarnetOuvert(false)} />

      <dialog ref={refConfirmation} className="modal" aria-labelledby={idConfirmation}>
        <div className="modal-box max-w-sm border-2 border-secondary p-4 text-base-content">
          <h2 id={idConfirmation} className="text-lg font-extrabold">
            Repartir de zéro ?
          </h2>
          <p className="py-2 text-sm text-base-content/80">
            Votre projet, vos choix et le carnet de voyage seront effacés de cet onglet.
          </p>
          <div className="modal-action">
            <form method="dialog">
              <button type="submit" className="btn btn-ghost btn-md">
                Garder ma sortie
              </button>
            </form>
            <button type="button" onClick={confirmerRecommencer} className="btn btn-error btn-md">
              <RotateCcw className="size-4" aria-hidden="true" />
              Effacer et recommencer
            </button>
          </div>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button type="submit">Fermer</button>
        </form>
      </dialog>
    </header>
  )
}
