import type { EvenementScene, HumeurScene, ReponseScene } from '../api/types'

/** Props communes à tous les panneaux d'étape (destination, trajet, vote, pré-réservation). */
export interface PropsPanneau {
  reponse: ReponseScene
  /** Envoie un événement à la machine à états du back (la scène se met à jour toute seule). */
  envoyer: (evenement: EvenementScene) => void
  chargement: boolean
  /**
   * Fait parler Tchouette sans appeler le back (ex. commentaires en direct pendant le vote).
   * `commenter(null)` rend la parole à la dernière réplique du back. Un nouveau tour du back efface la surcharge.
   */
  commenter: (texte: string | null, humeur?: HumeurScene) => void
}
