import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { CalendarDays } from 'lucide-react'
import type { EvenementScene, Saisie } from '../../api/types'

type SaisieDate = Extract<NonNullable<Saisie>, { type: 'date' }>

interface WidgetDateProps {
  saisie: SaisieDate
  actionPrimaireDejaPresente: boolean
  onValider: (evenement: EvenementScene) => void
}

function formaterDate(iso: string): string {
  const date = new Date(`${iso}T12:00:00`)
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
}

function erreurDe(valeur: string, min: string): string | null {
  if (!valeur) return 'Choisissez la date de la sortie.'
  if (valeur < min) return `La sortie doit avoir lieu le ${formaterDate(min)} ou après.`
  return null
}

/** Champ date avec la date minimale du back et son conseil (ex. « 21 jours avant, de préférence »). */
export default function WidgetDate({ saisie, actionPrimaireDejaPresente, onValider }: WidgetDateProps) {
  const [valeur, setValeur] = useState('')
  const [essaye, setEssaye] = useState(false)
  const idChamp = useId()
  const idAide = useId()
  const idErreur = useId()
  const erreur = essaye ? erreurDe(valeur, saisie.min) : null

  function valider(evenement: FormEvent) {
    evenement.preventDefault()
    setEssaye(true)
    if (erreurDe(valeur, saisie.min)) return
    onValider({ type: 'valeur', champ: 'date', valeur: { date: valeur } })
  }

  return (
    <form
      onSubmit={valider}
      noValidate
      className="flex flex-col gap-3 rounded-box border-2 border-secondary bg-base-100 p-4 shadow-[4px_4px_0_0] shadow-secondary motion-safe:animate-entree"
    >
      <fieldset className="fieldset p-0">
        <label className="label text-base font-bold text-base-content" htmlFor={idChamp}>
          <CalendarDays className="size-5" aria-hidden="true" />
          Date de la sortie
        </label>
        <input
          id={idChamp}
          aria-label="Date de la sortie"
          type="date"
          min={saisie.min}
          value={valeur}
          onChange={(e) => setValeur(e.target.value)}
          aria-invalid={erreur !== null}
          aria-describedby={`${saisie.aide ? idAide : ''} ${erreur ? idErreur : ''}`.trim() || undefined}
          className={erreur ? 'input input-error h-12 w-full text-base tabular-nums' : 'input h-12 w-full text-base tabular-nums'}
        />
        {saisie.aide && (
          <p id={idAide} className="label text-sm whitespace-normal">
            {saisie.aide}
          </p>
        )}
        {erreur && (
          <p id={idErreur} role="alert" className="text-sm font-semibold text-error">
            {erreur}
          </p>
        )}
      </fieldset>
      <div className="flex justify-end">
        <button type="submit" className={actionPrimaireDejaPresente ? 'btn btn-secondary btn-md' : 'btn btn-primary btn-md'}>
          Valider
        </button>
      </div>
    </form>
  )
}
