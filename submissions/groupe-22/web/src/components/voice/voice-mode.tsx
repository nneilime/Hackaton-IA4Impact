import { useEffect, useRef } from "react"
import { ChevronDownIcon, ChevronUpIcon, KeyboardIcon, MicIcon, MicOffIcon, PhoneOffIcon, RotateCcwIcon } from "lucide-react"
import { endInteraction } from "@/lib/rating"
import { useCompass } from "@/lib/store"
import { interrupt, levels, sendTurn, setMuted, startVoice, stopVoice, talk, useVoice, voiceActive, type VoiceStatus } from "@/lib/voice"
import { cn } from "@/lib/utils"
import { AssistantCardView, ToolChips } from "@/components/compass/cards"
import { CompassMark } from "@/components/compass/compass-mark"

const LABEL: Record<VoiceStatus, string> = {
  idle: "Prêt",
  connecting: "Connexion sécurisée…",
  listening: "Je vous écoute",
  user_speaking: "Je vous écoute…",
  thinking: "Compass réfléchit…",
  speaking: "Compass vous répond",
  error: "Voix indisponible",
}

/** Starts and stops the call as voice mode is toggled. */
export function VoiceController() {
  const voice = useCompass((s) => s.voice)
  useEffect(() => {
    if (voice && !voiceActive() && useVoice.getState().status !== "error") void startVoice()
    if (!voice) {
      if (voiceActive() || useVoice.getState().status === "connecting") stopVoice()
      else if (useVoice.getState().status === "error") useVoice.setState({ status: "idle", error: null })
    }
  }, [voice])
  return null
}

/** Hanging up ends the call, then asks for the stars (from the peek too). */
function hangUp() {
  stopVoice()
  const { sheet, setSheet, setVoice } = useCompass.getState()
  setVoice(false)
  endInteraction("voice", () => {
    if (sheet === "peek") setSheet("peek")
  })
}

/** Orb driven by real audio levels: inner = Compass speaking, ring = customer voice. */
function Orb({ size = 168 }: { size?: number }) {
  const inner = useRef<HTMLDivElement>(null)
  const ring = useRef<HTMLDivElement>(null)
  const status = useVoice((s) => s.status)
  useEffect(() => {
    let raf = 0
    const loop = () => {
      const o = levels.output
      const i = levels.input
      if (inner.current) inner.current.style.transform = `scale(${1 + o * 0.45})`
      if (ring.current) {
        ring.current.style.transform = `scale(${1 + i * 0.55})`
        ring.current.style.opacity = String(0.25 + i * 0.75)
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [])
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }} aria-hidden>
      <div ref={ring} className="absolute inset-0 rounded-full border-2 border-white/40 transition-transform duration-75" />
      <div
        className={cn(
          "absolute inset-[14%] rounded-full blur-2xl transition-colors duration-500",
          status === "speaking" ? "bg-[#369ad4]/70" : status === "thinking" ? "bg-[#7c90e0]/60" : "bg-white/15",
        )}
      />
      <div
        ref={inner}
        className={cn(
          "relative flex items-center justify-center rounded-full shadow-[0_0_60px_-10px_rgba(54,154,212,0.8)] transition-colors duration-500",
          status === "speaking" ? "bg-[#369ad4]" : "bg-[#18339f]",
        )}
        style={{ width: size * 0.56, height: size * 0.56 }}
      >
        <CompassMark className={cn("size-1/2 text-white", status === "thinking" && "animate-spin [animation-duration:2.4s]")} />
      </div>
    </div>
  )
}

export function VoiceMode() {
  const { status, error, muted, pushToTalk, talking } = useVoice()
  const messages = useCompass((s) => s.messages)
  const scroller = useRef<HTMLDivElement>(null)
  const voiceMsgs = messages.filter((m) => m.via === "voice")
  const lastCards = [...voiceMsgs].reverse().find((m) => m.role === "assistant" && m.cards.length)?.cards ?? []
  const live = status !== "idle" && status !== "connecting" && status !== "error"

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" })
  }, [messages])

  const backToText = () => {
    stopVoice()
    useCompass.getState().setVoice(false)
  }

  // The orb is the main button: it cuts the assistant off (greeting included), or in a
  // noisy room, opens the mic (« Parler ») and sends what was said (« Envoyer »).
  let action: { label: string; hint: string; run: () => void } | null = null
  if (live && pushToTalk) action = talking ? { label: "Envoyer", hint: "Touchez pour envoyer", run: sendTurn } : { label: "Parler", hint: "Touchez pour parler", run: talk }
  else if (live) action = { label: "Interrompre Compass", hint: status === "speaking" || status === "thinking" ? "Touchez pour l'interrompre" : "Parlez quand vous voulez", run: interrupt }

  return (
    <div className="flex h-full flex-col bg-[radial-gradient(120%_80%_at_50%_0%,#18339f_0%,#051b71_55%,#000c3c_100%)] text-white" aria-label="Conversation vocale avec Compass">
      <header className="flex shrink-0 items-center gap-2 px-4 pb-1 pt-3">
        <div className="flex-1">
          <h2 className="text-base font-extrabold">Conversation vocale</h2>
          <p className="text-[11px] font-semibold text-white/60">OpenAI Realtime · transcription affichée{pushToTalk ? " · pièce bruyante" : ""}</p>
        </div>
        <button type="button" onClick={() => useCompass.getState().setSheet("peek")} aria-label="Réduire et voir l'application" className="flex size-10 items-center justify-center rounded-full bg-white/10 hover:bg-white/20">
          <ChevronDownIcon className="size-5" />
        </button>
      </header>

      <div className="flex shrink-0 flex-col items-center gap-2 pb-2 pt-4">
        {action ? (
          <button type="button" onClick={action.run} aria-label={action.label} className="rounded-full">
            <Orb />
          </button>
        ) : (
          <Orb />
        )}
        {/* Not read out: screen readers would talk over the assistant. */}
        <p className="text-lg font-bold" aria-hidden>
          {talking ? "Je vous écoute… touchez pour envoyer" : muted && live ? "Micro coupé" : LABEL[status]}
        </p>
        {action && !talking && (
          <p className="text-xs font-semibold text-white/60" aria-hidden>
            {action.hint}
          </p>
        )}
        <p className="sr-only" role="status">
          {status === "connecting" ? "Connexion…" : live ? (pushToTalk ? "En ligne. Touchez « Parler », posez votre question, puis touchez « Envoyer »." : "En ligne. Parlez quand vous voulez. Pour couper la parole à Compass, parlez ou touchez « Interrompre Compass ».") : ""}
        </p>
      </div>

      {status === "error" ? (
        <div className="flex flex-1 flex-col items-center justify-start gap-4 px-6 pt-4 text-center">
          <p role="alert" className="rounded-2xl bg-white/10 p-4 text-sm font-semibold">
            {error}
          </p>
          <button type="button" onClick={backToText} className="flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-white font-bold text-navy">
            <KeyboardIcon className="size-5" aria-hidden /> Continuer par écrit
          </button>
          <button type="button" onClick={() => void startVoice()} className="flex h-11 items-center gap-2 text-sm font-bold text-white/80">
            <RotateCcwIcon className="size-4" aria-hidden /> Réessayer
          </button>
        </div>
      ) : (
        <div ref={scroller} className="no-scrollbar flex flex-1 flex-col gap-2.5 overflow-y-auto px-5 py-2" role="log" aria-label="Transcription">
          {voiceMsgs.slice(-8).map((m) => (
            <div key={m.id} className={cn("flex flex-col", m.role === "user" ? "items-end" : "items-start")}>
              {m.role === "assistant" && <ToolChips m={m} dark />}
              {m.text && (
                <p className={cn("text-[15px] leading-snug", m.role === "user" ? "rounded-2xl rounded-br-md bg-white/12 px-3 py-2 text-white/90" : "text-white")}>
                  <span className="sr-only">{m.role === "user" ? "Vous : " : "Compass : "}</span>
                  {m.text}
                </p>
              )}
              {m.error && (
                <p role="alert" className="mt-1 text-sm font-semibold text-[#faafb7]">
                  Erreur : {m.error}
                </p>
              )}
            </div>
          ))}
          {lastCards.length > 0 && (
            <div className="mt-1 flex flex-col gap-2 text-navy">
              {lastCards.slice(-2).map((c, i) => (
                <AssistantCardView key={i} card={c} />
              ))}
            </div>
          )}
        </div>
      )}

      <footer className="flex shrink-0 items-center justify-center gap-5 px-6 pb-[max(env(safe-area-inset-bottom),20px)] pt-3 lg:pb-8">
        {!pushToTalk && (
          <button
            type="button"
            onClick={() => setMuted(!muted)}
            disabled={!live}
            aria-pressed={muted}
            aria-label={muted ? "Réactiver le micro" : "Couper le micro"}
            className={cn("flex size-14 items-center justify-center rounded-full transition disabled:opacity-40", muted ? "bg-white text-navy" : "bg-white/12 text-white hover:bg-white/20")}
          >
            {muted ? <MicOffIcon className="size-6" /> : <MicIcon className="size-6" />}
          </button>
        )}
        <button type="button" onClick={hangUp} aria-label="Raccrocher" className="flex size-16 items-center justify-center rounded-full bg-[#d20319] text-white shadow-lg hover:bg-[#960010]">
          <PhoneOffIcon className="size-7" />
        </button>
        <button type="button" onClick={backToText} aria-label="Raccrocher et revenir à l'écrit" className="flex size-14 items-center justify-center rounded-full bg-white/12 text-white hover:bg-white/20">
          <KeyboardIcon className="size-6" />
        </button>
      </footer>
    </div>
  )
}

export function VoicePeek() {
  const { status, muted } = useVoice()
  const last = useCompass((s) => [...s.messages].reverse().find((m) => m.via === "voice" && m.role === "assistant" && m.text))
  return (
    <div className="flex items-center gap-2 rounded-[22px] bg-navy p-2 pl-2.5 text-white shadow-[0_12px_32px_-12px_rgba(8,13,52,0.7)]">
      <div className="shrink-0">
        <Orb size={44} />
      </div>
      <button type="button" onClick={() => useCompass.getState().setSheet("open")} className="min-w-0 flex-1 text-left" aria-label="Rouvrir la conversation vocale">
        <p className="text-[11px] font-bold uppercase tracking-wide text-white/60">{muted ? "Micro coupé" : LABEL[status]}</p>
        <p className="line-clamp-1 text-[13px] font-semibold">{last?.text ?? "Parlez, je vous écoute."}</p>
      </button>
      <button type="button" onClick={() => useCompass.getState().setSheet("open")} aria-label="Agrandir" className="flex size-9 items-center justify-center rounded-full bg-white/10">
        <ChevronUpIcon className="size-5" />
      </button>
      <button type="button" onClick={hangUp} aria-label="Raccrocher" className="flex size-9 items-center justify-center rounded-full bg-[#d20319]">
        <PhoneOffIcon className="size-4" />
      </button>
    </div>
  )
}
