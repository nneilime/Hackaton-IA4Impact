import { create } from "zustand"
import { api } from "./api"
import type { Demarche } from "./types"

// The démarches of this browser's session, as the server stored them
// (GET /api/demarches): a customer's (opposition, loan, complaint...), or a visitor's
// demo requests. Logging out ends the session, and its démarches with it.

type Stored = Omit<Demarche, "pdf"> & { pdf: string | null }

const useStore = create<{ demarches: Demarche[]; loaded: boolean }>(() => ({ demarches: [], loaded: false }))
export const useDemarches = useStore // newest first

function toDemarche(d: Stored): Demarche {
  const pdf = d.pdf ? { url: d.pdf, name: `recapitulatif-${d.kind}-${d.reference.replaceAll(" ", "-")}.pdf` } : undefined
  return { ...d, pdf }
}

export async function refreshDemarches() {
  try {
    const { demarches } = await api<{ demarches: Stored[] }>("/api/demarches")
    useStore.setState({ demarches: demarches.map(toDemarche), loaded: true })
  } catch {
    useStore.setState({ loaded: true })
  }
}

export async function clearDemarches() {
  await api("/api/demarches", { method: "DELETE" })
  useStore.setState({ demarches: [] })
}

export function resetDemarches() {
  useStore.setState({ demarches: [], loaded: false })
}

/** What the status means, said plainly: everything here is simulated. */
export const STATUS_LABEL: Record<string, string> = {
  done: "Effectuée (simulation)",
  requested: "Demandée (simulation)",
  transmitted: "Transmise (simulation)",
  demo_request: "Demande de démonstration enregistrée",
}
