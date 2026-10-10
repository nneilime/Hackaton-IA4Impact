import { useEffect, useState, type ReactNode } from 'react'
import type { AncreScene, HumeurScene } from '../api/types'
import Tchouette from './Tchouette'
import type { HumeurTchouette } from './Tchouette'
import { useMouvementReduit } from './useMouvementReduit'

// Une bande pleine largeur : Tchouette glisse sur un fin rail d'une ancre à l'autre, sa bulle de parole
// se place du côté qui a le plus de place. Sur mobile, elle est plus petite et la bulle passe dessous.
// Les classes Tailwind sont écrites en toutes lettres (pas de concaténation dynamique).

export interface RailTchouetteProps {
  /** Où se place Tchouette sur le rail. */
  ancre: AncreScene
  humeur: HumeurScene
  /** La réplique affichée dans la bulle, à côté d'elle (change à chaque tour). */
  replique: string
  /** Contenu sous la bulle (badges de source). */
  children?: ReactNode
}

/** Doit rester égal à `duration-700` des transitions ci-dessous. */
const DUREE_TRAJET_MS = 700

/** Position horizontale du centre de la mascotte (la bulle et sa queue s'en déduisent). */
const X_MASCOTTE: Record<AncreScene, string> = {
  centre: 'left-1/2',
  gauche: 'left-11 sm:left-16',
  droite: 'left-[calc(100%-2.75rem)] sm:left-[calc(100%-4rem)]',
  'haut-droite': 'left-[calc(100%-2.75rem)] sm:left-[calc(100%-4rem)]',
  'bas-droite': 'left-[calc(100%-2.75rem)] sm:left-[calc(100%-4rem)]',
}

/** Hauteur : trois niveaux dès `sm` (sur mobile, tout est au niveau du rail). */
const Y_MASCOTTE: Record<AncreScene, string> = {
  centre: 'bottom-1 sm:bottom-7',
  gauche: 'bottom-1 sm:bottom-7',
  droite: 'bottom-1 sm:bottom-7',
  'haut-droite': 'bottom-1 sm:bottom-[3.25rem]',
  'bas-droite': 'bottom-1',
}

/** Le rail suit la mascotte : il monte ou descend avec elle. */
const Y_RAIL: Record<AncreScene, string> = {
  centre: 'bottom-3 sm:bottom-9',
  gauche: 'bottom-3 sm:bottom-9',
  droite: 'bottom-3 sm:bottom-9',
  'haut-droite': 'bottom-3 sm:bottom-15',
  'bas-droite': 'bottom-3',
}

/** Colonne de la bulle : sous la piste sur mobile ; à gauche d'elle si elle est à droite, sinon à sa droite. */
const COLONNE_BULLE: Record<AncreScene, string> = {
  centre: 'sm:bottom-14 sm:left-[calc(50%+4.75rem)] sm:right-0 sm:items-start',
  gauche: 'sm:bottom-14 sm:left-36 sm:right-0 sm:items-start',
  droite: 'sm:bottom-14 sm:left-0 sm:right-36 sm:items-end',
  'haut-droite': 'sm:bottom-20 sm:left-0 sm:right-36 sm:items-end',
  'bas-droite': 'sm:bottom-8 sm:left-0 sm:right-36 sm:items-end',
}

/** Queue de la bulle sur mobile (vers le haut, au-dessus de la mascotte). */
const QUEUE_MOBILE: Record<AncreScene, string> = {
  centre: 'left-1/2',
  gauche: 'left-11',
  droite: 'left-[calc(100%-2.75rem)]',
  'haut-droite': 'left-[calc(100%-2.75rem)]',
  'bas-droite': 'left-[calc(100%-2.75rem)]',
}

/** Queue de la bulle dès `sm` (sur le bord tourné vers la mascotte). */
const QUEUE_BUREAU: Record<AncreScene, string> = {
  centre: 'sm:-left-2 sm:top-1/2 sm:-translate-y-1/2 sm:border-b-2 sm:border-l-2 sm:border-r-0 sm:border-t-0',
  gauche: 'sm:-left-2 sm:top-1/2 sm:-translate-y-1/2 sm:border-b-2 sm:border-l-2 sm:border-r-0 sm:border-t-0',
  droite: 'sm:-right-2 sm:left-auto sm:top-1/2 sm:-translate-y-1/2 sm:border-b-0 sm:border-l-0 sm:border-r-2 sm:border-t-2',
  'haut-droite': 'sm:-right-2 sm:left-auto sm:top-1/2 sm:-translate-y-1/2 sm:border-b-0 sm:border-l-0 sm:border-r-2 sm:border-t-2',
  'bas-droite': 'sm:-right-2 sm:left-auto sm:top-1/2 sm:-translate-y-1/2 sm:border-b-0 sm:border-l-0 sm:border-r-2 sm:border-t-2',
}

/** Voie ferrée en coupe : un rail, et des traverses en pointillés dessous. */
function Voie() {
  return (
    <svg aria-hidden="true" focusable="false" className="block h-3 w-full text-secondary" preserveAspectRatio="none">
      <line x1="0" x2="100%" y1="1.5" y2="1.5" stroke="currentColor" strokeWidth="3" />
      <line x1="0" x2="100%" y1="8" y2="8" stroke="currentColor" strokeWidth="7" strokeDasharray="4 9" />
    </svg>
  )
}

export default function RailTchouette({ ancre, humeur, replique, children }: RailTchouetteProps) {
  const reduit = useMouvementReduit()
  // Ancre que la mascotte a atteinte : la bulle ne bouge qu'à l'arrivée, pour ne jamais être traversée en route.
  const [arrivee, setArrivee] = useState<AncreScene>(ancre)
  const enRoute = !reduit && arrivee !== ancre
  const cote = reduit ? ancre : arrivee

  useEffect(() => {
    if (arrivee === ancre) return
    const minuteur = window.setTimeout(() => setArrivee(ancre), DUREE_TRAJET_MS)
    return () => window.clearTimeout(minuteur)
  }, [ancre, arrivee])

  // Les roues tournent le temps du trajet.
  const expression: HumeurTchouette = enRoute ? 'parle' : humeur

  return (
    <div className="relative flex flex-col sm:block sm:h-56">
      {/* Piste : le rail et la mascotte qui glisse dessus. */}
      <div className="relative h-28 shrink-0 sm:absolute sm:inset-0 sm:h-auto">
        <div className={`absolute inset-x-0 transition-[bottom] duration-700 ease-in-out motion-reduce:transition-none ${Y_RAIL[ancre]}`}>
          <Voie />
        </div>
        <div
          className={`absolute -translate-x-1/2 transition-[left,bottom] duration-700 ease-in-out motion-reduce:transition-none ${X_MASCOTTE[ancre]} ${Y_MASCOTTE[ancre]}`}
        >
          <Tchouette humeur={expression} taille={128} titre="Tchouette" className="block size-22 sm:size-32" />
        </div>
      </div>

      {/* Bulle de parole et badges de source. */}
      <div
        className={`relative mt-2 flex min-h-36 flex-col sm:absolute sm:top-0 sm:mt-0 sm:min-h-0 sm:justify-center ${COLONNE_BULLE[cote]} ${
          enRoute ? 'opacity-0' : 'opacity-100'
        }`}
      >
        <div aria-live="polite" className="w-full sm:w-fit sm:max-w-2xl">
          <div
            key={`${cote}|${replique}`}
            className="relative rounded-box border-2 border-secondary bg-base-100 p-3 shadow-[4px_4px_0_0] shadow-secondary motion-safe:animate-entree"
          >
            <p className="text-lg leading-snug">{replique}</p>
            <span
              aria-hidden="true"
              className={`absolute -top-2 size-3.5 -translate-x-1/2 rotate-45 border-l-2 border-t-2 border-secondary bg-base-100 sm:translate-x-0 ${QUEUE_MOBILE[cote]} ${QUEUE_BUREAU[cote]}`}
            />
          </div>
        </div>
        {children ? (
          <div key={`${cote}|${replique}|badges`} className="mt-3 sm:max-w-2xl motion-safe:animate-entree">
            {children}
          </div>
        ) : null}
      </div>
    </div>
  )
}
