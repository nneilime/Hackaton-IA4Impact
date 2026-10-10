import { useSyncExternalStore } from 'react'

/** Sous `sm` (640 px) : on raccourcit les libellés de la barre d'action pour éviter tout débordement. */
const REQUETE = '(max-width: 639.98px)'

function abonner(rappel: () => void) {
  const media = window.matchMedia(REQUETE)
  media.addEventListener('change', rappel)
  return () => media.removeEventListener('change', rappel)
}

export function useEcranEtroit(): boolean {
  return useSyncExternalStore(
    abonner,
    () => window.matchMedia(REQUETE).matches,
    () => false,
  )
}
