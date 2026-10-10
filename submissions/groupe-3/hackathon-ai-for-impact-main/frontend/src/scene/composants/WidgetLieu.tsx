import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { MapPin } from 'lucide-react'
import type { EvenementScene, Saisie } from '../../api/types'

type SaisieLieu = Extract<NonNullable<Saisie>, { type: 'lieu' }>

interface WidgetLieuProps {
  saisie: SaisieLieu
  actionPrimaireDejaPresente: boolean
  onValider: (evenement: EvenementScene) => void
}

/** Lieu de départ : champ texte et puces de suggestions (toucher une puce remplit le champ). */
export default function WidgetLieu({ saisie, actionPrimaireDejaPresente, onValider }: WidgetLieuProps) {
  const [lieu, setLieu] = useState('')
  const [essaye, setEssaye] = useState(false)
  const idChamp = useId()
  const idErreur = useId()
  const manquant = essaye && lieu.trim() === ''

  function valider(evenement: FormEvent) {
    evenement.preventDefault()
    setEssaye(true)
    const propre = lieu.trim()
    if (!propre) return
    onValider({ type: 'valeur', champ: 'lieu_depart', valeur: { libelle: propre } })
  }

  return (
    <form
      onSubmit={valider}
      noValidate
      className="flex flex-col gap-3 rounded-box border-2 border-secondary bg-base-100 p-4 shadow-[4px_4px_0_0] shadow-secondary motion-safe:animate-entree"
    >
      <fieldset className="fieldset p-0">
        <label className="label text-base font-bold text-base-content" htmlFor={idChamp}>
          <MapPin className="size-5" aria-hidden="true" />
          D&apos;où part la classe ?
        </label>
        <input
          id={idChamp}
          aria-label="Lieu de départ de la classe"
          type="text"
          value={lieu}
          onChange={(e) => setLieu(e.target.value)}
          placeholder="Ville, gare ou adresse de l'école"
          autoComplete="off"
          aria-invalid={manquant}
          aria-describedby={manquant ? idErreur : undefined}
          className={manquant ? 'input input-error h-12 w-full text-base' : 'input h-12 w-full text-base'}
        />
        {manquant && (
          <p id={idErreur} role="alert" className="text-sm font-semibold text-error">
            Indiquez la ville ou la gare de départ.
          </p>
        )}
      </fieldset>
      {saisie.suggestions.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Suggestions de lieux">
          {saisie.suggestions.map((suggestion) => (
            <li key={suggestion}>
              <button
                type="button"
                onClick={() => setLieu(suggestion)}
                aria-pressed={lieu === suggestion}
                className={lieu === suggestion ? 'btn btn-secondary btn-md rounded-full' : 'btn btn-outline btn-secondary btn-md rounded-full'}
              >
                {suggestion}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex justify-end">
        <button type="submit" className={actionPrimaireDejaPresente ? 'btn btn-secondary btn-md' : 'btn btn-primary btn-md'}>
          Valider
        </button>
      </div>
    </form>
  )
}
