export interface CheckRepartition {
  code: string;
  libelle: string;
  nb_ko: number;
  nb_a_verifier: number;
}

export interface CategoryRepartition {
  categorie: string;
  nb_invoices_ko: number;
  poids: number;
  description: string;
}

export interface DifficulteNiveau {
  niveau: string;
  nb: number;
}

export interface DifficulteGlobale {
  moyenne: number | null;
  repartition: DifficulteNiveau[];
}

export interface anomalieStats {
  nb_factures_total: number;
  nb_factures_ko: number;
  nb_factures_a_verifier: number;
  montant_total_a_risque: number;
  score_anomalie: number;
  repartition_par_categorie: CategoryRepartition[];
  repartition_par_check: CheckRepartition[];
  difficulte_globale?: DifficulteGlobale;
}

export interface EtablissementStats {
  finess: string;
  nb_factures: number;
  nb_ko: number;
  nb_a_verifier: number;
  taux_conformite: number;
  montant_a_risque: number;
  score_anomalie: number;
  difficulte_moyenne?: number | null;
  niveau_moyen?: string | null;
}

export interface DashboardStats {
  anomalie: anomalieStats;
  etablissements: EtablissementStats[];
}

// OCR status
export interface OcrFactureStatus {
  id: string;
  traite: boolean;
  zone_scores: Record<string, number> | null;
  zones_illisibles: number[];
}

export interface OcrStatus {
  nb_total: number;
  nb_traites: number;
  factures: OcrFactureStatus[];
}
