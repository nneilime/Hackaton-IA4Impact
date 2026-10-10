import { matchPath } from 'react-router-dom'

// La ligne liO du parcours : six gares, de l'idée de sortie au retour d'expérience.
// Le shell s'en sert pour la ligne des étapes et pour la barre de guidage.

export interface Etape {
  libelle: string
  /** Pourquoi la gare n'est pas encore desservie (titre de l'étape inactive). */
  verrou: string
}

export const ETAPES: readonly Etape[] = [
  { libelle: 'Mon projet', verrou: '' },
  { libelle: 'Où aller ?', verrou: "Décrivez d'abord votre projet à Tchouette." },
  { libelle: 'Comment y aller ?', verrou: "Choisissez d'abord une destination." },
  { libelle: 'Comparer', verrou: "Ajoutez d'abord un trajet à la comparaison." },
  { libelle: 'Pré-réserver', verrou: "Retenez d'abord un trajet." },
  { libelle: 'Mon retour', verrou: 'Disponible une fois la demande envoyée.' },
]

/** Un écran du parcours : sa route, son étape et ce que Tchouette en dit. */
export interface Ecran {
  motif: string
  /** Index dans ETAPES. */
  etape: number
  /** Consigne de l'étape, à l'impératif (15 mots au plus). */
  consigne: string
  /** Astuces de Tchouette, une par visite, à tour de rôle (15 mots au plus). */
  astuces: readonly string[]
}

export const ECRANS: readonly Ecran[] = [
  {
    motif: '/',
    etape: 0,
    consigne: 'Racontez votre projet de sortie à Tchouette',
    astuces: [
      "Donnez la classe et l'effectif : je compte les places pour vous.",
      'Pas encore de lieu ? Un thème du programme me suffit pour proposer.',
      'Parlez-moi comme à un collègue, je range tout dans la fiche projet.',
    ],
  },
  {
    motif: '/destinations',
    etape: 1,
    consigne: 'Choisissez la destination qui sert votre projet',
    astuces: [
      "L'intérêt pédagogique dit pourquoi ce lieu colle à votre programme.",
      "Regardez la gare d'arrivée : moins de marche, plus de visite.",
      'Vous hésitez ? Choisissez-en une, le retour arrière ne perd rien.',
    ],
  },
  {
    motif: '/trajets/:siteId',
    etape: 2,
    consigne: 'Choisissez les trains qui conviennent à la classe',
    astuces: [
      'La jauge de places montre si toute la classe voyage ensemble.',
      "Ajoutez jusqu'à trois trajets à la comparaison pour trancher sereinement.",
      "Un train moins chargé, c'est une classe assise et calme.",
    ],
  },
  {
    motif: '/comparer',
    etape: 3,
    consigne: 'Comparez vos trajets côte à côte et retenez le meilleur',
    astuces: [
      "Le meilleur score ne fait pas tout : vérifiez aussi l'heure de retour.",
      "L'indice de confiance dit si les places ont des chances de rester libres.",
      'Retenez un trajet : il ne restera que votre e-mail à donner.',
    ],
  },
  {
    motif: '/pre-reservation',
    etape: 4,
    consigne: 'Vérifiez le billet récapitulatif puis envoyez votre demande',
    astuces: [
      "Rien n'est payé : un chargé de clientèle liO valide votre demande.",
      'Donnez une adresse e-mail que vous consultez souvent : la réponse y arrive.',
    ],
  },
  {
    motif: '/dossier/:reference',
    etape: 4,
    consigne: 'Suivez la réponse de liO à votre demande',
    astuces: [
      'Gardez la référence du dossier : elle suffit pour le retrouver.',
      'Une contre-proposition ? Comparez-la à votre trajet avant de répondre.',
    ],
  },
  {
    motif: '/retour/:reference',
    etape: 5,
    consigne: 'Racontez la sortie pour aider les prochaines classes',
    astuces: [
      'Trois minutes suffisent : vos notes guident les collègues.',
      "Un quai bondé, un retard ? Dites-le, mes conseils s'affinent.",
    ],
  },
]

/** L'écran du parcours qui correspond à l'adresse, ou `null` (page introuvable). */
export function ecranDuChemin(chemin: string): Ecran | null {
  return ECRANS.find((ecran) => matchPath({ path: ecran.motif, end: true }, chemin)) ?? null
}

/** Ce que le voyage en cours a déjà débloqué. */
export interface Avancement {
  demande: boolean
  siteId: string | null
  comparaison: number
  propositionChoisie: boolean
  reference: string | null
}

/** Lien de l'étape si elle est déjà accessible, sinon `null`. */
export function lienEtape(index: number, a: Avancement): string | null {
  switch (index) {
    case 0:
      return '/'
    case 1:
      return a.demande ? '/destinations' : null
    case 2:
      return a.siteId ? `/trajets/${encodeURIComponent(a.siteId)}` : null
    case 3:
      return a.comparaison > 0 ? '/comparer' : null
    case 4:
      if (a.propositionChoisie) return '/pre-reservation'
      return a.reference ? `/dossier/${encodeURIComponent(a.reference)}` : null
    case 5:
      return a.reference ? `/retour/${encodeURIComponent(a.reference)}` : null
    default:
      return null
  }
}

/* ---------- Rotation des astuces ---------- */

// Une visite = une entrée d'historique (location.key). Le rang n'avance qu'une fois
// par visite, même si React rend deux fois (StrictMode) : l'opération est idempotente.
const visites = new Map<string, { cle: string; rang: number }>()
const depart = Math.floor(Math.random() * 3)

/** Rang de l'astuce à montrer pour cette visite de l'écran. */
export function rangAstuce(ecran: Ecran, cleVisite: string): number {
  const precedente = visites.get(ecran.motif)
  if (precedente?.cle === cleVisite) return precedente.rang % ecran.astuces.length
  const rang = precedente ? precedente.rang + 1 : depart
  visites.set(ecran.motif, { cle: cleVisite, rang })
  return rang % ecran.astuces.length
}
