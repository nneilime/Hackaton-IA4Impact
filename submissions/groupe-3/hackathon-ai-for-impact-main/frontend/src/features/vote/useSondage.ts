import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ErreurApi } from '../../api/client'
import type { Sondage } from '../../api/types'

export type EtatSondage = 'chargement' | 'pret' | 'introuvable' | 'erreur'

/**
 * Lit le vote puis l'interroge à intervalle régulier tant qu'il est ouvert (arrêt au démontage
 * et à la fermeture). Une erreur passagère pendant le suivi garde les derniers chiffres affichés
 * et signale la perte de connexion ; une erreur au premier chargement propose de réessayer.
 */
export function useSondage(code: string, intervalleMs: number) {
  const [sondage, setSondage] = useState<Sondage | null>(null)
  const [etat, setEtat] = useState<EtatSondage>('chargement')
  const [erreur, setErreur] = useState<string | null>(null)
  const [horsLigne, setHorsLigne] = useState(false)
  const [essai, setEssai] = useState(0)
  const aDesDonnees = useRef(false)
  const ouvert = sondage?.statut !== 'ferme'

  useEffect(() => {
    if (!ouvert) return
    let annule = false
    let minuteur: number | undefined

    async function lire() {
      try {
        const lu = await api.sondage(code)
        if (annule) return
        aDesDonnees.current = true
        setSondage(lu)
        setEtat('pret')
        setErreur(null)
        setHorsLigne(false)
        if (lu.statut === 'ferme') return
      } catch (e) {
        if (annule) return
        if (e instanceof ErreurApi && e.statut === 404) {
          setEtat('introuvable')
          return
        }
        setErreur(e instanceof Error ? e.message : 'Erreur inattendue.')
        if (!aDesDonnees.current) {
          setEtat('erreur')
          return
        }
        setHorsLigne(true)
      }
      minuteur = window.setTimeout(lire, intervalleMs)
    }

    void lire()
    return () => {
      annule = true
      window.clearTimeout(minuteur)
    }
  }, [code, intervalleMs, ouvert, essai])

  /** Après une erreur au premier chargement. */
  const reessayer = useCallback(() => {
    setEtat('chargement')
    setErreur(null)
    setEssai((n) => n + 1)
  }, [])

  /** Remplace les chiffres par la réponse d'une action (vote, fermeture) sans attendre le suivi. */
  const remplacer = useCallback((nouveau: Sondage) => {
    aDesDonnees.current = true
    setSondage(nouveau)
    setEtat('pret')
    setHorsLigne(false)
  }, [])

  return { sondage, etat, erreur, horsLigne, reessayer, remplacer }
}
