import { useEffect, useRef, useState } from 'react'
import type { Sondage } from '../../api/types'
import type { HumeurTchouette } from '../../mascot/Tchouette'
import { commenter } from './commentaires'
import type { Commentaire } from './commentaires'

/** Après ce délai sans nouveau vote, Tchouette repasse en mode « réflexion ». */
const DELAI_CALME_MS = 6000

/** Commentaire en direct de Tchouette, recalculé à chaque lecture du vote. */
export function useCommentaire(sondage: Sondage | null): { texte: string; humeur: HumeurTchouette } {
  const precedent = useRef<Sondage | null>(null)
  const minuteur = useRef<number | undefined>(undefined)
  const [commentaire, setCommentaire] = useState<Commentaire>({
    texte: 'Je prépare la course…',
    humeur: 'reflexion',
  })
  const [calme, setCalme] = useState(false)

  useEffect(() => {
    if (!sondage) return
    const nouveau = commenter(precedent.current, sondage)
    precedent.current = sondage
    if (!nouveau) return
    window.clearTimeout(minuteur.current)
    setCommentaire(nouveau)
    setCalme(false)
    if (nouveau.humeur === 'parle') {
      minuteur.current = window.setTimeout(() => setCalme(true), DELAI_CALME_MS)
    }
  }, [sondage])

  useEffect(() => () => window.clearTimeout(minuteur.current), [])

  return {
    texte: commentaire.texte,
    humeur: commentaire.humeur === 'parle' && calme ? 'reflexion' : commentaire.humeur,
  }
}
