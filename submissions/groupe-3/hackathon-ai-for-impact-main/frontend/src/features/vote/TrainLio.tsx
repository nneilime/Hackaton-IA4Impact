import { useId } from 'react'

// Petit train régional stylisé, vu de profil et tourné vers la droite (sens de la course).
// Dessin maison en aplats rouge, blanc et bleu nuit, façon Memphis : ce n'est pas le logo liO.
// Couleurs fixes de la charte : un élément de marque ne suit pas le thème.
const ROUGE = '#C8102E'
const NUIT = '#0B2341'
const NUIT_PROFONDE = '#071629'
const OR = '#FFCD00'
const BLANC = '#FFFFFF'
const BRUME = '#F4F5F7'

const CAISSE = 'M8 12 H88 C103 12 115 21 121 33 Q124 40 117 40 H8 Q4 40 4 36 V16 Q4 12 8 12 Z'
const FENETRES = [10, 27, 44, 61] as const
const ROUES = [17, 29, 91, 103] as const

interface TrainLioProps {
  /** Numéro de piste peint sur la caisse, comme un numéro de train. */
  numero: number
  className?: string
}

export default function TrainLio({ numero, className }: TrainLioProps) {
  const idCaisse = `train-caisse-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 128 50"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <clipPath id={idCaisse}>
          <path d={CAISSE} />
        </clipPath>
      </defs>
      {/* Ombre portée dure, décalée vers le bas à droite */}
      <path d={CAISSE} transform="translate(3 3)" fill={NUIT} />
      {/* Pantographe */}
      <path d="M38 12 L45 4 H55 M45 4 L51 12" fill="none" stroke={NUIT} strokeWidth={2} strokeLinejoin="round" />
      {/* Caisse blanche, jupe et nez rouges */}
      <path d={CAISSE} fill={BLANC} />
      <g clipPath={`url(#${idCaisse})`}>
        <rect x={0} y={30} width={128} height={12} fill={ROUGE} />
        <path d="M86 0 H130 V52 H100 Z" fill={ROUGE} />
      </g>
      <path d={CAISSE} fill="none" stroke={NUIT} strokeWidth={2.5} strokeLinejoin="round" />
      {/* Pare-brise, fenêtres et porte */}
      <path d="M95 15 C105 16 112 21 116 28 H98 Q96 28 96 26 Z" fill={NUIT} />
      {FENETRES.map((x) => (
        <rect key={x} x={x} y={16} width={13} height={9} rx={2} fill={NUIT} />
      ))}
      <rect x={76} y={15} width={8} height={21} rx={1.5} fill={BRUME} stroke={NUIT} strokeWidth={1.5} />
      {/* Phare */}
      <circle cx={117} cy={34} r={2.4} fill={OR} stroke={NUIT} strokeWidth={1} />
      {/* Numéro de piste sur une pastille or */}
      <circle cx={22} cy={35} r={6.5} fill={OR} stroke={NUIT} strokeWidth={1.5} />
      <text
        x={22}
        y={38.2}
        textAnchor="middle"
        fontSize={9}
        fontWeight={800}
        fontFamily="Montserrat Variable, Montserrat, sans-serif"
        fill={NUIT}
      >
        {numero}
      </text>
      {/* Bogies et roues */}
      <rect x={11} y={40} width={24} height={4} rx={2} fill={NUIT} />
      <rect x={85} y={40} width={24} height={4} rx={2} fill={NUIT} />
      {ROUES.map((x) => (
        <g key={x}>
          <circle cx={x} cy={44.5} r={4.2} fill={NUIT_PROFONDE} />
          <circle cx={x} cy={44.5} r={1.3} fill={OR} />
        </g>
      ))}
    </svg>
  )
}
