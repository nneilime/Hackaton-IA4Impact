import { create } from "zustand"
import type { ActionState, AppPage, AssistantCard, Highlight, TraceEvent } from "./types"

export interface ToolChip {
  id: string // the tool call's call_id
  name: string
  label: string
  status: "running" | "ok" | "waiting" | "error" | "cancelled"
}

export interface UIMessage {
  id: string
  role: "user" | "assistant"
  text: string
  cards: AssistantCard[]
  tools: ToolChip[]
  status: "streaming" | "done" | "error"
  via: "text" | "voice"
  error?: string
}

export type SheetMode = "closed" | "open" | "peek"
/** The stars asked when a conversation ends, then what was being done (see rating.ts). */
export type PendingRating = { mode: "voice" | "text"; then: () => void }
export type ChatStatus = "idle" | "connecting" | "open" | "ended" | "failed"

interface CompassState {
  sheet: SheetMode
  voice: boolean // the sheet shows the voice call
  messages: UIMessage[]
  busy: boolean // the written chat waits for an answer, tool calls included
  chatStatus: ChatStatus
  announce: string // a written answer, for screen readers, once complete
  page: AppPage
  highlight: { target: Highlight; nonce: number } | null
  trace: TraceEvent[] // newest first, for the demo panel
  actions: Record<string, ActionState> // the prepared actions, by id: their buttons
  rating: PendingRating | null // the sheet shows « Votre avis »
  setSheet: (m: SheetMode) => void
  setVoice: (v: boolean) => void
  setHighlight: (h: Highlight | null) => void
}

export const useCompass = create<CompassState>((set) => ({
  sheet: "closed",
  voice: false,
  messages: [],
  busy: false,
  chatStatus: "idle",
  announce: "",
  page: "accueil",
  highlight: null,
  trace: [],
  actions: {},
  rating: null,
  setSheet: (sheet) => set({ sheet }),
  setVoice: (voice) => set({ voice }),
  setHighlight: (h) => set({ highlight: h ? { target: h, nonce: Date.now() } : null }),
}))

let lastId = 0
/** An id for the page's own messages (crypto.randomUUID needs HTTPS). */
export const uid = () => `m${++lastId}`

export function addMessage(m: Omit<UIMessage, "id" | "cards" | "tools"> & Partial<UIMessage>): string {
  const id = m.id ?? uid()
  useCompass.setState((s) => ({ messages: [...s.messages, { cards: [], tools: [], ...m, id }] }))
  return id
}

export function patchMessage(id: string, fn: (m: UIMessage) => UIMessage) {
  useCompass.setState((s) => ({ messages: s.messages.map((m) => (m.id === id ? fn(m) : m)) }))
}

export function removeMessage(id: string) {
  useCompass.setState((s) => ({ messages: s.messages.filter((m) => m.id !== id) }))
}

export function hasMessage(id: string) {
  return useCompass.getState().messages.some((m) => m.id === id)
}
