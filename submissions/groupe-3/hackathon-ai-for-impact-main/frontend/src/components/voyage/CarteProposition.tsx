import { useId } from 'react'
import type { MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, CalendarDays, Check, CircleX, Hourglass, ListChecks, Scale, ShieldCheck, Sparkles, Trophy } from 'lucide-react'
import type { Proposition } from '../../api/types'
import FriseTrajet from './FriseTrajet'
import DetailIndice, { AnneauScore } from './IndiceConfiance'
import JaugePlaces, { LegendeSieges } from './JaugePlaces'
import ListeControles from './ListeControles'
import PastilleNiveau, { PuceNiveau } from './PastilleNiveau'
import { compterControles, formaterDateCourte, formaterDuree, pluriel } from './format'

const LIBELLES_COMPTE = { rouge: 'bloquant', orange: 'vigilance', vert: 'conforme' } as const

/** Bordure selon le verdict, contour or + ombre dure quand la proposition est sélectionnée. */
const ETATS = {
  repos:
    'card scroll-mt-36 cursor-pointer border-2 border-base-300 bg-base-100 transition-colors hover:border-secondary has-[input[type=radio]:focus-visible]:outline-secondary',
  reposRouge:
    'card scroll-mt-36 cursor-pointer border-2 border-error/50 bg-base-100 transition-colors hover:border-error has-[input[type=radio]:focus-visible]:outline-secondary',
  choisie:
    'card scroll-mt-36 cursor-pointer border-2 border-secondary bg-base-100 shadow-[4px_4px_0_0] shadow-secondary ring-4 ring-accent transition-colors has-[input[type=radio]:focus-visible]:outline-secondary',
  choisieRouge:
    'card scroll-mt-36 cursor-pointer border-2 border-error bg-base-100 shadow-[4px_4px_0_0] shadow-secondary ring-4 ring-accent transition-colors has-[input[type=radio]:focus-visible]:outline-secondary',
} as const

interface CartePropositionProps {
  proposition: Proposition
  /** Numéro affiché (« Proposition 2 ») ; absent pour une alternative. */
  numero: number | null
  /** Pour une alternative : numéro de la proposition remplacée. */
  numeroRemplace?: number | null
  /** Pour une proposition rouge : identifiant de son alternative, si elle existe. */
  alternativeId?: string | null
  /** Date de la demande : une proposition à une autre date est signalée. */
  dateDemande: string | null
  estMeilleure: boolean
  dansComparaison: boolean
  selectionnee: boolean
  /** Nom du groupe de boutons radio partagé par les propositions. */
  groupe: string
  onSelectionner: () => void
  onVoirAlternative?: () => void
}

/**
 * Une proposition de trajet en carte horizontale : trains (5/12), places (4/12), indice (3/12).
 * Les contrôles et le détail de l'indice restent repliés. Clic sur la carte = sélection.
 */
export default function CarteProposition({
  proposition,
  numero,
  numeroRemplace = null,
  alternativeId = null,
  dateDemande,
  estMeilleure,
  dansComparaison,
  selectionnee,
  groupe,
  onSelectionner,
  onVoirAlternative,
}: CartePropositionProps) {
  const idRadio = useId()
  const idTitre = useId()
  const { indice, aller, retour, controles } = proposition
  const rouge = indice.niveau === 'rouge'
  const score = Math.round(indice.score)
  const bloquants = controles.filter((controle) => controle.niveau === 'rouge')
  const compte = compterControles(controles)
  const autreDate = !!dateDemande && proposition.date.slice(0, 10) !== dateDemande.slice(0, 10)

  const titre =
    numero !== null
      ? `Proposition ${numero}`
      : numeroRemplace !== null
        ? `Alternative à la proposition ${numeroRemplace}`
        : 'Alternative'

  function surClic(evenement: MouseEvent<HTMLElement>) {
    // Les éléments interactifs (radio, libellé, liens, contrôles repliés) gardent leur propre comportement.
    if ((evenement.target as HTMLElement).closest('a, button, input, label, details')) return
    onSelectionner()
  }

  const classes = selectionnee
    ? rouge
      ? ETATS.choisieRouge
      : ETATS.choisie
    : rouge
      ? ETATS.reposRouge
      : ETATS.repos

  return (
    <article
      id={`proposition-${proposition.proposition_id}`}
      aria-labelledby={idTitre}
      onClick={surClic}
      className={classes}
    >
      {/* En-tête : bouton radio, titre, date et pastilles */}
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-base-300 px-4 py-2.5">
        <input
          id={idRadio}
          type="radio"
          name={groupe}
          value={proposition.proposition_id}
          checked={selectionnee}
          onChange={onSelectionner}
          aria-label={`${titre}, ${formaterDateCourte(proposition.date)}, départ ${aller.depart}, indice ${score} sur 100`}
          className="radio radio-sm radio-secondary"
        />
        <h3 id={idTitre} className="text-base font-bold leading-tight">
          <label htmlFor={idRadio} className="cursor-pointer">
            {titre}
            <span className="text-sm font-semibold tabular-nums"> · {formaterDateCourte(proposition.date)}</span>
          </label>
        </h3>
        <div className="flex flex-wrap items-center gap-1.5">
          {autreDate && (
            <span className="badge badge-info badge-sm h-auto min-h-5 gap-1 py-0.5 font-semibold">
              <CalendarDays className="size-3.5" aria-hidden="true" />
              Autre date
            </span>
          )}
          {proposition.est_alternative && (
            <span className="badge badge-accent badge-sm gap-1 font-semibold">
              <Sparkles className="size-3.5" aria-hidden="true" />
              Alternative
            </span>
          )}
          {estMeilleure && (
            <span className="badge badge-outline badge-sm gap-1 font-semibold">
              <Trophy className="size-3.5" aria-hidden="true" />
              Meilleure
            </span>
          )}
        </div>
        <div className="ms-auto flex flex-wrap items-center gap-1.5">
          {dansComparaison && (
            <span className="badge badge-ghost badge-sm gap-1 font-semibold">
              <Scale className="size-3.5" aria-hidden="true" />
              Comparée
            </span>
          )}
          {selectionnee && (
            <span className="badge badge-secondary badge-sm gap-1 font-bold motion-safe:animate-pop">
              <Check className="size-3.5" aria-hidden="true" />
              Sélectionnée
            </span>
          )}
        </div>
      </header>

      {/* Proposition rouge : l'alerte tient sur une ligne, l'alternative suit juste en dessous */}
      {rouge && (
        <div className="alert alert-error alert-soft mx-4 mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 px-3 py-1.5 text-sm">
          <CircleX className="size-4 shrink-0" aria-hidden="true" />
          <p className="min-w-0 flex-1">
            <span className="font-bold">Pas suffisamment fiable ou adaptée à votre groupe</span>
            {bloquants.length > 0
              ? ` : ${bloquants.map((c) => c.libelle.toLowerCase()).join(', ')}.`
              : ` : indice ${score}/100, sous le seuil de 60.`}
          </p>
          {alternativeId ? (
            <a href={`#proposition-${alternativeId}`} onClick={onVoirAlternative} className="link inline-flex items-center gap-1 font-semibold">
              Voici une alternative
              <ArrowDown className="size-3.5" aria-hidden="true" />
            </a>
          ) : (
            <Link to="/destinations" className="link font-semibold">
              Voir d'autres destinations
            </Link>
          )}
        </div>
      )}

      {/* Trains · places · indice */}
      <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,4fr)_minmax(0,3fr)] lg:gap-0">
        <section aria-label="Horaires des trains" className="grid content-start gap-3 lg:pe-5">
          <FriseTrajet trajet={aller} titre="Aller" />
          <FriseTrajet trajet={retour} titre="Retour" />
          <p className="flex items-center gap-1.5 text-xs">
            <Hourglass className="size-3.5 shrink-0" aria-hidden="true" />
            <span>
              <span className="font-bold tabular-nums">{formaterDuree(proposition.marge_avant_visite_min)}</span> de
              marge avant la visite
            </span>
          </p>
        </section>

        <section
          aria-label="Places du groupe"
          className="grid content-start gap-3 border-t border-dashed border-base-300 pt-4 lg:border-l lg:border-t-0 lg:px-5 lg:pt-0"
        >
          <JaugePlaces jauge={proposition.jauge_aller} titre="Aller" train={aller.segments[0]?.train} />
          <JaugePlaces jauge={proposition.jauge_retour} titre="Retour" train={retour.segments[0]?.train} />
          <LegendeSieges niveaux={[proposition.jauge_aller.niveau, proposition.jauge_retour.niveau]} />
        </section>

        <section
          aria-label="Indice de confiance"
          className="grid content-start gap-2 border-t border-dashed border-base-300 pt-4 lg:border-l lg:border-t-0 lg:ps-5 lg:pt-0"
        >
          <div className="flex items-center gap-3">
            <AnneauScore score={indice.score} niveau={indice.niveau} />
            <div className="grid gap-1">
              <p className="text-xs font-semibold uppercase tracking-wide">Indice de confiance</p>
              <PastilleNiveau niveau={indice.niveau} />
            </div>
          </div>
          <p className="line-clamp-2 text-sm leading-snug" title={proposition.explication_ia}>
            {proposition.explication_ia}
          </p>
        </section>
      </div>

      {/* Détails repliés par défaut */}
      <div className="grid items-start gap-2 border-t border-base-300 px-4 py-2.5 md:grid-cols-2">
        <details className="collapse collapse-arrow rounded-field border border-base-300 bg-base-100 text-sm">
          <summary className="collapse-title flex flex-wrap items-center gap-x-2 gap-y-1 px-3 py-2 pe-9 text-sm font-semibold">
            <ListChecks className="size-4 shrink-0" aria-hidden="true" />
            <span>Voir les {controles.length} contrôles</span>
            <span className="flex items-center gap-2 text-xs font-semibold tabular-nums">
              {(['rouge', 'orange', 'vert'] as const)
                .filter((niveau) => compte[niveau] > 0)
                .map((niveau) => (
                  <span key={niveau} className="inline-flex items-center gap-1">
                    <PuceNiveau niveau={niveau} />
                    {compte[niveau]} {pluriel(compte[niveau], LIBELLES_COMPTE[niveau])}
                  </span>
                ))}
            </span>
          </summary>
          <div className="collapse-content px-3">
            <ListeControles controles={controles} />
          </div>
        </details>
        <details className="collapse collapse-arrow rounded-field border border-base-300 bg-base-100 text-sm">
          <summary className="collapse-title flex flex-wrap items-center gap-x-2 gap-y-1 px-3 py-2 pe-9 text-sm font-semibold">
            <ShieldCheck className="size-4 shrink-0" aria-hidden="true" />
            <span>
              Pourquoi <span className="tabular-nums">{score}/100</span>&nbsp;?
            </span>
          </summary>
          <div className="collapse-content grid gap-3 px-3">
            <p className="text-sm leading-snug">{proposition.explication_ia}</p>
            <DetailIndice indice={indice} />
          </div>
        </details>
      </div>
    </article>
  )
}
