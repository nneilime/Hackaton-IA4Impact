import { usePrefs } from "./prefs"
import { addMessage, hasMessage, patchMessage, useCompass } from "./store"
import { HARMLESS_ERRORS, ToolTracker, type ServerEvent } from "./tools"

// Written mode: the page talks to our server over a WebSocket (/api/chat), which relays
// to a text-only Realtime session and runs the tools. The events are the Realtime
// API's (see CHAT_EVENTS in server.py). One conversation at a time, kept while the
// customer browses the app.

let socket: WebSocket | null = null
let turn: string | null = null // the assistant's message for the current question
let items = new Set<string>() // the answer's items in this turn: a new one, a new paragraph
let responding = false
let queue: string[] = [] // questions to ask once the assistant is free
let unavailable = false // the server couldn't reach OpenAI: a failure, not an end
const tools = new ToolTracker("text")

function turnMessage(): string {
  if (!turn || !hasMessage(turn)) turn = addMessage({ role: "assistant", text: "", status: "streaming", via: "text" })
  return turn
}

function finishTurn() {
  if (turn) patchMessage(turn, (m) => (m.status === "error" ? m : { ...m, status: "done", text: m.text.trim() }))
}

function post(event: object) {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(event))
}

function send(text: string) {
  addMessage({ role: "user", text, status: "done", via: "text" })
  turn = null
  items = new Set()
  post({ type: "message", text })
  useCompass.setState({ busy: true })
}

/** Asks the queued questions, one at a time, once the greeting or the answer is over. */
function setIdle() {
  useCompass.setState({ busy: false })
  const { chatStatus } = useCompass.getState()
  if (chatStatus === "open" && queue.length) send(queue.shift()!)
}

function onEvent(e: ServerEvent) {
  switch (e.type) {
    case "response.created":
      responding = true
      turnMessage()
      break
    case "response.output_text.delta": {
      const first = !items.has(e.item_id)
      items.add(e.item_id)
      patchMessage(turnMessage(), (m) => ({ ...m, status: "streaming", text: first && m.text ? `${m.text}\n\n${e.delta}` : m.text + e.delta }))
      break
    }
    case "response.output_text.done":
      // Screen readers read the whole answer once written, not each word.
      useCompass.setState({ announce: e.text })
      break
    case "response.done": {
      responding = false
      const calls = tools.onResponseDone(e.response, turnMessage)
      // The server runs the tools, then asks for the answer: still waiting.
      if (!(calls && e.response.status === "completed")) {
        finishTurn()
        setIdle()
      }
      break
    }
    case "conversation.item.done": // the server's tool results
      tools.onItemDone(e.item)
      break
    case "error":
      if (HARMLESS_ERRORS.includes(e.error?.code)) break
      if (e.error?.code === "unavailable") unavailable = true
      console.warn("Realtime error", e.error)
      patchMessage(turnMessage(), (m) => ({ ...m, status: "error", error: e.error?.message ?? "Erreur inconnue." }))
      if (!responding) setIdle() // no answer is coming
      break
  }
}

export function connectChat() {
  socket?.close()
  tools.reset()
  turn = null
  items = new Set()
  responding = false
  unavailable = false
  useCompass.setState({ chatStatus: "connecting", busy: true, announce: "" }) // the assistant says hi first
  const scheme = location.protocol === "https:" ? "wss" : "ws"
  // The server picks the tools from this browser's session cookie, not from the page.
  const simple = usePrefs.getState().simple ? "?simple=1" : ""
  const ws = new WebSocket(`${scheme}://${location.host}/api/chat${simple}`)
  socket = ws
  let opened = false
  ws.onopen = () => {
    opened = true
    useCompass.setState({ chatStatus: "open" })
  }
  ws.onmessage = (message) => onEvent(JSON.parse(message.data))
  ws.onclose = () => {
    if (socket !== ws) return // replaced by a new conversation
    socket = null
    finishTurn()
    useCompass.setState({ chatStatus: opened && !unavailable ? "ended" : "failed", busy: false })
  }
}

/** Asks a question in writing: now, or once the assistant is free (greeting included). */
export function sendChat(text: string) {
  const { chatStatus, busy } = useCompass.getState()
  if (chatStatus === "open" && !busy) return send(text)
  queue.push(text)
  if (chatStatus !== "open" && chatStatus !== "connecting") connectChat()
}

/** Whether the written conversation can take a message now. */
export const useChatOpen = () => useCompass((s) => s.chatStatus === "open")

/** « Explications simples », switched during a written conversation. */
export function setChatSimple(simple: boolean) {
  post({ type: "settings", simple })
}

/** « Arrêter »: stops the answer being written. */
export function cancelChat() {
  post({ type: "cancel" })
}

/** A new written conversation: the messages of the previous one go. */
export function newConversation(keepVoice: boolean) {
  queue = []
  useCompass.setState((s) => ({ messages: s.messages.filter((m) => keepVoice && m.via === "voice") }))
  connectChat()
}

/** Ends the written conversation, and its messages go: the next time Compass opens in
 * writing, a new one starts. */
export function closeChat(keepVoice: boolean) {
  queue = []
  const ws = socket
  socket = null // its onclose then does nothing
  ws?.close()
  turn = null
  useCompass.setState((s) => ({ chatStatus: "idle", busy: false, announce: "", rating: null, messages: s.messages.filter((m) => keepVoice && m.via === "voice") }))
}
