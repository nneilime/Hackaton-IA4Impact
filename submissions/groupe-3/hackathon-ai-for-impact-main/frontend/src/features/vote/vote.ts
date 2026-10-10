// Règles et calculs partagés par l'écran projeté (enseignant) et la page de vote (élèves).
import type { Destination, OptionSondage, Sondage } from '../../api/types'

/** Interrogation de l'API : l'écran projeté toutes les 2 s, les téléphones toutes les 3 s. */
export const INTERVALLE_ANIMATEUR_MS = 2000
export const INTERVALLE_ELEVE_MS = 3000

const CLE_VOTANT = 'lio-vote-votant'
const cleChoix = (code: string) => `lio-vote-choix-${code}`

/**
 * Identifiant aléatoire du téléphone, pour qu'un élève ne vote qu'une fois (il peut changer d'avis).
 * Aucune donnée personnelle. `crypto.randomUUID` n'existe qu'en contexte sécurisé (https ou
 * localhost) : sur http://<ip-locale>:5173, on fabrique un UUID v4 avec `getRandomValues`.
 */
function nouvelIdentifiant(): string {
  if (typeof crypto.randomUUID === 'function') {
    try {
      return crypto.randomUUID()
    } catch {
      // contexte non sécurisé : repli ci-dessous
    }
  }
  const octets = crypto.getRandomValues(new Uint8Array(16))
  octets[6] = (octets[6] & 0x0f) | 0x40
  octets[8] = (octets[8] & 0x3f) | 0x80
  const hex = Array.from(octets, (o) => o.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

let identifiantDeSecours: string | null = null

export function identifiantVotant(): string {
  try {
    const existant = localStorage.getItem(CLE_VOTANT)
    if (existant) return existant
    const id = nouvelIdentifiant()
    localStorage.setItem(CLE_VOTANT, id)
    return id
  } catch {
    // stockage bloqué (navigation privée) : un identifiant pour la durée de la page
    identifiantDeSecours ??= nouvelIdentifiant()
    return identifiantDeSecours
  }
}

/** Le choix de l'élève est retenu sur son téléphone pour le réafficher s'il recharge la page. */
export function lireChoix(code: string): string | null {
  try {
    return localStorage.getItem(cleChoix(code))
  } catch {
    return null
  }
}

export function memoriserChoix(code: string, siteId: string): void {
  try {
    localStorage.setItem(cleChoix(code), siteId)
  } catch {
    // sans stockage, le choix reste affiché tant que la page est ouverte
  }
}

/** Part des votes en pourcentage entier (0 quand personne n'a voté). */
export function part(option: OptionSondage, total: number): number {
  return total > 0 ? Math.round((option.votes / total) * 100) : 0
}

/** Les destinations en tête (plusieurs en cas d'égalité, aucune avant le premier vote). */
export function meneurs(sondage: Sondage): OptionSondage[] {
  const max = Math.max(0, ...sondage.options.map((o) => o.votes))
  return max === 0 ? [] : sondage.options.filter((o) => o.votes === max)
}

export function optionGagnante(sondage: Sondage): OptionSondage | null {
  return sondage.options.find((o) => o.site_id === sondage.gagnant) ?? null
}

export const libelleVotes = (n: number) => `${n} vote${n > 1 ? 's' : ''}`

/** Première idée de l'intérêt pédagogique, pour tenir sur une carte de téléphone. */
export function interetCourt(texte: string): string {
  const premier = texte.split(/\s[:;]\s|,\s/)[0]?.trim() ?? ''
  return premier.length >= 20 ? premier : texte
}

/** Adresse de vote encodée dans le QR code. */
export function urlVote(origine: string, code: string): string {
  return `${origine.replace(/\/$/, '')}/vote/${code}`
}

export const estLocal = (hote: string) => hote === 'localhost' || hote === '127.0.0.1' || hote === '[::1]'

/**
 * Destination à transmettre à l'étape « trajets » : celle de la recherche si elle est encore en
 * mémoire, sinon une version minimale reconstruite depuis l'option du vote.
 */
export function destinationDepuisOption(option: OptionSondage, destinations: Destination[]): Destination {
  const connue = destinations.find((d) => d.site_id === option.site_id)
  if (connue) return connue
  return {
    site_id: option.site_id,
    nom: option.nom,
    commune: option.commune,
    gare: { code_uic: '', nom: option.commune, lat: 0, lon: 0 },
    interet_pedagogique: option.interet_pedagogique,
    activites: [],
    themes: [],
    niveaux: [],
    temps_trajet_min: null,
    correspondances: 0,
    acces_gare_site: { mode: 'pied', minutes_groupe: 0, niveau: option.niveau, message: '' },
    indice_confiance: option.indice_confiance,
    niveau: option.niveau,
  }
}
