import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import {
  ArrowUpIcon, BookOpenTextIcon, ChevronDownIcon, ChevronUpIcon, CircleAlertIcon, LoaderCircleIcon, MapPinIcon, MicIcon, RotateCcwIcon, SquareIcon, XIcon,
} from "lucide-react"
import { useAuth } from "@/lib/auth"
import { cancelChat, connectChat, newConversation, sendChat } from "@/lib/chat"
import { usePrefs } from "@/lib/prefs"
import { endInteraction, rate } from "@/lib/rating"
import { PUBLIC_SUGGESTIONS, SUGGESTIONS } from "@/lib/site"
import { useCompass, type ChatStatus, type UIMessage } from "@/lib/store"
import { cn } from "@/lib/utils"
import { interrupt, voiceActive } from "@/lib/voice"
import { AssistantCardView, ToolChips } from "./cards"
import { CompassMark } from "./compass-mark"
import { RatingView } from "./rating"
import { VoiceController, VoiceMode, VoicePeek } from "@/components/voice/voice-mode"
import { setSimple } from "@/components/settings/accessibility"

const PAGE_LABEL: Record<string, string> = {
  accueil: "Accueil", comptes: "Comptes", operations: "Opérations", cartes: "Cartes", demarches: "Mes démarches", profil: "Profil",
}

const STATUS_LABEL: Record<ChatStatus, string> = {
  idle: "",
  connecting: "Connexion…",
  open: "En ligne",
  ended: "Conversation terminée",
  failed: "Hors ligne",
}

/** Minimal formatter: paragraphs + **bold**. Model text is never rendered as HTML. */
function RichText({ text }: { text: string }) {
  return (
    <>
      {text.split(/\n{2,}/).map((para, i) => (
        <p key={i} className="whitespace-pre-line [&+p]:mt-2">
          {para.split(/(\*\*[^*]+\*\*)/g).map((seg, j) =>
            seg.startsWith("**") && seg.endsWith("**") ? (
              <strong key={j} className="font-extrabold">
                {seg.slice(2, -2)}
              </strong>
            ) : (
              <span key={j}>{seg}</span>
            ),
          )}
        </p>
      ))}
    </>
  )
}

function Message({ m }: { m: UIMessage }) {
  if (m.role === "user")
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-[20px] rounded-br-md bg-navy px-3.5 py-2.5 text-[15px] leading-snug text-white">
          <span className="sr-only">Vous : </span>
          {m.via === "voice" && <MicIcon className="mr-1 inline size-3.5 opacity-70" aria-label="à la voix" />}
          {m.text}
        </p>
      </div>
    )
  const thinking = m.status === "streaming" && !m.text && !m.cards.length
  return (
    <div className="flex gap-2.5">
      <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-brand text-white" aria-hidden>
        <CompassMark className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <ToolChips m={m} />
        {thinking && (
          <span className="flex h-6 items-center gap-1" aria-label="Compass réfléchit">
            <span className="typing-dot size-1.5 rounded-full bg-navy" />
            <span className="typing-dot size-1.5 rounded-full bg-navy" />
            <span className="typing-dot size-1.5 rounded-full bg-navy" />
          </span>
        )}
        {m.text && (
          <div className="text-[15px] leading-relaxed text-navy">
            <span className="sr-only">Compass : </span>
            {m.via === "voice" && <MicIcon className="mr-1 inline size-3.5 text-muted-ink" aria-label="à la voix" />}
            <RichText text={m.text} />
            {m.status === "streaming" && <span className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 animate-pulse bg-brand" aria-hidden />}
          </div>
        )}
        {m.cards.length > 0 && (
          <div className="mt-2.5 flex flex-col gap-2">
            {m.cards.map((c, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 * i }}>
                <AssistantCardView card={c} />
              </motion.div>
            ))}
          </div>
        )}
        {m.status === "error" && m.error && (
          <p role="alert" className="mt-2 flex items-start gap-2 rounded-2xl bg-brand-soft p-3 text-sm font-semibold text-brand">
            <CircleAlertIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
            Erreur : {m.error}
          </p>
        )}
      </div>
    </div>
  )
}

function Typing() {
  return (
    <div className="flex gap-2.5" aria-label="Compass réfléchit">
      <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-brand text-white" aria-hidden>
        <CompassMark className="size-4" />
      </span>
      <span className="flex h-7 items-center gap-1" aria-hidden>
        <span className="typing-dot size-1.5 rounded-full bg-navy" />
        <span className="typing-dot size-1.5 rounded-full bg-navy" />
        <span className="typing-dot size-1.5 rounded-full bg-navy" />
      </span>
    </div>
  )
}

function Welcome({ firstName }: { firstName?: string }) {
  return (
    <div className="flex flex-col gap-2 pb-4 pt-2">
      <span className="flex size-12 items-center justify-center rounded-2xl bg-brand text-white shadow-[0_10px_24px_-10px_rgba(6,36,153,0.7)]">
        <CompassMark className="size-7" />
      </span>
      <p className="text-[22px] font-extrabold leading-tight tracking-tight text-navy">
        Bonjour{firstName ? ` ${firstName}` : ""} 👋
        <br />
        <span className="text-[17px] font-semibold text-muted-ink">
          {firstName ? "Solde, opérations, carte perdue, crédit, réclamation : dites-moi." : "Crédit, mot de passe oublié, réclamation, conseiller : posez votre question."}
        </span>
      </p>
      {!firstName && <p className="text-xs font-semibold text-muted-ink">Vous n&apos;êtes pas connecté·e : Compass n&apos;a accès à aucun compte.</p>}
    </div>
  )
}

function Suggestions({ customer }: { customer: boolean }) {
  return (
    <div className="grid grid-cols-2 gap-2 pt-4" role="group" aria-label="Suggestions">
      {(customer ? SUGGESTIONS : PUBLIC_SUGGESTIONS).map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => sendChat(s)}
          className="hc-outline min-h-14 rounded-2xl bg-surface px-3 py-2.5 text-left text-[13.5px] font-bold leading-snug text-navy transition hover:bg-line"
        >
          {s}
        </button>
      ))}
    </div>
  )
}

function Composer({ inputRef }: { inputRef: React.RefObject<HTMLTextAreaElement | null> }) {
  const busy = useCompass((s) => s.busy)
  const status = useCompass((s) => s.chatStatus)
  const [text, setText] = useState("")
  const over = status === "ended" || status === "failed"
  const send = () => {
    const t = text.trim()
    if (!t || busy || status !== "open") return
    setText("")
    sendChat(t)
  }
  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }, [text, inputRef])
  return (
    <div className="shrink-0 border-t border-line bg-white px-3 pb-[max(env(safe-area-inset-bottom),12px)] pt-2.5 lg:pb-6">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          send()
        }}
        className="flex items-end gap-2 rounded-[26px] bg-surface p-1.5 pl-4 ring-1 ring-line focus-within:ring-2 focus-within:ring-navy"
      >
        <label htmlFor="compass-input" className="sr-only">
          Votre message à Compass
        </label>
        <textarea
          id="compass-input"
          ref={inputRef}
          rows={1}
          value={text}
          maxLength={2000}
          disabled={over}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              send()
            }
          }}
          placeholder="Écrivez votre demande…"
          className="max-h-[120px] min-h-10 flex-1 resize-none bg-transparent py-2 text-[15px] text-navy outline-none placeholder:text-muted-ink"
        />
        <button
          type="button"
          onClick={() => useCompass.getState().setVoice(true)}
          aria-label="Passer en conversation vocale"
          className="flex size-10 shrink-0 items-center justify-center rounded-full text-navy hover:bg-white"
        >
          <MicIcon className="size-5" />
        </button>
        {busy && status === "open" ? (
          <button
            type="button"
            onClick={cancelChat}
            aria-label="Arrêter la réponse"
            title="Arrêter la réponse"
            className="flex size-10 shrink-0 items-center justify-center rounded-full bg-navy text-white"
          >
            <SquareIcon className="size-4 fill-current" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!text.trim() || status !== "open"}
            aria-label="Envoyer"
            className="flex size-10 shrink-0 items-center justify-center rounded-full bg-brand text-white transition disabled:bg-line disabled:text-muted-ink"
          >
            {status === "connecting" ? <LoaderCircleIcon className="size-5 animate-spin" /> : <ArrowUpIcon className="size-5" />}
          </button>
        )}
      </form>
      <p className="mt-1.5 text-center text-[10.5px] text-muted-ink">Ne partagez jamais vos codes. Compass peut se tromper : vérifiez avant de confirmer.</p>
    </div>
  )
}

/** Closing Compass ends the conversation for the customer: their stars first. */
const closeCompass = () => endInteraction("text", () => useCompass.getState().setSheet("closed"))

export function CompassLayer() {
  const sheet = useCompass((s) => s.sheet)
  const voice = useCompass((s) => s.voice)
  const messages = useCompass((s) => s.messages)
  const page = useCompass((s) => s.page)
  const busy = useCompass((s) => s.busy)
  const status = useCompass((s) => s.chatStatus)
  const announce = useCompass((s) => s.announce)
  const rating = useCompass((s) => s.rating)
  const person = useAuth((s) => s.customer)
  const simple = usePrefs((p) => p.simple)
  const scroller = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [navH, setNavH] = useState(0)

  // The peek sits above the bank's menu, which only a logged-in customer has.
  useEffect(() => {
    const nav = document.getElementById("bottom-nav")
    if (!nav) return setNavH(0)
    const ro = new ResizeObserver(() => setNavH(nav.offsetHeight))
    ro.observe(nav)
    return () => ro.disconnect()
  }, [person])

  // The written conversation opens the first time Compass is shown in writing.
  useEffect(() => {
    if (sheet === "open" && !voice && status === "idle") connectChat()
  }, [sheet, voice, status])

  // The latest message in view, also when the sheet opens or comes back from a call.
  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" })
  }, [messages, sheet, voice])

  useEffect(() => {
    if (sheet === "open" && !voice && !rating) setTimeout(() => inputRef.current?.focus({ preventScroll: true }), 250)
  }, [sheet, voice, rating])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || useCompass.getState().sheet !== "open") return
      if (useCompass.getState().rating) return rate(null) // « Passer »
      // During a call, Escape cuts the assistant off, like tapping the orb.
      if (useCompass.getState().voice && voiceActive()) interrupt()
      else useCompass.getState().setSheet("peek")
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [])

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant")
  const visible = messages.filter((m) => !(m.role === "assistant" && m.status === "done" && !m.text && !m.cards.length && !m.tools.length))
  const asked = messages.some((m) => m.role === "user")
  const over = status === "ended" || status === "failed"

  return (
    <>
      <VoiceController />
      <div aria-live="polite" className="sr-only">
        {announce && `Compass : ${announce}`}
      </div>
      <AnimatePresence>
        {sheet === "open" && (
          <motion.div
            key="dim"
            className="absolute inset-0 z-40 bg-navy/30"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => (useCompass.getState().rating ? rate(null) : useCompass.getState().setSheet("peek"))}
            aria-hidden
          />
        )}
        {sheet === "open" && (
          <motion.section
            key="sheet"
            role="dialog"
            aria-modal="true"
            aria-label="Compass, assistant bancaire"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 34, stiffness: 320 }}
            className="absolute inset-x-0 bottom-0 top-[5%] z-50 flex flex-col overflow-hidden rounded-t-[30px] bg-white shadow-[0_-20px_60px_-20px_rgba(8,13,52,0.45)] lg:top-[6.5%]"
          >
            {rating ? (
              <RatingView />
            ) : voice ? (
              <VoiceMode />
            ) : (
              <>
                <header className="shrink-0 border-b border-line/70 px-4 pb-2.5 pt-2">
                  <div className="mx-auto mb-2 h-1.5 w-10 rounded-full bg-line" aria-hidden />
                  <div className="flex items-center gap-2">
                    <span className="flex size-9 items-center justify-center rounded-xl bg-brand text-white" aria-hidden>
                      <CompassMark className="size-5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <h2 className="text-base font-extrabold leading-tight text-navy">Compass</h2>
                      <p className="flex items-center gap-1 truncate text-[11px] font-semibold text-muted-ink">
                        <MapPinIcon className="size-3" aria-hidden />
                        {person ? (PAGE_LABEL[page] ?? "Application") : "Non connecté·e"}
                        {STATUS_LABEL[status] && (
                          <>
                            {" · "}
                            <span className={cn(status === "open" && "text-ok", over && "text-brand")}>{STATUS_LABEL[status]}</span>
                          </>
                        )}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSimple(!simple)}
                      aria-pressed={simple}
                      aria-label="Explications simples"
                      title="Explications simples"
                      className={cn("flex size-9 items-center justify-center rounded-full hover:bg-surface", simple ? "bg-navy text-white hover:bg-navy-2" : "text-navy")}
                    >
                      <BookOpenTextIcon className="size-[18px]" />
                    </button>
                    <button
                      type="button"
                      onClick={() => endInteraction("text", () => newConversation(voiceActive()))}
                      disabled={status === "connecting"}
                      aria-label="Nouvelle conversation"
                      title="Nouvelle conversation"
                      className="flex size-9 items-center justify-center rounded-full text-navy hover:bg-surface disabled:opacity-40"
                    >
                      <RotateCcwIcon className="size-[18px]" />
                    </button>
                    <button type="button" onClick={() => useCompass.getState().setSheet("peek")} aria-label="Réduire Compass" className="flex size-9 items-center justify-center rounded-full text-navy hover:bg-surface">
                      <ChevronDownIcon className="size-5" />
                    </button>
                    <button type="button" onClick={closeCompass} aria-label="Fermer Compass" className="flex size-9 items-center justify-center rounded-full text-navy hover:bg-surface">
                      <XIcon className="size-5" />
                    </button>
                  </div>
                </header>
                <div ref={scroller} className="no-scrollbar flex-1 overflow-y-auto overscroll-contain px-4 py-4" role="log" aria-label="Conversation avec Compass">
                  {!asked && <Welcome firstName={person?.firstName} />}
                  <div className="flex flex-col gap-4">
                    {visible.map((m) => (
                      <Message key={m.id} m={m} />
                    ))}
                    {/* Until the answer's first event: the greeting, or right after a question. */}
                    {busy && visible[visible.length - 1]?.role !== "assistant" && <Typing />}
                  </div>
                  {status === "open" && !asked && !busy && <Suggestions customer={!!person} />}
                  {over && (
                    <div className="mt-5 flex flex-col items-center gap-3 rounded-3xl bg-surface p-4 text-center" role="status">
                      <p className="text-sm font-semibold text-navy">
                        {status === "ended" ? "La conversation est terminée." : "Impossible de joindre Compass. Vérifiez votre connexion, puis réessayez."}
                      </p>
                      <button type="button" onClick={() => (status === "ended" ? endInteraction("text", () => newConversation(voiceActive())) : newConversation(voiceActive()))} className="flex h-11 items-center gap-2 rounded-2xl bg-brand px-5 text-sm font-bold text-white hover:bg-brand-strong">
                        <RotateCcwIcon className="size-4" aria-hidden />
                        {status === "ended" ? "Nouvelle conversation" : "Réessayer"}
                      </button>
                    </div>
                  )}
                </div>
                <Composer inputRef={inputRef} />
              </>
            )}
          </motion.section>
        )}
        {sheet === "peek" && (
          <motion.div
            key="peek"
            initial={{ y: 30, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 30, opacity: 0 }}
            className="absolute inset-x-3 z-40"
            style={{ bottom: navH ? navH + 10 : "max(env(safe-area-inset-bottom), 12px)" }}
          >
            {voice ? (
              <VoicePeek />
            ) : (
              <div className="flex items-center gap-2 rounded-[22px] bg-white p-2 pl-3 shadow-[0_12px_32px_-12px_rgba(8,13,52,0.5)] ring-1 ring-line">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand text-white" aria-hidden>
                  <CompassMark className="size-4" />
                </span>
                <button type="button" onClick={() => useCompass.getState().setSheet("open")} className="min-w-0 flex-1 text-left" aria-label="Rouvrir la conversation avec Compass">
                  <p className="line-clamp-2 text-[13px] font-semibold leading-snug text-navy">
                    {busy && !lastAssistant?.text ? "Compass réfléchit…" : lastAssistant?.text || "Une question ? Je suis là."}
                  </p>
                </button>
                <button type="button" onClick={() => useCompass.getState().setSheet("open")} aria-label="Agrandir Compass" className="flex size-9 shrink-0 items-center justify-center rounded-full bg-surface text-navy">
                  <ChevronUpIcon className="size-5" />
                </button>
                <button type="button" onClick={closeCompass} aria-label="Fermer Compass" className="flex size-9 shrink-0 items-center justify-center rounded-full text-muted-ink hover:bg-surface">
                  <XIcon className="size-4" />
                </button>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
