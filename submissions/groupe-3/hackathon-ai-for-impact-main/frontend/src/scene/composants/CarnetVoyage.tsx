import { useEffect, useId, useRef } from 'react'
import { BookOpen } from 'lucide-react'
import type { Replique } from '../../api/types'

interface CarnetVoyageProps {
  repliques: Replique[]
  ouvert: boolean
  onFermer: () => void
}

/** Carnet de voyage : l'historique replié de la conversation, la réplique la plus récente en bas. */
export default function CarnetVoyage({ repliques, ouvert, onFermer }: CarnetVoyageProps) {
  const refDialogue = useRef<HTMLDialogElement>(null)
  const refFin = useRef<HTMLLIElement>(null)
  const idTitre = useId()

  useEffect(() => {
    const dialogue = refDialogue.current
    if (!dialogue) return
    if (ouvert && !dialogue.open) dialogue.showModal()
    if (!ouvert && dialogue.open) dialogue.close()
    if (ouvert) refFin.current?.scrollIntoView({ block: 'end' })
  }, [ouvert, repliques])

  return (
    <dialog ref={refDialogue} onClose={onFermer} className="modal modal-bottom sm:modal-middle" aria-labelledby={idTitre}>
      <div className="modal-box flex max-h-[80dvh] flex-col border-2 border-secondary p-0 text-base-content">
        <div className="flex items-center gap-2 border-b-2 border-dashed border-base-300 p-4">
          <BookOpen className="size-5" aria-hidden="true" />
          <h2 id={idTitre} className="text-lg font-extrabold">
            Carnet de voyage
          </h2>
        </div>
        <ul className="flex-1 overflow-y-auto px-4 py-3" aria-label="Historique de la conversation">
          {repliques.length === 0 ? (
            <li className="py-6 text-center text-sm text-base-content/70">
              Le carnet est encore vide : il se remplit au fil de votre conversation avec Tchouette.
            </li>
          ) : (
            repliques.map((replique, i) =>
              replique.qui === 'tchouette' ? (
                <li key={`${i}-t`} className="chat chat-start">
                  <div className="chat-header text-xs font-semibold opacity-70">Tchouette</div>
                  <div className="chat-bubble">{replique.texte}</div>
                </li>
              ) : (
                <li key={`${i}-e`} className="chat chat-end">
                  <div className="chat-header text-xs font-semibold opacity-70">Vous</div>
                  <div className="chat-bubble chat-bubble-secondary">{replique.texte}</div>
                </li>
              ),
            )
          )}
          <li ref={refFin} aria-hidden="true" />
        </ul>
        <div className="modal-action m-0 border-t-2 border-dashed border-base-300 p-3">
          <form method="dialog">
            <button type="submit" className="btn btn-secondary btn-md">
              Fermer le carnet
            </button>
          </form>
        </div>
      </div>
      <form method="dialog" className="modal-backdrop">
        <button type="submit">Fermer</button>
      </form>
    </dialog>
  )
}
