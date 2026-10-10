import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Bus,
  Check,
  CornerDownRight,
  Footprints,
  MapPin,
  PencilLine,
  Plus,
  RefreshCw,
  Scale,
  Ticket,
  TrainFront,
  TriangleAlert,
} from 'lucide-react'
import { api, ErreurApi } from '../api/client'
import type { Destination, Proposition } from '../api/types'
import BarreAction from '../layout/BarreAction'
import BandeauDemande from '../components/voyage/BandeauDemande'
import BulleTchouette from '../components/voyage/BulleTchouette'
import CarteProposition from '../components/voyage/CarteProposition'
import { ChargementTchouette, EtatErreur, EtatVide } from '../components/voyage/EtatsEcran'
import IntroEcran from '../components/voyage/IntroEcran'
import PastilleNiveau from '../components/voyage/PastilleNiveau'
import { LIBELLES_ACCES } from '../components/voyage/niveaux'
import { formaterDateCourte, formaterDateLongue, libelleAcces, nombreVoyageurs, pluriel } from '../components/voyage/format'
import { useEcranEtroit } from '../components/voyage/useEcranEtroit'
import { MAX_COMPARAISON, useVoyage } from '../state/VoyageContext'

type Statut = 'pret' | 'chargement' | 'erreur'

interface Avis {
  ton: 'info' | 'plein'
  texte: string
}

const CONTENEUR = 'mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)] gap-4 px-4 py-5 lg:gap-5 lg:px-6 lg:py-6'

/** Entrée décalée des propositions (data-rang = position dans la liste). */
const ENTREE =
  'motion-safe:data-[rang=0]:animate-entree motion-safe:data-[rang=1]:animate-[entree_280ms_ease-out_70ms_both] motion-safe:data-[rang=2]:animate-[entree_280ms_ease-out_140ms_both] motion-safe:data-[rang=3]:animate-[entree_280ms_ease-out_210ms_both] motion-safe:data-[rang=4]:animate-[entree_280ms_ease-out_280ms_both]'

/** Une proposition rouge et son alternative, groupées dans un cadre pointillé (gares reliées). */
const GROUPE_ALTERNATIVE =
  'grid gap-2 rounded-box border-2 border-dashed border-base-300 p-2 motion-safe:data-[rang=0]:animate-entree motion-safe:data-[rang=1]:animate-[entree_280ms_ease-out_70ms_both] motion-safe:data-[rang=2]:animate-[entree_280ms_ease-out_140ms_both] motion-safe:data-[rang=3]:animate-[entree_280ms_ease-out_210ms_both] motion-safe:data-[rang=4]:animate-[entree_280ms_ease-out_280ms_both]'

/** Une proposition et les alternatives qui la remplacent, affichées ensemble. */
interface Groupe {
  principale: Proposition
  alternatives: Proposition[]
}

function grouper(propositions: Proposition[]): Groupe[] {
  const ids = new Set(propositions.map((p) => p.proposition_id))
  const alternatives = new Map<string, Proposition[]>()
  const principales: Proposition[] = []
  for (const proposition of propositions) {
    if (proposition.est_alternative && proposition.remplace && ids.has(proposition.remplace)) {
      alternatives.set(proposition.remplace, [...(alternatives.get(proposition.remplace) ?? []), proposition])
    } else {
      principales.push(proposition)
    }
  }
  return principales.map((principale) => ({
    principale,
    alternatives: alternatives.get(principale.proposition_id) ?? [],
  }))
}

export default function Trajets() {
  const { siteId = '' } = useParams()
  // Une instance par site : changer de site repart d'un état propre.
  return <TrajetsDuSite key={siteId} siteId={siteId} />
}

function TrajetsDuSite({ siteId }: { siteId: string }) {
  const navigate = useNavigate()
  const etroit = useEcranEtroit()
  const groupeRadio = useId()
  const {
    demande,
    destinations,
    siteChoisi,
    propositionsParSite,
    definirPropositions,
    choisirSite,
    comparaison,
    basculerComparaison,
    choisirProposition,
  } = useVoyage()

  const siteConnu =
    siteChoisi?.site_id === siteId ? siteChoisi : (destinations.find((d) => d.site_id === siteId) ?? null)
  const enCache = propositionsParSite[siteId]
  const [site, setSite] = useState<Destination | null>(siteConnu)
  const [message, setMessage] = useState<string | null>(null)
  const [statut, setStatut] = useState<Statut>(demande && !(enCache && siteConnu) ? 'chargement' : 'pret')
  const [erreur, setErreur] = useState<string | null>(null)
  const [avis, setAvis] = useState<Avis | null>(null)
  const [choix, setChoix] = useState<string | null>(null)
  const requete = useRef(0)
  const premierChargement = useRef(false)

  /** Interroge l'API ; l'état « chargement » est posé par l'appelant. */
  const interroger = useCallback(() => {
    if (!demande) return
    const numero = ++requete.current
    api
      .trajets(demande, siteId)
      .then((reponse) => {
        if (numero !== requete.current) return
        definirPropositions(siteId, reponse.propositions)
        setSite(reponse.site)
        choisirSite(reponse.site)
        setMessage(reponse.message)
        setStatut('pret')
      })
      .catch((e: unknown) => {
        if (numero !== requete.current) return
        setErreur(
          e instanceof ErreurApi ? e.message : 'Une erreur inattendue a interrompu la recherche des trains.',
        )
        setStatut('erreur')
      })
  }, [demande, siteId, definirPropositions, choisirSite])

  function charger() {
    setStatut('chargement')
    setErreur(null)
    interroger()
  }

  useEffect(() => {
    // Un seul chargement automatique, seulement sans cache (l'état initial est alors « chargement »).
    if (premierChargement.current) return
    premierChargement.current = true
    if (demande && !(enCache && siteConnu)) interroger()
  }, [demande, enCache, siteConnu, interroger])

  useEffect(() => {
    if (!avis) return
    const minuteur = window.setTimeout(() => setAvis(null), 3500)
    return () => window.clearTimeout(minuteur)
  }, [avis])

  const groupes = useMemo(() => grouper(enCache ?? []), [enCache])
  const propositions = useMemo(() => groupes.flatMap((g) => [g.principale, ...g.alternatives]), [groupes])

  const meilleure = useMemo(
    () =>
      propositions
        .filter((p) => p.indice.niveau !== 'rouge')
        .reduce<Proposition | null>((m, p) => (!m || p.indice.score > m.indice.score ? p : m), null),
    [propositions],
  )

  // Par défaut, la meilleure proposition est sélectionnée : l'action principale est prête tout de suite.
  const choisie = propositions.find((p) => p.proposition_id === choix) ?? meilleure ?? propositions[0] ?? null
  const choisieRouge = choisie?.indice.niveau === 'rouge'
  const choisieComparee =
    !!choisie && comparaison.some((c) => c.proposition.proposition_id === choisie.proposition_id)

  function basculer(proposition: Proposition) {
    if (!site) return
    const present = comparaison.some((c) => c.proposition.proposition_id === proposition.proposition_id)
    if (!present && comparaison.length >= MAX_COMPARAISON) {
      setAvis({
        ton: 'plein',
        texte: `Déjà ${MAX_COMPARAISON} trajets comparés : retirez-en un sur l'écran Comparer.`,
      })
      return
    }
    basculerComparaison({ site, proposition })
    setAvis({
      ton: 'info',
      texte: present
        ? 'Retiré de la comparaison.'
        : `Ajouté à la comparaison (${comparaison.length + 1} sur ${MAX_COMPARAISON}).`,
    })
  }

  function preReserver() {
    if (!site || !choisie || choisieRouge) return
    choisirSite(site)
    choisirProposition({ site, proposition: choisie })
    navigate('/pre-reservation')
  }

  const retour = { libelle: 'Destinations', vers: '/destinations' }

  if (!demande) {
    return (
      <>
        <div className={CONTENEUR}>
          <IntroEcran titre={'Comment y aller ?'} phrase="Les trains liO vérifiés pour votre groupe." humeur="inquiete" />
          <EtatVide
            titre="Décrivez d'abord votre projet de sortie"
            actions={
              <Link to="/" className="btn btn-primary btn-sm">
                <PencilLine className="size-4" aria-hidden="true" />
                Décrire mon projet
              </Link>
            }
          >
            <p>Pour vérifier les trains liO, Tchouette doit connaître la date, le nombre de voyageurs et votre gare.</p>
          </EtatVide>
        </div>
        <BarreAction retour={retour} aide="Commencez par décrire votre sortie." />
      </>
    )
  }

  const messageAffiche =
    message ??
    (site ? `Voici les trains liO possibles pour ${site.nom}. Ce qui n'est pas garanti est signalé.` : null)
  const IconeAcces = site?.acces_gare_site.mode === 'urbain' ? Bus : Footprints
  const voyageurs = nombreVoyageurs(demande)

  return (
    <>
      <div className={CONTENEUR}>
        <IntroEcran
          titre={'Comment y aller ?'}
          phrase={site ? `Les trains liO vers ${site.nom}, vérifiés point par point.` : 'Les trains liO, vérifiés point par point.'}
          humeur={statut === 'chargement' ? 'reflexion' : statut === 'erreur' ? 'inquiete' : 'parle'}
          aside={
            statut === 'chargement' ? (
              <ChargementTchouette texte="Tchouette vérifie les trains, les places et les horaires…" />
            ) : (
              messageAffiche && <BulleTchouette texte={messageAffiche} />
            )
          }
        />

        <BandeauDemande
          demande={demande}
          gareArrivee={site?.gare.nom ?? null}
          action={
            <Link to="/" className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-accent hover:underline">
              <PencilLine className="size-3.5" aria-hidden="true" />
              Modifier
            </Link>
          }
        />

        {statut === 'erreur' && erreur && (
          <EtatErreur titre="Les trains n'ont pas pu être chargés" message={erreur} onReessayer={charger} />
        )}

        {statut === 'chargement' && (
          <div aria-hidden="true" className="grid gap-4">
            <div className="skeleton h-7 w-72" />
            {[0, 1].map((index) => (
              <div key={index} className="grid gap-3 rounded-box border-2 border-base-300 bg-base-100 p-4">
                <div className="flex items-center gap-3">
                  <div className="skeleton size-5 rounded-full" />
                  <div className="skeleton h-4 w-56" />
                </div>
                <div className="grid gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,4fr)_minmax(0,3fr)]">
                  <div className="grid gap-3">
                    <div className="skeleton h-12 w-full" />
                    <div className="skeleton h-12 w-full" />
                  </div>
                  <div className="grid gap-3">
                    <div className="skeleton h-10 w-full" />
                    <div className="skeleton h-10 w-full" />
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="skeleton size-14 shrink-0 rounded-full" />
                    <div className="grid flex-1 gap-2">
                      <div className="skeleton h-4 w-full" />
                      <div className="skeleton h-4 w-2/3" />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {statut === 'pret' && propositions.length === 0 && (
          <EtatVide
            titre="Aucun train liO compatible avec votre groupe ce jour-là"
            actions={
              <>
                <Link to="/destinations" className="btn btn-primary btn-sm">
                  <ArrowLeft className="size-4" aria-hidden="true" />
                  Autres destinations
                </Link>
                <Link to="/" className="btn btn-outline btn-secondary btn-sm">
                  <PencilLine className="size-4" aria-hidden="true" />
                  Modifier mon projet
                </Link>
              </>
            }
          >
            <p>
              Aucun train liO ouvert aux groupes ne permet d'arriver à temps, de rentrer avant{' '}
              {demande.heure_retour_max ?? "l'heure prévue"} et d'accueillir{' '}
              {voyageurs !== null ? `vos ${voyageurs} voyageurs` : 'tout votre groupe'} le{' '}
              {formaterDateLongue(demande.date)}.
            </p>
          </EtatVide>
        )}

        {statut === 'pret' && propositions.length > 0 && site && (
          <section aria-labelledby="titre-propositions" className="grid gap-3">
            <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
              <div className="grid gap-1">
                <h2 id="titre-propositions" className="text-lg font-bold lg:text-xl">
                  {propositions.length} {pluriel(propositions.length, 'proposition')} pour {site.nom}
                </h2>
                <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-semibold">
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
                    {site.commune}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <TrainFront className="size-3.5 shrink-0" aria-hidden="true" />
                    Gare de {site.gare.nom}
                  </span>
                  <span className="inline-flex items-center gap-1 tabular-nums">
                    <IconeAcces className="size-3.5 shrink-0" aria-hidden="true" />
                    {libelleAcces(site.acces_gare_site)}
                  </span>
                  <PastilleNiveau niveau={site.acces_gare_site.niveau} libelle={LIBELLES_ACCES[site.acces_gare_site.niveau]} />
                </p>
              </div>
              <button type="button" onClick={charger} className="btn btn-ghost btn-sm">
                <RefreshCw className="size-4" aria-hidden="true" />
                Actualiser les trains
              </button>
            </div>

            <ol aria-label="Propositions de trajet" className="grid gap-4">
              {groupes.map(({ principale, alternatives }, indexGroupe) => {
                const numeroPrincipale = indexGroupe + 1
                const rang = Math.min(indexGroupe, 4)
                const carte = (proposition: Proposition, estAlternative: boolean) => (
                  <CarteProposition
                    proposition={proposition}
                    numero={estAlternative ? null : numeroPrincipale}
                    numeroRemplace={estAlternative ? numeroPrincipale : null}
                    alternativeId={!estAlternative ? (alternatives[0]?.proposition_id ?? null) : null}
                    dateDemande={demande.date}
                    estMeilleure={meilleure?.proposition_id === proposition.proposition_id}
                    dansComparaison={comparaison.some((c) => c.proposition.proposition_id === proposition.proposition_id)}
                    selectionnee={choisie?.proposition_id === proposition.proposition_id}
                    groupe={groupeRadio}
                    onSelectionner={() => setChoix(proposition.proposition_id)}
                    onVoirAlternative={() => alternatives[0] && setChoix(alternatives[0].proposition_id)}
                  />
                )
                if (alternatives.length === 0) {
                  return (
                    <li key={principale.proposition_id} data-rang={rang} className={ENTREE}>
                      {carte(principale, false)}
                    </li>
                  )
                }
                return (
                  <li
                    key={principale.proposition_id}
                    aria-label={`Proposition ${numeroPrincipale} et son alternative`}
                    data-rang={rang}
                    className={GROUPE_ALTERNATIVE}
                  >
                    {carte(principale, false)}
                    {alternatives.map((alternative) => (
                      <div key={alternative.proposition_id} className="grid gap-1 lg:grid-cols-[1.75rem_minmax(0,1fr)]">
                        <CornerDownRight className="ms-1 mt-3 hidden size-5 text-secondary lg:block" aria-hidden="true" />
                        {carte(alternative, true)}
                      </div>
                    ))}
                  </li>
                )
              })}
            </ol>
          </section>
        )}
      </div>

      {/* Retour immédiat sur l'ajout à la comparaison, au-dessus de la barre d'action */}
      <div aria-live="polite" className="toast toast-end bottom-20 z-30">
        {avis && (
          <div
            role="status"
            className={
              avis.ton === 'plein'
                ? 'alert alert-warning px-3 py-2 text-sm'
                : 'alert border-2 border-secondary bg-base-100 px-3 py-2 text-sm text-base-content'
            }
          >
            {avis.ton === 'plein' ? (
              <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
            ) : (
              <Check className="size-4 shrink-0 text-success" aria-hidden="true" />
            )}
            <span>{avis.texte}</span>
          </div>
        )}
      </div>

      <BarreAction
        retour={retour}
        aide={
          choisie
            ? choisieRouge
              ? 'Ce trajet ne convient pas : regardez son alternative.'
              : `${formaterDateCourte(choisie.date)} : départ ${choisie.aller.depart}, retour en gare à ${choisie.retour.arrivee}.`
            : 'Sélectionnez une proposition.'
        }
        secondaire={
          <div className="flex items-center gap-1.5">
            {choisie && site && (
              <button
                type="button"
                onClick={() => basculer(choisie)}
                className={choisieComparee ? 'btn btn-accent btn-sm' : 'btn btn-outline btn-sm'}
              >
                {choisieComparee ? (
                  <Check className="size-4" aria-hidden="true" />
                ) : (
                  <Plus className="size-4" aria-hidden="true" />
                )}
                <span className="hidden lg:inline">
                  {choisieComparee ? 'Retirer de la comparaison' : 'Ajouter à la comparaison'}
                </span>
                <span className="sr-only lg:hidden">
                  {choisieComparee ? 'Retirer de la comparaison' : 'Ajouter à la comparaison'}
                </span>
              </button>
            )}
            <Link to="/comparer" className="btn btn-ghost btn-sm">
              <Scale className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">Comparer ·</span>
              <span
                key={comparaison.length}
                className="badge badge-secondary badge-sm font-bold tabular-nums motion-safe:animate-pop"
              >
                {comparaison.length}
              </span>
              <span className="sr-only">
                {' '}
                {pluriel(comparaison.length, 'trajet comparé', 'trajets comparés')}, voir la comparaison
              </span>
            </Link>
          </div>
        }
        principal={{
          libelle: etroit ? 'Pré-réserver' : 'Pré-réserver ce trajet',
          onClick: preReserver,
          desactive: !choisie || choisieRouge || statut !== 'pret',
          raison: choisieRouge
            ? 'Trajet pas adapté à votre groupe : choisissez son alternative.'
            : 'Sélectionnez d’abord une proposition.',
          icone: <Ticket className="size-4" aria-hidden="true" />,
        }}
      />
    </>
  )
}
