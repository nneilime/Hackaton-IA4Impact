import { useCallback, useEffect, useRef, useState } from 'react'

// Types minimaux de l'API Web Speech (absente des types DOM standard).
interface AlternativeReconnaissance {
  readonly transcript: string
}

interface ResultatReconnaissance {
  readonly isFinal: boolean
  readonly length: number
  readonly [index: number]: AlternativeReconnaissance
}

interface EvenementReconnaissance extends Event {
  readonly resultIndex: number
  readonly results: {
    readonly length: number
    readonly [index: number]: ResultatReconnaissance
  }
}

interface EvenementErreurReconnaissance extends Event {
  readonly error: string
}

interface ReconnaissanceVocale {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  onresult: ((evenement: EvenementReconnaissance) => void) | null
  onerror: ((evenement: EvenementErreurReconnaissance) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}

type ConstructeurReconnaissance = new () => ReconnaissanceVocale

function constructeurDisponible(): ConstructeurReconnaissance | null {
  if (typeof window === 'undefined') return null
  const fenetre = window as unknown as {
    SpeechRecognition?: ConstructeurReconnaissance
    webkitSpeechRecognition?: ConstructeurReconnaissance
  }
  return fenetre.SpeechRecognition ?? fenetre.webkitSpeechRecognition ?? null
}

function messageErreur(code: string): string | null {
  switch (code) {
    case 'aborted':
      return null
    case 'not-allowed':
    case 'service-not-allowed':
      return "Le micro n'est pas autorisé. Autorisez-le dans votre navigateur, ou tapez votre message."
    case 'no-speech':
      return "Je n'ai rien entendu. Appuyez sur le micro et parlez juste après."
    case 'audio-capture':
      return 'Aucun micro détecté sur cet appareil.'
    case 'network':
      return 'La dictée a besoin d’une connexion internet. Tapez votre message en attendant.'
    default:
      return 'La dictée s’est interrompue. Réessayez ou tapez votre message.'
  }
}

/** Dictée vocale en français ; `disponible` est faux si le navigateur ne la propose pas. */
export function useDictee(surTexte: (texte: string) => void) {
  const [disponible] = useState(() => constructeurDisponible() !== null)
  const [ecoute, setEcoute] = useState(false)
  const [erreur, setErreur] = useState<string | null>(null)
  const reconnaissance = useRef<ReconnaissanceVocale | null>(null)
  const rappel = useRef(surTexte)

  useEffect(() => {
    rappel.current = surTexte
  })

  useEffect(() => () => reconnaissance.current?.abort(), [])

  const demarrer = useCallback(() => {
    const Constructeur = constructeurDisponible()
    if (!Constructeur) return
    reconnaissance.current?.abort()
    const reco = new Constructeur()
    reco.lang = 'fr-FR'
    reco.continuous = false
    reco.interimResults = false
    reco.maxAlternatives = 1
    reco.onresult = (evenement) => {
      let texte = ''
      for (let i = evenement.resultIndex; i < evenement.results.length; i += 1) {
        const resultat = evenement.results[i]
        if (resultat.isFinal && resultat.length > 0) texte += resultat[0].transcript
      }
      if (texte.trim()) rappel.current(texte.trim())
    }
    reco.onerror = (evenement) => setErreur(messageErreur(evenement.error))
    reco.onend = () => {
      setEcoute(false)
      if (reconnaissance.current === reco) reconnaissance.current = null
    }
    setErreur(null)
    try {
      reco.start()
      reconnaissance.current = reco
      setEcoute(true)
    } catch {
      setErreur(messageErreur('inconnue'))
    }
  }, [])

  const arreter = useCallback(() => {
    reconnaissance.current?.stop()
  }, [])

  return { disponible, ecoute, erreur, demarrer, arreter }
}
