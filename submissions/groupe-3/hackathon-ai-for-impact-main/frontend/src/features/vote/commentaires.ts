// Tchouette commente la course en direct. Phrases fabriquées à partir des chiffres du vote,
// sans IA : c'est instantané, gratuit et prévisible devant une classe.
import type { Sondage } from '../../api/types'
import { libelleVotes, meneurs, optionGagnante } from './vote'

export interface Commentaire {
  texte: string
  humeur: 'parle' | 'reflexion' | 'joie'
}

/** Au-delà de ce nombre de votes, Tchouette guette les retardataires. */
const SEUIL_RETARDATAIRES = 15

const empreinte = (s: Sondage) => s.options.map((o) => `${o.site_id}:${o.votes}`).join('|')

const meneurUnique = (s: Sondage) => {
  const m = meneurs(s)
  return m.length === 1 ? m[0] : null
}

/**
 * Commentaire à afficher après une lecture du vote, ou `null` si rien n'a bougé depuis la
 * précédente (le commentaire en cours reste alors affiché).
 */
export function commenter(avant: Sondage | null, apres: Sondage): Commentaire | null {
  if (apres.statut === 'ferme') {
    const gagnante = optionGagnante(apres)
    if (avant?.statut === 'ferme') return null
    return gagnante
      ? { texte: `Et la classe a choisi… ${gagnante.nom} ! Tout le monde en voiture !`, humeur: 'joie' }
      : { texte: 'Le vote est terminé.', humeur: 'joie' }
  }

  const total = apres.total_votes
  if (total === 0) {
    if (avant && avant.total_votes === 0) return null
    return {
      texte: 'En attente du premier vote… Scannez le QR code pour monter à bord !',
      humeur: 'reflexion',
    }
  }
  if (avant && empreinte(avant) === empreinte(apres)) return null

  if (!avant || avant.total_votes === 0) {
    return total === 1
      ? { texte: 'Premier vote ! Ça démarre.', humeur: 'parle' }
      : { texte: `${libelleVotes(total)} déjà ! Les trains sont partis.`, humeur: 'parle' }
  }

  const tete = meneurs(apres)
  if (tete.length > 1) {
    return tete.length === apres.options.length
      ? { texte: 'Égalité parfaite, qui va faire la différence ?', humeur: 'parle' }
      : { texte: `Égalité parfaite entre ${tete.map((o) => o.nom).join(' et ')}, qui va faire la différence ?`, humeur: 'parle' }
  }

  const meneur = tete[0]
  const ancien = meneurUnique(avant)
  if (meneur && meneur.site_id !== ancien?.site_id) {
    return { texte: `${meneur.nom} prend la tête !`, humeur: 'parle' }
  }
  if (total === avant.total_votes) {
    return { texte: 'Quelqu’un a changé d’avis… la course se resserre !', humeur: 'parle' }
  }
  if (total >= SEUIL_RETARDATAIRES) {
    return { texte: `${libelleVotes(total)}, encore quelques retardataires ?`, humeur: 'parle' }
  }
  return { texte: `${libelleVotes(total)} ! ${meneur?.nom ?? 'La course'} reste en tête.`, humeur: 'parle' }
}
