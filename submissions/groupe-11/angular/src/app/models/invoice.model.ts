// Types du contrat d'API (voir PROMPT_FRONTEND.md). Les noms de champs suivent le backend, en français.

export type Statut = 'OK' | 'KO' | 'A_VERIFIER';

/** [x0, y0, x1, y1] en pixels de l'image d'origine */
export type Box = [number, number, number, number];

export interface Decision {
  statut: 'valide' | 'rejete';
  commentaire: string;
  overrides: string[];
}

/** Élément de GET /api/factures */
export interface FactureResume {
  id: string;
  nb_ko: number;
  nb_a_verifier: number;
  /** false tant que extract.py n'a pas analysé le scan : la facture ne doit pas être montrée à l'agent */
  ocr: boolean;
  /** true once the agent has validated or rejected it (backend/traitees.txt) */
  traitee: boolean;
  /** Difficulté de contrôle estimée, 0 (triviale) à 100 (la plus dure). 100 si absent (ancien backend). */
  difficulte: number;
  /** Bandeau lisible : Facile, Modérée, Moyenne, Difficile, Très difficile */
  niveau: string;
}

/** An act or prestation present in one document only. `sens`: the document it is missing from */
export interface Ecart {
  code: string;
  sens: 'absent_scan' | 'absent_b2';
  message: string;
}

export interface Check {
  code: string;
  libelle: string;
  statut: Statut;
  attendu: string;
  lu: string;
  zones: number[];
  boxes: Box[];
  /** Printed labels next to the values (e.g. "sous-total 4"): shown in the card crops, never highlighted */
  contexte?: Box[];
  /** List checks (C7, C9, C10b, C11), when KO: one line per item found in only one of the two documents */
  ecarts?: Ecart[];
  /** Confiance OCR de la valeur lue (min des scores de ligne sur les zones, 0–1), null si inconnue */
  confiance: number | null;
}

/** GET /api/factures/{id} */
export interface FactureDetail {
  id: string;
  image: { url: string; largeur: number; hauteur: number };
  checks: Check[];
  traitee: boolean;
  difficulte: number;
  niveau: string;
}
