import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { createPortal } from 'react-dom'
import {
  Check,
  CircleCheck,
  CircleX,
  Copy,
  FlaskConical,
  MessageSquareText,
  PartyPopper,
  Printer,
  RotateCcw,
  Route,
  Shuffle,
  TriangleAlert,
} from 'lucide-react'
import { ErreurApi, api } from '../api/client'
import type { Dossier as DossierApi, EtapeDossier, Statut } from '../api/types'
import BilletRecap from '../components/dossier/BilletRecap'
import { ChargementDossier, DossierIntrouvable, ErreurDossier } from '../components/dossier/EtatsDossier'
import FriseStatuts from '../components/dossier/FriseStatuts'
import type { IssueFrise } from '../components/dossier/FriseStatuts'
import IntroEtape from '../components/dossier/IntroEtape'
import PastilleStatut, { PuceStatut } from '../components/dossier/PastilleStatut'
import { LIBELLES_ETAPE, etapeFrise, formaterHorodatage } from '../components/dossier/format'
import { useDossier } from '../components/dossier/useDossier'
import { useEcranEtroit } from '../components/dossier/useEcranEtroit'
import BarreAction from '../layout/BarreAction'
import type { BarreActionProps } from '../layout/BarreAction'
import type { HumeurTchouette } from '../mascot/Tchouette'
import { useVoyage } from '../state/VoyageContext'

type Decision = 'confirmer' | 'contre-proposition'

const CONTENEUR = 'mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 lg:gap-5 lg:px-6 lg:py-6'

export default function Dossier() {
  const { reference = '' } = useParams()
  const { dossier, chargement, erreur, introuvable, recharger, remplacer } = useDossier(reference)
  const { dossier: dossierEnCours } = useVoyage()

  if (dossier) {
    return (
      <VueDossier
        dossier={dossier}
        actualisation={chargement}
        erreurActualisation={erreur?.message ?? null}
        onReessayer={recharger}
        onMiseAJour={remplacer}
      />
    )
  }

  let contenu
  if (introuvable) {
    contenu = <DossierIntrouvable reference={reference} referenceEnCours={dossierEnCours?.reference} />
  } else if (erreur && !chargement) {
    contenu = <ErreurDossier message={erreur.message} onReessayer={recharger} />
  } else {
    contenu = <ChargementDossier reference={reference} />
  }
  return <div className={CONTENEUR}>{contenu}</div>
}

interface VueDossierProps {
  dossier: DossierApi
  actualisation: boolean
  erreurActualisation: string | null
  onReessayer: () => void
  onMiseAJour: (dossier: DossierApi) => void
}

/** Les trois humeurs de Tchouette sur le dossier, selon le statut. */
type HumeurDossier = Extract<HumeurTchouette, 'parle' | 'joie' | 'inquiete'>

const TITRES_TCHOUETTE: Record<HumeurDossier, string> = {
  parle: 'Tchouette vous tient au courant',
  joie: 'Tchouette se réjouit',
  inquiete: "Tchouette s'inquiète",
}

function VueDossier({ dossier, actualisation, erreurActualisation, onReessayer, onMiseAJour }: VueDossierProps) {
  const [copie, setCopie] = useState<'repos' | 'ok' | 'echec'>('repos')
  const [simulation, setSimulation] = useState<Decision | null>(null)
  const [derniereDecision, setDerniereDecision] = useState<Decision | null>(null)
  const [erreurSimulation, setErreurSimulation] = useState<string | null>(null)
  const [celebrationFinie, setCelebrationFinie] = useState(false)
  // Statut à l'ouverture de la page : la pastille ne rebondit, et Tchouette ne fête la confirmation,
  // que si le statut change sous les yeux de l'enseignant (simulation ou actualisation).
  const [statutInitial] = useState<Statut>(dossier.statut)
  const celebration =
    dossier.statut === 'CONFIRMATION' && statutInitial !== 'CONFIRMATION' && !celebrationFinie

  useEffect(() => {
    if (copie === 'repos') return
    const minuteur = window.setTimeout(() => setCopie('repos'), 2500)
    return () => window.clearTimeout(minuteur)
  }, [copie])

  useEffect(() => {
    if (!celebration) return
    const minuteur = window.setTimeout(() => setCelebrationFinie(true), 4000)
    return () => window.clearTimeout(minuteur)
  }, [celebration])

  async function copier() {
    try {
      await navigator.clipboard.writeText(dossier.reference)
      setCopie('ok')
    } catch {
      setCopie('echec')
    }
  }

  async function simuler(decision: Decision) {
    setSimulation(decision)
    setDerniereDecision(decision)
    setErreurSimulation(null)
    try {
      onMiseAJour(await api.simulerReponse(dossier.reference, decision))
    } catch (cause) {
      setErreurSimulation(
        cause instanceof ErreurApi ? cause.message : 'La simulation a échoué. Réessayez dans un instant.',
      )
    } finally {
      setSimulation(null)
    }
  }

  const { statut } = dossier
  const termine = statut === 'CONFIRMATION' || statut === 'ANNULE'
  const issue: IssueFrise | undefined =
    statut === 'CONTRE_PROPOSITION' ? 'contre-proposition' : statut === 'ANNULE' ? 'annule' : undefined
  const humeur: HumeurDossier =
    statut === 'CONFIRMATION' ? 'joie' : statut === 'CONTRE_PROPOSITION' || statut === 'ANNULE' ? 'inquiete' : 'parle'
  const statutChange = statut !== statutInitial

  return (
    <>
      <div className={CONTENEUR}>
        <IntroEtape
          humeur={humeur}
          titreTchouette={TITRES_TCHOUETTE[humeur]}
          rebond={celebration}
          etoiles={celebration}
          titre={
            <span className="text-2xl font-extrabold tabular-nums wrap-anywhere">
              <span className="sr-only">Dossier </span>
              {dossier.reference}
            </span>
          }
          aCote={
            <>
              <button
                type="button"
                onClick={() => void copier()}
                className="btn btn-ghost btn-sm print:hidden"
                aria-describedby="copie-etat"
              >
                {copie === 'ok' ? (
                  <Check className="size-4 motion-safe:animate-pop" aria-hidden="true" />
                ) : (
                  <Copy className="size-4" aria-hidden="true" />
                )}
                {copie === 'ok' ? 'Copié' : 'Copier'}
                <span className="sr-only"> la référence</span>
              </button>
              <span key={statut} className={statutChange ? 'inline-flex motion-safe:animate-pop' : 'inline-flex'}>
                <PastilleStatut statut={statut} />
              </span>
              {actualisation && (
                <span className="flex items-center gap-1.5 text-xs font-semibold text-base-content/70 print:hidden">
                  <span className="loading loading-spinner loading-xs" aria-hidden="true" />
                  Actualisation…
                </span>
              )}
            </>
          }
          phrase={<span aria-live="polite">{dossier.message}</span>}
          meta={
            <>
              <p id="copie-etat" aria-live="polite" className="sr-only">
                {copie === 'ok' ? 'Référence copiée.' : copie === 'echec' ? 'La copie a échoué.' : ''}
              </p>
              {copie === 'echec' && (
                <p className="flex items-center gap-1.5 text-xs font-semibold text-error">
                  <CircleX className="size-3.5 shrink-0" aria-hidden="true" />
                  Copie impossible : sélectionnez la référence pour la copier.
                </p>
              )}
            </>
          }
        />

        {erreurActualisation && (
          <div role="alert" className="alert alert-warning alert-vertical text-sm sm:alert-horizontal print:hidden">
            <TriangleAlert className="size-5 shrink-0" aria-hidden="true" />
            <span>Le dossier affiché n'a pas pu être actualisé. {erreurActualisation}</span>
            <button type="button" className="btn btn-sm" onClick={onReessayer}>
              <RotateCcw className="size-4" aria-hidden="true" />
              Réessayer
            </button>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:items-start lg:gap-5">
          <div className="flex min-w-0 flex-col gap-4">
            <section
              aria-labelledby="titre-frise"
              className="card border-2 border-secondary bg-base-100 motion-safe:animate-entree"
            >
              <div className="card-body gap-3 p-4">
                <h2 id="titre-frise" className="card-title text-lg font-bold lg:text-xl">
                  Où en est votre demande ?
                </h2>
                <FriseStatuts etapeActuelle={issue ? 3 : etapeFrise(statut)} issue={issue} />
                <ProchaineEtape dossier={dossier} />
              </div>
            </section>
            <Historique historique={dossier.historique} />
          </div>

          <div className="flex min-w-0 flex-col gap-4">
            <div className="motion-safe:animate-entree motion-safe:[animation-delay:80ms]">
              <BilletRecap
                site={dossier.site}
                proposition={dossier.proposition}
                demande={dossier.demande}
                reference={dossier.reference}
              />
            </div>
            {!termine && (
              <section
                aria-labelledby="titre-demo"
                className="flex flex-col gap-2 rounded-box border-2 border-dashed border-secondary bg-base-100 p-3 print:hidden"
              >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                  <div className="min-w-48 flex-1">
                    <h2 id="titre-demo" className="flex items-center gap-1.5 text-sm font-bold">
                      <FlaskConical className="size-4 shrink-0" aria-hidden="true" />
                      Démonstration
                    </h2>
                    <p className="text-xs text-base-content/80">
                      Dans le vrai service, un chargé de clientèle SNCF répond. Simulez sa réponse :
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="btn btn-dash btn-secondary btn-sm"
                      disabled={simulation !== null}
                      onClick={() => void simuler('confirmer')}
                    >
                      {simulation === 'confirmer' ? (
                        <span className="loading loading-spinner loading-xs" aria-hidden="true" />
                      ) : (
                        <CircleCheck className="size-4" aria-hidden="true" />
                      )}
                      Simuler une confirmation
                    </button>
                    <button
                      type="button"
                      className="btn btn-dash btn-secondary btn-sm"
                      disabled={simulation !== null}
                      onClick={() => void simuler('contre-proposition')}
                    >
                      {simulation === 'contre-proposition' ? (
                        <span className="loading loading-spinner loading-xs" aria-hidden="true" />
                      ) : (
                        <Shuffle className="size-4" aria-hidden="true" />
                      )}
                      Simuler une contre-proposition
                    </button>
                  </div>
                </div>
                {erreurSimulation && (
                  <div role="alert" className="alert alert-error alert-vertical text-sm sm:alert-horizontal">
                    <CircleX className="size-5 shrink-0" aria-hidden="true" />
                    <span>{erreurSimulation}</span>
                    {derniereDecision && (
                      <button type="button" className="btn btn-sm" onClick={() => void simuler(derniereDecision)}>
                        <RotateCcw className="size-4" aria-hidden="true" />
                        Réessayer
                      </button>
                    )}
                  </div>
                )}
              </section>
            )}
          </div>
        </div>
      </div>

      {/* Portail vers <body> : un ancêtre animé (transform) ferait sinon du toast un élément « absolute ». */}
      {celebration &&
        createPortal(
          <div className="toast toast-center toast-bottom z-40 mb-20 print:hidden">
            <div
              role="status"
              className="alert alert-success whitespace-normal text-sm font-bold shadow-[4px_4px_0_0] shadow-secondary"
            >
              <PartyPopper className="size-5 shrink-0" aria-hidden="true" />
              <span>Sortie confirmée par SNCF : bon voyage avec liO !</span>
            </div>
          </div>,
          document.body,
        )}

      <BarreDossier dossier={dossier} />
    </>
  )
}

/** Barre d'action selon le statut : une seule action rouge, et seulement une fois la sortie confirmée. */
function BarreDossier({ dossier }: { dossier: DossierApi }) {
  const navigate = useNavigate()
  const etroit = useEcranEtroit()
  const { definirDemande, choisirSite, reinitialiser } = useVoyage()
  const { statut, site, reference } = dossier

  const imprimer = (
    <button type="button" onClick={() => window.print()} className="btn btn-ghost btn-sm">
      <Printer className="size-4" aria-hidden="true" />
      <span className="hidden sm:inline">Imprimer la fiche</span>
      <span className="sr-only sm:hidden">Imprimer la fiche</span>
    </button>
  )

  let principal: BarreActionProps['principal']
  let autre: ReactNode = null
  let aide = 'Gardez la référence : elle permet de retrouver votre demande.'

  if (statut === 'CONFIRMATION') {
    principal = {
      libelle: etroit ? 'Donner mon retour' : 'Donner mon retour après la sortie',
      vers: `/retour/${encodeURIComponent(reference)}`,
      icone: <MessageSquareText className="size-4" aria-hidden="true" />,
    }
    aide = 'Après la sortie, votre retour aide les prochaines classes.'
  } else if (statut === 'CONTRE_PROPOSITION') {
    autre = (
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        onClick={() => {
          definirDemande(dossier.demande)
          choisirSite(site)
          navigate(`/trajets/${encodeURIComponent(site.site_id)}`)
        }}
      >
        <Shuffle className="size-4" aria-hidden="true" />
        {etroit ? 'Autre trajet' : 'Choisir une autre proposition'}
      </button>
    )
    aide = 'SNCF propose autre chose : choisissez un autre trajet.'
  } else if (statut === 'ANNULE') {
    autre = (
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        onClick={() => {
          reinitialiser()
          navigate('/')
        }}
      >
        <RotateCcw className="size-4" aria-hidden="true" />
        {etroit ? 'Nouvelle sortie' : 'Organiser une nouvelle sortie'}
      </button>
    )
    aide = "Aucune place n'est retenue. Préparez une autre sortie quand vous voulez."
  }

  return (
    <BarreAction
      principal={principal}
      secondaire={
        <>
          {imprimer}
          {autre}
        </>
      }
      aide={aide}
    />
  )
}

const SUITES: Record<Statut, { titre: string; texte: (dossier: DossierApi) => ReactNode }> = {
  OPTION: {
    titre: 'En attente de la réponse SNCF',
    texte: (dossier) => (
      <>
        Un chargé de clientèle SNCF étudie la demande. Réponse envoyée à{' '}
        <strong className="wrap-anywhere">{dossier.email}</strong>.
      </>
    ),
  },
  PRE_RESERVATION: {
    titre: 'En attente de la réponse SNCF',
    texte: (dossier) => (
      <>
        Un chargé de clientèle SNCF étudie la demande. Réponse envoyée à{' '}
        <strong className="wrap-anywhere">{dossier.email}</strong>.
      </>
    ),
  },
  CONFIRMATION: {
    titre: 'Votre sortie est confirmée',
    texte: () => "Après la sortie, donnez votre retour en deux minutes : il fait évoluer l'indice du site.",
  },
  CONTRE_PROPOSITION: {
    titre: 'SNCF vous propose autre chose',
    texte: (dossier) => `Choisissez une autre proposition pour ${dossier.site.nom}, puis renvoyez une demande.`,
  },
  ANNULE: {
    titre: 'Cette demande est annulée',
    texte: () => "Aucune place n'est retenue pour ce dossier. Vous pouvez préparer une nouvelle sortie.",
  },
}

function ProchaineEtape({ dossier }: { dossier: DossierApi }) {
  const { titre, texte } = SUITES[dossier.statut]
  return (
    <div className="flex items-start gap-3 rounded-field bg-base-200 p-3">
      <PuceStatut statut={dossier.statut} />
      <div className="min-w-0">
        <h3 className="text-base font-bold">{titre}</h3>
        <p className="text-sm">{texte(dossier)}</p>
      </div>
    </div>
  )
}

function Historique({ historique }: { historique: EtapeDossier[] }) {
  return (
    <section
      aria-labelledby="titre-historique"
      className="card border border-base-300 bg-base-100 motion-safe:animate-entree motion-safe:[animation-delay:120ms]"
    >
      <div className="card-body gap-2 p-4">
        <h2 id="titre-historique" className="card-title text-base font-bold">
          <Route className="size-4 shrink-0" aria-hidden="true" />
          Historique de la demande
        </h2>
        {historique.length === 0 ? (
          <p className="text-sm">Aucune étape n'est encore enregistrée pour ce dossier.</p>
        ) : (
          <div
            tabIndex={0}
            aria-label="Étapes de l'historique"
            className="max-h-72 overflow-y-auto rounded-field focus-visible:outline-2 focus-visible:outline-secondary"
          >
            <ul className="timeline timeline-vertical timeline-compact text-sm">
              {historique.map((etape, index) => {
                const premiere = index === 0
                const derniere = index === historique.length - 1
                return (
                  <li key={`${etape.statut}-${etape.date}-${index}`}>
                    {!premiere && <hr className="bg-secondary" />}
                    <div className="timeline-middle">
                      <PuceStatut statut={etape.statut} />
                    </div>
                    <div className={derniere ? 'timeline-end pb-0.5' : 'timeline-end pb-3'}>
                      <p className="flex flex-wrap items-baseline gap-x-2">
                        <span className="font-bold">{LIBELLES_ETAPE[etape.statut]}</span>
                        <time dateTime={etape.date} className="text-xs font-semibold tabular-nums text-base-content/70">
                          {formaterHorodatage(etape.date)}
                        </time>
                      </p>
                      <p className="text-xs">{etape.message}</p>
                    </div>
                    {!derniere && <hr className="bg-secondary" />}
                  </li>
                )
              })}
            </ul>
          </div>
        )}
      </div>
    </section>
  )
}

