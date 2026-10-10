// The page's types: the logged-in demo customer (GET /api/customer, demo_customer.py),
// and what the assistant's tools (bank_tools.py) turn into on the page.

export type AccountType = "COMPTE_COURANT" | "LIVRET_A"
// LOCKED: temporary, the customer can unlock it. OPPOSED: definitive (opposition).
export type CardStatus = "ACTIVE" | "LOCKED" | "OPPOSED"
export type TxStatus = "COMPLETED" | "PENDING"

export interface Account {
  id: string
  type: AccountType
  label: string
  maskedIban: string
  balanceCents: number
  status: "OPEN" | "BLOCKED"
}

export interface Transaction {
  id: string
  accountId: string
  merchant: string
  label: string // raw bank statement label
  amountCents: number
  timestamp: string
  category: string
  status: TxStatus
  description: string
  channel: string
}

export interface Card {
  id: string
  accountId: string
  label: string
  kind: "PHYSICAL" | "VIRTUAL"
  network: "VISA" | "MASTERCARD"
  maskedNumber: string
  holder: string
  expiry: string
  status: CardStatus
  paymentLimitCents: number
  withdrawalLimitCents: number
  spentThisPeriodCents: number
  onlinePayments: boolean
  contactless: boolean
}

export interface CustomerData {
  customer: { id: string; firstName: string; displayName: string; initials: string }
  accounts: Account[]
  cards: Card[]
  transactions: Transaction[]
}

export type Mode = "voice" | "text"

// A loan simulation, as simulate_loan returns it.
export interface Loan {
  purpose: string
  amount_eur: number
  months: number
  annual_rate_percent: number
  monthly_payment_eur: number
  total_interest_eur: number
  debt_ratio_percent: number
  [key: string]: unknown
}

// A démarche done with the assistant, stored by the server for this session (see
// demarches.ts): an opposition, a loan or a complaint passed on, a demo request...
export interface Demarche {
  reference: string
  kind: string // start_request's kind, or loan, complaint, transfer
  title: string
  detail: string
  status: string // done, requested, transmitted, demo_request (demarches.ts STATUS_LABEL)
  pdf?: { url: string; name: string }
  at: number // Date.now()
  mode: Mode | "app"
}

/** An action Compass prepared (bank_tools.py), done only after the customer's yes. */
export interface PendingAction {
  id: string
  kind: string
  title: string
  details: string[]
  via: Mode // the conversation it belongs to: the yes goes there
}
export type ActionState = "pending" | "done" | "cancelled" | "failed"

/** An operation as search_transactions returns it. */
export interface FoundTransaction {
  id: string
  date: string
  merchant: string
  label: string
  amount: string
  amount_eur: number
  channel: string
  status: string
}

/** Rich blocks shown in the conversation. */
export type AssistantCard =
  | { kind: "loan"; loan: Loan }
  | { kind: "demarche"; demarche: Demarche }
  | { kind: "confirm"; action: PendingAction }
  | { kind: "login"; reason: string }
  | { kind: "accounts"; accounts: { label: string; balance_eur: number; iban_end: string }[] }
  | { kind: "transactions"; transactions: FoundTransaction[]; count: number }

// ---------------------------------------------------------------------------
// The app's pages, and what can be highlighted when the assistant's work shows on one.
// ---------------------------------------------------------------------------
export const APP_PAGES = {
  accueil: "/",
  comptes: "/comptes",
  operations: "/operations",
  cartes: "/cartes",
  demarches: "/demarches",
  profil: "/profil",
} as const
export type AppPage = keyof typeof APP_PAGES

export type Highlight = "balance" | "card-status" | "card-security" | "transaction" | "demarche" | "accessibility"

/** What the assistant did, for the demo panel's log. */
export interface TraceEvent {
  id: string // the tool call's call_id
  at: number
  channel: Mode
  name: string
  label: string
  outcome: "running" | "ok" | "waiting" | "error" | "cancelled"
  detail: string
}
