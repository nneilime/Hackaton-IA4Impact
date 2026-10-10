// Règles et formats partagés par la page d'accueil (chat, formulaire, billet).
import type { Demande } from '../../api/types'

export const ID_FORMULAIRE_PROJET = 'formulaire-projet'

/** Un groupe liO voyage avec 6 à 50 personnes, accompagnateurs compris. */
export const EFFECTIF_MIN = 6
export const EFFECTIF_MAX = 50
/** En dessous de ce délai, la demande est étudiée au cas par cas. */
export const DELAI_CONSEILLE_JOURS = 21

export const HEURE_DEPART_PAR_DEFAUT = '08:00'
export const HEURE_RETOUR_PAR_DEFAUT = '18:00'

export type EtatFormulaire = 'repos' | 'envoi' | 'erreur'

/** L'exemple de la fiche de cadrage, envoyé tel quel. */
export const EXEMPLE_FICHE =
  'Je souhaite travailler avec ma classe de 5e sur le Moyen Âge. Nous sommes 42 élèves et 4 accompagnateurs. Sortie à la journée le 12 novembre, départ le matin et retour avant 19h. Nous partons du collège de Foix.'

export interface Amorce {
  /** Message envoyé à Tchouette. */
  texte: string
  /** Libellé court affiché sur la puce (le texte complet sinon). */
  libelle?: string
  exemple?: boolean
}

export const AMORCES: Amorce[] = [
  { texte: EXEMPLE_FICHE, libelle: 'Essayer l’exemple : 5e, Moyen Âge, Foix', exemple: true },
  { texte: 'Je ne sais pas encore où aller' },
  { texte: 'Je connais déjà ma destination' },
]

export const GROUPES_NIVEAUX: { groupe: string; niveaux: string[] }[] = [
  { groupe: 'École élémentaire', niveaux: ['CP', 'CE1', 'CE2', 'CM1', 'CM2'] },
  { groupe: 'Collège', niveaux: ['6e', '5e', '4e', '3e'] },
  { groupe: 'Lycée', niveaux: ['2nde', '1re', 'Terminale'] },
]

export const THEMES = [
  'Moyen Âge',
  'Préhistoire',
  'Antiquité romaine',
  'Sciences et espace',
  'Biodiversité',
  'Art moderne',
  'Patrimoine industriel',
  'Montagne et Pyrénées',
  'Littoral méditerranéen',
  'Citoyenneté et institutions',
]

export const CHAMPS_OBLIGATOIRES = ['niveau', 'theme', 'nb_eleves', 'nb_accompagnateurs', 'date', 'lieu_depart']

/** Libellé d'un champ manquant, à glisser dans une phrase (« Il me manque la date »). */
export const LIBELLES_MANQUANTS: Record<string, string> = {
  niveau: 'la classe',
  theme: 'le thème ou la destination',
  nb_eleves: "le nombre d'élèves",
  nb_accompagnateurs: "le nombre d'accompagnateurs",
  date: 'la date',
  lieu_depart: 'le lieu de départ',
}

export const LIBELLES_DUREE: Record<'journee' | 'demi-journee', string> = {
  journee: 'Journée',
  'demi-journee': 'Demi-journée',
}

/** Même règle que l'API : champs obligatoires encore vides. */
export function champsManquants(d: Demande): string[] {
  const manquants: string[] = []
  if (!d.niveau) manquants.push('niveau')
  if (!d.theme && !d.destination_souhaitee) manquants.push('theme')
  if (d.nb_eleves === null) manquants.push('nb_eleves')
  if (d.nb_accompagnateurs === null) manquants.push('nb_accompagnateurs')
  if (!d.date) manquants.push('date')
  if (!d.lieu_depart?.libelle) manquants.push('lieu_depart')
  return manquants
}

/** Champs obligatoires encore manquants (tous, tant que rien n'est compris). */
export function manquantsObligatoires(d: Demande | null): string[] {
  return (d?.champs_manquants ?? CHAMPS_OBLIGATOIRES).filter((champ) => CHAMPS_OBLIGATOIRES.includes(champ))
}

export function totalVoyageurs(d: Demande | null): number | null {
  if (!d || d.nb_eleves === null || d.nb_accompagnateurs === null) return null
  return d.nb_eleves + d.nb_accompagnateurs
}

export type EtatEffectif = 'ok' | 'trop' | 'trop-peu'

export function etatEffectif(total: number): EtatEffectif {
  if (total > EFFECTIF_MAX) return 'trop'
  if (total < EFFECTIF_MIN) return 'trop-peu'
  return 'ok'
}

/** Demande complète et effectif compatible avec un groupe liO : on peut chercher les destinations. */
export function demandePrete(d: Demande | null): boolean {
  if (!d || d.champs_manquants.length > 0) return false
  const total = totalVoyageurs(d)
  return total === null || etatEffectif(total) === 'ok'
}

export function listeEnFrancais(elements: string[]): string {
  return new Intl.ListFormat('fr', { style: 'long', type: 'conjunction' }).format(elements)
}

// --- Dates (toujours en heure locale, format AAAA-MM-JJ) ---

export function dateIsoLocale(date: Date): string {
  const annee = date.getFullYear()
  const mois = String(date.getMonth() + 1).padStart(2, '0')
  const jour = String(date.getDate()).padStart(2, '0')
  return `${annee}-${mois}-${jour}`
}

export function demainIso(): string {
  const demain = new Date()
  demain.setDate(demain.getDate() + 1)
  return dateIsoLocale(demain)
}

function lireDate(iso: string): Date | null {
  const morceaux = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!morceaux) return null
  return new Date(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3]))
}

/** Nombre de jours entre aujourd'hui et la date de départ (négatif si elle est passée). */
export function joursAvantDepart(iso: string): number | null {
  const date = lireDate(iso)
  if (!date) return null
  const aujourdhui = new Date()
  aujourdhui.setHours(0, 0, 0, 0)
  return Math.round((date.getTime() - aujourdhui.getTime()) / 86_400_000)
}

const FORMAT_DATE_LONGUE = new Intl.DateTimeFormat('fr-FR', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

/** « Jeudi 12 novembre 2026 ». */
export function formaterDateLongue(iso: string): string {
  const date = lireDate(iso)
  if (!date) return iso
  const texte = FORMAT_DATE_LONGUE.format(date)
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}

const FORMAT_DATE_COURTE = new Intl.DateTimeFormat('fr-FR', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

/** « Jeu. 12 nov. 2026 », pour les cases étroites du billet. */
export function formaterDateCourte(iso: string): string {
  const date = lireDate(iso)
  if (!date) return iso
  const texte = FORMAT_DATE_COURTE.format(date)
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}

/** « 850 m » ou « 1,2 km ». */
export function formaterDistance(metres: number): string {
  if (metres < 1000) return `${Math.round(metres / 10) * 10} m`
  return `${(metres / 1000).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} km`
}
