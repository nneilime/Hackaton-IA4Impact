import { useEffect } from 'react'
import type { CarteScene } from '../../api/types'
import { ICONES_CARTE } from './iconesScene'

interface CartesReponseProps {
  cartes: CarteScene[]
  onChoisir: (id: string) => void
  /** Vrai pendant un tour du back : plus aucun clic ni raccourci n'est pris en compte. */
  desactive: boolean
}

const MAX_CARTES = 4

/** Pastilles d'icône des cartes neutres, en rotation pour garder le côté ludique sans jamais coder le sens par la couleur. */
const PASTILLES = [
  'bg-accent text-accent-content',
  'bg-secondary text-secondary-content',
  'bg-base-200 text-secondary',
  'bg-accent text-accent-content',
] as const

/** Apparition échelonnée (classes complètes, jamais assemblées). */
const ENTREES = [
  'motion-safe:animate-entree',
  'motion-safe:animate-entree motion-safe:[animation-delay:70ms]',
  'motion-safe:animate-entree motion-safe:[animation-delay:140ms]',
  'motion-safe:animate-entree motion-safe:[animation-delay:210ms]',
] as const

/** Même chose pour la 3e carte seule sur sa ligne : elle prend toute la largeur. */
const ENTREES_LARGES = [
  'min-[400px]:col-span-2 motion-safe:animate-entree',
  'min-[400px]:col-span-2 motion-safe:animate-entree motion-safe:[animation-delay:70ms]',
  'min-[400px]:col-span-2 motion-safe:animate-entree motion-safe:[animation-delay:140ms]',
  'min-[400px]:col-span-2 motion-safe:animate-entree motion-safe:[animation-delay:210ms]',
] as const

function estChampDeSaisie(cible: EventTarget | null): boolean {
  if (!(cible instanceof HTMLElement)) return false
  return cible.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(cible.tagName)
}

/** Grandes cartes-réponses à toucher (2 colonnes, 1 en très petit écran). Raccourcis clavier 1 à 4. */
export default function CartesReponse({ cartes, onChoisir, desactive }: CartesReponseProps) {
  const visibles = cartes.slice(0, MAX_CARTES)

  useEffect(() => {
    if (desactive) return
    function surTouche(evenement: KeyboardEvent) {
      if (evenement.ctrlKey || evenement.metaKey || evenement.altKey || evenement.repeat) return
      if (estChampDeSaisie(evenement.target)) return
      // Une fenêtre modale (carnet, confirmation) garde ses propres touches.
      if (document.querySelector('dialog[open]')) return
      const rang = Number(evenement.key) - 1
      if (Number.isInteger(rang) && rang >= 0 && rang < visibles.length) {
        evenement.preventDefault()
        onChoisir(visibles[rang].id)
      }
    }
    window.addEventListener('keydown', surTouche)
    return () => window.removeEventListener('keydown', surTouche)
  }, [desactive, visibles, onChoisir])

  if (visibles.length === 0) return null

  return (
    <ul className="grid grid-cols-1 gap-4 min-[400px]:grid-cols-2" aria-label="Vos réponses possibles">
      {visibles.map((carte, i) => {
        const Icone = carte.icone ? ICONES_CARTE[carte.icone] : null
        const primaire = carte.style === 'primaire'
        const seule = visibles.length === 3 && i === 2
        return (
          <li key={carte.id} className={seule ? ENTREES_LARGES[i] : ENTREES[i]}>
            <button
              type="button"
              disabled={desactive}
              aria-keyshortcuts={String(i + 1)}
              onClick={() => onChoisir(carte.id)}
              data-primaire={primaire}
              className="card min-h-28 w-full cursor-pointer border-2 border-secondary bg-base-100 text-left text-base-content shadow-[4px_4px_0_0] shadow-secondary transition-transform hover:-translate-y-0.5 active:translate-y-0.5 focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-secondary disabled:cursor-wait disabled:opacity-60 data-[primaire=true]:bg-primary data-[primaire=true]:text-primary-content"
            >
              <span className="card-body gap-2 p-4">
                <span className="flex items-start justify-between gap-2">
                  {Icone ? (
                    <span
                      className={
                        primaire
                          ? 'flex size-11 shrink-0 items-center justify-center rounded-full border-2 border-secondary bg-base-100 text-primary'
                          : `flex size-11 shrink-0 items-center justify-center rounded-full border-2 border-secondary ${PASTILLES[i]}`
                      }
                    >
                      <Icone className="size-6" aria-hidden="true" />
                    </span>
                  ) : (
                    <span />
                  )}
                  <kbd className="kbd kbd-sm hidden text-base-content sm:inline-flex" aria-hidden="true">
                    {i + 1}
                  </kbd>
                </span>
                <span className="card-title text-lg leading-tight font-extrabold">{carte.titre}</span>
                {carte.sous_titre && (
                  <span className={primaire ? 'text-sm text-primary-content/90' : 'text-sm text-base-content/70'}>
                    {carte.sous_titre}
                  </span>
                )}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
