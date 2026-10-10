// What the page shows of the assistant's tools (bank_tools.py), in both modes: a chip
// per tool call, cards (a loan simulation, the accounts and operations it read, an
// action waiting for the customer's yes, a démarche done, the Connexion démo offered),
// the demo panel's log, and the app responding: the server stored what was done, the
// page reloads it (Cartes, Mes démarches) and opens the right screen.

import { toast } from "@/components/shell/toast"
import { useAuth } from "./auth"
import { refreshCustomer } from "./customer"
import { refreshDemarches, useDemarches } from "./demarches"
import { euros } from "./format"
import { navigate } from "./router"
import { patchMessage, useCompass, type ToolChip } from "./store"
import type { ActionState, AssistantCard, Demarche, Loan, Mode, TraceEvent } from "./types"

export type ServerEvent = { type: string; [key: string]: any }
type Args = Record<string, any>

// Labels of bank_tools.py's enums, kept in sync with it.
const TOPICS: Record<string, string> = {
  code_perdu: "Code perdu",
  credit: "Crédit",
  gestion_privee: "Gestion privée",
  ouverture_compte: "Ouvrir un compte",
  reclamation: "Réclamation",
}

const REQUESTS: Record<string, string> = {
  card_lock: "verrouiller la carte",
  card_unlock: "déverrouiller la carte",
  card_block: "opposition sur la carte",
  pin_reissue: "réédition du code",
  password_reset: "nouveau mot de passe",
  appointment: "rendez-vous",
}

// Errors that just mean "nothing to cancel" or "nothing said" in push-to-talk.
export const HARMLESS_ERRORS = ["response_cancel_not_active", "input_audio_buffer_commit_empty"]

export function parse(json: string): Args {
  try {
    const value = JSON.parse(json || "{}")
    return value && typeof value === "object" ? value : {}
  } catch {
    return {}
  }
}

function describeCall(name: string, a: Args): string {
  switch (name) {
    case "get_procedure":
      return `Fiche ${TOPICS[a.topic] ?? a.topic}`
    case "simulate_loan":
      return `Simulation : ${euros(Number(a.amount))} sur ${a.months} mois`
    case "send_loan_to_advisor":
      return "Transmission au conseiller crédit"
    case "send_complaint":
      return "Réclamation"
    case "start_request":
      return `Demande : ${REQUESTS[a.kind] ?? a.kind}`
    case "transfer_to_advisor":
      return "Demande de conseiller"
    case "confirm_action":
      return a.confirmed ? "Votre accord" : "Annulation"
    case "get_accounts":
      return "Soldes consultés"
    case "search_transactions":
      return a.amount_eur ? `Recherche : ${euros(Number(a.amount_eur))}` : a.text ? `Recherche : « ${a.text} »` : "Dernières opérations"
    case "get_cards":
      return "Cartes consultées"
    case "offer_login":
      return "Connexion proposée"
    default:
      return name
  }
}

/** One line for the demo panel: what the back office receives, or why it didn't. */
function describeOutcome(name: string, r: Args): string {
  if (r.error) return r.error
  if (r.pending) return `En attente du oui du client : ${r.title}`
  if (r.cancelled) return "Annulée : rien n'a été fait."
  if (r.reference) return `${r.request} · ${r.reference}`
  if (r.ticket) return `${r.team} · ${r.when} · ${r.ticket}`
  if (r.card) return `${r.request} · ${r.card.id} → ${r.card.status}`
  if (r.monthly_payment_eur) return `${euros(r.monthly_payment_eur)} par mois, taux ${r.annual_rate_percent} %`
  if (r.accounts) return r.accounts.map((a: Args) => `${a.label} ${a.balance}`).join(" · ")
  if (r.transactions) return `${r.count} opération(s) trouvée(s)`
  if (r.cards) return r.cards.map((c: Args) => `${c.label} ${c.last_digits} : ${c.status}`).join(" · ")
  if (r.source) return r.say_word_for_word ?? `Lu : ${r.source}`
  return name
}

function trace(event: TraceEvent) {
  useCompass.setState((s) => ({ trace: [event, ...s.trace.filter((t) => t.id !== event.id)].slice(0, 40) }))
}

function setAction(id: string, state: ActionState) {
  useCompass.setState((s) => ({ actions: { ...s.actions, [id]: state } }))
}

function addCard(messageId: string, card: AssistantCard) {
  patchMessage(messageId, (m) => ({ ...m, cards: [...m.cards, card] }))
}

/** Lets the customer see the app respond: the right screen, highlighted. */
function showInApp(result: Args) {
  if (result.card) {
    const status = result.card.status === "OPPOSED" ? "opposition" : result.card.status === "LOCKED" ? "locked" : "active"
    toast(status === "opposition" ? `Opposition enregistrée · n° ${result.reference}` : status === "locked" ? "Carte verrouillée" : "Carte déverrouillée")
    navigate(`/cartes?card=${encodeURIComponent(result.card.id)}`)
    setTimeout(() => useCompass.getState().setHighlight("card-status"), 350)
    // The card changes on screen: tuck the assistant away so it shows.
    setTimeout(() => {
      if (useCompass.getState().sheet === "open") useCompass.getState().setSheet("peek")
    }, 650)
    return
  }
  const demarche = result.demarche as Demarche | undefined
  if (!demarche) return
  toast(`${demarche.title} · n° ${demarche.reference}`)
  // A visitor has no Mes démarches: the card in the conversation (and the public home's
  // « Vos demandes ») is the confirmation.
  if (useAuth.getState().status === "customer") navigate(`/demarches?ref=${encodeURIComponent(demarche.reference)}`)
}

/** Follows the tool calls of one conversation (voice call or written chat). The server
 * runs them: the page only sees the calls (response.done) and their results
 * (conversation.item.done). */
export class ToolTracker {
  private calls = new Map<string, { name: string; args: Args; messageId: string }>() // by call_id

  constructor(private mode: Mode) {}

  reset() {
    this.calls.clear()
  }

  /** A chip per tool call, on the turn's message. Returns whether the model called any. */
  onResponseDone(response: ServerEvent, turnMessage: () => string): boolean {
    const calls = (response.output ?? []).filter((item: ServerEvent) => item.type === "function_call")
    if (!calls.length) return false
    const messageId = turnMessage()
    for (const c of calls) {
      const args = parse(c.arguments)
      const label = describeCall(c.name, args)
      this.calls.set(c.call_id, { name: c.name, args, messageId })
      const chip: ToolChip = { id: c.call_id, name: c.name, label, status: "running" }
      patchMessage(messageId, (m) => ({ ...m, tools: [...m.tools, chip] }))
      const detail = Object.entries(args)
        .map(([k, v]) => `${k}: ${v}`)
        .join(" · ")
      trace({ id: c.call_id, at: Date.now(), channel: this.mode, name: c.name, label, outcome: "running", detail })
    }
    return true
  }

  onItemDone(item: ServerEvent) {
    if (item.type !== "function_call_output") return
    const call = this.calls.get(item.call_id)
    if (!call) return
    const { name, args, messageId } = call
    const r = parse(item.output)
    const status: ToolChip["status"] = r.error ? "error" : r.pending ? "waiting" : r.cancelled ? "cancelled" : "ok"
    const label = r.pending ? "En attente de votre accord" : r.cancelled ? "Annulé : rien n'a été fait" : describeCall(name, args)
    patchMessage(messageId, (m) => ({ ...m, tools: m.tools.map((t) => (t.id === item.call_id ? { ...t, label, status } : t)) }))
    trace({ id: item.call_id, at: Date.now(), channel: this.mode, name, label, outcome: status, detail: describeOutcome(name, r) })

    if (r.pending && r.action_id) {
      setAction(r.action_id, "pending")
      addCard(messageId, { kind: "confirm", action: { id: r.action_id, kind: r.kind, title: r.title, details: r.details ?? [], via: this.mode } })
      return
    }
    if (name === "confirm_action" && r.action_id) {
      setAction(r.action_id, r.cancelled ? "cancelled" : r.error ? "failed" : "done")
      if (r.error || r.cancelled || r.already_done) return
      if (r.demarche) {
        const demarche = useDemarches.getState().demarches.find((d) => d.reference === r.demarche.reference)
        const pdf = r.demarche.pdf ? { url: `/api/recaps/${r.demarche.pdf}`, name: `recapitulatif-${r.demarche.kind}-${r.demarche.reference.replaceAll(" ", "-")}.pdf` } : undefined
        addCard(messageId, { kind: "demarche", demarche: demarche ?? { ...r.demarche, pdf } })
        void refreshDemarches()
      }
      if (r.card) refreshCustomer()
      showInApp(r)
      return
    }
    if (r.error) return
    if (name === "simulate_loan" && r.monthly_payment_eur) addCard(messageId, { kind: "loan", loan: r as Loan })
    if (name === "offer_login") addCard(messageId, { kind: "login", reason: String(args.reason ?? "") })
    if (name === "get_accounts" && r.accounts) addCard(messageId, { kind: "accounts", accounts: r.accounts })
    if (name === "search_transactions" && r.transactions?.length) addCard(messageId, { kind: "transactions", transactions: r.transactions, count: r.count })
  }
}
