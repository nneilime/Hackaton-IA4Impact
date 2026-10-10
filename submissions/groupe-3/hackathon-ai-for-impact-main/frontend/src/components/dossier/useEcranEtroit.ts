import { useSyncExternalStore } from 'react'

const REQUETE = '(max-width: 639px)'

function abonner(rappel: () => void) {
  const requete = window.matchMedia(REQUETE)
  requete.addEventListener('change', rappel)
  return () => requete.removeEventListener('change', rappel)
}

/**
 * Vrai sous 640 px. Sert à raccourcir les libellés passés en texte à la barre d'action
 * (« Envoyer la demande » au lieu de « Envoyer la demande de pré-réservation ») pour
 * qu'elle tienne sur un téléphone sans défilement horizontal.
 */
export function useEcranEtroit() {
  return useSyncExternalStore(
    abonner,
    () => window.matchMedia(REQUETE).matches,
    () => false,
  )
}
