// Shapes returned by the FastAPI backend (api.py at the repository root).
// Amounts are integer cents, dates ISO strings.

export type Role = "reviewer" | "admin"
export type Verdict = "CORRECT" | "ISSUES"
export type TicketStatus = "open" | "assigned" | "resolved"
export type CheckStatus = "PASS" | "FAIL" | "UNVERIFIABLE"
export type FinalCategory = "none" | "ocr_error" | "billing_error" | "suspected_fraud"

export type User = {
  id: number
  username: string
  display_name: string | null
  role: Role
  active: boolean
  created_at: string
}

export type Me = User & {
  queue: { open: number; escalated: number; mine: number; resolved: number; resolved_by_me: number }
  max_active: number
}

export type ClinicStats = {
  id: number
  finess: string
  name: string | null
  postal_code: string | null
  city: string | null
  department: string | null
  region: string | null
  caisse: string | null
  lat: number | null
  lon: number | null
  invoices: number
  issues: number
  at_risk: number
  billed: number
  discrepancy: number
  pending: number
  confirmed_fraud: number
  reports: number
  error_rate: number
  flagged: boolean
}

export type ClinicReport = {
  id: number
  reason: string
  comment: string | null
  at: string
  user: string
  user_name: string | null
}

export type ClinicDetail = ClinicStats & { reports_list: ClinicReport[] }

export type InvoiceRow = {
  pair_id: number
  name: string
  clinic_id: number
  algo_verdict: Verdict
  risk_score: number
  has_image: number
  ticket_id: number
  ticket_status: TicketStatus
  final_verdict: Verdict | null
  final_category: FinalCategory | null
  escalated: number
  verdict: Verdict
  numero_facture: string | null
  date_fichier: string | null
  amount: number
  discrepancy: number
  failed_checks: number
  fraud_signals: number
}

export type Overview = {
  invoices: number
  issues: number
  algo_issues: number
  resolved: number
  pending: number
  escalated: number
  confirmed_fraud: number
  confirmed_fraud_amount: number
  at_risk: number
  billed: number
  discrepancy: number
  agreed: number
  clinics: number
  flagged_clinics: number
  error_rate: number
  agreement_rate: number | null
  reports: number
  top_failed_checks: { code: string; label: string; count: number }[]
}

export type TicketSummary = {
  id: number
  pair_id: number
  status: TicketStatus
  assignee_id: number | null
  final_verdict: Verdict | null
  final_category: FinalCategory | null
  final_comment: string | null
  resolved_by: number | null
  resolved_at: string | null
  created_at: string
  updated_at: string
  escalated: number
  escalation_comment: string | null
  pair_name: string
  algo_verdict: Verdict
  risk_score: number
  clinic_id: number | null
  clinic_name: string | null
  numero_facture: string | null
  date_fichier: string | null
  amount: number
  assignee: string | null
  assignee_name: string | null
  resolved_by_name: string | null
  failed_checks: number
  fraud_signals: string | null
}

export type Check = {
  code: string
  label: string
  category: string
  risk: "fraud" | "error" | "compliance"
  status: CheckStatus
  expected: string | null
  found: string | null
  detail: string
  ocr_suspect: boolean
  /** where each value comes from: the B2 file, the form (OCR), a CERFA rule, a calculation on the form, the scan */
  expected_source: ValueSource
  found_source: ValueSource
}

export type ValueSource = "b2" | "form" | "rule" | "form_calc" | "scan"

export type SignatureBox = {
  box: number
  bbox: [number, number, number, number] | null
  ink_ratio: number | null
  signed: boolean | null
  text: string | null
  text_source: string | null
  printed_executant: string | null
  printed_name: string | null
  printed_amount: number | null
  rows: number
  rows_by: string | null
  row_executants: string[]
  computed_amount: number | null
  executant_ok: boolean | null
  amount_ok: boolean | null
  problems: string[]
}

export type Provenance = Record<string, { raw: string; strategy: string; bbox: [number, number, number, number] } | null>

export type Pair = {
  id: number
  name: string
  status: string
  image_path: string | null
  algo_verdict: Verdict
  risk_score: number
  created_at: string
  updated_at: string
  ticket_id: number | null
  clinic: (Omit<ClinicStats, "invoices" | "issues" | "at_risk" | "billed" | "discrepancy" | "pending" | "confirmed_fraud" | "reports" | "error_rate" | "flagged">) | null
  checks: Check[]
  facture: {
    numero_tiers: string | null
    numero_lot: string | null
    numero_facture: string | null
    numero_assure: string | null
    numero_gh: string | null
    total_prestations: number | null
    total_honoraires: number | null
    date_fichier: string | null
  } | null
  bordereau: {
    cerfa_id: string | null
    finess: string | null
    numero_lot: string | null
    numero_facture: string | null
    numero_assure: string | null
    sous_total_123: number | null
    sous_total_4: number | null
    montant_total: number | null
    cerfa_code: string | null
    director_signature: boolean | null
    ocr_truncated: boolean | null
    provenance: Provenance | null
    signature_boxes: SignatureBox[]
  } | null
  issues: { step: string; severity: string; field: string | null; message: string }[]
}

export type TicketEvent = { action: string; detail: string | null; at: string; user: string | null; user_name: string | null }

export type CheckReview = { check_code: string; outcome: "confirmed" | "dismissed"; comment: string | null; at: string; user: string }

export type TicketDetail = TicketSummary & {
  events: TicketEvent[]
  check_reviews: CheckReview[]
  pair: Pair
  documents: { facture: string; ocr: string; image: string }
}
