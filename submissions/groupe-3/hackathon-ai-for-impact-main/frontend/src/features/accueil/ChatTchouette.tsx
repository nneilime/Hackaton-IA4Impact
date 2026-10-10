import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import type { FormEvent, KeyboardEvent, ReactNode } from 'react'
import {
  BookOpen,
  CalendarDays,
  CircleX,
  MapPin,
  MessagesSquare,
  Mic,
  MicOff,
  RotateCcw,
  SendHorizontal,
  Sparkles,
  Users,
} from 'lucide-react'
import Tchouette from '../../mascot/Tchouette'
import type { HumeurTchouette } from '../../mascot/Tchouette'
import { AMORCES } from './demande'
import type { Amorce } from './demande'
import type { Conversation } from './useConversation'
import { useDictee } from './useDictee'

/** Ce dont Tchouette a besoin, en quatre mots-clés. */
const BESOINS = [
  { icone: BookOpen, texte: 'La classe et le thème' },
  { icone: Users, texte: 'Élèves et accompagnateurs' },
  { icone: CalendarDays, texte: 'La date de sortie' },
  { icone: MapPin, texte: 'Le lieu de départ' },
]

/** Ce que Tchouette ressent, dit avec des mots (jamais par la seule couleur). */
const ETATS: Record<HumeurTchouette, { texte: string; pastille: string }> = {
  repos: { texte: 'Je vous écoute', pastille: 'status status-neutral' },
  salue: { texte: 'Je vous écoute', pastille: 'status status-neutral' },
  reflexion: { texte: 'Je réfléchis…', pastille: 'status status-warning motion-safe:animate-pulse' },
  parle: { texte: 'Je vous réponds', pastille: 'status status-info' },
  joie: { texte: 'Demande complète', pastille: 'status status-success' },
  inquiete: { texte: 'Un souci de connexion', pastille: 'status status-error' },
  pointe: { texte: 'Je vous réponds', pastille: 'status status-info' },
  loupe: { texte: 'Je réfléchis…', pastille: 'status status-warning motion-safe:animate-pulse' },
  celebre: { texte: 'Demande complète', pastille: 'status status-success' },
}

/** Classes complètes de chaque puce : elles apparaissent l'une après l'autre. */
const CLASSES_PUCES = [
  'shrink-0 motion-safe:animate-pop',
  'shrink-0 motion-safe:animate-pop motion-safe:[animation-delay:70ms]',
  'shrink-0 motion-safe:animate-pop motion-safe:[animation-delay:140ms]',
  'shrink-0 motion-safe:animate-pop motion-safe:[animation-delay:210ms]',
  'shrink-0 motion-safe:animate-pop motion-safe:[animation-delay:280ms]',
]

function BulleTchouette({ children, humeur = 'repos' }: { children: ReactNode; humeur?: HumeurTchouette }) {
  return (
    <div className="chat chat-start motion-safe:animate-entree">
      <div className="chat-image avatar">
        <div className="grid size-8 place-items-center rounded-full border-2 border-secondary bg-accent">
          <Tchouette humeur={humeur} taille={24} titre="" />
        </div>
      </div>
      <div className="chat-bubble max-w-[88%] text-sm leading-relaxed break-words lg:text-[15px]">
        <span className="sr-only">Tchouette : </span>
        {children}
      </div>
    </div>
  )
}

function BulleVous({ children }: { children: ReactNode }) {
  return (
    <div className="chat chat-end motion-safe:animate-entree">
      <div className="chat-bubble chat-bubble-secondary max-w-[88%] whitespace-pre-line text-sm leading-relaxed break-words lg:text-[15px]">
        <span className="sr-only">Vous : </span>
        {children}
      </div>
    </div>
  )
}

interface ChatTchouetteProps {
  conversation: Conversation
  /** Humeur de Tchouette sur la page, pour la pastille d'état de l'en-tête. */
  humeur: HumeurTchouette
  /** Demande complète : la réponse rapide « Voir les destinations » y mène directement. */
  pret: boolean
}

const VERS_DESTINATIONS = /^voir les destinations/i

export default function ChatTchouette({ conversation, humeur, pret }: ChatTchouetteProps) {
  const navigate = useNavigate()
  const { messages, enAttente, erreur, suggestions, brouillon, setBrouillon, envoyer, reessayer, recommencer } =
    conversation
  const filRef = useRef<HTMLDivElement>(null)
  const saisieRef = useRef<HTMLTextAreaElement>(null)
  const dictee = useDictee((texte) => setBrouillon((avant) => (avant.trim() ? `${avant.trimEnd()} ${texte}` : texte)))
  const etat = ETATS[humeur]

  // Défilement automatique vers le dernier message, dans la carte (la page ne bouge pas).
  useEffect(() => {
    const fil = filRef.current
    if (!fil) return
    const reduit = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    fil.scrollTo({ top: fil.scrollHeight, behavior: reduit ? 'auto' : 'smooth' })
  }, [messages.length, enAttente, erreur])

  const debut = messages.length === 0
  const reponsesRapides: Amorce[] = debut ? AMORCES : suggestions.map((texte) => ({ texte }))

  function focaliserSaisie() {
    saisieRef.current?.focus()
  }

  function soumettre(evenement?: FormEvent<HTMLFormElement>) {
    evenement?.preventDefault()
    if (dictee.ecoute) dictee.arreter()
    if (envoyer(brouillon)) setBrouillon('')
    focaliserSaisie()
  }

  function surTouche(evenement: KeyboardEvent<HTMLTextAreaElement>) {
    if (evenement.key === 'Enter' && !evenement.shiftKey && !evenement.nativeEvent.isComposing) {
      evenement.preventDefault()
      soumettre()
    }
  }

  function choisir(texte: string) {
    if (pret && VERS_DESTINATIONS.test(texte.trim())) {
      navigate('/destinations')
      return
    }
    envoyer(texte)
    focaliserSaisie()
  }

  return (
    <div className="flex h-[clamp(360px,calc(100dvh-210px),560px)] flex-col rounded-box border-2 border-secondary bg-base-100 shadow-[4px_4px_0_0] shadow-secondary lg:h-[clamp(420px,calc(100dvh-330px),620px)]">
      {/* En-tête : titre, état de Tchouette en mots, recommencer */}
      <div className="flex items-center gap-2 border-b-2 border-secondary px-3 py-1.5">
        <h2 className="flex min-w-0 items-center gap-2 text-base font-bold">
          <MessagesSquare className="size-4 shrink-0" aria-hidden="true" />
          <span className="truncate">Conversation avec Tchouette</span>
        </h2>
        <p className="ml-auto flex shrink-0 items-center gap-1.5 text-xs font-semibold text-base-content/80">
          <span className={etat.pastille} aria-hidden="true" />
          <span className="hidden sm:inline">{etat.texte}</span>
        </p>
        {!debut && (
          <button
            type="button"
            className="btn btn-ghost btn-sm max-lg:h-10"
            onClick={() => {
              recommencer()
              focaliserSaisie()
            }}
          >
            <RotateCcw className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Recommencer</span>
            <span className="sr-only sm:hidden">Recommencer la conversation</span>
          </button>
        )}
      </div>

      {/* Le fil : il défile DANS la carte */}
      <div
        ref={filRef}
        role="log"
        aria-live="polite"
        aria-label="Fil de la conversation avec Tchouette"
        tabIndex={0}
        className="min-h-0 flex-1 space-y-1 overflow-y-auto overscroll-contain px-3 py-3 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-secondary"
      >
        <BulleTchouette humeur={debut ? 'parle' : 'repos'}>
          <p>Bonjour, je suis Tchouette ! Racontez votre sortie avec vos mots. Il me faut :</p>
          <ul className="my-1.5 grid gap-x-3 gap-y-1 sm:grid-cols-2">
            {BESOINS.map(({ icone: Icone, texte }) => (
              <li key={texte} className="flex items-center gap-1.5 font-semibold">
                <Icone className="size-4 shrink-0" aria-hidden="true" />
                {texte}
              </li>
            ))}
          </ul>
          <p>Tout d’un coup ou petit à petit, comme vous voulez.</p>
        </BulleTchouette>

        {messages.map((message, index) =>
          message.role === 'assistant' ? (
            <BulleTchouette key={index}>
              <span className="whitespace-pre-line">{message.content}</span>
            </BulleTchouette>
          ) : (
            <BulleVous key={index}>{message.content}</BulleVous>
          ),
        )}

        {enAttente && (
          <BulleTchouette humeur="reflexion">
            <span className="flex items-center gap-2">
              <span className="loading loading-dots loading-sm" aria-hidden="true" />
              Tchouette réfléchit…
            </span>
          </BulleTchouette>
        )}
      </div>

      {erreur && (
        <div role="alert" className="alert alert-error alert-soft mx-3 mb-2 gap-2 px-3 py-2 text-sm">
          <CircleX className="size-4 shrink-0" aria-hidden="true" />
          <p className="min-w-0">
            <strong>Tchouette n’a pas pu répondre.</strong> {erreur}
          </p>
          <button
            type="button"
            className="btn btn-sm max-lg:h-10"
            onClick={() => {
              reessayer()
              focaliserSaisie()
            }}
          >
            <RotateCcw className="size-4" aria-hidden="true" />
            Réessayer
          </button>
        </div>
      )}

      {/* Réponses rapides : une rangée de petites puces au-dessus du champ */}
      {!enAttente && reponsesRapides.length > 0 && (
        <div className="flex items-center gap-2 border-t border-dashed border-base-300 px-3 py-2">
          <p
            id="titre-reponses-rapides"
            className="shrink-0 text-xs font-semibold uppercase tracking-wide text-base-content/70"
          >
            {debut ? 'Idées' : 'Réponses'}
          </p>
          <ul
            aria-labelledby="titre-reponses-rapides"
            className="flex min-w-0 flex-1 gap-1.5 overflow-x-auto py-0.5 [scrollbar-width:thin] lg:flex-wrap lg:overflow-visible"
          >
            {reponsesRapides.map((amorce, index) => (
              <li key={amorce.texte} className={CLASSES_PUCES[index] ?? CLASSES_PUCES[CLASSES_PUCES.length - 1]}>
                <button
                  type="button"
                  onClick={() => choisir(amorce.texte)}
                  title={amorce.libelle ? amorce.texte : undefined}
                  className={
                    amorce.exemple
                      ? 'btn btn-accent btn-sm rounded-full font-semibold whitespace-nowrap max-lg:h-10'
                      : 'btn btn-outline btn-secondary btn-sm rounded-full font-semibold whitespace-nowrap max-lg:h-10'
                  }
                >
                  {amorce.exemple && <Sparkles className="size-3.5 shrink-0" aria-hidden="true" />}
                  {amorce.libelle ?? amorce.texte}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Le champ de saisie : toujours visible en bas de la carte */}
      <form onSubmit={soumettre} className="border-t-2 border-secondary px-3 pb-2 pt-2">
        <label htmlFor="saisie-tchouette" className="sr-only">
          Votre message à Tchouette
        </label>
        <div className="flex items-end gap-2">
          <textarea
            id="saisie-tchouette"
            ref={saisieRef}
            rows={1}
            value={brouillon}
            onChange={(evenement) => setBrouillon(evenement.target.value)}
            onKeyDown={surTouche}
            aria-describedby="aide-saisie-tchouette"
            placeholder="Ma classe de CM2 part en mai, sur la biodiversité…"
            className="textarea textarea-sm min-h-10 max-h-28 w-full min-w-0 flex-1 resize-none text-sm field-sizing-content lg:text-[15px]"
          />
          {dictee.disponible && (
            <div className="tooltip" data-tip={dictee.ecoute ? 'Arrêter la dictée' : 'Dicter au micro'}>
              <button
                type="button"
                onClick={dictee.ecoute ? dictee.arreter : dictee.demarrer}
                aria-pressed={dictee.ecoute}
                aria-label={dictee.ecoute ? 'Arrêter la dictée' : 'Dicter votre message'}
                className={dictee.ecoute ? 'btn btn-square btn-error' : 'btn btn-square btn-outline btn-secondary'}
              >
                {dictee.ecoute ? (
                  <MicOff className="size-4" aria-hidden="true" />
                ) : (
                  <Mic className="size-4" aria-hidden="true" />
                )}
              </button>
            </div>
          )}
          <button
            type="submit"
            className="btn btn-secondary"
            disabled={enAttente || !brouillon.trim()}
            aria-label="Envoyer le message"
          >
            <SendHorizontal className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Envoyer</span>
          </button>
        </div>
        <p id="aide-saisie-tchouette" className="sr-only">
          Entrée pour envoyer, Maj et Entrée pour aller à la ligne.
        </p>
        {dictee.ecoute ? (
          <p role="status" className="mt-1 flex items-center gap-1.5 text-xs font-semibold">
            <span className="status status-error" aria-hidden="true" />
            Je vous écoute… parlez, puis marquez une pause.
          </p>
        ) : dictee.erreur ? (
          <p role="alert" className="mt-1 flex items-start gap-1.5 text-xs font-semibold text-error">
            <CircleX className="mt-px size-3.5 shrink-0" aria-hidden="true" />
            {dictee.erreur}
          </p>
        ) : (
          <p className="mt-1 hidden items-center gap-1 text-xs text-base-content/70 lg:flex" aria-hidden="true">
            <kbd className="kbd kbd-xs">Entrée</kbd> envoyer · <kbd className="kbd kbd-xs">Maj</kbd>+
            <kbd className="kbd kbd-xs">Entrée</kbd> à la ligne
          </p>
        )}
      </form>
    </div>
  )
}
