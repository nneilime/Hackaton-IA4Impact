import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { CircleCheck, CircleX, ShieldCheck, Vote, WifiOff } from 'lucide-react'
import { api, ErreurApi } from '../api/client'
import type { Sondage } from '../api/types'
import CarteChoix from '../features/vote/CarteChoix'
import { ErreurVote, VoteIntrouvable } from '../features/vote/EtatsVote'
import { useSondage } from '../features/vote/useSondage'
import {
  identifiantVotant,
  INTERVALLE_ELEVE_MS,
  lireChoix,
  memoriserChoix,
  optionGagnante,
} from '../features/vote/vote'
import Tchouette from '../mascot/Tchouette'
import type { HumeurTchouette } from '../mascot/Tchouette'

const DUREE_CONFIRMATION_MS = 3500

/**
 * Page de vote des élèves, ouverte en scannant le QR code projeté. Mobile d'abord, hors du shell.
 * Vote anonyme : aucun prénom demandé, seulement un identifiant aléatoire gardé sur le téléphone.
 */
export default function VoteEleve() {
  const { code: codeBrut = '' } = useParams()
  const code = codeBrut.trim().toUpperCase()
  const { sondage, etat, erreur, horsLigne, reessayer, remplacer } = useSondage(code, INTERVALLE_ELEVE_MS)

  return (
    <div className="min-h-screen bg-base-200 text-base-content">
      <header className="bg-secondary text-secondary-content">
        <div className="mx-auto flex max-w-xl items-center justify-between gap-3 px-4 py-2">
          <p className="flex items-center gap-2 font-extrabold">
            <Vote className="size-5 shrink-0" aria-hidden="true" />
            Vote de la classe
          </p>
          {code && (
            <p className="badge badge-accent badge-sm font-bold tabular-nums tracking-widest">
              <span className="sr-only">Code du vote :</span>
              {code}
            </p>
          )}
        </div>
      </header>

      <main id="contenu" className="mx-auto grid max-w-xl gap-4 px-4 py-4">
        {etat === 'chargement' && <ChargementEleve />}
        {etat === 'introuvable' && (
          <VoteIntrouvable titre="Oups, ce vote n’existe pas">
            <p>
              Le code <strong className="tabular-nums tracking-widest">{code}</strong> ne correspond à aucun vote.
            </p>
            <p>Vérifie le code affiché au tableau, ou scanne à nouveau le QR code.</p>
          </VoteIntrouvable>
        )}
        {etat === 'erreur' && (
          <ErreurVote
            titre="Impossible d’ouvrir le vote"
            message={erreur ?? 'Erreur inattendue.'}
            onReessayer={reessayer}
          />
        )}
        {etat === 'pret' && sondage && (
          <Bulletin code={code} sondage={sondage} horsLigne={horsLigne} remplacer={remplacer} />
        )}
      </main>
    </div>
  )
}

function ChargementEleve() {
  return (
    <div className="grid gap-4">
      <div role="status" className="flex items-center gap-3">
        <Tchouette humeur="reflexion" taille={72} titre="" />
        <p className="text-sm font-semibold">J’ouvre le vote de ta classe…</p>
        <span className="loading loading-dots loading-sm" aria-hidden="true" />
      </div>
      <div className="skeleton h-8 w-4/5" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="skeleton h-24 w-full" />
      ))}
    </div>
  )
}

interface BulletinProps {
  code: string
  sondage: Sondage
  horsLigne: boolean
  remplacer: (s: Sondage) => void
}

function Bulletin({ code, sondage, horsLigne, remplacer }: BulletinProps) {
  const [choix, setChoix] = useState<string | null>(() => lireChoix(code))
  const [envoi, setEnvoi] = useState<string | null>(null)
  const [erreurVote, setErreurVote] = useState<string | null>(null)
  const [confirmation, setConfirmation] = useState(false)
  const minuteur = useRef<number | undefined>(undefined)

  useEffect(() => () => window.clearTimeout(minuteur.current), [])

  const ferme = sondage.statut === 'ferme'
  const gagnante = optionGagnante(sondage)
  // Un choix mémorisé qui ne fait plus partie du vote (base réinitialisée) est ignoré.
  const monVote = sondage.options.some((o) => o.site_id === choix) ? choix : null

  async function voter(siteId: string) {
    if (envoi || ferme) return
    setEnvoi(siteId)
    setErreurVote(null)
    try {
      remplacer(await api.voter(code, siteId, identifiantVotant()))
      setChoix(siteId)
      memoriserChoix(code, siteId)
      setConfirmation(true)
      window.clearTimeout(minuteur.current)
      minuteur.current = window.setTimeout(() => setConfirmation(false), DUREE_CONFIRMATION_MS)
    } catch (e) {
      setErreurVote(e instanceof Error ? e.message : 'Erreur inattendue.')
      if (e instanceof ErreurApi && e.statut === 409) {
        // Le vote vient d'être clos : on affiche tout de suite le résultat.
        api.sondage(code).then(remplacer).catch(() => {})
      }
    } finally {
      setEnvoi(null)
    }
  }

  let humeur: HumeurTchouette = 'parle'
  let message = 'Salut ! Ta classe choisit sa sortie. Vote pour ta destination préférée !'
  if (ferme) {
    humeur = 'joie'
    message = gagnante
      ? `Le vote est terminé ! Ta classe part à la découverte de ${gagnante.nom}.`
      : 'Le vote est terminé !'
  } else if (monVote) {
    humeur = confirmation ? 'joie' : 'parle'
    message = 'C’est noté ! Tu peux changer d’avis tant que le vote est ouvert.'
  }

  return (
    <>
      <div className="chat chat-start">
        <div className="chat-image">
          <Tchouette humeur={humeur} taille={80} titre="" />
        </div>
        <div className="chat-header pb-1 text-sm font-bold">Tchouette</div>
        <div aria-live="polite" className="chat-bubble bg-base-100 text-sm leading-relaxed text-base-content">
          {message}
        </div>
      </div>

      <h1 className="text-2xl font-extrabold tracking-tight break-words">{sondage.titre}</h1>

      <section aria-labelledby="titre-choix" className="grid gap-2">
        <h2 id="titre-choix" className="text-xs font-semibold uppercase tracking-wide">
          {ferme ? 'Résultats du vote' : monVote ? 'Touche une autre carte pour changer d’avis' : 'Touche ta destination préférée'}
        </h2>
        <ul className="grid gap-3">
          {sondage.options.map((option) => (
            <li key={option.site_id}>
              <CarteChoix
                option={option}
                total={sondage.total_votes}
                choisie={option.site_id === monVote}
                gagnante={ferme && option.site_id === sondage.gagnant}
                ferme={ferme}
                montrerResultats={ferme || monVote !== null}
                envoi={envoi === option.site_id}
                onVoter={() => voter(option.site_id)}
              />
            </li>
          ))}
        </ul>
        {(ferme || monVote) && (
          <p className="text-xs font-semibold tabular-nums opacity-80">
            {sondage.total_votes} vote{sondage.total_votes > 1 ? 's' : ''} dans la classe
            {ferme ? '' : ' · mis à jour en direct'}
          </p>
        )}
      </section>

      {erreurVote && (
        <div role="alert" className="alert alert-error alert-soft text-sm">
          <CircleX className="size-5 shrink-0" aria-hidden="true" />
          <span>
            {erreurVote}
            {!ferme && ' Vérifie ta connexion et touche à nouveau ta destination.'}
          </span>
        </div>
      )}
      {horsLigne && !erreurVote && (
        <p role="status" className="flex items-center gap-2 text-sm font-semibold">
          <WifiOff className="size-4 shrink-0" aria-hidden="true" />
          Connexion perdue, nouvel essai…
        </p>
      )}

      <p className="flex items-start gap-2 text-xs opacity-80">
        <ShieldCheck className="size-4 shrink-0" aria-hidden="true" />
        Vote anonyme : personne ne te demande ton prénom.
      </p>

      {confirmation && !ferme && (
        <div className="toast toast-center toast-bottom z-10 w-max max-w-[calc(100vw-2rem)]">
          <div role="status" className="alert alert-success whitespace-normal motion-safe:animate-pop">
            <CircleCheck className="size-5 shrink-0" aria-hidden="true" />
            <span className="text-sm font-semibold">C’est noté ! Tu peux changer d’avis tant que le vote est ouvert.</span>
          </div>
        </div>
      )}
    </>
  )
}
