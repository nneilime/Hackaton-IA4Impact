import { useMemo } from 'react'
import { create } from 'qrcode'

// Couleurs fixes : un QR code doit garder un contraste maximal quel que soit le thème.
const NUIT = '#0B2341'
const BLANC = '#FFFFFF'
/** Marge blanche autour des modules (zone de silence), en modules. */
const MARGE = 2

interface QrCodeVoteProps {
  url: string
  className?: string
}

/** QR code dessiné en SVG (un seul tracé), lisible de loin sur un vidéoprojecteur. */
export default function QrCodeVote({ url, className }: QrCodeVoteProps) {
  const { taille, trace } = useMemo(() => {
    const { modules } = create(url, { errorCorrectionLevel: 'M' })
    const morceaux: string[] = []
    for (let ligne = 0; ligne < modules.size; ligne++) {
      for (let colonne = 0; colonne < modules.size; colonne++) {
        if (modules.get(ligne, colonne)) morceaux.push(`M${colonne + MARGE} ${ligne + MARGE}h1v1h-1z`)
      }
    }
    return { taille: modules.size + MARGE * 2, trace: morceaux.join('') }
  }, [url])

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${taille} ${taille}`}
      className={className}
      role="img"
      aria-label={`QR code pour rejoindre le vote : ${url}`}
      shapeRendering="crispEdges"
    >
      <rect width={taille} height={taille} fill={BLANC} />
      <path d={trace} fill={NUIT} />
    </svg>
  )
}
