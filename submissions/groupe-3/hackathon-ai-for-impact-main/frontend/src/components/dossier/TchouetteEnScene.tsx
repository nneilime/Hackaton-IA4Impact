import { Star } from 'lucide-react'
import Tchouette from '../../mascot/Tchouette'
import type { HumeurTchouette } from '../../mascot/Tchouette'

interface TchouetteEnSceneProps {
  humeur: HumeurTchouette
  titre?: string
  /** Petit rebond (animate-pop) : à activer au moment d'une bonne nouvelle. */
  rebond?: boolean
  /** Trois étoiles or qui surgissent autour de la mascotte (célébration). */
  etoiles?: boolean
  /** Rail de traverses sous la mascotte. À retirer si l'écran a déjà sa deuxième décoration. */
  rail?: boolean
}

/**
 * Tchouette d'intro de page (64 px, 72 px dès lg), posée sur deux formes Memphis au plus :
 * le « O » or (32 px) et le rail de traverses.
 */
export default function TchouetteEnScene({
  humeur,
  titre = 'Tchouette',
  rebond = false,
  etoiles = false,
  rail = true,
}: TchouetteEnSceneProps) {
  return (
    <div className="relative grid size-16 shrink-0 place-items-center lg:size-[72px] print:hidden">
      <span
        aria-hidden="true"
        className="absolute -right-1.5 -top-1.5 size-8 rounded-full border-2 border-secondary bg-accent"
      />
      {rail && (
        <span
          aria-hidden="true"
          className="absolute -bottom-1.5 left-1/2 h-1.5 w-20 -translate-x-1/2 bg-[repeating-linear-gradient(90deg,var(--color-secondary)_0_4px,transparent_4px_9px)]"
        />
      )}
      <span key={rebond ? 'rebond' : 'calme'} className={rebond ? 'relative motion-safe:animate-pop' : 'relative'}>
        <Tchouette humeur={humeur} taille={72} titre={titre} className="size-16 lg:size-[72px]" />
      </span>
      {etoiles && (
        <>
          <Star
            aria-hidden="true"
            className="absolute -left-2 -top-1 size-4 fill-accent text-secondary motion-safe:animate-pop"
          />
          <Star
            aria-hidden="true"
            className="absolute -right-3 top-1/2 size-5 fill-accent text-secondary motion-safe:animate-pop motion-safe:[animation-delay:120ms]"
          />
          <Star
            aria-hidden="true"
            className="absolute -left-3 bottom-1 size-3.5 fill-accent text-secondary motion-safe:animate-pop motion-safe:[animation-delay:240ms]"
          />
        </>
      )}
    </div>
  )
}
