import type { Niveau, Statut } from '../../api/types'

/** Taille maximale d'un groupe scolaire dans un train liO (fiche de cadrage). */
export const MAX_VOYAGEURS_GROUPE = 50

const FORMAT_DATE_LONGUE = new Intl.DateTimeFormat('fr-FR', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})
const FORMAT_JOUR = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
const FORMAT_JOUR_SEMAINE = new Intl.DateTimeFormat('fr-FR', { weekday: 'short' })
const FORMAT_MOIS_ANNEE = new Intl.DateTimeFormat('fr-FR', { month: 'short', year: 'numeric' })
const FORMAT_HEURE = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' })

function majuscule(texte: string) {
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}

/** « 2026-11-12 » → « Jeudi 12 novembre 2026 ». */
export function formaterDateLongue(date: string | null | undefined): string {
  if (!date) return 'Date à préciser'
  const [annee, mois, jour] = date.slice(0, 10).split('-').map(Number)
  if (!annee || !mois || !jour) return date
  return majuscule(FORMAT_DATE_LONGUE.format(new Date(annee, mois - 1, jour)))
}

/** « 2026-11-12 » → { jourSemaine: « jeu. », jour: « 12 », moisAnnee: « nov. 2026 » } pour le talon du billet. */
export function partiesDate(
  date: string | null | undefined,
): { jourSemaine: string; jour: string; moisAnnee: string } | null {
  if (!date) return null
  const [annee, mois, jour] = date.slice(0, 10).split('-').map(Number)
  if (!annee || !mois || !jour) return null
  const valeur = new Date(annee, mois - 1, jour)
  return {
    jourSemaine: FORMAT_JOUR_SEMAINE.format(valeur),
    jour: String(jour),
    moisAnnee: FORMAT_MOIS_ANNEE.format(valeur),
  }
}

/** Horodatage ISO → « 10 octobre 2026 à 14:32 ». */
export function formaterHorodatage(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return `${FORMAT_JOUR.format(date)} à ${FORMAT_HEURE.format(date)}`
}

/** 78 → « 1 h 18 », 45 → « 45 min ». */
export function formaterDuree(minutes: number): string {
  if (!Number.isFinite(minutes) || minutes < 0) return '—'
  const heures = Math.floor(minutes / 60)
  const reste = Math.round(minutes % 60)
  if (heures === 0) return `${reste} min`
  if (reste === 0) return `${heures} h`
  return `${heures} h ${String(reste).padStart(2, '0')}`
}

/** Minutes entre deux heures « HH:MM » du même jour, ou null si illisible. */
export function minutesEntre(debut: string, fin: string): number | null {
  const lire = (heure: string) => {
    const [h, m] = heure.split(':').map(Number)
    return Number.isFinite(h) && Number.isFinite(m) ? h * 60 + m : null
  }
  const a = lire(debut)
  const b = lire(fin)
  if (a === null || b === null) return null
  return b - a
}

const FORMAT_NOMBRE = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 })

/** 72.45 → « 72,5 » : virgule décimale française, une décimale au plus. */
export function formaterNombre(nombre: number): string {
  return FORMAT_NOMBRE.format(nombre)
}

export function pluriel(nombre: number, singulier: string, plurielTexte: string) {
  return `${nombre} ${nombre > 1 ? plurielTexte : singulier}`
}

export function libelleCorrespondances(nombre: number) {
  if (nombre <= 0) return 'Direct'
  return pluriel(nombre, 'correspondance', 'correspondances')
}

export const LIBELLES_NIVEAU_INDICE: Record<Niveau, string> = {
  vert: 'Confiance élevée',
  orange: 'Confiance moyenne',
  rouge: 'Confiance faible',
}

export const LIBELLES_NIVEAU_ACCES: Record<Niveau, string> = {
  vert: 'Accès simple',
  orange: 'Accès à anticiper',
  rouge: 'Accès difficile',
}

/** Libellés des étapes de l'historique du dossier. */
export const LIBELLES_ETAPE: Record<Statut, string> = {
  OPTION: 'Option posée sur les places',
  PRE_RESERVATION: 'Demande de pré-réservation transmise',
  CONFIRMATION: 'Confirmation du chargé de clientèle',
  CONTRE_PROPOSITION: 'Contre-proposition reçue',
  ANNULE: 'Demande annulée',
}

/** Position du statut sur la frise PROPOSITION → OPTION → PRÉ-RÉSERVATION → CONFIRMATION. */
export function etapeFrise(statut: Statut): number {
  switch (statut) {
    case 'OPTION':
      return 1
    case 'CONFIRMATION':
      return 3
    default:
      return 2
  }
}

const MOTIF_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

/** Message d'erreur à afficher sous le champ, ou null si l'adresse est valable. */
export function erreurEmail(email: string): string | null {
  const valeur = email.trim()
  if (!valeur) return 'Indiquez une adresse e-mail : la réponse du chargé de clientèle y sera envoyée.'
  if (!MOTIF_EMAIL.test(valeur)) return 'Cette adresse ne semble pas valide. Exemple : prenom.nom@ac-toulouse.fr'
  return null
}
