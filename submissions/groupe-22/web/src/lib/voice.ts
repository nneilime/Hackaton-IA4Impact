import { create } from "zustand"
import { usePrefs } from "./prefs"
import { addMessage, hasMessage, patchMessage, removeMessage, useCompass } from "./store"
import { HARMLESS_ERRORS, ToolTracker, type ServerEvent } from "./tools"

// Voice mode: the phone talks to the OpenAI Realtime API directly over WebRTC. Our
// server only forwards the offer (POST /api/session, with the API key, the session and
// the voice) and runs the tools on its own connection to the call; this side plays the
// audio, shows the transcript and the tools, and measures the audio levels for the orb.

export type VoiceStatus = "idle" | "connecting" | "listening" | "user_speaking" | "thinking" | "speaking" | "error"

interface VoiceState {
  status: VoiceStatus
  error: string | null
  muted: boolean
  pushToTalk: boolean // this call's: changing the setting applies to the next one
  talking: boolean // push-to-talk: between « Parler » and « Envoyer »
}

export const useVoice = create<VoiceState>(() => ({ status: "idle", error: null, muted: false, pushToTalk: false, talking: false }))

/** Live audio levels (0..1), read by the orb in a rAF loop (no React re-render). */
export const levels = { input: 0, output: 0 }

let call = 0 // the current call's number: a call stopped while it connects stays stopped
let pc: RTCPeerConnection | null = null
let dc: RTCDataChannel | null = null
let mic: MediaStream | null = null
let audioEl: HTMLAudioElement | null = null
let audioCtx: AudioContext | null = null
let wakeLock: WakeLockSentinel | null = null
let rafId = 0
let responding = false
let speaking = false
let turn: string | null = null // the assistant's message for the current question
let items = new Set<string>()
const userMessages = new Map<string, string>() // Realtime item_id -> message id
const tools = new ToolTracker("voice")

const setStatus = (status: VoiceStatus) => useVoice.setState({ status })

function send(event: object) {
  if (dc?.readyState === "open") dc.send(JSON.stringify(event))
}

function turnMessage(): string {
  if (!turn || !hasMessage(turn)) turn = addMessage({ role: "assistant", text: "", status: "streaming", via: "voice" })
  return turn
}

function finishTurn() {
  if (turn) patchMessage(turn, (m) => (m.status === "error" ? m : { ...m, status: "done", text: m.text.trim() }))
  turn = null
  items = new Set()
}

function analyse(stream: MediaStream, key: "input" | "output") {
  if (!audioCtx) return null
  const analyser = audioCtx.createAnalyser()
  analyser.fftSize = 512
  audioCtx.createMediaStreamSource(stream).connect(analyser)
  const buf = new Uint8Array(analyser.fftSize)
  return () => {
    analyser.getByteTimeDomainData(buf)
    let sum = 0
    for (const b of buf) sum += ((b - 128) / 128) ** 2
    levels[key] = levels[key] * 0.7 + Math.min(1, Math.sqrt(sum / buf.length) * 4) * 0.3
  }
}

async function keepScreenOn(on: boolean) {
  // A locked phone stops the mic: keep the screen on during the call.
  try {
    if (on) wakeLock = (await navigator.wakeLock?.request("screen")) ?? null
    else await wakeLock?.release()
  } catch {
    /* not supported, or battery saver: the call still works */
  }
}

function onEvent(e: ServerEvent) {
  switch (e.type) {
    case "input_audio_buffer.speech_started":
      setStatus("user_speaking")
      break
    case "input_audio_buffer.speech_stopped":
      setStatus("thinking")
      break
    case "input_audio_buffer.committed":
      // Placeholder: keeps the turns in order when the transcript comes after the answer.
      finishTurn()
      userMessages.set(e.item_id, addMessage({ role: "user", text: "…", status: "streaming", via: "voice" }))
      break
    case "conversation.item.input_audio_transcription.completed": {
      const text = String(e.transcript ?? "").trim()
      const id = userMessages.get(e.item_id)
      if (id && text) patchMessage(id, (m) => ({ ...m, text, status: "done" }))
      else if (id) removeMessage(id)
      break
    }
    case "response.created":
      responding = true
      break
    case "response.output_audio_transcript.delta": {
      const first = !items.has(e.item_id)
      items.add(e.item_id)
      patchMessage(turnMessage(), (m) => ({ ...m, status: "streaming", text: first && m.text ? `${m.text}\n\n${e.delta}` : m.text + e.delta }))
      break
    }
    case "output_audio_buffer.started":
      speaking = true
      setStatus("speaking")
      break
    case "output_audio_buffer.stopped":
    case "output_audio_buffer.cleared":
      speaking = false
      if (useVoice.getState().status === "speaking") setStatus("listening")
      break
    case "response.done":
      responding = false
      if (tools.onResponseDone(e.response, turnMessage)) setStatus("thinking") // the server runs them
      else {
        if (turn) patchMessage(turn, (m) => (m.status === "error" ? m : { ...m, status: "done" }))
        if (useVoice.getState().status === "thinking") setStatus("listening")
      }
      break
    case "conversation.item.done": // the server's tool results, when they reach us
      tools.onItemDone(e.item)
      break
    case "error":
      if (HARMLESS_ERRORS.includes(e.error?.code)) break
      console.warn("Realtime error", e.error)
      patchMessage(turnMessage(), (m) => ({ ...m, status: "error", error: e.error?.message ?? "Erreur inconnue." }))
      break
  }
}

export async function startVoice() {
  if (pc || useVoice.getState().status === "connecting") return
  const mine = ++call
  const { voice, pushToTalk, simple } = usePrefs.getState()
  useVoice.setState({ status: "connecting", error: null, muted: false, pushToTalk, talking: false })
  tools.reset()
  turn = null
  items = new Set()
  userMessages.clear()
  responding = speaking = false
  let stream: MediaStream | null = null
  try {
    // The browser cancels the echo of the assistant's voice: no need for headphones.
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
    } catch {
      throw new Error("Le micro est bloqué : autorisez-le dans le navigateur, ou continuez par écrit : toutes les démarches sont possibles.")
    }
    if (mine !== call) return stream.getTracks().forEach((t) => t.stop()) // hung up meanwhile
    mic = stream
    const track = mic.getAudioTracks()[0]
    track.enabled = !pushToTalk // push-to-talk: silent until « Parler »

    audioCtx = new AudioContext()
    void audioCtx.resume()
    pc = new RTCPeerConnection()
    audioEl = new Audio()
    audioEl.autoplay = true
    const ticks: (() => void)[] = []
    const inTick = analyse(mic, "input")
    if (inTick) ticks.push(inTick)
    pc.ontrack = (event) => {
      audioEl!.srcObject = event.streams[0]
      audioEl!.play().catch(() => {}) // autoplay already allowed: the call started on a tap
      const outTick = analyse(event.streams[0], "output")
      if (outTick) ticks.push(outTick)
    }
    const loop = () => {
      ticks.forEach((tick) => tick())
      rafId = requestAnimationFrame(loop)
    }
    rafId = requestAnimationFrame(loop)
    pc.addTrack(track, mic)
    pc.onconnectionstatechange = () => {
      if (mine === call && pc?.connectionState === "failed") stopVoice("La connexion a été perdue. Vous pouvez continuer par écrit.")
    }

    dc = pc.createDataChannel("oai-events")
    dc.onopen = () => {
      setStatus("listening")
      send({ type: "response.create" }) // the assistant says hi first
    }
    dc.onmessage = (message) => onEvent(JSON.parse(message.data))
    dc.onclose = () => {
      if (mine === call && pc) stopVoice("L'appel a été coupé.")
    }

    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    // The server gives the call the tools of this browser's session (cookie).
    const response = await fetch(`/api/session?ptt=${pushToTalk ? 1 : 0}&voice=${voice}&simple=${simple ? 1 : 0}`, {
      method: "POST",
      headers: { "Content-Type": "application/sdp" },
      body: offer.sdp,
    })
    if (!response.ok) throw new Error("Le serveur n'a pas pu ouvrir l'appel.")
    const answer = await response.text()
    if (mine !== call || !pc) return
    await pc.setRemoteDescription({ type: "answer", sdp: answer })
    void keepScreenOn(true)
  } catch (error) {
    if (mine !== call) return
    const message = error instanceof Error ? error.message : "La voix est indisponible."
    stopVoice(message.startsWith("Le micro") ? message : `${message} Vous pouvez continuer par écrit.`)
  }
}

export function stopVoice(error: string | null = null) {
  call++
  cancelAnimationFrame(rafId)
  const channel = dc
  dc = null
  channel?.close()
  pc?.close()
  mic?.getTracks().forEach((t) => t.stop())
  void audioCtx?.close().catch(() => null)
  if (audioEl) audioEl.srcObject = null
  pc = null
  mic = null
  audioCtx = null
  audioEl = null
  levels.input = 0
  levels.output = 0
  responding = speaking = false
  finishTurn()
  useCompass.setState((s) => ({ messages: s.messages.map((m) => (m.status === "streaming" && m.via === "voice" ? { ...m, status: "done" } : m)) }))
  useVoice.setState({ status: error ? "error" : "idle", error, muted: false, talking: false })
  void keepScreenOn(false)
}

/** Cuts the assistant off, greeting included: talking over it doesn't always work (the
 * phone's echo cancellation can muffle the voice while the speaker plays). */
export function interrupt() {
  if (responding) send({ type: "response.cancel" })
  if (speaking) send({ type: "output_audio_buffer.clear" })
}

export function setMuted(muted: boolean) {
  mic?.getAudioTracks().forEach((t) => (t.enabled = !muted))
  useVoice.setState({ muted })
}

/** Push-to-talk: « Parler » interrupts the assistant and opens the mic... */
export function talk() {
  interrupt()
  send({ type: "input_audio_buffer.clear" })
  mic?.getAudioTracks().forEach((t) => (t.enabled = true))
  useVoice.setState({ talking: true, status: "user_speaking" })
}

/** ...and « Envoyer » sends what was said. */
export function sendTurn() {
  useVoice.setState({ talking: false, status: "thinking" })
  // The last words are still on their way: close the mic a bit later.
  setTimeout(() => {
    mic?.getAudioTracks().forEach((t) => (t.enabled = false))
    send({ type: "input_audio_buffer.commit" })
    send({ type: "response.create" })
  }, 400)
}

/** A question tapped in the app during a call: asked in the call, as if said. */
export function sendVoiceText(text: string) {
  interrupt()
  finishTurn()
  addMessage({ role: "user", text, status: "done", via: "voice" })
  send({ type: "conversation.item.create", item: { type: "message", role: "user", content: [{ type: "input_text", text }] } })
  send({ type: "response.create" })
}

export const voiceActive = () => !!pc
