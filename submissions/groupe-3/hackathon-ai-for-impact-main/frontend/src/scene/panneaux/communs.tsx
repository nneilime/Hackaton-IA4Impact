import type { ReactNode } from 'react'
import { SearchX } from 'lucide-react'
import type { DetailScene } from '../../api/types'
import { PuceNiveau } from '../../components/voyage/PastilleNiveau'
import { INFOS_NIVEAU } from '../../components/voyage/niveaux'

/** Voie ferrée vue de dessus : deux rails et des traverses, bleu nuit. Bandeau signature des cartes. */
export function Rail() {
  return (
    <div
      aria-hidden="true"
      className="h-2.5 shrink-0 border-b-2 border-secondary bg-[repeating-linear-gradient(90deg,var(--color-secondary)_0_3px,transparent_3px_9px)]"
    />
  )
}

/** Deux formes Memphis dans le coin de la carte (décor, 48 px au plus). */
export function DecorCoin() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute right-0 top-2.5 size-12 overflow-hidden">
      <span className="absolute -right-5 -top-5 size-12 rounded-full border-2 border-secondary bg-accent" />
      <span className="absolute bottom-1 left-1 size-3 rounded-full bg-primary" />
    </div>
  )
}

interface CadrePanneauProps {
  /** Identifiant du titre (aria-labelledby). */
  titreId: string
  /** Les données sont en cours de rafraîchissement : la carte s'estompe sans disparaître. */
  occupe?: boolean
  children: ReactNode
}

/** Carte d'étape : bordure et ombre dure bleu nuit, entrée douce, décor discret. */
export function CadrePanneau({ titreId, occupe = false, children }: CadrePanneauProps) {
  return (
    <article
      aria-labelledby={titreId}
      aria-busy={occupe}
      className={
        occupe
          ? 'relative flex min-w-0 flex-col overflow-hidden rounded-box border-2 border-secondary bg-base-100 opacity-60 shadow-[4px_4px_0_0] shadow-secondary motion-safe:animate-entree motion-safe:transition-opacity'
          : 'relative flex min-w-0 flex-col overflow-hidden rounded-box border-2 border-secondary bg-base-100 shadow-[4px_4px_0_0] shadow-secondary motion-safe:animate-entree motion-safe:transition-opacity'
      }
    >
      <Rail />
      <DecorCoin />
      {children}
    </article>
  )
}

/** Squelette à la forme d'une carte d'étape. */
export function SqueletteCarte({ lignes = 3 }: { lignes?: number }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-w-0 flex-col gap-3 rounded-box border-2 border-base-300 bg-base-100 p-4"
    >
      <span className="sr-only">Tchouette prépare la suite…</span>
      <div className="skeleton h-6 w-2/3" />
      <div className="skeleton h-4 w-1/3" />
      {Array.from({ length: lignes }, (_, i) => (
        <div key={i} className="skeleton h-4 w-full" />
      ))}
      <div className="grid grid-cols-3 gap-2">
        <div className="skeleton h-20" />
        <div className="skeleton h-20" />
        <div className="skeleton h-20" />
      </div>
    </div>
  )
}

interface PanneauVideProps {
  titre: string
  texte: string
}

/** Rien à montrer pour l'instant : on explique pourquoi et comment avancer. */
export function PanneauVide({ titre, texte }: PanneauVideProps) {
  return (
    <section
      aria-label={titre}
      className="flex items-start gap-3 rounded-box border-2 border-dashed border-base-300 bg-base-100 p-4 motion-safe:animate-entree"
    >
      <SearchX className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <div className="grid gap-1">
        <h2 className="text-base font-bold">{titre}</h2>
        <p className="text-sm">{texte}</p>
      </div>
    </section>
  )
}

interface RepliableProps {
  titre: string
  /** Résumé court affiché sous le titre, replié. */
  resume?: string
  /** Ouvert d'emblée (ex. l'enseignant vient de demander « Pourquoi ? »). */
  ouvert?: boolean
  children: ReactNode
}

/** Détail à la demande : fermé par défaut, ouvert au clavier comme à la souris. */
export function Repliable({ titre, resume, ouvert = false, children }: RepliableProps) {
  return (
    <details open={ouvert} className="collapse collapse-arrow rounded-box border border-base-300 bg-base-100">
      <summary className="collapse-title min-h-12 py-2.5 pe-10 text-sm font-semibold">
        <span className="flex flex-wrap items-baseline gap-x-2">
          {titre}
          {resume && <span className="text-xs font-normal text-base-content/70">{resume}</span>}
        </span>
      </summary>
      <div className="collapse-content text-sm">{children}</div>
    </details>
  )
}

/** Le détail « Pourquoi ? » du back : libellé, valeur, pastille de niveau (couleur + icône + texte). */
export function DetailPourquoi({ detail, titre }: { detail: DetailScene; titre?: string }) {
  return (
    <Repliable titre={titre ?? detail.titre} ouvert>
      <ul className="grid gap-2 pt-1">
        {detail.lignes.map((ligne, index) => (
          <li key={`${ligne.libelle}-${index}`} className="flex items-start gap-2.5">
            {ligne.niveau ? (
              <PuceNiveau niveau={ligne.niveau} />
            ) : (
              <span aria-hidden="true" className="mt-1.5 size-2 shrink-0 rounded-full bg-secondary" />
            )}
            <p className="min-w-0 leading-snug">
              <span className="font-semibold">{ligne.libelle}</span>
              <span className="text-base-content/70"> : </span>
              <span className="tabular-nums">{ligne.valeur}</span>
              {ligne.niveau && <span className="sr-only"> ({INFOS_NIVEAU[ligne.niveau].libelle})</span>}
            </p>
          </li>
        ))}
      </ul>
    </Repliable>
  )
}
