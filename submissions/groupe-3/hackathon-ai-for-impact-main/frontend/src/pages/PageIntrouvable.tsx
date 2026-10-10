import { Link, useLocation } from 'react-router-dom'
import { CircleDot, FolderOpen, House } from 'lucide-react'
import IntroEtape from '../components/dossier/IntroEtape'
import { useVoyage } from '../state/VoyageContext'

/** Les vraies gares de la ligne, pour repartir du bon quai. */
const GARES = [
  { libelle: 'Mon projet', vers: '/' },
  { libelle: 'Où aller ?', vers: '/destinations' },
  { libelle: 'Comparer', vers: '/comparer' },
] as const

export default function PageIntrouvable() {
  const { pathname } = useLocation()
  const { dossier } = useVoyage()

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 lg:gap-5 lg:px-6 lg:py-6">
      <section className="flex flex-col gap-4 rounded-box border-2 border-secondary bg-base-100 p-4 shadow-[4px_4px_0_0] shadow-secondary md:flex-row md:items-center lg:p-5">
        <div className="min-w-0 flex-1">
          <IntroEtape
            humeur="inquiete"
            titreTchouette="Tchouette s'inquiète"
            rail={false}
            titre="Cette gare n'existe pas sur la ligne."
            phrase={
              <>
                L'adresse{' '}
                <code className="rounded-field bg-base-200 px-1 font-mono text-xs wrap-anywhere">{pathname}</code> ne
                correspond à aucun arrêt du parcours. Le lien est peut-être ancien.
              </>
            }
          />
        </div>
        <Link to="/" className="btn btn-primary btn-md self-start md:self-center">
          <House className="size-4" aria-hidden="true" />
          Revenir à l'accueil
        </Link>
      </section>

      <nav aria-labelledby="titre-gares" className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h2 id="titre-gares" className="text-xs font-semibold uppercase tracking-wide text-base-content/70">
          Gares desservies
        </h2>
        <ul className="flex flex-wrap items-center gap-1">
          {GARES.map((gare) => (
            <li key={gare.vers}>
              <Link to={gare.vers} className="btn btn-ghost btn-sm">
                <CircleDot className="size-4" aria-hidden="true" />
                {gare.libelle}
              </Link>
            </li>
          ))}
          {dossier && (
            <li>
              <Link to={`/dossier/${encodeURIComponent(dossier.reference)}`} className="btn btn-ghost btn-sm">
                <FolderOpen className="size-4" aria-hidden="true" />
                Mon dossier <span className="tabular-nums">{dossier.reference}</span>
              </Link>
            </li>
          )}
        </ul>
        {/* La voie s'arrête : traverses puis heurtoir rouge, là où la gare demandée devrait être. */}
        <span aria-hidden="true" className="hidden items-center sm:flex">
          <span className="h-3 w-32 bg-[repeating-linear-gradient(90deg,var(--color-secondary)_0_4px,transparent_4px_10px)]" />
          <span className="h-6 w-3 rounded-sm border-2 border-secondary bg-primary" />
        </span>
      </nav>
    </div>
  )
}
