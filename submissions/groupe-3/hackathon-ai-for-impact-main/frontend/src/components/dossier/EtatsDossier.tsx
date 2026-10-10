import { Link } from 'react-router-dom'
import { CircleX, FolderOpen, House, RotateCcw, SearchX } from 'lucide-react'
import Tchouette from '../../mascot/Tchouette'
import IntroEtape from './IntroEtape'

/** Squelette aux proportions de l'écran du dossier (intro + deux colonnes), avec Tchouette qui cherche. */
export function ChargementDossier({ reference }: { reference: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-4 lg:gap-5">
      <span className="sr-only">Chargement du dossier {reference}…</span>
      <div className="flex items-center gap-3 lg:gap-4">
        <Tchouette humeur="reflexion" taille={72} titre="" className="size-16 shrink-0 lg:size-[72px]" />
        <div className="flex flex-1 flex-col gap-2">
          <div className="skeleton h-8 w-full max-w-sm" />
          <div className="skeleton h-4 w-full max-w-xl" />
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:gap-5">
        <div className="flex flex-col gap-4">
          <div className="skeleton h-40 w-full" />
          <div className="skeleton h-48 w-full" />
        </div>
        <div className="skeleton h-80 w-full" />
      </div>
    </div>
  )
}

/** Référence inconnue de l'API : message clair, retour à l'accueil. */
export function DossierIntrouvable({
  reference,
  referenceEnCours,
}: {
  reference: string
  /** Dossier gardé en mémoire pour cette session, s'il est différent. */
  referenceEnCours?: string | null
}) {
  return (
    <section className="flex flex-col gap-4 rounded-box border-2 border-secondary bg-base-100 p-4 lg:p-5">
      <IntroEtape
        humeur="inquiete"
        titreTchouette="Tchouette s'inquiète"
        titre="Aucun dossier ne porte cette référence."
        phrase={
          <>
            <SearchX className="mr-1 inline size-4 align-[-3px]" aria-hidden="true" />
            <strong className="tabular-nums wrap-anywhere">{reference}</strong> est introuvable. Format attendu :{' '}
            <span className="tabular-nums">LIO-2026-000123</span>.
          </>
        }
      />
      <div className="flex flex-wrap gap-2">
        <Link to="/" className="btn btn-primary btn-md">
          <House className="size-4" aria-hidden="true" />
          Revenir à l'accueil
        </Link>
        {referenceEnCours && referenceEnCours !== reference && (
          <Link to={`/dossier/${encodeURIComponent(referenceEnCours)}`} className="btn btn-ghost btn-sm self-center">
            <FolderOpen className="size-4" aria-hidden="true" />
            Ouvrir mon dossier en cours
          </Link>
        )}
      </div>
    </section>
  )
}

/** Erreur de chargement sans dossier à afficher : message de l'API + Réessayer. */
export function ErreurDossier({ message, onReessayer }: { message: string; onReessayer: () => void }) {
  return (
    <section className="flex flex-col gap-4">
      <IntroEtape
        humeur="inquiete"
        titreTchouette="Tchouette s'inquiète"
        titre="Le dossier n'a pas pu être chargé."
        phrase="Le serveur n'a pas répondu comme prévu. Réessayez dans un instant."
      />
      <div role="alert" className="alert alert-error alert-vertical text-sm sm:alert-horizontal">
        <CircleX className="size-5 shrink-0" aria-hidden="true" />
        <span>{message}</span>
        <button type="button" className="btn btn-sm" onClick={onReessayer}>
          <RotateCcw className="size-4" aria-hidden="true" />
          Réessayer
        </button>
      </div>
      <Link to="/" className="link self-start text-sm font-semibold">
        Revenir à l'accueil
      </Link>
    </section>
  )
}
