import { create } from "zustand"
import { api } from "./api"
import { useCompass, type PendingRating } from "./store"

// The stars (1 to 5) asked when a conversation ends: on hanging up, closing Compass or
// starting a new conversation, once the customer has asked something. What was rated
// or skipped isn't asked again; the server keeps the ratings (POST /api/ratings).

export type RatingSummary = { count: number; average: number | null }

/** Every rating given, all sessions together: for the demo panel. */
export const useRatings = create<RatingSummary>(() => ({ count: 0, average: null }))

const done = new Set<string>() // the customer's messages already rated or skipped

const unrated = () => useCompass.getState().messages.filter((m) => m.role === "user" && !done.has(m.id))

/** Asks for the stars before `then`, if the customer asked something since the last
 * time; otherwise `then` at once. */
export function endInteraction(mode: PendingRating["mode"], then: () => void) {
  if (!unrated().length) return then()
  useCompass.setState({ rating: { mode, then }, sheet: "open" })
}

/** The customer's stars, or null (« Passer »): then on with what was being done. */
export function rate(stars: number | null) {
  const pending = useCompass.getState().rating
  if (!pending) return
  unrated().forEach((m) => done.add(m.id))
  useCompass.setState({ rating: null })
  if (stars)
    api<RatingSummary>("/api/ratings", { method: "POST", body: { stars, mode: pending.mode } })
      .then((summary) => useRatings.setState(summary))
      .catch(() => null) // a lost rating isn't worth an error message
  pending.then()
}

export function loadRatings() {
  api<RatingSummary>("/api/ratings")
    .then((summary) => useRatings.setState(summary))
    .catch(() => null)
}
