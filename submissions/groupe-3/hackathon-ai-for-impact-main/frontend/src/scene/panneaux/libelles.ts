import type { Niveau } from '../../api/types'

/** Vocabulaire d'enseignant : jamais de code R1 à R10 en clair. Les messages détaillés viennent du back. */
export const LIBELLES_CONTROLE_ENSEIGNANT: Record<string, string> = {
  R1: 'Train ouvert aux groupes',
  R2: 'Place dans le train',
  R3: 'Marche depuis la gare',
  R4: 'Marge avant la visite',
  R5: 'Retour à l’heure prévue',
  R6: 'Horaires de l’offre groupe (9 h à 16 h)',
  R7: 'Demande faite assez tôt (21 jours avant)',
  R8: 'Établissement en Occitanie',
  R9: 'Autres groupes sur le même train',
  R10: 'Capacité d’accueil du site',
}

export const LIBELLES_CRITERE_ENSEIGNANT: Record<string, string> = {
  'Capacité et confort': 'Place et confort dans le train',
  Régularité: 'Trains à l’heure',
  'Risque de suppression': 'Risque de train supprimé',
  'Faisabilité des horaires': 'Horaires adaptés à la visite',
  'Accès gare → site': 'Marche depuis la gare',
  'Adéquation pédagogique': 'Intérêt pour votre projet',
  'Satisfaction et coup de cœur': 'Avis des autres classes',
}

/** Statut d'un contrôle, dit simplement (la couleur et l'icône l'accompagnent toujours). */
export const STATUT_CONTROLE: Record<Niveau, string> = {
  vert: 'Conforme',
  orange: 'À surveiller',
  rouge: 'Bloquant',
}

export const PHRASE_INDICE: Record<Niveau, string> = {
  vert: 'Ce trajet est fiable pour votre classe.',
  orange: 'Ce trajet est possible, avec quelques points à surveiller.',
  rouge: 'Ce trajet n’est pas assez fiable pour votre groupe.',
}

export const LIBELLES_INDICE: Record<Niveau, string> = {
  vert: 'Confiance élevée',
  orange: 'Confiance moyenne',
  rouge: 'Confiance faible',
}

export const LIBELLES_ACCES: Record<Niveau, string> = {
  vert: 'Accès simple',
  orange: 'Accès à anticiper',
  rouge: 'Accès difficile',
}

export const LIBELLES_PLACES: Record<Niveau, string> = {
  vert: 'Places suffisantes',
  orange: 'Places justes',
  rouge: 'Places insuffisantes',
}

export const CLASSES_BARRE_PLACES: Record<Niveau, string> = {
  vert: 'progress progress-success h-2.5 w-full',
  orange: 'progress progress-warning h-2.5 w-full',
  rouge: 'progress progress-error h-2.5 w-full',
}
