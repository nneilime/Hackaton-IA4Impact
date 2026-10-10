import { useEffect, useRef, type CSSProperties } from "react";

// Onde de la dictée : des barres qui défilent de droite à gauche au rythme de la voix (niveau RMS du micro,
// lu par un AnalyserNode). Sans flux (demande d'autorisation, transcription en cours), les barres ondulent
// en CSS pour montrer que quelque chose se passe. Les hauteurs sont écrites directement dans le style des
// barres à chaque pas : passer par l'état React re-rendrait tout le chat quinze fois par seconde.
const BARS = 40;
const STEP_MS = 70;

export default function VoiceMeter({ stream, busy, label }: { stream: MediaStream | null; busy: boolean; label: string }) {
  const barsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const bars = barsRef.current ? (Array.from(barsRef.current.children) as HTMLElement[]) : [];
    bars.forEach((b) => b.style.removeProperty("--h"));
    if (!stream) return;
    const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AC) return;
    const ctx = new AC();
    void ctx.resume();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const data = new Uint8Array(analyser.fftSize);
    const levels = new Array<number>(BARS).fill(0);
    const id = setInterval(() => {
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (const v of data) sum += ((v - 128) / 128) ** 2;
      // Courbe douce : une voix normale remplit la moitié de la hauteur, un silence reste une ligne
      levels.shift();
      levels.push(Math.min(1, Math.sqrt(Math.sqrt(sum / data.length)) * 1.6));
      bars.forEach((b, i) => b.style.setProperty("--h", (0.08 + levels[i] * 0.92).toFixed(3)));
    }, STEP_MS);
    return () => {
      clearInterval(id);
      void ctx.close();
    };
  }, [stream]);

  return (
    <div className={busy ? "voice-meter is-busy" : "voice-meter"} ref={barsRef} role="img" aria-label={label}>
      {Array.from({ length: BARS }, (_, i) => (
        <span key={i} style={{ "--i": i } as CSSProperties} />
      ))}
    </div>
  );
}
