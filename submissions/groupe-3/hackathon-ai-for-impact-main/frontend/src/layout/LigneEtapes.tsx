import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Check, Lock } from 'lucide-react'
import { useMouvementReduit } from '../mascot/useMouvementReduit'
import { ETAPES, lienEtape } from './etapes'
import type { Avancement } from './etapes'

// La ligne des étapes : six gares reliées par un rail. Les gares déjà desservies
// sont des liens ; les autres restent visibles, inactives, avec la raison en titre.
// Sur mobile, la ligne défile dans son conteneur et se recentre sur la gare actuelle.

/* Classes complètes par état (pas de concaténation : Tailwind et daisyUI les voient telles quelles). */
const GARE = {
  parcourue: 'step step-accent relative grid-rows-[1.5rem_auto] before:h-1',
  aVenir: 'step relative grid-rows-[1.5rem_auto] before:h-1',
}
const PASTILLE = {
  actuelle:
    'step-icon pointer-events-none size-5 text-xs font-extrabold tabular-nums shadow-[2px_2px_0_0] shadow-secondary-content motion-safe:animate-pop',
  ouverte: 'step-icon pointer-events-none size-5 text-xs font-extrabold tabular-nums',
  fermee: 'step-icon pointer-events-none size-5 text-xs font-extrabold tabular-nums opacity-50',
}
const LIBELLE_LIEN = {
  actuel:
    'link link-hover rounded-sm px-1 font-extrabold whitespace-nowrap text-accent after:absolute after:inset-0 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent',
  autre:
    'link link-hover rounded-sm px-1 whitespace-nowrap text-secondary-content/85 after:absolute after:inset-0 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent',
}
const LIBELLE_INACTIF = {
  actuel: 'px-1 font-extrabold whitespace-nowrap text-accent',
  autre: 'px-1 whitespace-nowrap text-secondary-content/55',
}

interface LigneEtapesProps {
  /** Index de l'étape affichée, `null` hors parcours (page introuvable). */
  courante: number | null
  avancement: Avancement
}

export default function LigneEtapes({ courante, avancement }: LigneEtapesProps) {
  const refDefilement = useRef<HTMLDivElement>(null)
  const mouvementReduit = useMouvementReduit()

  useEffect(() => {
    const conteneur = refDefilement.current
    const gare = conteneur?.querySelector<HTMLElement>('[data-courante]')
    if (!conteneur || !gare || conteneur.scrollWidth <= conteneur.clientWidth) return
    const gauche = gare.offsetLeft - (conteneur.clientWidth - gare.offsetWidth) / 2
    conteneur.scrollTo({ left: Math.max(0, gauche), behavior: mouvementReduit ? 'auto' : 'smooth' })
  }, [courante, mouvementReduit])

  return (
    <nav aria-label="Étapes du parcours">
      <div
        ref={refDefilement}
        className="relative mx-auto max-w-7xl overflow-x-auto px-2 pt-0.5 pb-1.5 [scrollbar-width:none] lg:px-4"
      >
        <ol className="steps grid w-full min-w-[36rem] overflow-visible text-xs font-semibold">
          {ETAPES.map((etape, index) => {
            const lien = lienEtape(index, avancement)
            const actuelle = index === courante
            const faite = courante !== null && index < courante
            const parcourue = faite || actuelle

            return (
              <li
                key={etape.libelle}
                data-courante={actuelle || undefined}
                title={lien ? undefined : etape.verrou}
                className={parcourue ? GARE.parcourue : GARE.aVenir}
              >
                <span className={actuelle ? PASTILLE.actuelle : lien ? PASTILLE.ouverte : PASTILLE.fermee}>
                  {faite ? (
                    <Check className="size-3" strokeWidth={3} aria-hidden="true" />
                  ) : lien || actuelle ? (
                    index + 1
                  ) : (
                    <Lock className="size-2.5" strokeWidth={3} aria-hidden="true" />
                  )}
                </span>

                {lien ? (
                  <Link
                    to={lien}
                    aria-current={actuelle ? 'step' : undefined}
                    className={actuelle ? LIBELLE_LIEN.actuel : LIBELLE_LIEN.autre}
                  >
                    {etape.libelle}
                    {faite && <span className="sr-only"> (étape faite)</span>}
                  </Link>
                ) : (
                  <span
                    aria-current={actuelle ? 'step' : undefined}
                    className={actuelle ? LIBELLE_INACTIF.actuel : LIBELLE_INACTIF.autre}
                  >
                    {etape.libelle}
                    {!actuelle && <span className="sr-only"> (pas encore disponible : {etape.verrou})</span>}
                  </span>
                )}
              </li>
            )
          })}
        </ol>
      </div>
    </nav>
  )
}
