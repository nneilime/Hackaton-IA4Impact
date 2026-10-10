// The controls of pipeline/compare.py, described for the agents (labels in French) and tied to where they can be seen
// on the scanned bordereau: an OCR field (its bbox is in pair.bordereau.provenance, 0-1000 page coordinates), the
// signature boxes (pixel bboxes), or a whole zone of the form (approximate, 0-1000 page coordinates).
import type { Check, Pair } from "../api/types"

type CheckInfo = {
  field: string
  zone: string
  provenance?: string // key in pair.bordereau.provenance
  region?: [number, number, number, number] // fallback area of the form, 0-1000
  signatures?: boolean
}

// zones of the CERFA 12278 layout, measured on the three scan layouts (0-1000 coordinates)
const HEADER: [number, number, number, number] = [10, 20, 990, 120]
const ZONE_6: [number, number, number, number] = [10, 205, 500, 330]
const ZONE_7: [number, number, number, number] = [10, 320, 990, 500]
const ZONE_10: [number, number, number, number] = [10, 500, 820, 860]
const ZONE_11: [number, number, number, number] = [810, 500, 995, 900]
const FOOTER: [number, number, number, number] = [10, 840, 995, 990]

export const CHECK_INFO: Record<string, CheckInfo> = {
  C1: { field: "Identifiant CERFA", zone: "Zone 1", provenance: "cerfa_id", region: HEADER },
  C2: { field: "N° FINESS", zone: "Zone 2", provenance: "finess", region: HEADER },
  C3: { field: "N° de lot", zone: "Zone 3", provenance: "numero_lot", region: HEADER },
  C4: { field: "N° de facture", zone: "Zone 4", provenance: "numero_facture", region: HEADER },
  C5: { field: "N° d’immatriculation", zone: "Zone 5", provenance: "numero_assure", region: HEADER },
  C6: { field: "Prestation GHS", zone: "Zone 6", region: ZONE_6 },
  C7: { field: "N° GHS", zone: "Zone 6", region: ZONE_6 },
  C8: { field: "Prestations facturées", zone: "Zone 6", region: ZONE_6 },
  C9: { field: "Cohérence des GH (fichier)", zone: "Fichier B2" },
  C10: { field: "GH des prestations", zone: "Zones 6-7", region: ZONE_6 },
  C11: { field: "Produits LPP / médicaments", zone: "Zone 7", region: ZONE_7 },
  C12: { field: "Sous-total 1+2+3", zone: "Zone 8", provenance: "sous_total_123", region: ZONE_7 },
  C13: { field: "Prestations du fichier", zone: "Zones 6-7", region: ZONE_6 },
  C14: { field: "Actes NGAP", zone: "Zone 10", region: ZONE_10 },
  C15: { field: "Codes CCAM", zone: "Zone 10", region: ZONE_10 },
  C16: { field: "GH des honoraires", zone: "Zone 10", region: ZONE_10 },
  C17: { field: "Sous-total 4 (honoraires)", zone: "Zone 12", provenance: "sous_total_4", region: ZONE_10 },
  C18: { field: "Signatures des praticiens", zone: "Zone 11", signatures: true, region: ZONE_11 },
  C19: { field: "Actes du fichier", zone: "Zone 10", region: ZONE_10 },
  C20: { field: "Montant total", zone: "Zone 13", provenance: "montant_total", region: FOOTER },
  C21: { field: "Signature du directeur", zone: "Zone 14", region: FOOTER },
  C22: { field: "Code CERFA (S3404)", zone: "Zone 15", provenance: "cerfa_code", region: FOOTER },
  X1: { field: "Structure du fichier B2", zone: "Fichier B2" },
  X2: { field: "Actes facturés en double", zone: "Zones 6-10", region: ZONE_10 },
  X3: { field: "Totaux des cases de signature", zone: "Zone 11", signatures: true, region: ZONE_11 },
}

export function checkField(check: Check): string {
  return CHECK_INFO[check.code]?.field ?? check.label
}

export function checkZone(check: Check): string {
  return CHECK_INFO[check.code]?.zone ?? ""
}

export const SOURCE_LABEL: Record<Check["expected_source"], string> = {
  b2: "Facture B2",
  form: "Bordereau",
  rule: "Règle CERFA",
  form_calc: "Calcul sur le bordereau",
  scan: "Analyse du scan",
}

export const RISK_LABEL: Record<Check["risk"], string> = {
  fraud: "Risque de fraude",
  error: "Erreur de facturation",
  compliance: "Conformité",
}

export const STATUS_ORDER: Record<Check["status"], number> = { FAIL: 0, UNVERIFIABLE: 1, PASS: 2 }

/** Areas to highlight on the scan for a check. Units say how to read them. */
export type Highlight = { box: [number, number, number, number]; units: "norm" | "px"; label: string }

export function checkHighlights(check: Check, pair: Pair): Highlight[] {
  const info = CHECK_INFO[check.code]
  if (!info) return []
  if (info.signatures && pair.bordereau?.signature_boxes.some((b) => b.bbox)) {
    const boxes = pair.bordereau.signature_boxes.filter(
      (b) => b.bbox && (b.signed || b.rows > 0 || b.problems.length > 0),
    )
    return boxes.map((b) => ({ box: b.bbox!, units: "px", label: `Case ${b.box}` }))
  }
  const provenance = info.provenance ? pair.bordereau?.provenance?.[info.provenance] : null
  if (provenance) return [{ box: provenance.bbox, units: "norm", label: info.zone }]
  if (info.region) return [{ box: info.region, units: "norm", label: info.zone }]
  return []
}

export const CATEGORY_LABEL: Record<string, string> = {
  none: "Conforme",
  ocr_error: "Erreur de lecture (OCR)",
  billing_error: "Erreur de facturation",
  suspected_fraud: "Suspicion de fraude",
}

export const EVENT_LABEL: Record<string, string> = {
  created: "Dossier créé",
  reprocessed: "Analyse mise à jour",
  assigned: "Attribué",
  released: "Libéré",
  escalated: "Avis manager demandé",
  check_reviewed: "Contrôle annoté",
  resolved: "Clôturé",
  reopened: "Rouvert",
}
