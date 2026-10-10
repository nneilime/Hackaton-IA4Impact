import { useEffect, useRef, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { api, ErreurApi } from '../../api/client'
import type { MessageChat } from '../../api/types'
import { useVoyage } from '../../state/VoyageContext'

const CLE_SUGGESTIONS = 'lio-accueil-suggestions'
/** Durée pendant laquelle Tchouette garde l'air de parler après une réponse. */
const DUREE_PAROLE_MS = 6000
const ERREUR_INCONNUE = "Tchouette n'a pas pu vous répondre. Vérifiez votre connexion, puis réessayez."

function lireSuggestions(): string[] {
  try {
    const brut = sessionStorage.getItem(CLE_SUGGESTIONS)
    const valeur: unknown = brut ? JSON.parse(brut) : []
    return Array.isArray(valeur) ? valeur.filter((s): s is string => typeof s === 'string') : []
  } catch {
    return []
  }
}

export interface Conversation {
  messages: MessageChat[]
  enAttente: boolean
  erreur: string | null
  /** Réponses rapides proposées par l'API après le dernier message. */
  suggestions: string[]
  /** Tchouette vient de répondre. */
  parle: boolean
  brouillon: string
  setBrouillon: Dispatch<SetStateAction<string>>
  /** Envoie un message ; renvoie false s'il est vide ou si une réponse est attendue. */
  envoyer: (texte: string) => boolean
  /** Renvoie la conversation telle quelle (le dernier message de l'enseignant). */
  reessayer: () => void
  recommencer: () => void
}

/** Conversation avec Tchouette : messages et demande vivent dans le contexte, le reste ici. */
export function useConversation(): Conversation {
  const { messages, demande, definirMessages, definirDemande } = useVoyage()
  const [enAttente, setEnAttente] = useState(false)
  const [erreur, setErreur] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<string[]>(lireSuggestions)
  const [parle, setParle] = useState(false)
  const [brouillon, setBrouillon] = useState('')
  const requeteCourante = useRef(0)
  const minuterieParole = useRef<number | undefined>(undefined)

  useEffect(() => () => window.clearTimeout(minuterieParole.current), [])

  useEffect(() => {
    try {
      sessionStorage.setItem(CLE_SUGGESTIONS, JSON.stringify(suggestions))
    } catch {
      // stockage indisponible : les suggestions restent en mémoire
    }
  }, [suggestions])

  function faireParler() {
    window.clearTimeout(minuterieParole.current)
    setParle(true)
    minuterieParole.current = window.setTimeout(() => setParle(false), DUREE_PAROLE_MS)
  }

  async function appeler(conversation: MessageChat[]) {
    const id = ++requeteCourante.current
    setEnAttente(true)
    setErreur(null)
    setParle(false)
    try {
      const reponse = await api.chat(conversation, demande)
      if (id !== requeteCourante.current) return
      definirMessages([...conversation, { role: 'assistant', content: reponse.reponse }])
      definirDemande(reponse.demande)
      setSuggestions(reponse.suggestions ?? [])
      faireParler()
    } catch (e) {
      if (id !== requeteCourante.current) return
      setErreur(e instanceof ErreurApi ? e.message : ERREUR_INCONNUE)
    } finally {
      if (id === requeteCourante.current) setEnAttente(false)
    }
  }

  function envoyer(texte: string) {
    const propre = texte.trim()
    if (!propre || enAttente) return false
    const conversation: MessageChat[] = [...messages, { role: 'user', content: propre }]
    definirMessages(conversation)
    setSuggestions([])
    void appeler(conversation)
    return true
  }

  function reessayer() {
    if (enAttente || messages.length === 0) return
    void appeler(messages)
  }

  function recommencer() {
    requeteCourante.current += 1
    window.clearTimeout(minuterieParole.current)
    setEnAttente(false)
    setErreur(null)
    setParle(false)
    setSuggestions([])
    setBrouillon('')
    definirMessages([])
    definirDemande(null)
  }

  return {
    messages,
    enAttente,
    // une erreur n'a de sens que s'il reste un message à renvoyer
    erreur: messages.length > 0 ? erreur : null,
    suggestions,
    parle,
    brouillon,
    setBrouillon,
    envoyer,
    reessayer,
    recommencer,
  }
}
