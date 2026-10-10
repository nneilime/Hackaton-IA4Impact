import type { ReactNode } from 'react'
import { BookOpen, CalendarDays, GraduationCap, TrainFront, Users } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Demande } from '../../api/types'
import { formaterDateCourte, libelleDureeSortie, nombreVoyageurs } from './format'

interface Puce {
  Icone: LucideIcon
  libelle: string
  valeur: string
}

function puces(demande: Demande): Puce[] {
  const voyageurs = nombreVoyageurs(demande)
  const duree = libelleDureeSortie(demande.duree)
  return [
    { Icone: GraduationCap, libelle: 'Classe', valeur: demande.niveau ?? 'Classe à préciser' },
    {
      Icone: BookOpen,
      libelle: demande.theme ? 'Thème' : 'Destination',
      valeur: demande.theme ?? demande.destination_souhaitee ?? 'Thème à préciser',
    },
    {
      Icone: Users,
      libelle: 'Voyageurs',
      valeur:
        voyageurs !== null
          ? `${voyageurs} voyageurs (${demande.nb_eleves ?? 0} él. + ${demande.nb_accompagnateurs ?? 0} acc.)`
          : 'Voyageurs à préciser',
    },
    {
      Icone: CalendarDays,
      libelle: 'Date',
      valeur: duree ? `${formaterDateCourte(demande.date)} · ${duree}` : formaterDateCourte(demande.date),
    },
  ]
}

interface BandeauDemandeProps {
  demande: Demande
  /** Gare d'arrivée : le talon affiche alors « départ → arrivée ». */
  gareArrivee?: string | null
  /** Lien court placé sur le talon (ex. « Modifier »). */
  action?: ReactNode
}

/**
 * Rappel de la demande en une fine bande de quai : les puces à gauche,
 * la gare de départ sur le talon perforé du billet à droite.
 */
export default function BandeauDemande({ demande, gareArrivee, action }: BandeauDemandeProps) {
  const gare = demande.gare_depart?.nom ?? demande.lieu_depart?.libelle ?? 'Gare à préciser'
  return (
    <section
      aria-label="Rappel de votre demande"
      className="flex flex-wrap items-stretch rounded-box bg-secondary text-sm text-secondary-content motion-safe:animate-entree"
    >
      <dl className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2">
        {puces(demande).map(({ Icone, libelle, valeur }) => (
          <div key={libelle} className="flex min-w-0 items-center gap-1.5">
            <dt className="shrink-0">
              <Icone className="size-3.5 text-accent" aria-hidden="true" />
              <span className="sr-only">{libelle}</span>
            </dt>
            <dd className="font-semibold tabular-nums">{valeur}</dd>
          </div>
        ))}
      </dl>
      <div className="relative flex w-full items-center gap-x-3 gap-y-1 border-t-2 border-dashed border-secondary-content/40 px-4 py-2 sm:w-auto sm:border-l-2 sm:border-t-0 sm:before:absolute sm:before:-left-2 sm:before:-top-2 sm:before:size-3.5 sm:before:rounded-full sm:before:bg-base-200 sm:after:absolute sm:after:-bottom-2 sm:after:-left-2 sm:after:size-3.5 sm:after:rounded-full sm:after:bg-base-200">
        <p className="flex min-w-0 items-center gap-1.5 font-bold">
          <TrainFront className="size-4 shrink-0 text-accent" aria-hidden="true" />
          <span className="sr-only">Trajet : </span>
          <span className="truncate">
            {gare}
            {gareArrivee && <> → {gareArrivee}</>}
          </span>
        </p>
        {action}
      </div>
    </section>
  )
}
