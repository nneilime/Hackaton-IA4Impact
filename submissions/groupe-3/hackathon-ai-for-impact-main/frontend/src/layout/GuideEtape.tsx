import { Lightbulb, X } from 'lucide-react'
import { ETAPES, rangAstuce } from './etapes'
import type { Ecran } from './etapes'

// Barre de guidage (une ligne, 40 px) : où en est l'enseignant, ce qu'il doit faire,
// et une astuce de Tchouette qui change à chaque visite de l'étape.

interface GuideEtapeProps {
  ecran: Ecran
  /** Identifiant de la visite (location.key) : une nouvelle visite, une nouvelle astuce. */
  cleVisite: string
  onMasquer: () => void
}

export default function GuideEtape({ ecran, cleVisite, onMasquer }: GuideEtapeProps) {
  const numero = ecran.etape + 1
  const astuce = ecran.astuces[rangAstuce(ecran, cleVisite)]

  return (
    <aside aria-label="Guide de l'étape" className="overflow-hidden border-b border-base-300 bg-base-100 text-base-content print:hidden">
      <div
        key={cleVisite}
        className="mx-auto flex h-10 max-w-7xl items-center gap-2.5 px-4 motion-safe:animate-entree lg:gap-3 lg:px-6"
      >
        {/* Pastille de gare : le numéro de l'étape en or sur bleu nuit */}
        <span
          aria-hidden="true"
          className="grid size-6 shrink-0 place-items-center rounded-full bg-secondary text-xs font-extrabold text-accent tabular-nums"
        >
          {numero}
        </span>

        <p className="line-clamp-2 min-w-0 shrink text-xs leading-4 sm:text-sm sm:leading-5 md:line-clamp-1 md:shrink-0 md:max-w-[55%]">
          <span className="font-semibold tracking-wide text-base-content/60 uppercase max-sm:sr-only sm:text-xs">
            Étape {numero} sur {ETAPES.length}
          </span>
          <span aria-hidden="true" className="px-1.5 text-base-content/40 max-sm:hidden">
            ·
          </span>
          <strong className="font-bold">{ecran.consigne}</strong>
        </p>

        {/* Pointillés de gares, puis l'astuce de Tchouette */}
        <span
          aria-hidden="true"
          className="hidden h-1 w-6 shrink-0 bg-[radial-gradient(circle,var(--color-base-content)_1px,transparent_1.5px)] bg-size-[6px_4px] opacity-40 md:block"
        />
        <p className="hidden min-w-0 flex-1 items-center gap-2 text-sm text-base-content/75 md:flex" title={astuce}>
          <span className="grid size-6 shrink-0 place-items-center rounded-full bg-accent text-accent-content">
            <Lightbulb className="size-3.5" aria-hidden="true" />
          </span>
          <span className="truncate">
            <span className="sr-only">Astuce de Tchouette : </span>
            {astuce}
          </span>
        </p>

        <button
          type="button"
          onClick={onMasquer}
          title="Masquer le guide pour cette session"
          className="btn btn-ghost btn-square btn-md ml-auto shrink-0 sm:btn-sm"
        >
          <X className="size-4" aria-hidden="true" />
          <span className="sr-only">Masquer le guide pour cette session</span>
        </button>
      </div>
    </aside>
  )
}
