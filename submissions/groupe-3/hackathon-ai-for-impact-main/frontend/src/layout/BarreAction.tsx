import { useEffect, useId, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Info } from 'lucide-react'
import Tchouette from '../mascot/Tchouette'

// Barre d'action collante en bas de chaque étape (frontend/DESIGN.md §4).
// Toujours au même endroit : retour à gauche, aide de Tchouette au centre, action principale à droite.
// Elle figure un quai de gare : bord bleu nuit et ligne de sécurité or en pointillés.
// L'interface (props) est partagée par toutes les pages : ne pas la casser.

export interface ActionPrincipale {
  libelle: string
  /** Lien de destination. Ignoré si `onClick` ou `form` est fourni. */
  vers?: string
  onClick?: () => void
  /** Identifiant d'un <form> : le bouton devient son bouton d'envoi. */
  form?: string
  desactive?: boolean
  /** Explication affichée à côté du bouton quand il est désactivé. */
  raison?: string
  chargement?: boolean
  icone?: ReactNode
}

export interface BarreActionProps {
  retour?: { libelle: string; vers: string }
  principal?: ActionPrincipale
  /** Actions secondaires (ex. « Comparer · 2 »), placées avant l'action principale. */
  secondaire?: ReactNode
  /** Une phrase courte de Tchouette (15 mots au plus). */
  aide?: string
}

/** Durée pendant laquelle Tchouette « parle » quand l'aide change, avant de se calmer. */
const DUREE_PAROLE_MS = 2400

/** Bulle d'aide : Tchouette parle quelques secondes à chaque nouvelle phrase, puis se repose. */
function AideTchouette({ texte }: { texte: string }) {
  const [parle, setParle] = useState(true)

  useEffect(() => {
    const minuteur = window.setTimeout(() => setParle(false), DUREE_PAROLE_MS)
    return () => window.clearTimeout(minuteur)
  }, [])

  return (
    <div className="flex min-w-0 items-center gap-2 motion-safe:animate-entree">
      <Tchouette humeur={parle ? 'parle' : 'repos'} taille={32} titre="" className="shrink-0" />
      <p
        className="min-w-0 truncate rounded-box border border-base-300 bg-base-200 px-3 py-1 text-sm text-base-content/85"
        title={texte}
      >
        {texte}
      </p>
    </div>
  )
}

export default function BarreAction({ retour, principal, secondaire, aide }: BarreActionProps) {
  const idRaison = useId()
  const icone = principal?.icone ?? <ArrowRight className="size-4" aria-hidden="true" />
  const raisonVisible = principal?.desactive && principal.raison
  // Sur mobile, l'action principale prend la largeur restante (et passe à la ligne si besoin).
  const classesPrincipal = 'btn btn-primary btn-md min-w-0 max-sm:grow max-sm:shrink sm:shrink-0'
  const classesPrincipalInactif = 'btn btn-primary btn-md btn-disabled min-w-0 max-sm:grow max-sm:shrink sm:shrink-0'

  const contenuBouton = (
    <>
      {principal?.chargement ? <span className="loading loading-spinner loading-sm" aria-hidden="true" /> : null}
      <span className="min-w-0 truncate">{principal?.libelle}</span>
      {!principal?.chargement && icone}
    </>
  )

  return (
    <div className="sticky bottom-0 z-20 mt-6 border-t-2 border-secondary bg-base-100 pb-[env(safe-area-inset-bottom)] before:absolute before:inset-x-0 before:top-0 before:h-1 before:bg-[repeating-linear-gradient(90deg,var(--color-accent)_0_14px,transparent_14px_22px)] print:hidden">
      <div className="mx-auto flex min-h-14 max-w-7xl flex-wrap items-center gap-2 px-4 pt-2.5 pb-2 sm:flex-nowrap sm:gap-3 lg:px-6">
        {retour && (
          <Link to={retour.vers} className="btn btn-ghost btn-square btn-md shrink-0 sm:btn-sm sm:w-auto sm:px-3">
            <ArrowLeft className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">{retour.libelle}</span>
            <span className="sr-only sm:hidden">{retour.libelle}</span>
          </Link>
        )}

        <div className="hidden min-w-0 flex-1 md:flex">{aide && <AideTchouette key={aide} texte={aide} />}</div>
        <div className="hidden flex-1 sm:block md:hidden" />

        {secondaire}

        {raisonVisible && (
          <p
            id={idRaison}
            className="flex max-w-60 items-center gap-1.5 text-xs text-base-content/70 max-sm:order-last max-sm:max-w-none max-sm:basis-full"
          >
            <Info className="size-3.5 shrink-0" aria-hidden="true" />
            <span>{principal.raison}</span>
          </p>
        )}

        {principal &&
          (principal.form || principal.onClick || !principal.vers ? (
            <button
              type={principal.form ? 'submit' : 'button'}
              form={principal.form}
              onClick={principal.onClick}
              disabled={principal.desactive || principal.chargement}
              aria-busy={principal.chargement || undefined}
              aria-describedby={raisonVisible ? idRaison : undefined}
              className={classesPrincipal}
            >
              {contenuBouton}
            </button>
          ) : principal.desactive ? (
            <span
              role="link"
              aria-disabled="true"
              aria-describedby={raisonVisible ? idRaison : undefined}
              className={classesPrincipalInactif}
            >
              {contenuBouton}
            </span>
          ) : (
            <Link to={principal.vers} className={classesPrincipal}>
              {contenuBouton}
            </Link>
          ))}
      </div>
    </div>
  )
}
