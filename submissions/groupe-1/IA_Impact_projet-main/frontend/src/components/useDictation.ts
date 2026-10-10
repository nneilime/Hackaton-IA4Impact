import { useCallback, useEffect, useRef, useState } from "react";
import { api, DictationFailure } from "../api";

// Dictée du chat, reprise du VoiceRecorder de la branche chatbot-enseignants : micro → MediaRecorder →
// POST /transcribe → le texte revient dans le champ de saisie, où l'utilisateur le relit et le corrige avant
// d'envoyer (une transcription n'est jamais envoyée d'office : un chiffre ou un nom de gare mal compris
// partirait au modèle sans que personne l'ait vu).
export type DictationPhase = "idle" | "requesting" | "recording" | "transcribing";
export type DictationErrorCode =
  | "denied" | "nomic" | "unsupported"
  | "audio_empty" | "audio_too_large" | "audio_format"
  | "chat_unavailable" | "chat_rate_limit" | "network";

const MAX_SECONDS = 120;
// Chrome / Firefox : Opus en WebM ou Ogg ; Safari : AAC en MP4
const MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];

export const dictationSupported = () =>
  typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";

function pickMimeType() {
  return typeof MediaRecorder.isTypeSupported === "function" ? MIME_TYPES.find((t) => MediaRecorder.isTypeSupported(t)) : undefined;
}

export function useDictation(onText: (text: string) => void) {
  const [phase, setPhase] = useState<DictationPhase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<DictationErrorCode | null>(null);
  // Le flux du micro, exposé pour l'onde de la barre d'enregistrement (null hors enregistrement)
  const [stream, setStream] = useState<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cancelledRef = useRef(false);
  const onTextRef = useRef(onText);
  onTextRef.current = onText;

  const release = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setStream(null);
  }, []);

  const stop = useCallback(() => {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
  }, []);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    stop();
    release();
    setPhase("idle");
  }, [release, stop]);

  const start = useCallback(async () => {
    setError(null);
    if (!dictationSupported()) return setError("unsupported");
    cancelledRef.current = false;
    setElapsed(0);
    setPhase("requesting");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      const name = e instanceof DOMException ? e.name : "";
      setPhase("idle");
      setError(name === "NotAllowedError" || name === "SecurityError" ? "denied" : name === "NotFoundError" ? "nomic" : "unsupported");
      return;
    }
    if (cancelledRef.current) return stream.getTracks().forEach((t) => t.stop());
    streamRef.current = stream;
    setStream(stream);

    let rec: MediaRecorder;
    try {
      const mimeType = pickMimeType();
      rec = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    } catch {
      release();
      setPhase("idle");
      return setError("unsupported");
    }
    recorderRef.current = rec;
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => e.data.size > 0 && chunks.push(e.data);
    rec.onstop = async () => {
      release();
      if (cancelledRef.current) return;
      const blob = new Blob(chunks, { type: rec.mimeType || chunks[0]?.type || "audio/webm" });
      if (blob.size < 1000) {
        setPhase("idle");
        return setError("audio_empty");
      }
      setPhase("transcribing");
      try {
        const text = await api.transcribe(blob);
        if (!cancelledRef.current) onTextRef.current(text);
      } catch (e) {
        if (!cancelledRef.current) setError(e instanceof DictationFailure ? e.code : "network");
      } finally {
        if (!cancelledRef.current) setPhase("idle");
      }
    };
    rec.start(250);
    setPhase("recording");
    timerRef.current = setInterval(() => {
      setElapsed((s) => {
        if (s + 1 >= MAX_SECONDS) stop(); // arrêt automatique : la transcription part quand même
        return s + 1;
      });
    }, 1000);
  }, [release, stop]);

  // Fermer le chat (ou quitter la page) coupe le micro : le voyant d'enregistrement ne doit pas rester allumé
  useEffect(() => cancel, [cancel]);

  return { phase, elapsed, maxSeconds: MAX_SECONDS, stream, error, clearError: () => setError(null), start, stop, cancel };
}
