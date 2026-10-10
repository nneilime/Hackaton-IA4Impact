import { useId } from 'react'
import {
  ArrowLeftRight,
  CalendarClock,
  CalendarSearch,
  CheckCircle2,
  Clock,
  Hourglass,
  Train,
  TriangleAlert,
  Users,
} from 'lucide-react'
import type { Controle, CritereIndice, DateProche, Jauge, OptionHoraire } from '../../api/types'
import type { PropsPanneau } from '../types'
import ImpactCO2, { distanceKm } from './ImpactCO2'
import FriseTrajet from '../../components/voyage/FriseTrajet'
import { AnneauScore } from '../../components/voyage/IndiceConfiance'
import PastilleNiveau, { PuceNiveau } from '../../components/voyage/PastilleNiveau'
import {
  RANG_NIVEAU,
  compterControles,
  formaterDateCourte,
  formaterDateLongue,
  formaterDuree,
  formaterPoints,
  pluriel,
} from '../../components/voyage/format'
import { CadrePanneau, DetailPourquoi, PanneauVide, Repliable, SqueletteCarte } from './communs'
import {
  CLASSES_BARRE_PLACES,
  LIBELLES_CONTROLE_ENSEIGNANT,
  LIBELLES_CRITERE_ENSEIGNANT,
  LIBELLES_INDICE,
  LIBELLES_PLACES,
  PHRASE_INDICE,
  STATUT_CONTROLE,
} from './libelles'

/** Un seul chiffre pour les places : le train le plus chargé, aller ou retour. Jamais l'identité d'un autre groupe. */
function jaugeLaPlusTendue(aller: Jauge, retour: Jauge): Jauge {
  if (aller.disponibles !== retour.disponibles) return aller.disponibles < retour.disponibles ? aller : retour
  return RANG_NIVEAU[retour.niveau] > RANG_NIVEAU[aller.niveau] ? retour : aller
}

function BlocPlaces({ jauge, differe }: { jauge: Jauge; differe: boolean }) {
  const { disponibles, besoin, niveau } = jauge
  const couverture = besoin > 0 ? Math.min(disponibles, besoin) : 0
  return (
    <section aria-label="Places dans le train" className="grid min-w-0 content-start gap-2 rounded-field bg-base-200 p-3">
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <p className="flex items-center gap-1.5 text-xs font-semibold text-base-content/70">
          <Users className="size-3.5 shrink-0" aria-hidden="true" />
          Places dans le train
        </p>
        <PastilleNiveau niveau={niveau} libelle={LIBELLES_PLACES[niveau]} />
      </div>
      <progress
        className={CLASSES_BARRE_PLACES[niveau]}
        value={couverture}
        max={Math.max(1, besoin)}
        aria-label={`${disponibles} places disponibles pour ${besoin} voyageurs`}
      />
      <p className="text-sm tabular-nums">
        <span className="font-bold">
          {disponibles} {pluriel(disponibles, 'place disponible', 'places disponibles')}
        </span>{' '}
        pour <span className="font-bold">{besoin}</span> {pluriel(besoin, 'voyageur')}
        {differe && (
          <span className="block text-xs text-base-content/70">Sur le train le plus chargé, aller ou retour.</span>
        )}
      </p>
    </section>
  )
}

function ListeControlesEnseignant({ controles }: { controles: Controle[] }) {
  if (controles.length === 0) return <p>Aucun contrôle n’a été transmis pour ce trajet.</p>
  const tries = [...controles].sort((a, b) => RANG_NIVEAU[b.niveau] - RANG_NIVEAU[a.niveau])
  return (
    <ul className="grid gap-2.5 pt-1">
      {tries.map((controle, index) => (
        <li key={`${controle.regle}-${index}`} className="flex items-start gap-2.5">
          <PuceNiveau niveau={controle.niveau} />
          <div className="grid min-w-0 gap-0.5">
            <p className="font-semibold leading-snug">
              {LIBELLES_CONTROLE_ENSEIGNANT[controle.regle] ?? controle.libelle}
              <span className="font-bold"> · {STATUT_CONTROLE[controle.niveau]}</span>
            </p>
            <p className="text-xs leading-snug">{controle.message}</p>
          </div>
        </li>
      ))}
    </ul>
  )
}

function ListeCriteres({ details }: { details: CritereIndice[] }) {
  if (details.length === 0) return <p>Le détail du score n’est pas disponible pour ce trajet.</p>
  return (
    <ul className="grid gap-3 pt-1">
      {details.map((critere) => {
        const nom = LIBELLES_CRITERE_ENSEIGNANT[critere.critere] ?? critere.critere
        return (
          <li key={critere.critere} className="grid gap-1">
            <div className="flex items-baseline justify-between gap-3">
              <span className="font-semibold">{nom}</span>
              <span className="shrink-0 font-bold tabular-nums">
                {formaterPoints(critere.points)}/{formaterPoints(critere.max)}
              </span>
            </div>
            <progress
              className="progress h-1.5 w-full"
              value={critere.points}
              max={Math.max(1, critere.max)}
              aria-label={`${nom} : ${formaterPoints(critere.points)} points sur ${formaterPoints(critere.max)}`}
            />
            <p className="text-xs leading-snug">{critere.explication}</p>
          </li>
        )
      })}
    </ul>
  )
}

function resumeControles(controles: Controle[]): string {
  const c = compterControles(controles)
  const morceaux: string[] = []
  if (c.vert > 0) morceaux.push(`${c.vert} ${pluriel(c.vert, 'conforme')}`)
  if (c.orange > 0) morceaux.push(`${c.orange} à surveiller`)
  if (c.rouge > 0) morceaux.push(`${c.rouge} ${pluriel(c.rouge, 'bloquant')}`)
  return morceaux.join(' · ')
}

const SENS: Record<'aller' | 'retour', { titre: string; id: string }> = {
  aller: { titre: 'Autre horaire pour l’aller', id: 'changer_aller' },
  retour: { titre: 'Autre horaire pour le retour', id: 'changer_retour' },
}

/** Liste de circulations faisables (calculées par le serveur) pour changer l'aller ou le retour. */
function AutreHoraire({
  sens,
  options,
  envoyer,
  occupe,
}: {
  sens: 'aller' | 'retour'
  options: OptionHoraire[]
  envoyer: PropsPanneau['envoyer']
  occupe: boolean
}) {
  const autres = options.filter((o) => !o.actuel).length
  if (options.length < 2) return null
  return (
    <Repliable titre={SENS[sens].titre} resume={`${autres} ${pluriel(autres, 'autre choix', 'autres choix')}`}>
      <p className="flex items-center gap-1.5 pb-2 text-xs">
        <ArrowLeftRight className="size-3.5 shrink-0" aria-hidden="true" />
        {sens === 'retour' ? 'Retours possibles avant votre heure limite.' : 'Départs possibles depuis votre gare.'}
      </p>
      <ul className="grid gap-2">
        {options.map((o) => (
          <li key={o.id}>
            <button
              type="button"
              disabled={occupe || o.actuel}
              aria-current={o.actuel ? 'true' : undefined}
              onClick={() => envoyer({ type: 'choix', id: `${SENS[sens].id}:${o.id}` })}
              className={`grid w-full min-w-0 gap-1.5 rounded-field border-2 p-2.5 text-left ${
                o.actuel ? 'border-primary bg-base-200' : 'border-base-300 bg-base-100 hover:border-primary'
              }`}
            >
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1 font-bold tabular-nums">
                <Clock className="size-4 shrink-0" aria-hidden="true" />
                {o.depart} → {o.arrivee}
                <span className="text-xs font-semibold">
                  {formaterDuree(o.duree_min)} · {o.correspondances === 0 ? 'direct' : `${o.correspondances} corresp.`}
                </span>
                {o.actuel && (
                  <span className="badge badge-sm gap-1 font-bold">
                    <CheckCircle2 className="size-3.5" aria-hidden="true" />
                    Horaire actuel
                  </span>
                )}
              </span>
              <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                <span className="flex items-center gap-1 tabular-nums">
                  <Users className="size-3.5 shrink-0" aria-hidden="true" />
                  {o.places_disponibles} places pour {o.besoin} voyageurs
                </span>
                <PastilleNiveau niveau={o.niveau} libelle={LIBELLES_INDICE[o.niveau]} />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Repliable>
  )
}

function DatesProches({
  dates,
  envoyer,
  occupe,
}: {
  dates: DateProche[]
  envoyer: PropsPanneau['envoyer']
  occupe: boolean
}) {
  return (
    <ul className="grid gap-2">
      {dates.map((d) => (
        <li key={d.date}>
          <button
            type="button"
            disabled={occupe}
            onClick={() => envoyer({ type: 'choix', id: `choisir_date:${d.date}` })}
            className="grid w-full min-w-0 gap-1 rounded-field border-2 border-base-300 bg-base-100 p-3 text-left hover:border-primary"
          >
            <span className="flex flex-wrap items-center gap-2 font-bold">
              <CalendarSearch className="size-4 shrink-0" aria-hidden="true" />
              {formaterDateLongue(d.date)}
              <span className="text-xs font-semibold tabular-nums">
                ({d.ecart_jours > 0 ? '+' : '−'}
                {Math.abs(d.ecart_jours)} j)
              </span>
            </span>
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs tabular-nums">
              <span className="flex items-center gap-1">
                <Train className="size-3.5 shrink-0" aria-hidden="true" />
                Aller {d.aller.depart} · retour {d.retour.arrivee}
              </span>
              <PastilleNiveau niveau={d.niveau} libelle={LIBELLES_INDICE[d.niveau]} />
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}

/** Étape « trajet » : le meilleur trajet pour la date demandée, compact. Le détail est à la demande. */
export default function PanneauTrajet({ reponse, chargement, envoyer }: PropsPanneau) {
  const titreId = useId()
  const proposition = reponse.proposition
  const destination = reponse.destination

  const retourEtape = (
    <button
      type="button"
      disabled={chargement}
      onClick={() => envoyer({ type: 'choix', id: 'retour_etape' })}
      className="btn btn-ghost btn-sm justify-start gap-1.5 self-start"
    >
      <ArrowLeftRight className="size-4" aria-hidden="true" />
      Revenir à l’étape précédente
    </button>
  )

  if (!proposition && (reponse.dates_proches?.length ?? 0) > 0) {
    return (
      <div className="flex min-w-0 flex-col gap-3">
        <CadrePanneau titreId={titreId} occupe={chargement}>
          <div className="flex flex-col gap-3 p-4 sm:p-5">
            <h2 id={titreId} className="flex items-start gap-2 text-lg font-bold leading-tight">
              <TriangleAlert className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden="true" />
              Pas de train fiable à cette date
            </h2>
            <p className="text-sm">Choisissez une date proche : Tchouette relance le parcours avec elle.</p>
            <DatesProches dates={reponse.dates_proches ?? []} envoyer={envoyer} occupe={chargement} />
          </div>
        </CadrePanneau>
        {retourEtape}
      </div>
    )
  }

  if (!proposition) {
    return chargement ? (
      <SqueletteCarte />
    ) : (
      <PanneauVide
        titre="Pas encore de trajet à vous montrer"
        texte="Tchouette n’a pas trouvé de train pour cette date. Revenez en arrière avec « Retour » pour essayer une autre idée."
      />
    )
  }

  const dateDemandee = reponse.etat.demande.date
  const autreDate = !!dateDemandee && proposition.date.slice(0, 10) !== dateDemandee.slice(0, 10)
  const jauge = jaugeLaPlusTendue(proposition.jauge_aller, proposition.jauge_retour)
  const jaugesDifferent = proposition.jauge_aller.disponibles !== proposition.jauge_retour.disponibles
  const { indice } = proposition
  const depart = reponse.etat.demande.gare_depart
  const kmAllerRetour = depart && destination?.gare ? 2 * distanceKm(depart, destination.gare) : null
  const bloquant = proposition.controles.some((c) => c.niveau === 'rouge')

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <CadrePanneau titreId={titreId} occupe={chargement}>
        <div className="flex flex-col gap-4 p-4 sm:p-5">
          <header className="flex min-w-0 flex-col gap-1.5 pe-10">
            <h2 id={titreId} className="text-lg font-bold leading-tight">
              {destination ? `Aller-retour pour ${destination.nom}` : 'Votre aller-retour en train liO'}
            </h2>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
              <CalendarClock className="size-4 shrink-0" aria-hidden="true" />
              <time dateTime={proposition.date} className="font-semibold">
                {formaterDateLongue(proposition.date)}
              </time>
              {autreDate && (
                <span className="badge badge-warning badge-sm gap-1 font-bold">
                  <TriangleAlert className="size-3.5" aria-hidden="true" />
                  Autre date
                </span>
              )}
            </p>
            {autreDate && (
              <p className="text-xs">
                Vous aviez demandé le {formaterDateCourte(dateDemandee)} : Tchouette vous propose ce jour-là.
              </p>
            )}
          </header>

          <div className="grid gap-3">
            <FriseTrajet trajet={proposition.aller} titre="Aller" />
            <div aria-hidden="true" className="border-t-2 border-dashed border-base-300" />
            <FriseTrajet trajet={proposition.retour} titre="Retour" />
          </div>

          <div className="grid gap-2 sm:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <BlocPlaces jauge={jauge} differe={jaugesDifferent} />
            <section
              aria-label="Marge avant la visite"
              className="flex min-w-0 flex-col items-start gap-1.5 rounded-field bg-base-200 p-3"
            >
              <p className="flex items-center gap-1.5 text-xs font-semibold text-base-content/70">
                <Hourglass className="size-3.5 shrink-0" aria-hidden="true" />
                Marge avant la visite
              </p>
              <p className="text-lg font-extrabold leading-none tabular-nums">
                {formaterDuree(proposition.marge_avant_visite_min)}
              </p>
              <p className="text-xs leading-snug">entre l’arrivée du train et le début de la visite</p>
            </section>
          </div>

          <div className="flex items-center gap-3 border-t-2 border-dashed border-base-300 pt-4">
            <AnneauScore score={indice.score} niveau={indice.niveau} taille="md" />
            <div className="grid min-w-0 justify-items-start gap-1">
              <PastilleNiveau niveau={indice.niveau} libelle={LIBELLES_INDICE[indice.niveau]} />
              <p className="text-sm font-semibold leading-snug">{PHRASE_INDICE[indice.niveau]}</p>
            </div>
          </div>

          {bloquant && (
            <p role="note" className="flex items-start gap-2 rounded-field bg-error/10 p-2.5 text-sm font-semibold">
              <TriangleAlert className="mt-0.5 size-4 shrink-0 text-error" aria-hidden="true" />
              <span>Un point bloquant a été relevé : ouvrez « Voir les contrôles » pour le détail.</span>
            </p>
          )}
        </div>
      </CadrePanneau>

      {reponse.alternatives && (
        <>
          <AutreHoraire sens="aller" options={reponse.alternatives.aller} envoyer={envoyer} occupe={chargement} />
          <AutreHoraire sens="retour" options={reponse.alternatives.retour} envoyer={envoyer} occupe={chargement} />
        </>
      )}
      {kmAllerRetour !== null && <ImpactCO2 km={kmAllerRetour} />}
      <Repliable titre="Voir les contrôles" resume={resumeControles(proposition.controles)}>
        <ListeControlesEnseignant controles={proposition.controles} />
      </Repliable>
      <Repliable titre="Pourquoi ce score ?" resume={`${indice.score} sur 100`}>
        <ListeCriteres details={indice.details} />
      </Repliable>
      {reponse.detail && <DetailPourquoi key={reponse.detail.titre} detail={reponse.detail} />}
      {retourEtape}
    </div>
  )
}
