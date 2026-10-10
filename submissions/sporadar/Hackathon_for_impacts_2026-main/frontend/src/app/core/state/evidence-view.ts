import type { Evidence } from '../api/models';

/**
 * Tout ce que le panneau de preuve a besoin d'afficher pour UNE valeur, quel que soit le gabarit d'origine.
 * Le panneau est unique : chaque gabarit construit simplement cet objet au clic.
 */
export interface EvidenceView {
  /** Ce que la valeur représente, ex. « Statut au Canada », « Dose · Fraisier × Otiorhynque ». */
  title: string;
  evidence: Evidence;
  /** Valeur telle que normalisée (jamais convertie). */
  valueNormalized?: string | null;
  /** Texte d'origine de la source, dans sa langue. */
  valueOriginal?: string | null;
  /** Nom par lequel la ligne a été trouvée (alias compris). */
  matchedVia?: string | null;
  /** Confiance IA propre à cette valeur ; à défaut, celle de la preuve. */
  confidence?: number | null;
}
