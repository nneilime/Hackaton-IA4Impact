import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowRight,
  CalendarDays,
  CircleX,
  FolderOpen,
  Heart,
  Info,
  MapPin,
  Minus,
  RotateCcw,
  Send,
  Star,
  Ticket,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { ErreurApi, api } from '../api/client'
import type { Destination, Dossier as DossierApi, ReponseRetour } from '../api/types'
import { ChargementDossier, DossierIntrouvable, ErreurDossier } from '../components/dossier/EtatsDossier'
import IntroEtape from '../components/dossier/IntroEtape'
import { formaterDateLongue, formaterNombre, pluriel } from '../components/dossier/format'
import { useDossier } from '../components/dossier/useDossier'
import { useEcranEtroit } from '../components/dossier/useEcranEtroit'
import BarreAction from '../layout/BarreAction'
import { useVoyage } from '../state/VoyageContext'

type Critere = 'satisfaction' | 'adaptation_train' | 'acces_gare_site' | 'confiance'

const CRITERES: { cle: Critere; legende: string; aide: string }[] = [
  {
    cle: 'satisfaction',
    legende: 'Satisfaction globale',
    aide: 'La sortie a-t-elle servi votre projet pédagogique ?',
  },
  {
    cle: 'adaptation_train',
    legende: 'Adaptation du train au groupe',
    aide: 'Places, montée, descente : le train convenait-il à la classe ?',
  },
  {
    cle: 'acces_gare_site',
    legende: 'Accès de la gare au site',
    aide: 'Le trajet gare → site était-il simple avec les élèves ?',
  },
  {
    cle: 'confiance',
    legende: 'Sentiment de confiance',
    aide: 'Le voyage vous a-t-il paru serein, du départ au retour ?',
  },
]

const LIBELLES_NOTE = ['', 'Très insuffisant', 'Insuffisant', 'Correct', 'Bien', 'Excellent'] as const
const NOTES = [1, 2, 3, 4, 5] as const
const LONGUEUR_COMMENTAIRE = 1000
const ID_FORMULAIRE = 'formulaire-retour'
const CONTENEUR = 'mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 lg:gap-5 lg:px-6 lg:py-6'

type Notes = Record<Critere, number | null>

interface Merci {
  resultat: ReponseRetour
  site: Destination
  reference: string
}

export default function Retour() {
  const { reference = '' } = useParams()
  const { dossier, chargement, erreur, introuvable, recharger } = useDossier(reference)
  const { dossier: dossierEnCours } = useVoyage()
  const [merci, setMerci] = useState<Merci | null>(null)

  if (merci) return <EcranMerci merci={merci} />
  if (dossier) return <QuestionnaireRetour dossier={dossier} onEnvoye={setMerci} />

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

function NoteCritere({
  critere,
  valeur,
  onChange,
  desactive,
}: {
  critere: (typeof CRITERES)[number]
  valeur: number | null
  onChange: (note: number) => void
  desactive: boolean
}) {
  const idTitre = `titre-${critere.cle}`
  const idAide = `aide-${critere.cle}`
  return (
    <div
      role="radiogroup"
      aria-labelledby={idTitre}
      aria-describedby={idAide}
      className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5 rounded-field border border-base-300 p-3"
    >
      <div className="min-w-0 flex-1 basis-48">
        <p id={idTitre} className="text-sm font-bold">
          {critere.legende}
        </p>
        <p id={idAide} className="text-xs text-base-content/70">
          {critere.aide}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <div className="rating rating-md">
          {NOTES.map((note) => (
            <input
              key={note}
              type="radio"
              name={`note-${critere.cle}`}
              value={note}
              className="mask mask-star-2 bg-secondary"
              aria-label={`${note} sur 5 : ${LIBELLES_NOTE[note]}`}
              checked={valeur === note}
              onChange={() => onChange(note)}
              disabled={desactive}
            />
          ))}
        </div>
        <span
          key={valeur ?? 'vide'}
          aria-hidden="true"
          className={
            valeur
              ? 'w-32 text-xs font-bold tabular-nums motion-safe:animate-pop'
              : 'w-32 text-xs font-semibold text-base-content/70'
          }
        >
          {valeur ? `${valeur}/5 · ${LIBELLES_NOTE[valeur]}` : 'À noter'}
        </span>
      </div>
    </div>
  )
}

function QuestionnaireRetour({ dossier, onEnvoye }: { dossier: DossierApi; onEnvoye: (merci: Merci) => void }) {
  const [notes, setNotes] = useState<Notes>({
    satisfaction: null,
    adaptation_train: null,
    acces_gare_site: null,
    confiance: null,
  })
  const [recommande, setRecommande] = useState(false)
  const [commentaire, setCommentaire] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [erreurEnvoi, setErreurEnvoi] = useState<string | null>(null)
  const formulaire = useRef<HTMLFormElement>(null)

  const { site, reference } = dossier
  const date = dossier.proposition.date || dossier.demande.date
  const manquants = CRITERES.filter((critere) => notes[critere.cle] === null)
  const notees = CRITERES.length - manquants.length

  async function envoyer() {
    const { satisfaction, adaptation_train, acces_gare_site, confiance } = notes
    if (satisfaction === null || adaptation_train === null || acces_gare_site === null || confiance === null) {
      const premier = CRITERES.find((critere) => notes[critere.cle] === null)
      formulaire.current?.querySelector<HTMLInputElement>(`input[name="note-${premier?.cle}"]`)?.focus()
      return
    }
    if (envoi) return
    setEnvoi(true)
    setErreurEnvoi(null)
    try {
      const resultat = await api.envoyerRetour({
        reference,
        satisfaction,
        adaptation_train,
        acces_gare_site,
        confiance,
        recommande,
        commentaire: commentaire.trim(),
      })
      onEnvoye({ resultat, site, reference })
    } catch (cause) {
      setErreurEnvoi(
        cause instanceof ErreurApi ? cause.message : "L'envoi de votre retour a échoué. Réessayez dans un instant.",
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
      <div className={CONTENEUR}>
        <IntroEtape
          humeur={envoi ? 'reflexion' : 'parle'}
          titreTchouette={envoi ? 'Tchouette réfléchit' : 'Tchouette vous écoute'}
          titre="Comment s'est passée la sortie ?"
          phrase="Quatre notes, et c'est fini : vos réponses font évoluer l'indice du site."
          meta={
            <ul className="mt-0.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs font-semibold text-base-content/80">
              <li className="flex items-center gap-1.5">
                <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
                {site.nom}, {site.commune}
              </li>
              <li className="flex items-center gap-1.5">
                <CalendarDays className="size-3.5 shrink-0" aria-hidden="true" />
                {date ? <time dateTime={date}>{formaterDateLongue(date)}</time> : 'Date à préciser'}
              </li>
              <li className="flex items-center gap-1.5">
                <Ticket className="size-3.5 shrink-0" aria-hidden="true" />
                Dossier <span className="tabular-nums">{reference}</span>
              </li>
            </ul>
          }
        />

        {dossier.statut !== 'CONFIRMATION' && (
          <div role="note" className="alert alert-info alert-soft text-sm">
            <Info className="size-4 shrink-0" aria-hidden="true" />
            <span>Ce dossier n'est pas encore confirmé par SNCF : le retour est prévu après la sortie.</span>
          </div>
        )}

        <form ref={formulaire} id={ID_FORMULAIRE} noValidate onSubmit={soumettre} className="flex flex-col gap-4 lg:gap-5">
          <section
            aria-labelledby="titre-notes"
            className="card border-2 border-secondary bg-base-100 shadow-[4px_4px_0_0] shadow-secondary motion-safe:animate-entree"
          >
            <div className="card-body gap-3 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 id="titre-notes" className="card-title text-lg font-bold lg:text-xl">
                  <Star className="size-5 shrink-0" aria-hidden="true" />
                  Vos notes
                </h2>
                <p className="flex grow-0 items-center gap-2 text-xs font-semibold text-base-content/80">
                  De 1 (très insuffisant) à 5 (excellent)
                  <span
                    key={notees}
                    className={
                      manquants.length === 0
                        ? 'badge badge-success badge-sm font-bold tabular-nums motion-safe:animate-pop'
                        : 'badge badge-ghost badge-sm font-bold tabular-nums'
                    }
                  >
                    {notees} / {CRITERES.length} notées
                  </span>
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {CRITERES.map((critere) => (
                  <NoteCritere
                    key={critere.cle}
                    critere={critere}
                    valeur={notes[critere.cle]}
                    onChange={(note) => setNotes((avant) => ({ ...avant, [critere.cle]: note }))}
                    desactive={envoi}
                  />
                ))}
              </div>
            </div>
          </section>

          <section
            aria-label="Pour finir"
            className="card border border-base-300 bg-base-100 motion-safe:animate-entree motion-safe:[animation-delay:80ms]"
          >
            <div className="card-body grid gap-4 p-4 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
              <fieldset className="fieldset content-start gap-1 p-0">
                <legend className="fieldset-legend pt-0 text-sm font-bold">Recommanderiez-vous cette sortie ?</legend>
                <label className="label w-fit cursor-pointer gap-2.5 text-sm text-base-content">
                  <input
                    type="checkbox"
                    className="toggle toggle-sm toggle-secondary"
                    checked={recommande}
                    onChange={(evenement) => setRecommande(evenement.target.checked)}
                    disabled={envoi}
                    aria-describedby="recommande-etat"
                  />
                  <Heart
                    key={recommande ? 'aime' : 'neutre'}
                    className={
                      recommande ? 'size-5 shrink-0 fill-primary text-primary motion-safe:animate-pop' : 'size-5 shrink-0'
                    }
                    aria-hidden="true"
                  />
                  <span className="font-bold">Coup de cœur</span>
                </label>
                <p id="recommande-etat" className="text-xs text-base-content/70">
                  {recommande
                    ? 'Vous recommandez cette sortie aux autres enseignants.'
                    : 'Activez la bascule si vous la recommandez aux autres enseignants.'}
                </p>
              </fieldset>

              <fieldset className="fieldset gap-1 p-0">
                <legend className="fieldset-legend pt-0 text-sm font-bold">Commentaire libre (facultatif)</legend>
                <label htmlFor="commentaire" className="label whitespace-normal text-xs text-base-content/70">
                  Ce qui a bien marché, ce qui serait à améliorer.
                </label>
                <textarea
                  id="commentaire"
                  className="textarea textarea-sm h-20 w-full"
                  maxLength={LONGUEUR_COMMENTAIRE}
                  value={commentaire}
                  onChange={(evenement) => setCommentaire(evenement.target.value)}
                  disabled={envoi}
                  aria-describedby="commentaire-aide"
                />
                <p id="commentaire-aide" className="flex flex-wrap justify-between gap-x-3 text-xs text-base-content/70">
                  <span>Merci de ne pas citer le nom des élèves.</span>
                  <span className="tabular-nums">
                    {commentaire.length} / {LONGUEUR_COMMENTAIRE}
                  </span>
                </p>
              </fieldset>
            </div>
          </section>

          {erreurEnvoi && (
            <div role="alert" className="alert alert-error alert-vertical text-sm sm:alert-horizontal">
              <CircleX className="size-5 shrink-0" aria-hidden="true" />
              <div>
                <h3 className="font-bold">Votre retour n'est pas parti.</h3>
                <p className="text-xs">{erreurEnvoi}</p>
              </div>
              <button type="button" className="btn btn-sm" onClick={() => void envoyer()}>
                <RotateCcw className="size-4" aria-hidden="true" />
                Réessayer
              </button>
            </div>
          )}
          <p role="status" aria-live="polite" className="sr-only">
            {envoi ? 'Envoi de votre retour en cours.' : ''}
          </p>
        </form>
      </div>

      <BarreAction
        retour={{ libelle: 'Mon dossier', vers: `/dossier/${encodeURIComponent(reference)}` }}
        principal={{
          libelle: envoi ? 'Envoi…' : 'Envoyer mon retour',
          form: ID_FORMULAIRE,
          chargement: envoi,
          desactive: manquants.length > 0,
          raison:
            manquants.length > 0
              ? `Il manque ${pluriel(manquants.length, 'note', 'notes')} sur ${CRITERES.length}.`
              : undefined,
          icone: <Send className="size-4" aria-hidden="true" />,
        }}
        aide={
          manquants.length > 0
            ? 'Quatre notes suffisent, le commentaire est facultatif.'
            : "Parfait ! Il ne reste qu'à envoyer."
        }
      />
    </>
  )
}

function EcranMerci({ merci }: { merci: Merci }) {
  const titre = useRef<HTMLHeadingElement>(null)
  const navigate = useNavigate()
  const etroit = useEcranEtroit()
  const { reinitialiser } = useVoyage()
  const { resultat, site, reference } = merci
  const ecart = Math.round((resultat.indice_apres - resultat.indice_avant) * 10) / 10

  useEffect(() => {
    titre.current?.focus()
  }, [])

  let IconeEcart = Minus
  let phraseEcart = 'Indice inchangé : votre retour confirme le niveau actuel.'
  if (ecart > 0) {
    IconeEcart = TrendingUp
    phraseEcart = `+${formaterNombre(ecart)} ${ecart > 1 ? 'points' : 'point'} grâce à votre retour.`
  } else if (ecart < 0) {
    IconeEcart = TrendingDown
    phraseEcart = `−${formaterNombre(-ecart)} ${ecart < -1 ? 'points' : 'point'} : votre retour signale des points à améliorer.`
  }

  return (
    <>
      <div className={CONTENEUR}>
        <IntroEtape
          humeur="joie"
          titreTchouette="Tchouette se réjouit"
          rebond
          etoiles
          refTitre={titre}
          titre="Merci pour votre retour !"
          phrase="Votre avis aide les prochaines classes à choisir leur sortie en train liO."
        />

        <section
          aria-labelledby="titre-indice"
          className="card border-2 border-secondary bg-base-100 shadow-[4px_4px_0_0] shadow-secondary motion-safe:animate-entree"
        >
          <div className="card-body flex-col gap-4 p-4 md:flex-row md:items-center md:gap-6 lg:p-5">
            <div className="min-w-0 md:w-56 md:shrink-0">
              <h2 id="titre-indice" className="text-xs font-semibold uppercase tracking-wide text-base-content/70">
                Indice de confiance
              </h2>
              <p className="text-base font-bold leading-snug">{site.nom}</p>
              <p className="sr-only">
                L'indice passe de {formaterNombre(resultat.indice_avant)} à {formaterNombre(resultat.indice_apres)} sur
                100.
              </p>
            </div>

            <div aria-hidden="true" className="flex items-center gap-3">
              <div className="flex flex-col items-center gap-1">
                <span className="grid size-14 place-items-center rounded-full border-2 border-dashed border-secondary text-xl font-extrabold tabular-nums">
                  {formaterNombre(resultat.indice_avant)}
                </span>
                <span className="text-xs font-semibold">Avant</span>
              </div>
              <ArrowRight className="size-5 shrink-0" />
              <div className="flex flex-col items-center gap-1">
                <span className="grid size-16 place-items-center rounded-full border-2 border-secondary bg-accent text-2xl font-extrabold text-accent-content tabular-nums motion-safe:animate-pop motion-safe:[animation-delay:240ms]">
                  {formaterNombre(resultat.indice_apres)}
                </span>
                <span className="text-xs font-semibold">Après · sur 100</span>
              </div>
            </div>

            <div className="min-w-0 flex-1 border-t-2 border-dashed border-base-300 pt-3 md:border-l-2 md:border-t-0 md:pl-6 md:pt-0">
              <p className="flex items-center gap-1.5 text-sm font-bold tabular-nums">
                <IconeEcart className="size-4 shrink-0" aria-hidden="true" />
                {phraseEcart}
              </p>
              <p className="text-sm">{resultat.message}</p>
            </div>
          </div>
        </section>
      </div>

      <BarreAction
        secondaire={
          <Link to={`/dossier/${encodeURIComponent(reference)}`} className="btn btn-ghost btn-sm">
            <FolderOpen className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Revoir le dossier</span>
            <span className="sr-only sm:hidden">Revoir le dossier</span>
          </Link>
        }
        principal={{
          libelle: etroit ? 'Nouvelle sortie' : 'Organiser une nouvelle sortie',
          onClick: () => {
            reinitialiser()
            navigate('/')
          },
          icone: <RotateCcw className="size-4" aria-hidden="true" />,
        }}
        aide="Une autre sortie en tête ? On repart quand vous voulez."
      />
    </>
  )
}
