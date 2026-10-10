// Thin fetch wrapper around the backend. Requests go to /api, which Vite proxies to FastAPI (see vite.config.ts).
import type {
  ClinicDetail,
  ClinicStats,
  FinalCategory,
  InvoiceRow,
  Me,
  Overview,
  TicketDetail,
  TicketStatus,
  TicketSummary,
  User,
  Verdict,
} from "./types"

const BASE = "/api"
const TOKEN_KEY = "controle-factures.token"

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

let token: string | null = readToken()
let onUnauthorized: (() => void) | null = null

function readToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(value: string | null) {
  token = value
  try {
    if (value) window.localStorage.setItem(TOKEN_KEY, value)
    else window.localStorage.removeItem(TOKEN_KEY)
  } catch {
    // storage unavailable (private window): the session lasts until the page is closed
  }
}

export function hasToken() {
  return token !== null
}

/** Called when the backend rejects the session, so the app can go back to the login page. */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler
}

function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === "string") return detail
    if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? String(d)).join(" · ")
  }
  return fallback
}

async function request<T>(path: string, options: { method?: string; body?: unknown; text?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`
  if (options.body !== undefined) headers["Content-Type"] = "application/json"
  let response: Response
  try {
    response = await fetch(BASE + path, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch {
    throw new ApiError(0, "Serveur injoignable : l'API est-elle lancée (uvicorn api:app --port 8000) ?")
  }
  if (response.status === 401 && path !== "/auth/login") {
    setToken(null)
    onUnauthorized?.()
  }
  if (!response.ok) {
    let body: unknown = null
    try {
      body = await response.json()
    } catch {
      // not JSON (e.g. the proxy's own error page)
    }
    const fallback = response.status >= 500 ? "Erreur du serveur" : `Erreur ${response.status}`
    throw new ApiError(response.status, errorMessage(body, fallback))
  }
  if (response.status === 204) return undefined as T
  return (options.text ? response.text() : response.json()) as Promise<T>
}

const qs = (params: Record<string, string | number | boolean | null | undefined>) => {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ""
}

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string; user: User }>("/auth/login", { method: "POST", body: { username, password } }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<Me>("/me"),

  overview: () => request<Overview>("/stats/overview"),
  clinics: () => request<ClinicStats[]>("/clinics"),
  clinic: (id: number) => request<ClinicDetail>(`/clinics/${id}`),
  updateClinic: (id: number, changes: Partial<Pick<ClinicStats, "name" | "city" | "postal_code" | "region" | "caisse" | "lat" | "lon">>) =>
    request<ClinicStats>(`/clinics/${id}`, { method: "PATCH", body: changes }),
  clinicInvoices: (id: number) => request<InvoiceRow[]>(`/clinics/${id}/invoices`),
  reportClinic: (id: number, reason: string, comment: string) =>
    request<unknown>(`/clinics/${id}/reports`, { method: "POST", body: { reason, comment: comment || null } }),

  tickets: (params: { status?: TicketStatus; mine?: boolean; escalated?: boolean; algo_verdict?: Verdict; clinic_id?: number; limit?: number } = {}) =>
    request<TicketSummary[]>(`/tickets${qs(params)}`),
  ticket: (id: number) => request<TicketDetail>(`/tickets/${id}`),
  claimNext: () => request<TicketDetail>("/tickets/claim-next", { method: "POST" }),
  requestTicket: (id: number) => request<TicketDetail>(`/tickets/${id}/request`, { method: "POST" }),
  releaseTicket: (id: number, reason?: string) =>
    request<TicketDetail>(`/tickets/${id}/release`, { method: "POST", body: { reason: reason ?? null } }),
  escalateTicket: (id: number, comment: string) =>
    request<TicketDetail>(`/tickets/${id}/escalate`, { method: "POST", body: { comment } }),
  resolveTicket: (id: number, finalVerdict: Verdict, category: FinalCategory, comment: string) =>
    request<TicketDetail>(`/tickets/${id}/resolve`, {
      method: "POST",
      body: { final_verdict: finalVerdict, category, comment: comment || null },
    }),
  reopenTicket: (id: number, reason?: string) =>
    request<TicketDetail>(`/tickets/${id}/reopen`, { method: "POST", body: { reason: reason ?? null } }),
  reviewCheck: (id: number, code: string, outcome: "confirmed" | "dismissed", comment?: string) =>
    request<TicketDetail>(`/tickets/${id}/checks/${encodeURIComponent(code)}`, {
      method: "PUT",
      body: { outcome, comment: comment ?? null },
    }),

  documentText: (pairId: number, kind: "facture" | "ocr") =>
    request<string>(`/pairs/${pairId}/documents/${kind}`, { text: true }),
  /** An <img> cannot send the Authorization header, so the token goes in the query string (local app). */
  imageUrl: (pairId: number) => `${BASE}/pairs/${pairId}/documents/image${qs({ token })}`,
}
