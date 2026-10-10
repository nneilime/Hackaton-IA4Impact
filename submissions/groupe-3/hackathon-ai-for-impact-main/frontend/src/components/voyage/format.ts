import type { AccesGareSite, Controle, Demande, Niveau } from '../../api/types'

/** Ordre de gravité des niveaux : utile pour trier et comparer. */
export const RANG_NIVEAU: Record<Niveau, number> = { vert: 0, orange: 1, rouge: 2 }

/** Le moins bon des deux niveaux (règle de la fiche : on retient le train le plus fragile). */
export function niveauLePlusBas(a: Niveau, b: Niveau): Niveau {
  return RANG_NIVEAU[a] >= RANG_NIVEAU[b] ? a : b
}

/** « 1 h 15 », « 2 h », « 45 min ». */
export function formaterDuree(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined || Number.isNaN(minutes)) return 'Durée à préciser'
  const total = Math.max(0, Math.round(minutes))
  const heures = Math.floor(total / 60)
  const reste = total % 60
  if (heures === 0) return `${reste} min`
  if (reste === 0) return `${heures} h`
  return `${heures} h ${String(reste).padStart(2, '0')}`
}

function lireDate(iso: string): Date | null {
  // Midi local : évite qu'un fuseau horaire fasse reculer la date d'un jour.
  const date = new Date(`${iso.slice(0, 10)}T12:00:00`)
  return Number.isNaN(date.getTime()) ? null : date
}

/** « jeudi 12 novembre 2026 ». */
export function formaterDateLongue(iso: string | null | undefined): string {
  if (!iso) return 'Date à préciser'
  const date = lireDate(iso)
  if (!date) return iso
  return date.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

/** « jeu. 12 nov. ». */
export function formaterDateCourte(iso: string | null | undefined): string {
  if (!iso) return 'Date à préciser'
  const date = lireDate(iso)
  if (!date) return iso
  return date.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' })
}

/** Minutes écoulées entre deux heures « HH:MM » (passe minuit si besoin). */
export function minutesEntre(debut: string, fin: string): number | null {
  const [hd, md] = debut.split(':').map(Number)
  const [hf, mf] = fin.split(':').map(Number)
  if ([hd, md, hf, mf].some((n) => Number.isNaN(n))) return null
  const ecart = hf * 60 + mf - (hd * 60 + md)
  return ecart < 0 ? ecart + 24 * 60 : ecart
}

export function pluriel(nombre: number, singulier: string, forme?: string): string {
  return nombre > 1 ? (forme ?? `${singulier}s`) : singulier
}

/** « Direct », « 1 correspondance », « 2 correspondances ». */
export function libelleCorrespondances(nombre: number): string {
  if (nombre <= 0) return 'Direct'
  return `${nombre} ${pluriel(nombre, 'correspondance')}`
}

/** Élèves et accompagnateurs réunis. */
export function nombreVoyageurs(demande: Demande | null): number | null {
  if (!demande) return null
  if (demande.nb_eleves === null && demande.nb_accompagnateurs === null) return null
  return (demande.nb_eleves ?? 0) + (demande.nb_accompagnateurs ?? 0)
}

/** « 18 min à pied », « 25 min en transport urbain ». */
export function libelleAcces(acces: AccesGareSite): string {
  return acces.mode === 'pied'
    ? `${acces.minutes_groupe} min à pied`
    : `${acces.minutes_groupe} min en transport urbain`
}

export function libelleDureeSortie(duree: Demande['duree']): string | null {
  if (duree === 'journee') return 'Journée'
  if (duree === 'demi-journee') return 'Demi-journée'
  return null
}

/** « 8 », « 12,5 » : points de l'indice, à la française. */
export function formaterPoints(points: number): string {
  return points.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
}

/** Nombre de contrôles par niveau, pour le titre du collapse. */
export function compterControles(controles: Controle[]): Record<Niveau, number> {
  const compte: Record<Niveau, number> = { vert: 0, orange: 0, rouge: 0 }
  for (const controle of controles) compte[controle.niveau] += 1
  return compte
}
