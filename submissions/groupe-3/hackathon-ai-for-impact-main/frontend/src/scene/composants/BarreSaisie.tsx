import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { Mic, MicOff, Send } from 'lucide-react'
import { useDictee } from '../../features/accueil/useDictee'

interface BarreSaisieProps {
  onEnvoyer: (texte: string) => void
  /** Vrai pendant un tour du back. */
  desactive: boolean
}

/**
 * « Écrire ou parler » : champ + micro + envoyer, toujours visible.
 * Mains libres : à la fin de la dictée, le texte part tout seul. Le micro n'existe pas si le navigateur ne sait pas dicter.
 */
export default function BarreSaisie({ onEnvoyer, desactive }: BarreSaisieProps) {
  const [texte, setTexte] = useState('')
  const idChamp = useId()
  const dictee = useDictee((dicte) => {
    if (!desactive) onEnvoyer(dicte)
  })

  function envoyer(evenement: FormEvent) {
    evenement.preventDefault()
    const propre = texte.trim()
    if (!propre || desactive) return
    dictee.arreter()
    setTexte('')
    onEnvoyer(propre)
  }

  return (
    <form onSubmit={envoyer} className="flex flex-col gap-1.5" aria-label="Écrire ou parler à Tchouette">
      {dictee.ecoute && (
        <p role="status" className="flex items-center gap-2 text-sm font-bold text-primary">
          <span className="loading loading-bars loading-xs" aria-hidden="true" />
          Je vous écoute…
        </p>
      )}
      {dictee.erreur && (
        <p role="alert" className="text-sm font-semibold text-error">
          {dictee.erreur}
        </p>
      )}
      <div className="flex items-center gap-2">
        <label htmlFor={idChamp} className="sr-only">
          Écrire à Tchouette
        </label>
        <input
          id={idChamp}
          aria-label="Écrire à Tchouette"
          type="text"
          value={texte}
          onChange={(e) => setTexte(e.target.value)}
          placeholder={dictee.ecoute ? 'Parlez, j’écoute…' : 'Écrire ou parler…'}
          autoComplete="off"
          enterKeyHint="send"
          className="input h-12 min-w-0 flex-1 border-2 border-secondary text-base"
        />
        {dictee.disponible && (
          <button
            type="button"
            onClick={dictee.ecoute ? dictee.arreter : dictee.demarrer}
            disabled={desactive}
            aria-pressed={dictee.ecoute}
            aria-label={dictee.ecoute ? 'Arrêter l’écoute' : 'Parler à Tchouette'}
            className={dictee.ecoute ? 'btn btn-circle btn-secondary btn-lg shrink-0' : 'btn btn-circle btn-outline btn-secondary btn-lg shrink-0'}
          >
            {dictee.ecoute ? <MicOff className="size-6" aria-hidden="true" /> : <Mic className="size-6" aria-hidden="true" />}
          </button>
        )}
        <button
          type="submit"
          disabled={desactive || texte.trim() === ''}
          aria-label="Envoyer à Tchouette"
          className="btn btn-circle btn-secondary btn-lg shrink-0"
        >
          <Send className="size-6" aria-hidden="true" />
        </button>
      </div>
    </form>
  )
}
