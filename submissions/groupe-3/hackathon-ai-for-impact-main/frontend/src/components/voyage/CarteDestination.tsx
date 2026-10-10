import { useId } from 'react'
import type { MouseEvent } from 'react'
import { Bus, Check, Circle, Footprints, MapPin, TrainFront } from 'lucide-react'
import type { Destination, Niveau } from '../../api/types'
import PastilleNiveau, { PuceNiveau } from './PastilleNiveau'
import { AnneauScore } from './IndiceConfiance'
import { LIBELLES_ACCES } from './niveaux'
import { formaterDuree, libelleCorrespondances } from './format'

/** Libellés courts de l'indice, pour tenir sous l'anneau. */
const LIBELLES_INDICE: Record<Niveau, string> = {
  vert: 'Fiable',
  orange: 'Vigilance',
  rouge: 'Pas adapté',
}

/**
 * La carte occupe 4 rangées de la grille parente (sous-grille) : en-tête, texte, activités, indicateurs.
 * Les trois cartes s'alignent ainsi au pixel, quelle que soit la longueur des textes.
 * Le petit trait au-dessus relie la carte à sa gare sur le rail.
 */
const CARTE_REPOS =
  'card relative grid cursor-pointer content-start gap-3 border-2 border-base-300 bg-base-100 p-4 transition-colors hover:border-secondary has-[input:focus-visible]:outline-secondary lg:row-span-4 lg:grid-rows-subgrid lg:before:absolute lg:before:-top-3 lg:before:left-1/2 lg:before:h-3 lg:before:w-0.5 lg:before:-translate-x-1/2 lg:before:bg-secondary motion-safe:data-[rang=0]:animate-entree motion-safe:data-[rang=1]:animate-[entree_280ms_ease-out_70ms_both] motion-safe:data-[rang=2]:animate-[entree_280ms_ease-out_140ms_both] motion-safe:data-[rang=3]:animate-[entree_280ms_ease-out_210ms_both]'

const CARTE_CHOISIE =
  'card relative grid cursor-pointer content-start gap-3 border-2 border-secondary bg-base-100 p-4 shadow-[4px_4px_0_0] shadow-secondary ring-4 ring-accent transition-colors has-[input:focus-visible]:outline-secondary lg:row-span-4 lg:grid-rows-subgrid lg:before:absolute lg:before:-top-3 lg:before:left-1/2 lg:before:h-3 lg:before:w-0.5 lg:before:-translate-x-1/2 lg:before:bg-secondary motion-safe:data-[rang=0]:animate-entree motion-safe:data-[rang=1]:animate-[entree_280ms_ease-out_70ms_both] motion-safe:data-[rang=2]:animate-[entree_280ms_ease-out_140ms_both] motion-safe:data-[rang=3]:animate-[entree_280ms_ease-out_210ms_both]'

interface CarteDestinationProps {
  destination: Destination
  /** Numéro de la gare sur la ligne (1, 2, 3). */
  numero: number
  selectionnee: boolean
  /** Nom du groupe de boutons radio partagé par les cartes. */
  groupe: string
  onSelectionner: () => void
}

/** Une destination du catalogue, posée sur la ligne comme une gare d'arrivée. Clic = sélection. */
export default function CarteDestination({
  destination,
  numero,
  selectionnee,
  groupe,
  onSelectionner,
}: CarteDestinationProps) {
  const idRadio = useId()
  const idResume = useId()
  const { acces_gare_site: acces } = destination
  const IconeAcces = acces.mode === 'pied' ? Footprints : Bus
  const activites = destination.activites.slice(0, 3)

  function surClic(evenement: MouseEvent<HTMLElement>) {
    // Le libellé et le bouton radio gèrent eux-mêmes la sélection.
    if ((evenement.target as HTMLElement).closest('input, label')) return
    onSelectionner()
  }

  return (
    <article
      onClick={surClic}
      data-rang={Math.min(numero - 1, 3)}
      className={selectionnee ? CARTE_CHOISIE : CARTE_REPOS}
    >
      <input
        id={idRadio}
        type="radio"
        name={groupe}
        value={destination.site_id}
        checked={selectionnee}
        onChange={onSelectionner}
        aria-label={destination.nom}
        aria-describedby={idResume}
        className="sr-only"
      />

      {/* 1. En-tête : gare n°, nom, commune et gare, état de sélection */}
      <div className="flex items-start gap-2.5">
        <span
          aria-hidden="true"
          className={
            selectionnee
              ? 'grid size-7 shrink-0 place-items-center rounded-full border-2 border-secondary bg-accent text-sm font-extrabold tabular-nums text-accent-content'
              : 'grid size-7 shrink-0 place-items-center rounded-full border-2 border-secondary bg-base-100 text-sm font-extrabold tabular-nums'
          }
        >
          {numero}
        </span>
        <div className="grid min-w-0 flex-1 gap-0.5">
          <h3 className="text-base font-bold leading-tight">
            <label htmlFor={idRadio} className="cursor-pointer">
              {destination.nom}
            </label>
          </h3>
          <p className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs font-semibold">
            <span className="inline-flex items-center gap-1">
              <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
              {destination.commune}
            </span>
            <span className="inline-flex min-w-0 items-center gap-1">
              <TrainFront className="size-3.5 shrink-0" aria-hidden="true" />
              Gare de {destination.gare.nom}
            </span>
          </p>
        </div>
        {selectionnee ? (
          <span className="badge badge-accent badge-sm shrink-0 gap-1 font-bold motion-safe:animate-pop">
            <Check className="size-3.5" aria-hidden="true" />
            Sélectionnée
          </span>
        ) : (
          <span aria-hidden="true" className="badge badge-ghost badge-sm shrink-0 gap-1 font-semibold">
            <Circle className="size-3" />
            Choisir
          </span>
        )}
      </div>

      {/* 2. Intérêt pédagogique, 3 lignes au plus */}
      <p className="line-clamp-3 text-sm leading-snug" title={destination.interet_pedagogique}>
        {destination.interet_pedagogique}
      </p>

      {/* 3. Sur place : 3 activités au plus */}
      {activites.length > 0 ? (
        <ul aria-label="Sur place" className="flex flex-wrap content-start gap-1">
          {activites.map((activite) => (
            <li key={activite} className="badge badge-ghost badge-sm h-auto max-w-full py-0.5" title={activite}>
              <span className="line-clamp-1 break-words">{activite}</span>
            </li>
          ))}
        </ul>
      ) : (
        <span aria-hidden="true" />
      )}

      {/* 4. Trois indicateurs alignés : trajet · accès gare → site · indice */}
      <dl
        id={idResume}
        className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_6.5rem] items-start divide-x divide-base-300 self-end rounded-field bg-base-200 py-2"
      >
        <div className="grid content-start gap-0.5 px-2.5">
          <dt className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide">
            <TrainFront className="size-3.5 shrink-0" aria-hidden="true" />
            Trajet
          </dt>
          <dd className="text-base font-extrabold tabular-nums">{formaterDuree(destination.temps_trajet_min)}</dd>
          <dd className="text-xs">{libelleCorrespondances(destination.correspondances)}</dd>
        </div>
        <div className="grid content-start gap-0.5 px-2.5">
          <dt className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide">
            <IconeAcces className="size-3.5 shrink-0" aria-hidden="true" />
            <span>
              Gare <span aria-hidden="true">→</span>
              <span className="sr-only">jusqu'au</span> site
            </span>
          </dt>
          <dd className="text-base font-extrabold tabular-nums">
            {acces.minutes_groupe} min
            <span className="sr-only">{acces.mode === 'pied' ? ' à pied' : ' en transport urbain'}</span>
          </dd>
          <dd className="flex items-center gap-1 text-xs">
            <PuceNiveau niveau={acces.niveau} />
            {LIBELLES_ACCES[acces.niveau]}
          </dd>
        </div>
        <div className="grid justify-items-center gap-1 px-2">
          <dt className="sr-only">Indice de confiance</dt>
          <dd>
            <AnneauScore score={destination.indice_confiance} niveau={destination.niveau} />
          </dd>
          <dd>
            <PastilleNiveau niveau={destination.niveau} libelle={LIBELLES_INDICE[destination.niveau]} />
          </dd>
        </div>
      </dl>
    </article>
  )
}
