import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Circle, CircleCheck, CircleX, Compass, Mail, RotateCcw, Send } from 'lucide-react'
import { ErreurApi, api } from '../api/client'
import type { Demande } from '../api/types'
import BilletRecap from '../components/dossier/BilletRecap'
import FriseStatuts from '../components/dossier/FriseStatuts'
import IntroEtape from '../components/dossier/IntroEtape'
import { erreurEmail } from '../components/dossier/format'
import { useEcranEtroit } from '../components/dossier/useEcranEtroit'
import BarreAction from '../layout/BarreAction'
import { useVoyage } from '../state/VoyageContext'
import type { PropositionSite } from '../state/VoyageContext'

const ID_FORMULAIRE = 'formulaire-pre-reservation'

export default function PreReservation() {
  const { demande, propositionChoisie } = useVoyage()
  if (!propositionChoisie || !demande) return <AucunTrajet />
  return <FormulairePreReservation demande={demande} choix={propositionChoisie} />
}

function AucunTrajet() {
  return (
    <>
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 lg:gap-5 lg:px-6 lg:py-6">
        <IntroEtape
          humeur="inquiete"
          titreTchouette="Tchouette s'inquiète"
          titre="Aucun trajet n'est encore choisi."
          phrase="Choisissez d'abord une destination, puis le trajet liO qui convient à votre classe."
        />
      </div>
      <BarreAction
        retour={{ libelle: 'Mon projet', vers: '/' }}
        principal={{
          libelle: 'Voir les destinations',
          vers: '/destinations',
          icone: <Compass className="size-4" aria-hidden="true" />,
        }}
        aide="Une destination, un trajet, et je prépare la demande."
      />
    </>
  )
}

/** Condition à remplir avant l'envoi : pastille couleur + icône + texte. */
function Condition({ remplie, libelle }: { remplie: boolean; libelle: string }) {
  return (
    <li>
      {remplie ? (
        <span key="ok" className="badge badge-success badge-sm gap-1 font-bold motion-safe:animate-pop">
          <CircleCheck className="size-3.5" aria-hidden="true" />
          {libelle}
          <span className="sr-only"> : c'est fait</span>
        </span>
      ) : (
        <span key="a-faire" className="badge badge-ghost badge-sm gap-1 font-semibold">
          <Circle className="size-3.5" aria-hidden="true" />
          {libelle}
          <span className="sr-only"> : à faire</span>
        </span>
      )}
    </li>
  )
}

function FormulairePreReservation({ demande, choix }: { demande: Demande; choix: PropositionSite }) {
  const { definirDossier } = useVoyage()
  const navigate = useNavigate()
  const etroit = useEcranEtroit()
  const [email, setEmail] = useState('')
  const [emailTouche, setEmailTouche] = useState(false)
  const [compris, setCompris] = useState(false)
  const [envoi, setEnvoi] = useState(false)
  const [erreurEnvoi, setErreurEnvoi] = useState<string | null>(null)
  const champEmail = useRef<HTMLInputElement>(null)
  const caseCompris = useRef<HTMLInputElement>(null)

  const { site, proposition } = choix
  const messageEmail = erreurEmail(email)
  const emailValide = messageEmail === null
  const pret = emailValide && compris
  const afficherErreurEmail = emailTouche && !emailValide

  let raison: string | undefined
  if (!emailValide && !compris) raison = 'Indiquez votre e-mail et cochez la case.'
  else if (!emailValide) raison = 'Indiquez une adresse e-mail valide.'
  else if (!compris) raison = 'Cochez la case pour confirmer.'

  async function envoyer() {
    if (!emailValide) {
      setEmailTouche(true)
      champEmail.current?.focus()
      return
    }
    if (!compris) {
      caseCompris.current?.focus()
      return
    }
    if (envoi) return
    setEnvoi(true)
    setErreurEnvoi(null)
    try {
      const dossier = await api.preReserver(proposition.proposition_id, email.trim(), demande)
      definirDossier(dossier)
      navigate(`/dossier/${encodeURIComponent(dossier.reference)}`)
    } catch (cause) {
      setErreurEnvoi(
        cause instanceof ErreurApi ? cause.message : "L'envoi de la demande a échoué. Réessayez dans un instant.",
      )
      setEnvoi(false)
    }
  }

  function soumettre(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault()
    void envoyer()
  }

  return (
    <>
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 lg:gap-5 lg:px-6 lg:py-6">
        <IntroEtape
          humeur={envoi ? 'reflexion' : 'parle'}
          titreTchouette={envoi ? 'Tchouette transmet votre demande' : 'Tchouette vous explique la suite'}
          titre="Pré-réservez votre sortie"
          phrase="Relisez le billet et laissez votre e-mail : rien n'est réservé avant la réponse SNCF."
        />

        <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-start lg:gap-5">
          <div className="min-w-0 motion-safe:animate-entree">
            <BilletRecap site={site} proposition={proposition} demande={demande} />
          </div>

          <section
            aria-labelledby="titre-suite"
            className="card min-w-0 border border-base-300 bg-base-100 motion-safe:animate-entree motion-safe:[animation-delay:80ms]"
          >
            <div className="card-body gap-3 p-4">
              <h2 id="titre-suite" className="card-title text-lg font-bold lg:text-xl">
                Ce qui va se passer
              </h2>
              <FriseStatuts etapeActuelle={0} />
              <p className="text-sm">
                En envoyant, une option est posée sur les places. Un chargé de clientèle SNCF confirme ou propose
                autre chose.
              </p>

              <form
                id={ID_FORMULAIRE}
                noValidate
                onSubmit={soumettre}
                className="flex flex-col gap-3 border-t-2 border-dashed border-base-300 pt-3"
              >
                <fieldset className="fieldset gap-1 p-0">
                  <legend className="fieldset-legend pt-0 text-sm font-bold">Vos coordonnées</legend>
                  <label htmlFor="email-contact" className="label text-xs font-semibold text-base-content">
                    E-mail de contact
                  </label>
                  <label className={afficherErreurEmail ? 'input input-sm input-error w-full' : 'input input-sm w-full'}>
                    <Mail className="size-4 shrink-0" aria-hidden="true" />
                    <input
                      ref={champEmail}
                      id="email-contact"
                      type="email"
                      inputMode="email"
                      autoComplete="email"
                      placeholder="prenom.nom@ac-toulouse.fr"
                      className="grow"
                      value={email}
                      onChange={(evenement) => setEmail(evenement.target.value)}
                      onBlur={() => setEmailTouche(true)}
                      disabled={envoi}
                      required
                      aria-invalid={afficherErreurEmail}
                      aria-describedby={afficherErreurEmail ? 'email-aide email-erreur' : 'email-aide'}
                    />
                  </label>
                  <p id="email-aide" className="label whitespace-normal text-xs text-base-content/70">
                    La réponse du chargé de clientèle SNCF arrivera à cette adresse.
                  </p>
                  {afficherErreurEmail && (
                    <p id="email-erreur" className="flex items-start gap-1.5 text-xs font-semibold text-error">
                      <CircleX className="size-3.5 shrink-0" aria-hidden="true" />
                      {messageEmail}
                    </p>
                  )}
                </fieldset>

                <label className="label cursor-pointer items-start gap-2.5 whitespace-normal text-sm text-base-content">
                  <input
                    ref={caseCompris}
                    type="checkbox"
                    className="checkbox checkbox-sm checkbox-secondary mt-0.5 rounded-field"
                    checked={compris}
                    onChange={(evenement) => setCompris(evenement.target.checked)}
                    disabled={envoi}
                    required
                  />
                  <span>J'ai compris : c'est une demande de pré-réservation, pas une réservation confirmée.</span>
                </label>

                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <p id="titre-conditions" className="grow-0 text-xs font-semibold text-base-content/70">
                    Avant d'envoyer :
                  </p>
                  <ul aria-labelledby="titre-conditions" className="flex flex-wrap gap-1.5">
                    <Condition remplie={emailValide} libelle="E-mail valide" />
                    <Condition remplie={compris} libelle="Case cochée" />
                  </ul>
                </div>

                {erreurEnvoi && (
                  <div role="alert" className="alert alert-error alert-vertical text-sm sm:alert-horizontal">
                    <CircleX className="size-5 shrink-0" aria-hidden="true" />
                    <div>
                      <h3 className="font-bold">La demande n'est pas partie.</h3>
                      <p className="text-xs">{erreurEnvoi}</p>
                    </div>
                    <button type="button" className="btn btn-sm" onClick={() => void envoyer()}>
                      <RotateCcw className="size-4" aria-hidden="true" />
                      Réessayer
                    </button>
                  </div>
                )}

                <p role="status" aria-live="polite" className="sr-only">
                  {envoi ? 'Tchouette transmet votre demande au chargé de clientèle SNCF…' : ''}
                </p>
              </form>
            </div>
          </section>
        </div>
      </div>

      <BarreAction
        retour={{ libelle: 'Changer de trajet', vers: `/trajets/${encodeURIComponent(site.site_id)}` }}
        principal={{
          libelle: envoi
            ? 'Envoi de la demande…'
            : etroit
              ? 'Envoyer la demande'
              : 'Envoyer la demande de pré-réservation',
          form: ID_FORMULAIRE,
          chargement: envoi,
          desactive: !pret,
          raison,
          icone: <Send className="size-4" aria-hidden="true" />,
        }}
        aide="Rien n'est réservé tant que SNCF n'a pas confirmé."
      />
    </>
  )
}
