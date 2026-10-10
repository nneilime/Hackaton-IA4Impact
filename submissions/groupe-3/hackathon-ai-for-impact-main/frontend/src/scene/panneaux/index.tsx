import type { PropsPanneau } from '../types'
import PanneauDestination from './PanneauDestination'
import PanneauPrereservation from './PanneauPrereservation'
import PanneauTrajet from './PanneauTrajet'
import PanneauVote from './PanneauVote'

/**
 * Rend le panneau propre à l'étape courante, sous la mascotte. Rien pour les étapes qui n'utilisent que la
 * bulle, les cartes et la saisie (accueil, thème, critères). Aucune logique métier : tout vient du back.
 * La clé relance l'animation d'entrée quand la destination ou le trajet change (« Une autre idée »).
 */
export default function PanneauEtape(props: PropsPanneau) {
  const { reponse } = props
  switch (reponse.etape) {
    case 'destination':
      return <PanneauDestination key={reponse.destination?.site_id ?? 'destination'} {...props} />
    case 'trajet':
      return <PanneauTrajet key={reponse.proposition?.proposition_id ?? 'trajet'} {...props} />
    case 'vote':
      return <PanneauVote {...props} />
    case 'prereservation':
    case 'fin':
      return <PanneauPrereservation {...props} />
    default:
      return null
  }
}
