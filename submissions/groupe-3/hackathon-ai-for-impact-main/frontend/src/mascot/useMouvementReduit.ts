import { useSyncExternalStore } from 'react'

const REQUETE = '(prefers-reduced-motion: reduce)'

function mediaQuery(): MediaQueryList | null {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return null
  return window.matchMedia(REQUETE)
}

function abonner(prevenir: () => void): () => void {
  const mq = mediaQuery()
  if (!mq) return () => {}
  mq.addEventListener('change', prevenir)
  return () => mq.removeEventListener('change', prevenir)
}

const lire = (): boolean => mediaQuery()?.matches ?? false
const lireCoteServeur = (): boolean => false

/**
 * Vrai quand l'utilisateur a demandé à réduire les animations
 * (`prefers-reduced-motion: reduce`). Suit les changements en direct.
 */
export function useMouvementReduit(): boolean {
  return useSyncExternalStore(abonner, lire, lireCoteServeur)
}
