import { useId, useState } from 'react'

/** Au-delà, la bulle se replie sur trois lignes avec « Tout lire ». */
const LONGUEUR_REPLIEE = 150

interface BulleTchouetteProps {
  texte: string
}

/**
 * Tchouette prend la parole dans l'intro : bulle compacte, repliée sur trois lignes.
 * La mascotte est déjà à gauche de l'intro ; la queue de la bulle pointe vers elle.
 */
export default function BulleTchouette({ texte }: BulleTchouetteProps) {
  const [ouverte, setOuverte] = useState(false)
  const idTexte = useId()
  const longue = texte.length > LONGUEUR_REPLIEE
  return (
    <div className="chat chat-start motion-safe:animate-entree">
      <div className="chat-bubble w-full max-w-none border border-base-300 bg-base-100 px-3 py-2 text-sm leading-snug text-base-content">
        <p className="sr-only">Tchouette :</p>
        <p id={idTexte} className={longue && !ouverte ? 'line-clamp-3' : undefined}>
          {texte}
        </p>
        {longue && (
          <button
            type="button"
            onClick={() => setOuverte((o) => !o)}
            aria-expanded={ouverte}
            aria-controls={idTexte}
            className="link mt-0.5 text-xs font-semibold"
          >
            {ouverte ? 'Réduire' : 'Tout lire'}
          </button>
        )}
      </div>
    </div>
  )
}
