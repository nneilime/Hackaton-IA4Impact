// Libellés métier (version 3.0) : l'agent lit une phrase, pas un code. Les références techniques (R12, statut
// interne) restent disponibles dans « Voir les détails ».
import { RuleResult, RuleStatus } from "./api";

export const ISSUE_TITLE: Record<string, string> = {
  R01: "Identifiant du formulaire différent", R02: "N° FINESS différent", R03: "N° de lot différent",
  R04: "N° de facture différent", R05: "N° d'assuré différent", R06: "Prestation GHS absente du bordereau",
  R07: "N° GHS différent", R08: "Prestation du bordereau absente du fichier", R09: "N° GH incohérent dans le fichier",
  R10: "N° GH d'un produit différent du GHS", R11: "Produit (LPP, pharmacie) du bordereau absent du fichier",
  R12: "Montant des prestations différent", R13: "Prestation facturée absente du bordereau",
  R14: "Acte du bordereau absent du fichier", R15: "Code CCAM du bordereau absent du fichier",
  R16: "N° GH d'un acte différent du GHS", R17: "Montant des honoraires différent",
  R18: "Signature d'un praticien manquante", R19: "Acte facturé absent du bordereau",
  R20: "Montant total incohérent", R21: "Signature du directeur manquante", R22: "Code CERFA différent",
};

export const SUBJECT: Record<string, string> = {
  R01: "identifiant du formulaire", R02: "n° FINESS", R03: "n° de lot", R04: "n° de facture", R05: "n° d'assuré",
  R06: "prestation GHS", R07: "n° GHS", R08: "prestations de la zone 6", R09: "n° GH du fichier",
  R10: "n° GH des produits", R11: "produits de la zone 7", R12: "montant des prestations",
  R13: "prestations facturées", R14: "actes de la zone 10", R15: "codes CCAM", R16: "n° GH des actes",
  R17: "montant des honoraires", R18: "signatures des praticiens", R19: "actes facturés", R20: "montant total",
  R21: "signature du directeur", R22: "code CERFA",
};

export const PLAIN_STATUS: Record<RuleStatus, string> = {
  CONFORME: "Conforme", ANOMALIE: "Écart", NON_VERIFIABLE: "À vérifier manuellement",
  NON_APPLICABLE: "Sans objet", ERREUR_TECHNIQUE: "Erreur technique",
};

export function issueTitle(r: RuleResult): string {
  if (r.status === "ANOMALIE") return ISSUE_TITLE[r.rule_id] || r.title;
  if (r.status === "NON_VERIFIABLE") return `À vérifier manuellement : ${SUBJECT[r.rule_id] || r.title}`;
  if (r.status === "ERREUR_TECHNIQUE") return `Contrôle impossible : ${SUBJECT[r.rule_id] || r.title}`;
  return r.title;
}

/** Pourquoi le moteur doute, en une phrase simple. */
export function plainDoubt(reason?: string | null): string {
  if (!reason) return "";
  if (/ex æquo|contradictoire/.test(reason)) return "Les lectures du document se contredisent.";
  if (/désaccord|divergent/.test(reason)) return "Les deux moteurs de lecture ne lisent pas la même valeur.";
  if (/localisation/.test(reason)) return "La case n'a pas pu être localisée avec certitude sur le scan.";
  if (/découpage|tableau/.test(reason)) return "Les lignes du tableau n'ont pas pu être séparées avec certitude.";
  if (/vide/.test(reason)) return "La case paraît vide sur le bordereau.";
  if (/illisible|aucune lecture/.test(reason)) return "La valeur est illisible sur le bordereau.";
  if (/isolée|seul passage/.test(reason)) return "Une seule lecture du document : à confirmer.";
  return reason;
}

export const DECISION_LABEL: Record<string, string> = {
  examen: "Examiné", confirmation: "Écart confirmé", faux_positif: "Faux positif", revue_complementaire: "À revoir",
  commentaire: "Commentaire", statut: "Statut", escalade: "Transmis au superviseur", priorite: "Priorité",
  decision_motivee: "Décision motivée", affectation: "Affectation", annulation: "Décision annulée",
};
