import type { AnimationEvent } from 'react'

// Train régional liO stylisé (aplats Memphis, couleurs fixes de la charte) qui file
// le long d'un fin rail dans la moitié basse du bandeau, avec une traînée or.
// Décoratif : caché aux lecteurs d'écran, jamais cliquable, toujours sous le contenu.
// Mouvement réduit : pas de traversée, le train reste garé à droite, sans traînée.

const ROUGE = '#C8102E'
const ROUGE_FONCE = '#A00D24'
const NUIT = '#0B2341'
const NUIT_PROFONDE = '#071629'
const OR = '#FFCD00'
const BLANC = '#FFFFFF'

/** Voiture motrice : toit droit, nez profilé vers la droite (sens de la marche). */
const CAISSE_AVANT = 'M107 3 H180 C194 3 204 8.5 211 15 Q213.5 17.4 211.5 19 H107 Z'
const PARE_BRISE = 'M181 6.5 H185 C192.5 6.5 198.5 9.6 203.5 13.2 H181 Z'
const FENETRES = [7, 19, 31, 76, 88, 121, 133, 145, 157, 169] as const
const PORTES = [44, 112] as const
const BOGIES = [12, 74, 118, 172] as const

function SilhouetteTrain({ className }: { className: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 216 24"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {/* Pantographe en zigzag sur la motrice */}
      <path d="M126 3 L131 0.8 L136 3 M128.5 0.8 H134" fill="none" stroke={BLANC} strokeWidth={0.9} strokeLinejoin="round" />

      {/* Bogies et roues or, posés sur le rail */}
      {BOGIES.map((x) => (
        <g key={x}>
          <rect x={x} y={18.4} width={26} height={3} rx={1} fill={NUIT_PROFONDE} />
          <circle cx={x + 5} cy={21.8} r={1.9} fill={OR} stroke={NUIT_PROFONDE} strokeWidth={0.6} />
          <circle cx={x + 21} cy={21.8} r={1.9} fill={OR} stroke={NUIT_PROFONDE} strokeWidth={0.6} />
        </g>
      ))}

      {/* Caisses rouges à liseré blanc (effet autocollant, lisible sur bleu nuit) */}
      <g stroke={BLANC} strokeWidth={1.2} strokeLinejoin="round" fill={ROUGE}>
        <rect x={2} y={3} width={100} height={16} rx={3} />
        <path d={CAISSE_AVANT} />
      </g>
      <rect x={102} y={6} width={5} height={11} fill={NUIT_PROFONDE} />

      {/* Liseré de toit or et bande de livrée blanche */}
      <rect x={5} y={4.4} width={94} height={1.1} fill={OR} />
      <rect x={110} y={4.4} width={68} height={1.1} fill={OR} />
      <rect x={3} y={15} width={98} height={1.6} fill={BLANC} />
      <rect x={108} y={15} width={100} height={1.6} fill={BLANC} />
      <rect x={3} y={16.6} width={98} height={2.2} fill={ROUGE_FONCE} />
      <rect x={108} y={16.6} width={102} height={2.2} fill={ROUGE_FONCE} />

      {/* Baies vitrées découpées, portes or */}
      {FENETRES.map((x) => (
        <rect key={x} x={x} y={6.6} width={9} height={5} rx={1.2} fill={NUIT} />
      ))}
      {PORTES.map((x) => (
        <rect key={x} x={x} y={6} width={6} height={9} rx={0.8} fill={OR} stroke={NUIT} strokeWidth={0.6} />
      ))}
      <path d={PARE_BRISE} fill={NUIT} />

      {/* « liO » en texte simple sur la caisse (pas le logotype officiel) */}
      <text x={53} y={12.6} fill={BLANC} fontSize={7.5} fontWeight={800} letterSpacing={0.2}>
        liO
      </text>

      {/* Phare avant */}
      <circle cx={208.6} cy={17.2} r={1.2} fill={OR} />
    </svg>
  )
}

interface TrainLioProps {
  /** Appelé au début de chaque traversée (cycle de 11 s de `animate-train-passe`). */
  onPassage?: () => void
}

export default function TrainLio({ onPassage }: TrainLioProps) {
  function surCycle(evenement: AnimationEvent<HTMLDivElement>) {
    if (evenement.target === evenement.currentTarget) onPassage?.()
  }

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* Le rail : un fil clair et des traverses en pointillés */}
      <div className="absolute inset-x-0 bottom-[5px] h-px bg-secondary-content/25" />
      <div className="absolute inset-x-0 bottom-[2px] h-[3px] bg-[repeating-linear-gradient(90deg,var(--color-secondary-content)_0_2px,transparent_2px_14px)] opacity-20" />

      {/* Convoi : traînée or + train. Il part de -60vw et finit à 100vw, donc hors champ aux deux bouts. */}
      <div
        onAnimationStart={surCycle}
        onAnimationIteration={surCycle}
        className="absolute bottom-[5px] left-[-30vw] flex w-[min(60vw,34rem)] items-end motion-safe:animate-train-passe motion-reduce:right-3 motion-reduce:left-auto motion-reduce:w-auto lg:motion-reduce:right-[calc(max(0px,(100%_-_80rem)/2)_+_22rem)]"
      >
        <div className="relative h-3.5 flex-1 motion-reduce:hidden sm:h-[18px]">
          <span className="absolute top-[12%] right-1 h-0.5 w-full rounded-full bg-linear-to-r from-transparent to-accent opacity-80" />
          <span className="absolute top-[38%] right-0 h-[3px] w-3/5 rounded-full bg-linear-to-r from-transparent via-accent/70 to-accent" />
          <span className="absolute top-[62%] right-3 h-px w-4/5 bg-linear-to-r from-transparent to-secondary-content/70" />
          <span className="absolute bottom-[8%] right-0 h-0.5 w-2/5 rounded-full bg-linear-to-r from-transparent to-accent opacity-90" />
        </div>
        <SilhouetteTrain className="h-3.5 w-[7.875rem] shrink-0 opacity-90 sm:h-[18px] sm:w-[10.125rem]" />
      </div>
    </div>
  )
}
