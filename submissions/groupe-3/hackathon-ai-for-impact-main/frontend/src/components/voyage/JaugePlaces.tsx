import { useId } from 'react'
import type { Jauge, Niveau } from '../../api/types'
import PastilleNiveau from './PastilleNiveau'
import { LIBELLES_JAUGE } from './niveaux'
import { pluriel } from './format'

/** Au-delà, le plan de voiture deviendrait illisible : on garde le texte. */
const SIEGES_AFFICHABLES_MAX = 120

type EtatSiege = 'option' | 'groupe' | 'libre' | 'manquant'

const CLASSES_SIEGE: Record<Exclude<EtatSiege, 'groupe'>, string> = {
  option: 'h-2 rounded-xs bg-secondary',
  libre: 'h-2 rounded-xs border border-secondary/40 bg-base-100',
  manquant: 'h-2 rounded-xs border border-dashed border-error bg-base-100',
}

/** Sièges du groupe : couleur du verdict (le texte et la pastille portent le sens). */
const CLASSES_SIEGE_GROUPE: Record<Niveau, string> = {
  vert: 'h-2 rounded-xs bg-success',
  orange: 'h-2 rounded-xs bg-warning',
  rouge: 'h-2 rounded-xs bg-error',
}

const CLASSES_LEGENDE_GROUPE: Record<Niveau, string> = {
  vert: 'size-2.5 rounded-xs bg-success',
  orange: 'size-2.5 rounded-xs bg-warning',
  rouge: 'size-2.5 rounded-xs bg-error',
}

interface JaugePlacesProps {
  jauge: Jauge
  /** « Aller » ou « Retour ». */
  titre: string
  /** Numéro du premier train concerné, pour situer la jauge. */
  train?: string
}

/**
 * Jauge compacte de pré-réservation d'un train : le plan des sièges du groupe (50 en général),
 * les places sous option et le besoin. Jamais l'identité des autres groupes.
 */
export default function JaugePlaces({ jauge, titre, train }: JaugePlacesProps) {
  const titreId = useId()
  const { capacite, sous_option, disponibles, groupes_positionnes, besoin, niveau } = jauge
  const couverts = Math.max(0, Math.min(besoin, disponibles))
  const manquants = Math.max(0, besoin - disponibles)
  const afficherPlan = capacite > 0 && capacite + manquants <= SIEGES_AFFICHABLES_MAX

  const sieges: EtatSiege[] = afficherPlan
    ? [
        ...Array.from({ length: capacite }, (_, i): EtatSiege =>
          i < sous_option ? 'option' : i < sous_option + couverts ? 'groupe' : 'libre',
        ),
        ...Array.from({ length: manquants }, (): EtatSiege => 'manquant'),
      ]
    : []

  const groupes =
    groupes_positionnes === 0
      ? 'aucun autre groupe'
      : `${groupes_positionnes} ${pluriel(groupes_positionnes, 'autre groupe')}`

  return (
    <section aria-labelledby={titreId} className="grid content-start gap-1.5">
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <h4 id={titreId} className="text-xs font-semibold uppercase tracking-wide">
          {titre}
          {train && <span className="normal-case tabular-nums"> · train {train}</span>}
        </h4>
        <PastilleNiveau niveau={niveau} libelle={LIBELLES_JAUGE[niveau]} />
      </div>
      {afficherPlan && (
        <div aria-hidden="true" className="grid grid-cols-[repeat(25,minmax(0,1fr))] gap-0.5">
          {sieges.map((etat, index) => (
            <span key={index} className={etat === 'groupe' ? CLASSES_SIEGE_GROUPE[niveau] : CLASSES_SIEGE[etat]} />
          ))}
        </div>
      )}
      <p className="text-xs tabular-nums">
        <span className="font-bold">
          {disponibles} {pluriel(disponibles, 'place libre', 'places libres')} pour {besoin}{' '}
          {pluriel(besoin, 'voyageur')}
        </span>{' '}
        · {sous_option} sous option · {groupes}
        {manquants > 0 && <span className="font-bold"> · {manquants} manquantes</span>}
      </p>
    </section>
  )
}

/** Légende du plan des sièges, une seule fois sous les deux jauges (une pastille par verdict affiché). */
export function LegendeSieges({ niveaux }: { niveaux: Niveau[] }) {
  const distincts = [...new Set(niveaux)]
  return (
    <ul aria-hidden="true" className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
      <li className="flex items-center gap-1">
        <span className="size-2.5 rounded-xs bg-secondary" />
        Sous option
      </li>
      <li className="flex items-center gap-1">
        {distincts.map((niveau) => (
          <span key={niveau} className={CLASSES_LEGENDE_GROUPE[niveau]} />
        ))}
        Votre groupe
      </li>
      <li className="flex items-center gap-1">
        <span className="size-2.5 rounded-xs border border-secondary/40 bg-base-100" />
        Libre
      </li>
      <li className="flex items-center gap-1">
        <span className="size-2.5 rounded-xs border border-dashed border-error bg-base-100" />
        Manquante
      </li>
    </ul>
  )
}
