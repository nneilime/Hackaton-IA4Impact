import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Circle,
  CircleCheck,
  CircleX,
  Copy,
  Hourglass,
  MapPin,
  MessageSquareHeart,
  Send,
  TrainFront,
  Users,
} from 'lucide-react'
import { ErreurApi, api } from '../../api/client'
import type { Demande, Destination, Dossier, Proposition, Trajet } from '../../api/types'
import type { PropsPanneau } from '../types'
import { erreurEmail, etapeFrise, formaterDateLongue, partiesDate } from '../../components/dossier/format'
import { AnneauScore } from '../../components/voyage/IndiceConfiance'
import PastilleNiveau from '../../components/voyage/PastilleNiveau'
import { formaterDuree, libelleCorrespondances, pluriel } from '../../components/voyage/format'
import { useVoyage } from '../../state/VoyageContext'
import { CadrePanneau, PanneauVide, SqueletteCarte } from './communs'
import { LIBELLES_INDICE } from './libelles'

const MESSAGE_TRANSMIS = 'Demande de pré-réservation transmise — confirmation en attente'

/** Les quatre gares de la demande. La confirmation n'arrive qu'après la réponse du chargé de clientèle SNCF. */
const ETAPES_DOSSIER = ['Proposition', 'Option', 'Pré-réservation', 'Confirmation'] as const

function LigneTrajet({ sens, trajet }: { sens: string; trajet: Trajet }) {
  const premier = trajet.segments[0]
  const dernier = trajet.segments[trajet.segments.length - 1]
  return (
    <div className="grid min-w-0 gap-1">
      <p className="flex flex-wrap items-center gap-x-2 text-xs font-semibold">
        <span className="badge badge-secondary badge-sm font-bold">{sens}</span>
        <span className="tabular-nums text-base-content/70">
          {formaterDuree(trajet.duree_min)} · {libelleCorrespondances(trajet.correspondances)}
        </span>
      </p>
      <p className="flex flex-wrap items-baseline gap-x-2 tabular-nums">
        <span className="text-lg font-bold">{trajet.depart}</span>
        <span aria-hidden="true">→</span>
        <span className="sr-only">arrivée</span>
        <span className="text-lg font-bold">{trajet.arrivee}</span>
      </p>
      <p className="text-xs leading-snug">
        {premier?.gare_depart ?? 'Gare de départ'} <span aria-hidden="true">→</span>
        <span className="sr-only"> vers </span> {dernier?.gare_arrivee ?? 'gare d’arrivée'}
      </p>
    </div>
  )
}

interface BilletProps {
  destination: Destination
  proposition: Proposition
  demande: Demande
  reference: string | null
  titreId: string
}

/** Le billet épuré : destination, date, aller, retour, voyageurs, indice. Talon perforé à droite. */
function BilletEpure({ destination, proposition, demande, reference, titreId }: BilletProps) {
  const eleves = demande.nb_eleves ?? 0
  const accompagnateurs = demande.nb_accompagnateurs ?? 0
  const total = eleves + accompagnateurs
  const parties = partiesDate(proposition.date || demande.date)

  return (
    <div className="grid sm:grid-cols-[minmax(0,1fr)_auto]">
      <div className="flex min-w-0 flex-col gap-4 p-4 sm:p-5">
        <header className="flex min-w-0 flex-col gap-1 pe-10">
          <h2 id={titreId} className="text-xl font-bold leading-tight">
            {destination.nom}
          </h2>
          <p className="flex flex-wrap items-center gap-x-1.5 text-sm">
            <MapPin className="size-4 shrink-0" aria-hidden="true" />
            <span className="font-semibold">{destination.commune}</span>
            <span aria-hidden="true">·</span>
            <span>Gare : {destination.gare.nom}</span>
          </p>
        </header>

        <div className="grid gap-4 @sm:grid-cols-2">
          <LigneTrajet sens="Aller" trajet={proposition.aller} />
          <LigneTrajet sens="Retour" trajet={proposition.retour} />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t-2 border-dashed border-base-300 pt-4">
          <p className="flex items-start gap-2 text-sm tabular-nums">
            <Users className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>
              <span className="font-extrabold">{total}</span> {pluriel(total, 'voyageur')}
              <span className="block text-xs">
                {eleves} {pluriel(eleves, 'élève')} + {accompagnateurs} {pluriel(accompagnateurs, 'accompagnateur')}
              </span>
            </span>
          </p>
          <div className="flex items-center gap-2">
            <AnneauScore score={proposition.indice.score} niveau={proposition.indice.niveau} />
            <PastilleNiveau
              niveau={proposition.indice.niveau}
              libelle={LIBELLES_INDICE[proposition.indice.niveau]}
            />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 border-t-2 border-dashed border-secondary px-4 py-3 sm:min-w-36 sm:flex-col sm:justify-center sm:border-l-2 sm:border-t-0 sm:px-5 sm:text-center">
        {parties ? (
          <time dateTime={proposition.date} className="grid justify-items-center leading-none sm:gap-0.5">
            <span className="text-xs font-semibold uppercase">{parties.jourSemaine}</span>
            <span className="text-3xl font-extrabold tabular-nums">{parties.jour}</span>
            <span className="text-xs font-semibold">{parties.moisAnnee}</span>
          </time>
        ) : (
          <p className="text-sm font-semibold">Date à préciser</p>
        )}
        <p className="grid min-w-0 gap-0.5 text-xs">
          <span className="sr-only">{formaterDateLongue(proposition.date || demande.date)}</span>
          {reference ? (
            <>
              <span className="font-semibold">Dossier</span>
              <span className="break-all font-mono font-bold">{reference}</span>
            </>
          ) : (
            <span className="flex items-center gap-1">
              <TrainFront className="size-3.5 shrink-0" aria-hidden="true" />
              Train liO
            </span>
          )}
        </p>
      </div>
    </div>
  )
}

/** Frise des 4 statuts, simplifiée : couleur + marque + libellé, jamais « confirmé » avant la vraie confirmation. */
function FriseSimple({ etapeActuelle }: { etapeActuelle: number }) {
  return (
    <ol aria-label="Étapes de la demande de pré-réservation" className="steps steps-vertical w-full text-xs @md:steps-horizontal">
      {ETAPES_DOSSIER.map((libelle, index) => {
        const faite = index < etapeActuelle
        const actuelle = index === etapeActuelle
        return (
          <li
            key={libelle}
            data-content={faite ? '✓' : actuelle ? '●' : ''}
            aria-current={actuelle ? 'step' : undefined}
            className={faite || actuelle ? 'step step-secondary' : 'step'}
          >
            <span className={actuelle ? 'font-bold' : 'font-semibold'}>
              {libelle}
              <span className="sr-only">{faite ? ' (étape franchie)' : actuelle ? ' (étape en cours)' : ' (à venir)'}</span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}

/** Étapes « prereservation » et « fin » : relire le billet, envoyer la demande, puis suivre le dossier. */
export default function PanneauPrereservation({ reponse, envoyer, chargement }: PropsPanneau) {
  const titreId = useId()
  const { dossier, definirDossier } = useVoyage()
  const demande = reponse.etat.demande

  const [email, setEmail] = useState('')
  const [emailTouche, setEmailTouche] = useState(false)
  const [compris, setCompris] = useState(false)
  const [envoi, setEnvoi] = useState(false)
  const [erreurEnvoi, setErreurEnvoi] = useState<string | null>(null)
  const [referenceLocale, setReferenceLocale] = useState<string | null>(null)
  const [dossierRecupere, setDossierRecupere] = useState<Dossier | null>(null)
  const [copie, setCopie] = useState<'oui' | 'non' | 'echec'>('non')
  const champEmail = useRef<HTMLInputElement>(null)
  const minuteurCopie = useRef<number | undefined>(undefined)

  const reference = referenceLocale ?? reponse.etat.dossier_reference ?? null
  const envoyee = reponse.etape === 'fin' || reference !== null

  // Le dossier complet vient du contexte ; après un rechargement de page, on le relit auprès du back.
  const dossierContexte = dossier && dossier.reference === reference ? dossier : null
  useEffect(() => {
    if (!reference || dossierContexte || dossierRecupere?.reference === reference) return
    let annule = false
    api
      .dossier(reference)
      .then((lu) => {
        if (!annule) setDossierRecupere(lu)
      })
      .catch(() => {
        // sans le dossier, la frise garde l'étape « Pré-réservation » : c'est l'état de toute demande transmise
      })
    return () => {
      annule = true
    }
  }, [reference, dossierContexte, dossierRecupere])
  useEffect(() => () => window.clearTimeout(minuteurCopie.current), [])

  // À l'étape « fin », le back ne renvoie plus la destination ni le trajet : on les reprend du dossier transmis.
  const dossierCourant = dossierContexte ?? (dossierRecupere?.reference === reference ? dossierRecupere : null)
  const destination = reponse.destination ?? dossierCourant?.site ?? null
  const proposition = reponse.proposition ?? dossierCourant?.proposition ?? null

  if (!destination || !proposition) {
    return chargement || (envoyee && reference) ? (
      <SqueletteCarte />
    ) : (
      <PanneauVide
        titre="Aucun trajet à pré-réserver pour l’instant"
        texte="Choisissez d’abord une destination et un trajet avec Tchouette, ou revenez en arrière avec « Retour »."
      />
    )
  }

  const messageEmail = erreurEmail(email)
  const emailValide = messageEmail === null
  const pret = emailValide && compris
  const afficherErreurEmail = emailTouche && !emailValide

  let raison = ''
  if (!emailValide && !compris) raison = 'Indiquez votre e-mail et cochez la case pour envoyer la demande.'
  else if (!emailValide) raison = 'Indiquez une adresse e-mail valide pour envoyer la demande.'
  else if (!compris) raison = 'Cochez la case pour envoyer la demande.'

  async function soumettre(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault()
    if (!proposition) return
    if (!emailValide) {
      setEmailTouche(true)
      champEmail.current?.focus()
      return
    }
    if (!compris || envoi) return
    setEnvoi(true)
    setErreurEnvoi(null)
    try {
      const cree = await api.preReserver(proposition.proposition_id, email.trim(), demande)
      definirDossier(cree)
      setReferenceLocale(cree.reference)
      envoyer({ type: 'prereservation_faite', reference: cree.reference })
    } catch (cause) {
      setErreurEnvoi(
        cause instanceof ErreurApi ? cause.message : 'L’envoi de la demande a échoué. Vérifiez votre connexion, puis réessayez.',
      )
    } finally {
      setEnvoi(false)
    }
  }

  async function copier() {
    if (!reference) return
    window.clearTimeout(minuteurCopie.current)
    try {
      await navigator.clipboard.writeText(reference)
      setCopie('oui')
    } catch {
      setCopie('echec')
    }
    minuteurCopie.current = window.setTimeout(() => setCopie('non'), 2500)
  }

  const etapeCourante = dossierCourant ? etapeFrise(dossierCourant.statut) : 2

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <CadrePanneau titreId={titreId} occupe={chargement && !envoi}>
        <div className="@container">
          <BilletEpure
            destination={destination}
            proposition={proposition}
            demande={demande}
            reference={envoyee ? reference : null}
            titreId={titreId}
          />
        </div>
      </CadrePanneau>

      {envoyee ? (
        <section
          aria-label="Votre demande"
          className="@container flex min-w-0 flex-col gap-4 rounded-box border-2 border-secondary bg-base-100 p-4 motion-safe:animate-pop sm:p-5"
        >
          <div role="status" aria-live="polite" className="grid gap-3">
            <p className="flex items-start gap-2 text-base font-bold leading-snug">
              <Hourglass className="mt-0.5 size-5 shrink-0 text-info" aria-hidden="true" />
              {MESSAGE_TRANSMIS}
            </p>
            {reference && (
              <div className="grid gap-1">
                <p className="text-xs font-semibold uppercase tracking-wide text-base-content/70">
                  Référence du dossier
                </p>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                  <p className="[user-select:all] break-all font-mono text-2xl font-extrabold tabular-nums">{reference}</p>
                  <button type="button" onClick={() => void copier()} className="btn btn-outline btn-sm min-h-10">
                    {copie === 'oui' ? (
                      <CircleCheck className="size-4" aria-hidden="true" />
                    ) : (
                      <Copy className="size-4" aria-hidden="true" />
                    )}
                    {copie === 'oui' ? 'Référence copiée' : 'Copier la référence'}
                  </button>
                </div>
                {copie === 'echec' && (
                  <p className="text-xs">La copie n’a pas fonctionné : sélectionnez la référence pour la copier.</p>
                )}
              </div>
            )}
            {dossierCourant?.email && (
              <p className="text-sm">
                La réponse du chargé de clientèle SNCF sera envoyée à{' '}
                <span className="break-all font-semibold">{dossierCourant.email}</span>.
              </p>
            )}
          </div>

          <FriseSimple etapeActuelle={etapeCourante} />

          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {reference && (
              <Link
                to={`/dossier/${encodeURIComponent(reference)}`}
                className="btn btn-primary btn-md min-h-11"
              >
                Suivre mon dossier
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            )}
            {reference && (
              <Link
                to={`/retour/${encodeURIComponent(reference)}`}
                className="btn btn-outline btn-md min-h-11"
              >
                <MessageSquareHeart className="size-4" aria-hidden="true" />
                Donner mon retour après la sortie
              </Link>
            )}
          </div>
        </section>
      ) : (
        <form
          onSubmit={(e) => void soumettre(e)}
          noValidate
          aria-label="Envoyer la demande de pré-réservation"
          className="flex min-w-0 flex-col gap-4 rounded-box border border-base-300 bg-base-100 p-4 motion-safe:animate-entree sm:p-5"
        >
          <fieldset className="fieldset gap-1 p-0" disabled={envoi}>
            <label className="label text-sm font-semibold text-base-content" htmlFor={`${titreId}-email`}>
              Votre e-mail
            </label>
            <input
              ref={champEmail}
              id={`${titreId}-email`}
              type="email"
              aria-label="Votre e-mail"
              inputMode="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onBlur={() => setEmailTouche(true)}
              placeholder="prenom.nom@ac-toulouse.fr"
              aria-invalid={afficherErreurEmail}
              aria-describedby={afficherErreurEmail ? `${titreId}-email-erreur` : undefined}
              className={
                afficherErreurEmail
                  ? 'input input-error input-md min-h-11 w-full'
                  : 'input input-md min-h-11 w-full'
              }
            />
            {afficherErreurEmail && (
              <p id={`${titreId}-email-erreur`} role="alert" className="flex items-start gap-1.5 text-sm font-semibold text-error">
                <CircleX className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                {messageEmail}
              </p>
            )}
          </fieldset>

          <label className="flex min-h-10 cursor-pointer items-start gap-3 text-sm">
            <input
              type="checkbox"
              checked={compris}
              onChange={(e) => setCompris(e.target.checked)}
              disabled={envoi}
              className="checkbox checkbox-secondary mt-0.5"
            />
            <span>J’ai compris qu’il s’agit d’une demande de pré-réservation, pas d’une réservation confirmée.</span>
          </label>

          <div className="grid gap-2">
            <button
              type="submit"
              disabled={!pret || envoi}
              aria-describedby={pret ? undefined : `${titreId}-raison`}
              className="btn btn-primary btn-md min-h-11 w-full sm:w-fit"
            >
              {envoi ? (
                <span className="loading loading-spinner loading-sm" aria-hidden="true" />
              ) : (
                <Send className="size-4" aria-hidden="true" />
              )}
              {envoi ? 'Envoi en cours…' : 'Envoyer la demande'}
            </button>
            {!pret && (
              <p id={`${titreId}-raison`} className="flex items-start gap-1.5 text-xs">
                <Circle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                {raison}
              </p>
            )}
            {erreurEnvoi && (
              <div role="alert" className="alert alert-error alert-soft text-sm">
                <CircleX className="size-5 shrink-0" aria-hidden="true" />
                <span>{erreurEnvoi}</span>
              </div>
            )}
          </div>
        </form>
      )}
    </div>
  )
}
