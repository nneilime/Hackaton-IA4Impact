import { Fragment, useId } from 'react'
import { ArrowLeftRight, Bus, Footprints, Gauge, MapPin, TrainFront, Users } from 'lucide-react'
import type { Demande, Destination, Proposition, Trajet } from '../../api/types'
import PastilleNiveau from './PastilleNiveau'
import {
  LIBELLES_NIVEAU_ACCES,
  LIBELLES_NIVEAU_INDICE,
  MAX_VOYAGEURS_GROUPE,
  formaterDateLongue,
  formaterDuree,
  libelleCorrespondances,
  minutesEntre,
  partiesDate,
  pluriel,
} from './format'

interface BilletRecapProps {
  site: Destination
  proposition: Proposition
  demande: Demande | null
  /** Référence du dossier, imprimée sur le talon une fois la demande envoyée. */
  reference?: string
}

const LIBELLE_RUBRIQUE = 'flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-base-content/70'

function LigneTrajet({ sens, trajet }: { sens: 'Aller' | 'Retour'; trajet: Trajet }) {
  const premier = trajet.segments[0]
  const dernier = trajet.segments[trajet.segments.length - 1]
  const direct = trajet.segments.length <= 1

  return (
    <section aria-label={`Trajet ${sens.toLowerCase()}`} className="flex min-w-0 flex-col gap-1">
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <span className="badge badge-secondary badge-sm font-bold">{sens}</span>
        <span className="text-xs font-semibold tabular-nums text-base-content/80">
          {formaterDuree(trajet.duree_min)} · {libelleCorrespondances(trajet.correspondances)}
        </span>
      </div>

      <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2">
        <time dateTime={trajet.depart} className="text-lg font-bold tabular-nums">
          {trajet.depart}
        </time>
        <span
          aria-hidden="true"
          className="relative h-0.5 bg-[repeating-linear-gradient(90deg,var(--color-secondary)_0_5px,transparent_5px_9px)]"
        >
          <span className="absolute -left-0.5 top-1/2 size-2.5 -translate-y-1/2 rounded-full border-2 border-secondary bg-base-100" />
          <span className="absolute -right-0.5 top-1/2 size-2.5 -translate-y-1/2 rounded-full bg-secondary" />
        </span>
        <time dateTime={trajet.arrivee} className="text-lg font-bold tabular-nums">
          {trajet.arrivee}
        </time>
      </div>

      <div className="flex justify-between gap-3 text-xs font-semibold">
        <span className="min-w-0">{premier?.gare_depart ?? 'Gare de départ'}</span>
        <span className="min-w-0 text-right">{dernier?.gare_arrivee ?? "Gare d'arrivée"}</span>
      </div>

      {direct
        ? premier && (
            <p className="flex items-center gap-1.5 text-xs">
              <TrainFront className="size-3.5 shrink-0" aria-hidden="true" />
              Train liO <span className="font-bold tabular-nums">{premier.train}</span>
            </p>
          )
        : (
            <ol className="flex flex-col gap-0.5 border-l-2 border-dashed border-secondary pl-2.5 text-xs">
              {trajet.segments.map((segment, index) => {
                const precedent = index > 0 ? trajet.segments[index - 1] : undefined
                const attente = precedent ? minutesEntre(precedent.arrivee, segment.depart) : null
                return (
                  <Fragment key={`${segment.train}-${segment.depart}-${index}`}>
                    {precedent && (
                      <li className="flex items-center gap-1.5 font-semibold">
                        <ArrowLeftRight className="size-3.5 shrink-0" aria-hidden="true" />
                        <span>
                          Changement à {segment.gare_depart}
                          {attente !== null && attente >= 0 && (
                            <>
                              {' · '}
                              <span className="tabular-nums">{attente} min</span>
                            </>
                          )}
                        </span>
                      </li>
                    )}
                    <li className="flex items-start gap-1.5">
                      <TrainFront className="mt-px size-3.5 shrink-0" aria-hidden="true" />
                      <span>
                        <span className="font-bold tabular-nums">Train {segment.train}</span>{' '}
                        <span className="tabular-nums">{segment.depart}</span> <span aria-hidden="true">→</span>
                        <span className="sr-only">arrivée</span> <span className="tabular-nums">{segment.arrivee}</span>{' '}
                        {segment.gare_arrivee}
                      </span>
                    </li>
                  </Fragment>
                )
              })}
            </ol>
          )}
    </section>
  )
}

/**
 * Le billet récapitulatif, version large et basse : élément signature des écrans de fin de parcours.
 * Rangée 1 : aller et retour côte à côte. Rangée 2 : voyageurs · accès · indice.
 * Talon perforé à droite (date de la sortie, référence du dossier), encoches en demi-cercle,
 * ombre dure bleu nuit. La mise en page suit la largeur du billet (requêtes de conteneur),
 * pas celle de l'écran : il s'adapte à la colonne qui l'accueille.
 */
export default function BilletRecap({ site, proposition, demande, reference }: BilletRecapProps) {
  const idTitre = useId()
  const eleves = demande?.nb_eleves ?? 0
  const accompagnateurs = demande?.nb_accompagnateurs ?? 0
  const total = eleves + accompagnateurs
  const acces = site.acces_gare_site
  const IconeAcces = acces.mode === 'pied' ? Footprints : Bus
  const { indice } = proposition
  const date = proposition.date || demande?.date || null
  const parties = partiesDate(date)

  return (
    <article
      aria-labelledby={idTitre}
      className="@container rounded-box border-2 border-secondary bg-base-100 shadow-[4px_4px_0_0] shadow-secondary print:shadow-none"
    >
      <div className="grid @2xl:grid-cols-[minmax(0,1fr)_auto_9.5rem]">
        {/* Partie principale du billet */}
        <div className="@container/billet flex min-w-0 flex-col gap-3 p-4">
          <header className="flex min-w-0 flex-col gap-0.5">
            {/* Pas de majuscules forcées ici : « liO » s'écrit toujours ainsi. */}
            <p className="flex items-center gap-1.5 text-xs font-semibold text-base-content/70">
              <TrainFront className="size-3.5 shrink-0" aria-hidden="true" />
              Billet récapitulatif · sortie en train liO
            </p>
            <h2 id={idTitre} className="text-lg font-bold leading-tight">
              {site.nom}
            </h2>
            <p className="flex flex-wrap items-center gap-x-1.5 text-xs">
              <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
              <span className="font-semibold">{site.commune}</span>
              <span aria-hidden="true">·</span>
              <span>Gare d'arrivée : {site.gare.nom}</span>
            </p>
          </header>

          <div className="grid gap-3 @lg/billet:grid-cols-2 @lg/billet:gap-5">
            <LigneTrajet sens="Aller" trajet={proposition.aller} />
            <LigneTrajet sens="Retour" trajet={proposition.retour} />
          </div>

          <dl className="grid grid-cols-2 gap-3 border-t-2 border-dashed border-base-300 pt-3 @lg/billet:grid-cols-3">
            <div className="flex min-w-0 flex-col gap-1">
              <dt className={LIBELLE_RUBRIQUE}>
                <Users className="size-3.5 shrink-0" aria-hidden="true" />
                Voyageurs
              </dt>
              <dd className="flex flex-col items-start gap-1">
                <p className="tabular-nums">
                  <span className="text-lg font-extrabold">{total}</span>{' '}
                  <span className="text-xs font-semibold">sur {MAX_VOYAGEURS_GROUPE} max.</span>
                </p>
                <p className="text-xs tabular-nums">
                  {pluriel(eleves, 'élève', 'élèves')} + {pluriel(accompagnateurs, 'accompagnateur', 'accompagnateurs')}
                </p>
                {total > MAX_VOYAGEURS_GROUPE && (
                  <PastilleNiveau niveau="orange" libelle={`Au-delà de ${MAX_VOYAGEURS_GROUPE}`} taille="sm" />
                )}
              </dd>
            </div>
            <div className="flex min-w-0 flex-col gap-1">
              <dt className={LIBELLE_RUBRIQUE}>
                <IconeAcces className="size-3.5 shrink-0" aria-hidden="true" />
                Gare → site
              </dt>
              <dd className="flex flex-col items-start gap-1">
                <p>
                  <span className="text-lg font-extrabold tabular-nums">{acces.minutes_groupe}</span>{' '}
                  <span className="text-xs font-semibold">min {acces.mode === 'pied' ? 'à pied' : 'en transport urbain'}</span>
                </p>
                <PastilleNiveau niveau={acces.niveau} libelle={LIBELLES_NIVEAU_ACCES[acces.niveau]} taille="sm" />
              </dd>
            </div>
            <div className="flex min-w-0 flex-col gap-1">
              <dt className={LIBELLE_RUBRIQUE}>
                <Gauge className="size-3.5 shrink-0" aria-hidden="true" />
                Indice
              </dt>
              <dd className="flex flex-col items-start gap-1">
                <p className="tabular-nums">
                  <span className="text-lg font-extrabold">{indice.score}</span>{' '}
                  <span className="text-xs font-semibold">sur 100</span>
                </p>
                <PastilleNiveau niveau={indice.niveau} libelle={LIBELLES_NIVEAU_INDICE[indice.niveau]} taille="sm" />
              </dd>
            </div>
          </dl>
        </div>

        {/* Ligne de perforations et encoches */}
        <div aria-hidden="true" className="relative h-6 @2xl:h-auto @2xl:w-6">
          <span className="absolute inset-x-5 top-1/2 h-0.5 -translate-y-1/2 bg-[repeating-linear-gradient(90deg,var(--color-secondary)_0_6px,transparent_6px_11px)] @2xl:hidden" />
          <span className="absolute inset-y-5 left-1/2 hidden w-0.5 -translate-x-1/2 bg-[repeating-linear-gradient(180deg,var(--color-secondary)_0_6px,transparent_6px_11px)] @2xl:block" />
          <span className="absolute -left-0.5 top-1/2 h-6 w-3 -translate-y-1/2 rounded-r-full border-2 border-l-0 border-secondary bg-base-200 @2xl:hidden" />
          <span className="absolute -right-0.5 top-1/2 h-6 w-3 -translate-y-1/2 rounded-l-full border-2 border-r-0 border-secondary bg-base-200 @2xl:hidden" />
          <span className="absolute -top-0.5 left-1/2 hidden h-3 w-6 -translate-x-1/2 rounded-b-full border-2 border-t-0 border-secondary bg-base-200 @2xl:block" />
          <span className="absolute -bottom-0.5 left-1/2 hidden h-3 w-6 -translate-x-1/2 rounded-t-full border-2 border-b-0 border-secondary bg-base-200 @2xl:block" />
        </div>

        {/* Talon : date de la sortie, référence, code-barres */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 @2xl:flex-col @2xl:flex-nowrap @2xl:justify-center @2xl:text-center">
          <div className="flex flex-col @2xl:items-center">
            <p className="text-xs font-semibold uppercase tracking-wide text-base-content/70">Sortie du</p>
            {parties && date ? (
              <time dateTime={date} className="flex items-baseline gap-1.5 @2xl:flex-col @2xl:items-center @2xl:gap-0">
                <span className="sr-only">{formaterDateLongue(date)}</span>
                <span aria-hidden="true" className="text-sm font-bold">
                  {parties.jourSemaine}
                </span>
                <span aria-hidden="true" className="text-2xl font-extrabold leading-none tabular-nums">
                  {parties.jour}
                </span>
                <span aria-hidden="true" className="text-sm font-bold">
                  {parties.moisAnnee}
                </span>
              </time>
            ) : (
              <p className="text-sm font-bold">Date à préciser</p>
            )}
          </div>
          <div className="flex flex-col @2xl:items-center">
            <p className="text-xs font-semibold uppercase tracking-wide text-base-content/70">Dossier</p>
            <p className="text-xs font-extrabold tabular-nums wrap-anywhere">{reference ?? 'Après envoi'}</p>
          </div>
          <div
            aria-hidden="true"
            className="h-8 w-24 bg-[repeating-linear-gradient(90deg,var(--color-secondary)_0_2px,transparent_2px_5px,var(--color-secondary)_5px_9px,transparent_9px_11px,var(--color-secondary)_11px_12px,transparent_12px_16px)]"
          />
        </div>
      </div>
    </article>
  )
}
