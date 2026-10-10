import type { LucideIcon } from 'lucide-react'
import { CircleCheck, CircleX, Compass, MessageSquareText, ShieldCheck, Ticket, TriangleAlert } from 'lucide-react'

interface Arret {
  verbe: string
  texte: string
  icone: LucideIcon
  /** Classes complètes du cercle de la gare. */
  pastille: string
}

/** Les quatre promesses du pitch, posées comme des gares sur la ligne. */
const ARRETS: Arret[] = [
  {
    verbe: 'Proposer',
    texte: 'Des sorties en Occitanie, adaptées à votre projet.',
    icone: Compass,
    pastille:
      'grid size-8 shrink-0 place-items-center rounded-full border-2 border-secondary bg-accent text-accent-content',
  },
  {
    verbe: 'Vérifier',
    texte: 'Trains liO ouverts aux groupes, places et accès au site.',
    icone: ShieldCheck,
    pastille:
      'grid size-8 shrink-0 place-items-center rounded-full border-2 border-secondary bg-base-100 text-secondary',
  },
  {
    verbe: 'Rassurer',
    texte: 'Chaque choix expliqué, chaque point de vigilance signalé.',
    icone: MessageSquareText,
    pastille:
      'grid size-8 shrink-0 place-items-center rounded-full border-2 border-secondary bg-secondary text-secondary-content',
  },
  {
    verbe: 'Pré-réserver',
    texte: 'Une demande prête à envoyer, puis vos retours.',
    icone: Ticket,
    pastille:
      'grid size-8 shrink-0 place-items-center rounded-full border-2 border-secondary bg-base-100 text-secondary',
  },
]

/** Bande compacte sous le corps de page : la promesse en quatre gares, et le droit de dire non. */
export default function LignePromesse() {
  return (
    <section
      aria-labelledby="titre-promesse"
      className="rounded-box border border-base-300 bg-base-100 px-4 py-3 motion-safe:animate-entree"
    >
      <div className="grid gap-3 lg:grid-cols-[12rem_minmax(0,1fr)] lg:items-center lg:gap-5">
        <div>
          <h2 id="titre-promesse" className="text-lg font-bold text-secondary lg:text-xl">
            Une ligne, quatre arrêts
          </h2>
          <p className="text-xs text-base-content/70">De votre idée à la pré-réservation.</p>
        </div>

        <div className="relative">
          {/* Le rail : deux files et leurs traverses, d'une gare à l'autre (dès md) */}
          <span
            aria-hidden="true"
            className="pointer-events-none absolute left-4 right-0 top-4 hidden h-2 -translate-y-1/2 border-y-2 border-secondary bg-[repeating-linear-gradient(90deg,var(--color-secondary)_0_2px,transparent_2px_8px)] md:block"
          />
          <ol className="grid grid-cols-2 gap-x-4 gap-y-3 md:grid-cols-4">
            {ARRETS.map(({ verbe, texte, icone: Icone, pastille }, index) => (
              <li key={verbe} className="relative flex min-w-0 items-start gap-2 md:flex-col md:gap-1.5">
                <span className={pastille}>
                  <Icone className="size-4" aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <h3 className="text-sm font-bold text-secondary">
                    <span className="sr-only">Arrêt {index + 1} : </span>
                    {verbe}
                  </h3>
                  <p className="text-xs leading-snug text-base-content/80">{texte}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div className="mt-3 flex flex-col gap-2 border-t border-dashed border-base-300 pt-2 md:flex-row md:items-center md:justify-between">
        <p className="text-sm">
          <strong className="text-secondary">Tchouette sait dire non.</strong> Pas fiable pour votre groupe ? Elle
          l’explique et propose autre chose.
        </p>
        <ul className="flex shrink-0 flex-wrap gap-1.5" aria-label="Les trois niveaux de fiabilité d’une proposition">
          <li className="badge badge-success badge-sm gap-1 font-semibold">
            <CircleCheck className="size-3.5" aria-hidden="true" />
            Fiable
          </li>
          <li className="badge badge-warning badge-sm gap-1 font-semibold">
            <TriangleAlert className="size-3.5" aria-hidden="true" />
            Point de vigilance
          </li>
          <li className="badge badge-error badge-sm gap-1 font-semibold">
            <CircleX className="size-3.5" aria-hidden="true" />
            Pas adapté
          </li>
        </ul>
      </div>
    </section>
  )
}
