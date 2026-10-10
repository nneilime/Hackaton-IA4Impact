import { useMemo } from 'react'
import type { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Accessibility,
  ArrowLeft,
  Award,
  BookOpen,
  Bus,
  Footprints,
  Heart,
  Plus,
  Route,
  ShieldCheck,
  Ticket,
  Trophy,
  Users,
  X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Proposition } from '../api/types'
import BarreAction from '../layout/BarreAction'
import BandeauDemande from '../components/voyage/BandeauDemande'
import BulleTchouette from '../components/voyage/BulleTchouette'
import { EtatVide } from '../components/voyage/EtatsEcran'
import IntroEcran from '../components/voyage/IntroEcran'
import PastilleNiveau from '../components/voyage/PastilleNiveau'
import { LIBELLES_ACCES, LIBELLES_JAUGE } from '../components/voyage/niveaux'
import {
  RANG_NIVEAU,
  formaterDateCourte,
  formaterDuree,
  formaterPoints,
  libelleAcces,
  libelleCorrespondances,
  niveauLePlusBas,
  pluriel,
} from '../components/voyage/format'
import { useEcranEtroit } from '../components/voyage/useEcranEtroit'
import { MAX_COMPARAISON, useVoyage } from '../state/VoyageContext'
import type { PropositionSite } from '../state/VoyageContext'

type Sens = 'max' | 'min'

interface Cellule {
  contenu: ReactNode
  /** Valeur comparable ; null quand le critère ne peut pas départager. */
  valeur: number | null
}

interface Ligne {
  id: string
  libelle: string
  aide: string
  Icone: LucideIcon
  sens: Sens
  cellules: Cellule[]
}

const CONTENEUR = 'mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)] gap-4 px-4 py-5 lg:gap-5 lg:px-6 lg:py-6'

const MOTIF_PEDAGOGIE = /p[ée]dagog/i
const MOTIF_SATISFACTION = /satisfaction/i
const MOTIF_SANS_RETOUR = /pas encore de retour/i

function critere(proposition: Proposition, motif: RegExp) {
  return proposition.indice.details.find((c) => motif.test(c.critere)) ?? null
}

/** Repère la ou les meilleures valeurs d'une ligne (ex aequo compris). */
function meilleurs(valeurs: (number | null)[], sens: Sens): boolean[] {
  const definies = valeurs.filter((v): v is number => v !== null)
  if (valeurs.length < 2 || definies.length === 0) return valeurs.map(() => false)
  const cible = sens === 'max' ? Math.max(...definies) : Math.min(...definies)
  return valeurs.map((v) => v !== null && Math.abs(v - cible) < 1e-9)
}

function construireLignes(colonnes: PropositionSite[]): Ligne[] {
  return [
    {
      id: 'pedagogie',
      libelle: 'Intérêt pédagogique',
      aide: 'Programme et thèmes du site',
      Icone: BookOpen,
      sens: 'max',
      cellules: colonnes.map(({ site, proposition }) => {
        const c = critere(proposition, MOTIF_PEDAGOGIE)
        return {
          valeur: c && c.max > 0 ? c.points / c.max : null,
          contenu: (
            <>
              <p className="font-bold tabular-nums">{c ? `${formaterPoints(c.points)}/${formaterPoints(c.max)}` : 'Non évalué'}</p>
              {c?.explication && <p className="text-xs leading-snug">{c.explication}</p>}
              {site.themes.length > 0 && (
                <ul aria-label="Thèmes" className="flex flex-wrap gap-1">
                  {site.themes.slice(0, 3).map((theme) => (
                    <li key={theme} className="badge badge-ghost badge-sm">
                      {theme}
                    </li>
                  ))}
                </ul>
              )}
            </>
          ),
        }
      }),
    },
    {
      id: 'simplicite',
      libelle: 'Simplicité du trajet',
      aide: 'Correspondances, puis durée',
      Icone: Route,
      sens: 'min',
      cellules: colonnes.map(({ proposition: { aller, retour } }) => ({
        valeur: (aller.correspondances + retour.correspondances) * 600 + aller.duree_min + retour.duree_min,
        contenu: (
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 tabular-nums">
            <dt className="font-bold">Aller</dt>
            <dd>
              {aller.depart} → {aller.arrivee} · {formaterDuree(aller.duree_min)} ·{' '}
              {libelleCorrespondances(aller.correspondances)}
            </dd>
            <dt className="font-bold">Retour</dt>
            <dd>
              {retour.depart} → {retour.arrivee} · {formaterDuree(retour.duree_min)} ·{' '}
              {libelleCorrespondances(retour.correspondances)}
            </dd>
          </dl>
        ),
      })),
    },
    {
      id: 'accessibilite',
      libelle: 'Accessibilité',
      aide: 'De la gare au site',
      Icone: Accessibility,
      sens: 'min',
      cellules: colonnes.map(({ site: { acces_gare_site: acces } }) => {
        const IconeAcces = acces.mode === 'pied' ? Footprints : Bus
        return {
          valeur: RANG_NIVEAU[acces.niveau] * 1000 + acces.minutes_groupe,
          contenu: (
            <>
              <p className="flex items-center gap-1.5 font-bold tabular-nums">
                <IconeAcces className="size-4 shrink-0" aria-hidden="true" />
                {libelleAcces(acces)}
              </p>
              <PastilleNiveau niveau={acces.niveau} libelle={LIBELLES_ACCES[acces.niveau]} />
            </>
          ),
        }
      }),
    },
    {
      id: 'fiabilite',
      libelle: 'Fiabilité',
      aide: 'Indice Confiance Voyageur Scolaire',
      Icone: ShieldCheck,
      sens: 'max',
      cellules: colonnes.map(({ proposition: { indice } }) => ({
        valeur: indice.score,
        contenu: (
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xl font-extrabold tabular-nums">
              {Math.round(indice.score)}
              <span className="text-xs font-semibold">/100</span>
            </p>
            <PastilleNiveau niveau={indice.niveau} />
          </div>
        ),
      })),
    },
    {
      id: 'disponibilite',
      libelle: 'Disponibilité',
      aide: 'Places libres sur le train le moins bien placé',
      Icone: Users,
      sens: 'max',
      cellules: colonnes.map(({ proposition: { jauge_aller, jauge_retour } }) => {
        const disponibles = Math.min(jauge_aller.disponibles, jauge_retour.disponibles)
        const besoin = Math.max(jauge_aller.besoin, jauge_retour.besoin)
        const niveau = niveauLePlusBas(jauge_aller.niveau, jauge_retour.niveau)
        return {
          valeur: disponibles - besoin,
          contenu: (
            <>
              <p className="font-bold tabular-nums">
                {disponibles} {pluriel(disponibles, 'place')} pour {besoin} {pluriel(besoin, 'voyageur')}
              </p>
              <PastilleNiveau niveau={niveau} libelle={LIBELLES_JAUGE[niveau]} />
            </>
          ),
        }
      }),
    },
    {
      id: 'satisfaction',
      libelle: 'Satisfaction',
      aide: 'Retours des enseignants déjà partis',
      Icone: Heart,
      sens: 'max',
      cellules: colonnes.map(({ proposition }) => {
        const c = critere(proposition, MOTIF_SATISFACTION)
        const sansRetour = !c || MOTIF_SANS_RETOUR.test(c.explication)
        return {
          valeur: !sansRetour && c && c.max > 0 ? c.points / c.max : null,
          contenu:
            sansRetour || !c ? (
              <p className="font-semibold">Pas encore de retours</p>
            ) : (
              <>
                <p className="font-bold tabular-nums">
                  {formaterPoints(c.points)}/{formaterPoints(c.max)}
                </p>
                <p className="text-xs leading-snug">{c.explication}</p>
              </>
            ),
        }
      }),
    },
  ]
}

export default function Comparer() {
  const navigate = useNavigate()
  const etroit = useEcranEtroit()
  const { demande, comparaison, basculerComparaison, choisirProposition, choisirSite, siteChoisi } = useVoyage()

  const lignes = useMemo(
    () =>
      construireLignes(comparaison).map((ligne) => ({
        ...ligne,
        meilleurs: meilleurs(
          ligne.cellules.map((c) => c.valeur),
          ligne.sens,
        ),
      })),
    [comparaison],
  )

  /** Colonne recommandée : le plus de critères gagnés, puis le meilleur indice ; jamais une proposition rouge. */
  const { meilleureColonne, victoires } = useMemo(() => {
    const totaux = comparaison.map((_, i) => lignes.filter((l) => l.meilleurs[i]).length)
    let retenue: number | null = null
    comparaison.forEach(({ proposition }, i) => {
      if (proposition.indice.niveau === 'rouge') return
      if (
        retenue === null ||
        totaux[i] > totaux[retenue] ||
        (totaux[i] === totaux[retenue] && proposition.indice.score > comparaison[retenue].proposition.indice.score)
      ) {
        retenue = i
      }
    })
    return { meilleureColonne: retenue as number | null, victoires: totaux }
  }, [comparaison, lignes])

  function choisir(element: PropositionSite) {
    if (element.proposition.indice.niveau === 'rouge') return
    choisirSite(element.site)
    choisirProposition(element)
    navigate('/pre-reservation')
  }

  const lienAjout = siteChoisi ? `/trajets/${encodeURIComponent(siteChoisi.site_id)}` : '/destinations'
  const retour = siteChoisi
    ? { libelle: 'Trains', vers: lienAjout }
    : { libelle: 'Destinations', vers: '/destinations' }

  if (comparaison.length === 0) {
    return (
      <>
        <div className={CONTENEUR}>
          <IntroEcran titre="Comparer" phrase="Vos trajets côte à côte, sur les 6 critères de la fiche." humeur="repos" />
          <EtatVide
            titre="Aucun trajet à comparer pour l'instant"
            humeur="repos"
            actions={
              <>
                <Link to={lienAjout} className="btn btn-sm">
                  <ArrowLeft className="size-4" aria-hidden="true" />
                  {siteChoisi ? `Revenir aux trains pour ${siteChoisi.nom}` : 'Voir les destinations'}
                </Link>
                {siteChoisi && (
                  <Link to="/destinations" className="btn btn-ghost btn-sm">
                    Autres destinations
                  </Link>
                )}
              </>
            }
          >
            <p>
              Sur l'écran « Comment y aller ? », sélectionnez un trajet puis « Ajouter à la comparaison ». Comparez
              jusqu'à {MAX_COMPARAISON} trajets.
            </p>
          </EtatVide>
        </div>
        <BarreAction retour={retour} aide="Ajoutez deux ou trois trajets pour les comparer." />
      </>
    )
  }

  const colonneRecommandee = meilleureColonne !== null ? comparaison[meilleureColonne] : null
  const memeSite =
    !!colonneRecommandee &&
    comparaison.filter((c) => c.site.site_id === colonneRecommandee.site.site_id).length > 1
  const nomRecommande = colonneRecommandee
    ? `${colonneRecommandee.site.nom}${memeSite ? ` (${colonneRecommandee.proposition.aller.depart})` : ''}`
    : null
  const messageTchouette =
    comparaison.length === 1
      ? 'Ajoutez un ou deux autres trajets pour les comparer. En attendant, voici celui-ci sur les 6 critères de la fiche.'
      : colonneRecommandee && meilleureColonne !== null
        ? `La meilleure option de chaque critère est marquée « Meilleur ». ${colonneRecommandee.site.nom} (départ ${colonneRecommandee.proposition.aller.depart}) l'emporte sur ${victoires[meilleureColonne]} ${pluriel(victoires[meilleureColonne], 'critère')} sur 6.`
        : 'Aucune de ces propositions n’est adaptée à votre groupe : revenez aux trains pour en choisir une autre.'

  return (
    <>
      <div className={CONTENEUR}>
        <IntroEcran
          titre="Comparer"
          phrase={`${comparaison.length} ${pluriel(comparaison.length, 'trajet')} côte à côte, sur les 6 critères de la fiche.`}
          humeur={colonneRecommandee ? 'joie' : 'inquiete'}
          aside={<BulleTchouette texte={messageTchouette} />}
        />

        {demande && <BandeauDemande demande={demande} />}

        <section
          aria-labelledby="titre-tableau"
          className="card min-w-0 border-2 border-secondary bg-base-100 shadow-[4px_4px_0_0] shadow-secondary motion-safe:animate-entree"
        >
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-base-300 px-4 py-2.5">
            <h2 id="titre-tableau" className="text-lg font-bold lg:text-xl">
              Tableau de comparaison
            </h2>
            <p className="flex items-center gap-1.5 text-xs">
              <Award className="size-3.5 shrink-0" aria-hidden="true" />
              « Meilleur » marque la meilleure valeur de chaque ligne, ex aequo compris.
            </p>
          </div>
          <div className="max-w-full overflow-x-auto">
            <table className="table table-sm text-sm">
              <caption className="sr-only">
                Comparaison de {comparaison.length} {pluriel(comparaison.length, 'trajet')} sur 6 critères. La meilleure
                valeur de chaque ligne est marquée « Meilleur ».
              </caption>
              <thead className="text-base-content">
                <tr className="border-b-2 border-base-300">
                  <th scope="col" className="sticky left-0 z-1 w-40 min-w-40 bg-base-100 align-bottom text-xs uppercase tracking-wide lg:w-52 lg:min-w-52">
                    Critère
                  </th>
                  {comparaison.map(({ site, proposition }, i) => (
                    <th key={proposition.proposition_id} scope="col" className="min-w-52 align-bottom">
                      <div className="grid gap-1">
                        {meilleureColonne === i && comparaison.length > 1 && (
                          <span className="badge badge-accent badge-sm w-fit gap-1 font-bold motion-safe:animate-pop">
                            <Trophy className="size-3.5" aria-hidden="true" />
                            Recommandé
                          </span>
                        )}
                        <span className="text-sm font-bold leading-tight">{site.nom}</span>
                        <span className="text-xs font-semibold tabular-nums">
                          {site.commune} · {formaterDateCourte(proposition.date)} · départ {proposition.aller.depart}
                        </span>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {lignes.map((ligne) => (
                  <tr key={ligne.id} className="border-b border-base-300">
                    <th scope="row" className="sticky left-0 z-1 bg-base-100 align-top">
                      <span className="flex items-center gap-1.5 font-bold">
                        <ligne.Icone className="size-4 shrink-0" aria-hidden="true" />
                        {ligne.libelle}
                      </span>
                      <span className="mt-0.5 block text-xs font-normal leading-snug">{ligne.aide}</span>
                    </th>
                    {ligne.cellules.map((cellule, i) => (
                      <td
                        key={comparaison[i].proposition.proposition_id}
                        className={ligne.meilleurs[i] ? 'bg-accent/15 align-top' : 'align-top'}
                      >
                        <div className="grid justify-items-start gap-1">
                          {ligne.meilleurs[i] && (
                            <span className="badge badge-accent badge-sm gap-1 font-bold">
                              <Award className="size-3.5" aria-hidden="true" />
                              Meilleur
                            </span>
                          )}
                          {cellule.contenu}
                        </div>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
              <tfoot className="text-base-content">
                <tr className="border-t-2 border-base-300">
                  <th scope="row" className="sticky left-0 z-1 bg-base-100 align-middle text-xs uppercase tracking-wide">
                    Votre choix
                  </th>
                  {comparaison.map((element) => {
                    const { site, proposition } = element
                    const rouge = proposition.indice.niveau === 'rouge'
                    const libelleTrajet = `${site.nom}, ${formaterDateCourte(proposition.date)}, départ ${proposition.aller.depart}`
                    return (
                      <td key={proposition.proposition_id} className="align-top">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => choisir(element)}
                            disabled={rouge}
                            className="btn btn-sm"
                          >
                            <Ticket className="size-4" aria-hidden="true" />
                            Choisir
                            <span className="sr-only"> {libelleTrajet}</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => basculerComparaison(element)}
                            className="btn btn-ghost btn-sm"
                          >
                            <X className="size-4" aria-hidden="true" />
                            Retirer
                            <span className="sr-only"> {libelleTrajet}</span>
                          </button>
                        </div>
                        {rouge && <p className="mt-1 text-xs font-semibold">Non adapté à votre groupe</p>}
                      </td>
                    )
                  })}
                </tr>
              </tfoot>
            </table>
          </div>
        </section>
      </div>

      <BarreAction
        retour={retour}
        aide={
          colonneRecommandee
            ? `Tchouette recommande ${colonneRecommandee.site.nom}.`
            : 'Aucun trajet adapté : revenez aux trains.'
        }
        secondaire={
          comparaison.length < MAX_COMPARAISON ? (
            <Link to={lienAjout} className="btn btn-ghost btn-sm">
              <Plus className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">Ajouter un trajet</span>
              <span className="sr-only sm:hidden">Ajouter un trajet</span>
            </Link>
          ) : undefined
        }
        principal={{
          libelle: nomRecommande && !etroit ? `Pré-réserver ${nomRecommande}` : 'Pré-réserver',
          onClick: () => colonneRecommandee && choisir(colonneRecommandee),
          desactive: !colonneRecommandee,
          raison: 'Aucun trajet comparé n’est adapté à votre groupe.',
          icone: <Ticket className="size-4" aria-hidden="true" />,
        }}
      />
    </>
  )
}
