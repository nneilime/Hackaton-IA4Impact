import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { Minus, Plus, Users } from 'lucide-react'
import type { EvenementScene, Saisie } from '../../api/types'

type SaisieEffectif = Extract<NonNullable<Saisie>, { type: 'effectif' }>

interface WidgetEffectifProps {
  saisie: SaisieEffectif
  /** Vrai si une carte primaire (rouge) est déjà à l'écran : "Valider" devient alors secondaire. */
  actionPrimaireDejaPresente: boolean
  onValider: (evenement: EvenementScene) => void
}

const ELEVES_PAR_DEFAUT = 25
const ACCOMPAGNATEURS_PAR_DEFAUT = 3

interface CompteurProps {
  libelle: string
  valeur: number
  min: number
  max: number
  onChange: (valeur: number) => void
}

function Compteur({ libelle, valeur, min, max, onChange }: CompteurProps) {
  return (
    <div role="group" aria-label={libelle} className="flex items-center justify-between gap-2">
      <span className="min-w-0 text-base font-bold">{libelle}</span>
      <div className="flex shrink-0 items-center gap-1.5">
        <button
          type="button"
          className="btn btn-circle btn-outline btn-secondary btn-md size-11"
          aria-label={`Retirer : ${libelle.toLowerCase()}`}
          disabled={valeur <= min}
          onClick={() => onChange(valeur - 1)}
        >
          <Minus className="size-5" aria-hidden="true" />
        </button>
        <output className="w-11 text-center text-3xl font-extrabold tabular-nums" aria-label={`${valeur} ${libelle.toLowerCase()}`}>
          {valeur}
        </output>
        <button
          type="button"
          className="btn btn-circle btn-outline btn-secondary btn-md size-11"
          aria-label={`Ajouter : ${libelle.toLowerCase()}`}
          disabled={valeur >= max}
          onClick={() => onChange(valeur + 1)}
        >
          <Plus className="size-5" aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}

/** Deux compteurs (élèves, accompagnateurs), total en direct et limites claires. */
export default function WidgetEffectif({ saisie, actionPrimaireDejaPresente, onValider }: WidgetEffectifProps) {
  const [eleves, setEleves] = useState(saisie.eleves ?? ELEVES_PAR_DEFAUT)
  const [accompagnateurs, setAccompagnateurs] = useState(saisie.accompagnateurs ?? ACCOMPAGNATEURS_PAR_DEFAUT)
  const idMessage = useId()
  const total = eleves + accompagnateurs
  const trop = total > saisie.max
  const tropPeu = total < saisie.min
  const invalide = trop || tropPeu

  function valider(evenement: FormEvent) {
    evenement.preventDefault()
    if (invalide) return
    onValider({ type: 'valeur', champ: 'effectif', valeur: { eleves, accompagnateurs } })
  }

  return (
    <form
      onSubmit={valider}
      noValidate
      aria-label="Effectif de la sortie"
      className="flex flex-col gap-4 rounded-box border-2 border-secondary bg-base-100 p-4 shadow-[4px_4px_0_0] shadow-secondary motion-safe:animate-entree"
    >
      <Compteur
        libelle="Élèves"
        valeur={eleves}
        min={1}
        max={saisie.max}
        onChange={setEleves}
      />
      <Compteur
        libelle="Accompagnateurs"
        valeur={accompagnateurs}
        min={0}
        max={saisie.max}
        onChange={setAccompagnateurs}
      />
      <div className="flex flex-wrap items-center justify-between gap-3 border-t-2 border-dashed border-base-300 pt-3">
        <p className="flex items-center gap-2 text-lg font-extrabold tabular-nums" aria-live="polite">
          <Users className="size-5" aria-hidden="true" />
          {total} {total > 1 ? 'voyageurs' : 'voyageur'}
        </p>
        <button
          type="submit"
          disabled={invalide}
          className={actionPrimaireDejaPresente ? 'btn btn-secondary btn-md' : 'btn btn-primary btn-md'}
        >
          Valider
        </button>
      </div>
      {invalide && (
        <p id={idMessage} role="alert" className="text-sm font-semibold text-error">
          {trop
            ? `Au plus ${saisie.max} voyageurs par sortie : il y en a ${total - saisie.max} de trop.`
            : `Il faut au moins ${saisie.min} voyageurs pour une sortie : il en manque ${saisie.min - total}.`}
        </p>
      )}
    </form>
  )
}
