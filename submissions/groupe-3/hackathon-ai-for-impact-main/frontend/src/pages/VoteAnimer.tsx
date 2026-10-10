import { useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Hourglass, Lock, TrainTrack, Users, WifiOff } from 'lucide-react'
import { api } from '../api/client'
import type { OptionSondage, Sondage } from '../api/types'
import BilletGagnant from '../features/vote/BilletGagnant'
import CarteRejoindre from '../features/vote/CarteRejoindre'
import CourseTrains from '../features/vote/CourseTrains'
import { ErreurVote, VoteIntrouvable } from '../features/vote/EtatsVote'
import { useCommentaire } from '../features/vote/useCommentaire'
import { useSondage } from '../features/vote/useSondage'
import { useUrlVote } from '../features/vote/useUrlVote'
import {
  destinationDepuisOption,
  INTERVALLE_ANIMATEUR_MS,
  libelleVotes,
  optionGagnante,
} from '../features/vote/vote'
import Tchouette from '../mascot/Tchouette'
import { useVoyage } from '../state/VoyageContext'

/**
 * Écran projeté par l'enseignant pendant le vote en classe : QR code à gauche, course des trains
 * à droite, Tchouette qui commente en direct. Hors du shell, pensé pour un vidéoprojecteur.
 */
export default function VoteAnimer() {
  const { code: codeBrut = '' } = useParams()
  const code = codeBrut.trim().toUpperCase()
  const { sondage, etat, erreur, horsLigne, reessayer, remplacer } = useSondage(code, INTERVALLE_ANIMATEUR_MS)

  return (
    <div className="flex min-h-screen flex-col bg-base-200 text-base-content">
      <BarreProjection sondage={sondage} horsLigne={horsLigne} />
      <main id="contenu" className="flex-1">
        {etat === 'chargement' && <ChargementProjection />}
        {etat === 'introuvable' && (
          <div className="px-4 py-10">
            <VoteIntrouvable
              titre="Ce vote n’existe pas"
              action={
                <Link to="/destinations" className="btn btn-primary btn-sm">
                  <ArrowLeft className="size-4" aria-hidden="true" />
                  Retour aux destinations
                </Link>
              }
            >
              <p>
                Le code <strong className="tabular-nums tracking-widest">{code}</strong> ne correspond à aucun vote.
              </p>
              <p>Relancez le vote depuis la liste des destinations proposées par Tchouette.</p>
            </VoteIntrouvable>
          </div>
        )}
        {etat === 'erreur' && (
          <div className="grid justify-items-center px-4 py-10">
            <ErreurVote
              titre="Impossible de charger le vote"
              message={erreur ?? 'Erreur inattendue.'}
              onReessayer={reessayer}
            />
          </div>
        )}
        {etat === 'pret' && sondage && <Projection code={code} sondage={sondage} remplacer={remplacer} />}
      </main>
    </div>
  )
}

function BarreProjection({ sondage, horsLigne }: { sondage: Sondage | null; horsLigne: boolean }) {
  return (
    <header className="bg-secondary text-secondary-content">
      <nav className="navbar min-h-12 gap-3 px-4 py-1 lg:px-6" aria-label="Vote en classe">
        <div className="navbar-start">
          <Link to="/destinations" className="btn btn-ghost btn-sm text-secondary-content">
            <ArrowLeft className="size-4" aria-hidden="true" />
            Quitter le vote
          </Link>
        </div>
        <div className="navbar-center hidden items-center gap-2 md:flex">
          <Tchouette humeur="repos" taille={32} titre="" />
          <span className="font-extrabold">Vote en classe</span>
          <span className="text-sm font-semibold opacity-80">· sortie scolaire en train liO</span>
        </div>
        <div className="navbar-end">
          <EtatDirect sondage={sondage} horsLigne={horsLigne} />
        </div>
      </nav>
    </header>
  )
}

/** Fraîcheur des chiffres affichés : en direct, connexion perdue ou vote clos. */
function EtatDirect({ sondage, horsLigne }: { sondage: Sondage | null; horsLigne: boolean }) {
  if (!sondage) return null
  if (sondage.statut === 'ferme') {
    return (
      <p className="flex items-center gap-2 text-sm font-semibold">
        <Lock className="size-4" aria-hidden="true" />
        Vote clos
      </p>
    )
  }
  if (horsLigne) {
    return (
      <p role="status" className="flex items-center gap-2 text-sm font-semibold">
        <WifiOff className="size-4 text-warning" aria-hidden="true" />
        Connexion perdue, nouvel essai…
      </p>
    )
  }
  return (
    <p className="flex items-center gap-2 text-sm font-semibold">
      <span className="inline-grid *:[grid-area:1/1]" aria-hidden="true">
        <span className="status status-success motion-safe:animate-ping" />
        <span className="status status-success" />
      </span>
      En direct · actualisé toutes les 2 s
    </p>
  )
}

function ChargementProjection() {
  return (
    <div className="mx-auto grid w-full max-w-[110rem] gap-5 px-4 py-5 lg:grid-cols-12 lg:gap-6 lg:px-6">
      <div className="skeleton h-[32rem] lg:col-span-4" />
      <div className="grid content-start gap-4 lg:col-span-8">
        <div className="skeleton h-12 w-3/4" />
        <div className="grid gap-3 rounded-box border-2 border-secondary bg-base-100 p-5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton h-24 w-full" />
          ))}
        </div>
        <div role="status" className="flex items-center gap-4">
          <Tchouette humeur="reflexion" taille={120} titre="" />
          <p className="text-xl font-bold">Je prépare la course…</p>
          <span className="loading loading-dots loading-md" aria-hidden="true" />
        </div>
      </div>
    </div>
  )
}

interface ProjectionProps {
  code: string
  sondage: Sondage
  remplacer: (s: Sondage) => void
}

function Projection({ code, sondage, remplacer }: ProjectionProps) {
  const navigate = useNavigate()
  const { destinations, choisirSite } = useVoyage()
  const adresse = useUrlVote(code)
  const commentaire = useCommentaire(sondage)
  const [fermeture, setFermeture] = useState(false)
  const [erreurFermeture, setErreurFermeture] = useState<string | null>(null)
  const confirmation = useRef<HTMLDialogElement>(null)

  const ferme = sondage.statut === 'ferme'
  const gagnante = optionGagnante(sondage)
  const total = sondage.total_votes
  const enAttente = !ferme && total === 0

  async function clore() {
    confirmation.current?.close()
    setFermeture(true)
    setErreurFermeture(null)
    try {
      remplacer(await api.fermerSondage(code))
    } catch (e) {
      setErreurFermeture(e instanceof Error ? e.message : 'Erreur inattendue.')
    } finally {
      setFermeture(false)
    }
  }

  function voirTrains(option: OptionSondage) {
    choisirSite(destinationDepuisOption(option, destinations))
    navigate(`/trajets/${encodeURIComponent(option.site_id)}`)
  }

  return (
    <div className="mx-auto grid w-full max-w-[110rem] gap-5 px-4 py-5 lg:grid-cols-12 lg:gap-6 lg:px-6">
      <section aria-labelledby="titre-rejoindre" className="lg:col-span-4">
        <CarteRejoindre code={code} adresse={adresse} />
      </section>

      <section aria-labelledby="titre-vote" className="grid min-w-0 content-start gap-4 lg:col-span-8">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <h1 id="titre-vote" className="min-w-0 text-3xl font-extrabold tracking-tight lg:text-4xl xl:text-5xl">
            {sondage.titre}
          </h1>
          <div className="stats border border-base-300 bg-base-100">
            <div className="stat px-5 py-2">
              <div className="stat-figure text-secondary">
                <Users className="size-8" aria-hidden="true" />
              </div>
              <div className="stat-title text-sm font-semibold">Votes reçus</div>
              <div className="stat-value tabular-nums" aria-live="polite">
                {total}
              </div>
            </div>
          </div>
        </header>

        {ferme && gagnante && (
          <BilletGagnant option={gagnante} total={total} onVoirTrains={() => voirTrains(gagnante)} />
        )}

        <div className="grid gap-3 rounded-box border-2 border-secondary bg-base-100 p-4 lg:p-5">
          <h2 className="flex flex-wrap items-center gap-x-3 gap-y-1 text-lg font-bold lg:text-xl">
            <TrainTrack className="size-5 shrink-0" aria-hidden="true" />
            La course des trains
            <span className="text-sm font-semibold opacity-75">Chaque train avance selon sa part des votes.</span>
          </h2>
          <CourseTrains sondage={sondage} />
          {enAttente && (
            <p className="flex items-center gap-2 text-lg font-semibold">
              <Hourglass className="size-5 shrink-0" aria-hidden="true" />
              En attente du premier vote…
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="chat chat-start min-w-0 flex-1 basis-[28rem]">
            <div className={enAttente ? 'chat-image motion-safe:animate-flotte' : 'chat-image'}>
              <Tchouette humeur={commentaire.humeur} taille={190} titre="" />
            </div>
            <div className="chat-header pb-1 text-base font-bold">Tchouette</div>
            <div
              aria-live="polite"
              className="chat-bubble bg-base-100 text-2xl font-bold leading-snug text-base-content lg:text-3xl"
            >
              {commentaire.texte}
            </div>
          </div>

          {!ferme && (
            <div className="grid justify-items-end gap-2">
              {erreurFermeture && (
                <p role="alert" className="alert alert-error alert-soft py-2 text-sm">
                  {erreurFermeture}
                </p>
              )}
              <button
                type="button"
                onClick={() => confirmation.current?.showModal()}
                disabled={fermeture || total === 0}
                className="btn btn-primary btn-md text-base"
              >
                {fermeture ? (
                  <span className="loading loading-spinner loading-sm" aria-hidden="true" />
                ) : (
                  <Lock className="size-5" aria-hidden="true" />
                )}
                Clore le vote
              </button>
              <p className="text-sm font-semibold opacity-80">
                {total === 0 ? 'Disponible dès le premier vote.' : 'Égalité ? Le meilleur indice de confiance l’emporte.'}
              </p>
            </div>
          )}
        </div>
      </section>

      <dialog ref={confirmation} className="modal" aria-labelledby="titre-clore">
        <div className="modal-box border-2 border-secondary">
          <h2 id="titre-clore" className="text-2xl font-extrabold tracking-tight">
            Clore le vote maintenant ?
          </h2>
          <p className="py-3 text-lg">
            {libelleVotes(total)} reçu{total > 1 ? 's' : ''}. Les élèves ne pourront plus voter ni changer d’avis.
          </p>
          <div className="modal-action">
            <form method="dialog">
              <button className="btn btn-md">Laisser voter</button>
            </form>
            <button type="button" onClick={clore} className="btn btn-primary btn-md">
              <Lock className="size-5" aria-hidden="true" />
              Clore le vote
            </button>
          </div>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>Fermer</button>
        </form>
      </dialog>
    </div>
  )
}
