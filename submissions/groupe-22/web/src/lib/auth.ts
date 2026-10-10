import { create } from "zustand"
import { toast } from "@/components/shell/toast"
import { api, onUnauthorized } from "./api"
import { closeChat } from "./chat"
import { resetCustomer } from "./customer"
import { refreshDemarches, resetDemarches } from "./demarches"
import { navigate } from "./router"
import { useCompass } from "./store"
import { stopVoice, voiceActive } from "./voice"

// Who is using the page: a visitor (the public home) or a demo customer (the bank's
// app), as the server says (GET /api/me). The page only shows what follows from it:
// the server enforces it on every request and every tool of the assistant.

export interface Person {
  id: string
  firstName: string
  displayName: string
  initials: string
}

export interface Profile {
  id: string
  displayName: string
  description: string
}

interface AuthState {
  status: "loading" | "visitor" | "customer" | "offline"
  customer: Person | null
  loginOpen: boolean
  next: string | null // where to go after the login (a private page asked for)
}

export const useAuth = create<AuthState>(() => ({ status: "loading", customer: null, loginOpen: false, next: null }))

type Me = { kind: "visitor" } | { kind: "customer"; customer: Person }

function apply(me: Me) {
  const before = useAuth.getState()
  const same = me.kind === "customer" ? before.customer?.id === me.customer.id : before.status === "visitor"
  // Logged out or in elsewhere (another tab): this page's conversation and data go.
  if (!same && (before.status === "customer" || before.status === "visitor")) {
    resetConversations()
    void refreshDemarches()
  }
  useAuth.setState(me.kind === "customer" ? { status: "customer", customer: me.customer } : { status: "visitor", customer: null })
}

/** Back on the tab: the session may have changed meanwhile (logout in another tab). */
export function watchSession() {
  const check = () => {
    if (document.visibilityState !== "visible" || useAuth.getState().status === "loading") return
    void api<Me>("/api/me")
      .then(apply)
      .catch(() => {})
  }
  document.addEventListener("visibilitychange", check)
  window.addEventListener("focus", check)
}

export async function loadSession() {
  try {
    apply(await api<Me>("/api/me"))
  } catch {
    useAuth.setState({ status: "offline", customer: null })
  }
}

/** A new person: the previous conversation (voice or written) and data go. */
function resetConversations() {
  if (voiceActive()) stopVoice()
  closeChat(false)
  useCompass.setState({ voice: false, sheet: "closed", messages: [], actions: {} })
  resetCustomer()
  resetDemarches()
}

export function openLogin(next: string | null = null) {
  useAuth.setState({ loginOpen: true, next })
}

export function closeLogin() {
  useAuth.setState({ loginOpen: false, next: null })
}

export async function login(profile: string, code: string) {
  const me = await api<Me>("/api/auth/login", { method: "POST", body: { profile, code } })
  const next = useAuth.getState().next
  resetConversations()
  useAuth.setState({ status: "customer", customer: me.kind === "customer" ? me.customer : null })
  useAuth.setState({ loginOpen: false, next: null })
  void refreshDemarches()
  if (next) navigate(next)
  if (me.kind === "customer") toast(`Connecté·e : ${me.customer.displayName} (profil fictif)`)
}

export async function logout({ quiet = false } = {}) {
  try {
    await api<Me>("/api/auth/logout", { method: "POST", body: {} })
  } catch {
    /* the server ends it anyway when it expires */
  }
  resetConversations()
  useAuth.setState({ status: "visitor", customer: null })
  void refreshDemarches()
  navigate("/")
  if (!quiet) toast("Vous êtes déconnecté·e.", "info")
}

// The session ended on the server (expired, or logged out in another tab).
onUnauthorized(() => {
  if (useAuth.getState().status !== "customer") return
  resetConversations()
  useAuth.setState({ status: "visitor", customer: null })
  toast("Votre session de démonstration est terminée : reconnectez-vous.", "info")
})
