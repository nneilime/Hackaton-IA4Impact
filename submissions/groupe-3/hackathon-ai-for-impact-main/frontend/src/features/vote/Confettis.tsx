// Confettis géométriques façon Memphis (or, rouge, bleu nuit) qui éclatent quand le vote se termine.
// Formes simples posées en composition fixe : elles « poppent » une fois, puis restent immobiles.
// Les formes occupent la marge du bloc de célébration (bandes haute et basse, bords) pour ne
// jamais masquer le nom de la destination gagnante.
const FORMES = [
  'absolute motion-safe:animate-pop left-[3%] top-1 size-7 rounded-full border-4 border-secondary bg-accent',
  'absolute motion-safe:animate-pop left-[13%] top-2 size-6 rotate-12 bg-primary [clip-path:polygon(50%_0,100%_100%,0_100%)] [animation-delay:90ms]',
  'absolute motion-safe:animate-pop left-[24%] top-3 h-3 w-12 -rotate-[24deg] rounded-full bg-secondary [animation-delay:160ms]',
  'absolute motion-safe:animate-pop left-[46%] top-1 size-6 bg-[repeating-linear-gradient(45deg,var(--color-secondary)_0_3px,var(--color-accent)_3px_7px)] [animation-delay:60ms]',
  'absolute motion-safe:animate-pop left-[58%] top-2 size-7 -rotate-12 bg-accent [clip-path:polygon(50%_0,100%_100%,0_100%)] [animation-delay:140ms]',
  'absolute motion-safe:animate-pop left-[78%] top-1 h-5 w-10 rotate-180 rounded-t-full bg-secondary [animation-delay:200ms]',
  'absolute motion-safe:animate-pop left-[90%] top-2 size-6 rounded-full border-[5px] border-primary [animation-delay:300ms]',
  'absolute motion-safe:animate-pop right-0.5 top-[44%] size-5 rounded-full bg-primary [animation-delay:340ms]',
  'absolute motion-safe:animate-pop left-0.5 top-[48%] size-5 rotate-45 bg-secondary [animation-delay:380ms]',
  'absolute motion-safe:animate-pop left-[8%] bottom-1 h-5 w-10 rounded-t-full bg-accent [animation-delay:220ms]',
  'absolute motion-safe:animate-pop left-[36%] bottom-2 h-3 w-14 rotate-[18deg] rounded-full bg-primary [animation-delay:260ms]',
  'absolute motion-safe:animate-pop left-[66%] bottom-1 size-7 rotate-45 border-4 border-secondary bg-base-100 [animation-delay:120ms]',
  'absolute motion-safe:animate-pop left-[86%] bottom-2 size-6 rounded-full bg-accent [animation-delay:180ms]',
] as const

/** Zigzag bleu nuit, la signature graphique Memphis. */
function Zigzag({ className }: { className: string }) {
  return (
    <svg viewBox="0 0 60 16" className={className} aria-hidden="true" focusable="false">
      <path
        d="M2 12 L10 4 L18 12 L26 4 L34 12 L42 4 L50 12 L58 4"
        fill="none"
        stroke="#0B2341"
        strokeWidth={4}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default function Confettis() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden rounded-box">
      {FORMES.map((classes) => (
        <span key={classes} className={classes} />
      ))}
      <Zigzag className="absolute left-[33%] top-1 w-14 motion-safe:animate-pop motion-safe:[animation-delay:240ms]" />
      <Zigzag className="absolute bottom-1 left-[52%] w-12 -rotate-6 motion-safe:animate-pop motion-safe:[animation-delay:320ms]" />
    </div>
  )
}
