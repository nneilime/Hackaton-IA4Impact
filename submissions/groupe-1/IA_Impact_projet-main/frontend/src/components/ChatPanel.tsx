import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { api, ChatFailure, type CatalogPlace, type ChatAction, type ChatError } from "../api";
import { useI18n } from "../i18n";
import Trame from "./Trame";
import VoiceMeter from "./VoiceMeter";
import { MOBILE_QUERY } from "./MobileNav";
import { dictationSupported, useDictation } from "./useDictation";

// `dictated` : le message part d'une dictée (relue dans le champ) — c'est ce texte-là que l'IA a reçu
type Message =
  | { id: number; role: "user" | "assistant"; text: string; dictated?: boolean }
  | { id: number; role: "error"; code: ChatError };

// Assistant flottant : une bulle en bas à droite qui ouvre une fenêtre de discussion.
// Les réponses viennent de POST /chat (modèle OpenAI côté backend, qui calcule les trajets avec le même moteur
// que /route) ; ses `actions` remontent à App, qui affiche l'itinéraire ou les lieux proposés sur la carte.
// Ouverture pilotée par l'application : sur mobile, c'est l'onglet « Assistant » de la barre du bas qui l'ouvre,
// et la discussion se loge dans le panneau coulissant du bas (`docked`) au lieu de flotter par-dessus.
// La conversation vit dans App (`messages`) : sur mobile comme sur ordinateur, elle survit à la fermeture.
type Props = {
  open: boolean;
  setOpen: (o: boolean | ((o: boolean) => boolean)) => void;
  docked?: boolean;
  catalog: CatalogPlace[];
  onActions: (actions: ChatAction[]) => void;
  messages: Message[];
  setMessages: (m: Message[] | ((m: Message[]) => Message[])) => void;
};
export type { Message as ChatMessage };
export default function ChatPanel({ open, setOpen, docked = false, catalog, onActions, messages, setMessages }: Props) {
  const { t } = useI18n();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  // Champ agrandi : il prend toute la fenêtre du chat pour relire un long texte (dictée de deux minutes)
  const [expanded, setExpanded] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const dictatedRef = useRef(false);
  const caretToEndRef = useRef(false);
  // La dictée remplit le champ (à la suite de ce qui était déjà écrit) : on relit, on corrige, on envoie
  const dictation = useDictation((text) => {
    setDraft((d) => (d.trim() ? d.trimEnd() + " " + text : text));
    dictatedRef.current = true;
    caretToEndRef.current = true;
  });
  const listening = dictation.phase !== "idle";

  // Le champ grandit avec le texte (jusqu'au plafond de max-height, puis il défile) : une dictée de deux minutes
  // se relit en entier avant d'être envoyée. Après une dictée, curseur et défilement vont à la fin du texte ajouté.
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "";
    if (!expanded) {
      el.style.height = "auto";
      const border = el.offsetHeight - el.clientHeight;
      el.style.height = el.scrollHeight + border + "px";
    }
    if (caretToEndRef.current) {
      caretToEndRef.current = false;
      // Dictée trop longue pour le champ : on l'agrandit, le texte se relit sans défiler
      if (!expanded && el.scrollHeight > el.clientHeight + 4) {
        caretToEndRef.current = true;
        return setExpanded(true);
      }
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
      el.scrollTop = el.scrollHeight;
    }
  }, [draft, listening, open, expanded]);
  // Le bouton d'agrandissement n'apparaît que si le texte déborde (ou que le champ est déjà agrandi)
  const [overflows, setOverflows] = useState(false);
  useLayoutEffect(() => {
    const el = inputRef.current;
    setOverflows(!!el && el.scrollHeight > el.clientHeight + 4);
  }, [draft, expanded, listening, open]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, open, busy]);

  const { cancel: cancelDictation } = dictation;
  useEffect(() => {
    if (!open) return cancelDictation();
    // Sur téléphone, pas de focus d'office : le clavier recouvrirait la conversation dès l'ouverture
    if (!window.matchMedia(MOBILE_QUERY).matches) inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  async function ask(text: string) {
    text = text.trim();
    if (!text || busy) return;
    setDraft("");
    setExpanded(false);
    const mine: Message = { id: Date.now(), role: "user", text, dictated: dictatedRef.current || undefined };
    dictatedRef.current = false;
    // Historique envoyé : les échanges réussis seulement (une erreur affichée n'est pas un tour de parole)
    const history = [...messages, mine].flatMap((m) => (m.role === "error" ? [] : [{ role: m.role, content: m.text }]));
    setMessages((m) => [...m, mine]);
    setBusy(true);
    try {
      const { reply, actions } = await api.chat(history, catalog);
      setMessages((m) => [...m, { id: Date.now(), role: "assistant", text: reply }]);
      if (actions.length) onActions(actions);
    } catch (e) {
      setMessages((m) => [...m, { id: Date.now(), role: "error", code: e instanceof ChatFailure ? e.code : "network" }]);
    } finally {
      setBusy(false);
    }
  }
  function send(e: FormEvent) {
    e.preventDefault();
    ask(draft);
  }
  // Entrée envoie, Maj + Entrée va à la ligne ; sur téléphone, Entrée va à la ligne (le bouton envoie)
  function onKeyDown(e: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (e.key !== "Enter" || e.shiftKey || e.nativeEvent.isComposing || window.matchMedia(MOBILE_QUERY).matches) return;
    e.preventDefault();
    ask(draft);
  }
  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <>
      {open && (
        <section className={`chat-pop${docked ? " chat-dock" : ""}${expanded && !listening ? " is-expanded" : ""}`} role={docked ? "region" : "dialog"} aria-label={t.chatTitle}>
          <div className="hero hero-compact chat-head">
            <h1>{t.chatTitle}</h1>
            <button className="chat-close" onClick={() => setOpen(false)} aria-label={t.close}>
              ×
            </button>
            <Trame className="hero-trame" rows={2} columns={30} />
          </div>
          <div className="chat-list" ref={listRef} aria-live="polite">
            <p className="chat-msg bot">{t.chatWelcome}</p>
            {messages.length === 0 && (
              <div className="chat-suggest">
                {t.chatSuggestions.map((q) => (
                  <button key={q} type="button" onClick={() => ask(q)}>
                    {q}
                  </button>
                ))}
              </div>
            )}
            {messages.map((m) =>
              m.role === "error" ? (
                <p key={m.id} className="chat-msg bot error" role="alert">
                  {t.chatErrors[m.code]}
                </p>
              ) : (
                <p key={m.id} className={`chat-msg ${m.role === "user" ? "user" : "bot"}`}>
                  {m.role === "user" && m.dictated && (
                    <span className="chat-msg-src">
                      <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
                      {t.chatDictated}
                    </span>
                  )}
                  {m.text}
                </p>
              ),
            )}
            {busy && (
              <p className="chat-msg bot chat-typing" aria-label={t.chatTyping}>
                <span />
                <span />
                <span />
              </p>
            )}
          </div>
          {dictation.error && (
            <p className="chat-mic-error" role="alert">
              {t.micErrors[dictation.error]}
              <button type="button" onClick={dictation.clearError} aria-label={t.close}>
                ×
              </button>
            </p>
          )}
          {listening ? (
            <div className={`chat-recorder is-${dictation.phase}`} role="group" aria-label={t.micStart}>
              <div className="rec-top">
                <span className={dictation.phase === "recording" ? "chat-rec-dot live" : "chat-rec-dot"} aria-hidden="true" />
                <span className="chat-rec-label" role="status">
                  {dictation.phase === "requesting" ? t.micRequesting : dictation.phase === "recording" ? t.micRecording : t.micTranscribing}
                </span>
                <span className="chat-rec-time">
                  {fmt(dictation.elapsed)}
                  <span className="rec-max" aria-label={t.micMaxLabel}> / {fmt(dictation.maxSeconds)}</span>
                </span>
              </div>
              <VoiceMeter stream={dictation.stream} busy={dictation.phase !== "recording"} label={t.micHeard} />
              <div className="rec-progress" aria-hidden="true">
                <span style={{ width: `${Math.min(100, (dictation.elapsed / dictation.maxSeconds) * 100)}%` }} />
              </div>
              <div className="rec-actions">
                <button type="button" className="rec-cancel" onClick={dictation.cancel} aria-label={t.micCancel}>
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7L7 17" /></svg>
                  {t.micCancelShort}
                </button>
                <button type="button" className="rec-stop" onClick={dictation.stop} disabled={dictation.phase !== "recording"} aria-label={t.micStop}>
                  <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
                  {t.micDone}
                </button>
              </div>
            </div>
          ) : (
            <form className="chat-input" onSubmit={send}>
              <div className="chat-field">
              <textarea
                ref={inputRef}
                rows={1}
                value={draft}
                onChange={(e) => {
                  setDraft(e.target.value);
                  if (!e.target.value.trim()) dictatedRef.current = false;
                }}
                onKeyDown={onKeyDown}
                placeholder={t.chatPh}
                aria-label={t.chatPh}
              />
              {(overflows || expanded) && (
                <button
                  type="button"
                  className="chat-expand"
                  onClick={() => setExpanded((x) => !x)}
                  aria-pressed={expanded}
                  aria-label={expanded ? t.chatShrink : t.chatExpand}
                  title={expanded ? t.chatShrink : t.chatExpand}
                >
                  {expanded ? (
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7" /></svg>
                  ) : (
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" /></svg>
                  )}
                </button>
              )}
              </div>
              {dictationSupported() && (
                <button type="button" className="chat-mic" onClick={dictation.start} disabled={busy} aria-label={t.micStart} title={t.micStart}>
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <rect x="9" y="3" width="6" height="11" rx="3" />
                    <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
                  </svg>
                </button>
              )}
              <button type="submit" className="chat-send" disabled={!draft.trim() || busy} aria-label={t.chatSend} title={t.chatSend}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6" /></svg>
              </button>
            </form>
          )}
        </section>
      )}
      {!docked && (
      <button className={open ? "chat-fab open" : "chat-fab"} onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label={open ? t.close : t.chatOpen}>
        {open ? (
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
        ) : (
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z" /></svg>
        )}
      </button>
      )}
    </>
  );
}
