import { useEffect } from "react"
import { create } from "zustand"
import { api } from "./api"
import { useAuth } from "./auth"
import { useDemarches } from "./demarches"
import type { CustomerData } from "./types"

// The logged-in demo customer's data (GET /api/customer, only for their session): the
// screens and the assistant's tools read the same, card statuses included. Nothing is
// fetched for a visitor, and the server would refuse it anyway.

const useStore = create<{ data: CustomerData | null; error: boolean; loading: boolean }>(() => ({
  data: null,
  error: false,
  loading: false,
}))

let generation = 0 // a reset during a fetch: its answer is someone else's, dropped

async function load() {
  if (useStore.getState().loading) return
  const mine = generation
  useStore.setState({ loading: true, error: false })
  try {
    const data = await api<CustomerData>("/api/customer")
    if (mine === generation) useStore.setState({ data })
  } catch {
    if (mine === generation) useStore.setState({ error: true })
  } finally {
    if (mine === generation) useStore.setState({ loading: false })
  }
}

/** After an action (a card locked by Compass or on the Cartes screen). */
export function refreshCustomer() {
  if (useAuth.getState().status === "customer") void load()
}

/** Logout or a new login: the previous customer's data goes at once. */
export function resetCustomer() {
  generation++
  useStore.setState({ data: null, error: false, loading: false })
}

export function useCustomer() {
  const { data, error } = useStore()
  const customer = useAuth((s) => s.status === "customer")
  const opposition = useDemarches((s) => s.demarches.find((d) => d.kind === "card_block"))
  useEffect(() => {
    if (customer && !useStore.getState().data) void load()
  }, [customer])
  return { data: customer ? data : null, error, retry: load, opposition }
}
