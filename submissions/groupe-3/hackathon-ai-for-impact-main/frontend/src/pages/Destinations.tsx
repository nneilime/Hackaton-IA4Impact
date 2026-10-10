import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CircleX, EyeOff, PencilLine, QrCode, RefreshCw, TrainFront, Vote } from 'lucide-react'
import { api, ErreurApi } from '../api/client'
import type { Destination } from '../api/types'
import BarreAction from '../layout/BarreAction'
import BandeauDemande from '../components/voyage/BandeauDemande'
import BulleTchouette from '../components/voyage/BulleTchouette'
import CarteDestination from '../components/voyage/CarteDestination'
import { ChargementTchouette, EtatErreur, EtatVide } from '../components/voyage/EtatsEcran'
import IntroEcran from '../components/voyage/IntroEcran'
import { pluriel } from '../components/voyage/format'
import { useEcranEtroit } from '../components/voyage/useEcranEtroit'
import { useVoyage } from '../state/VoyageContext'

type Statut = 'pret' | 'chargement' | 'erreur'

/** Le vote en classe demande au moins deux options (contrat : 2 à 4). */
const OPTIONS_VOTE_MIN = 2

const CONTENEUR = 'mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)] gap-4 px-4 py-5 lg:gap-5 lg:px-6 lg:py-6'

/** Destination sans train liO compatible : indice 0/100 ou aucun temps de trajet. */
function estEcartee(destination: Destination): boolean {
  return destination.temps_trajet_min === null || Math.round(destination.indice_confiance) <= 0
}

/**
 * Rail horizontal (à partir de lg) : la ligne part de la gare de départ, chaque destination
 * est une gare posée au-dessus de sa carte. La grille superposée reprend les colonnes des cartes.
 */
function RailLigne({ gareDepart, nombre, indexChoisi }: { gareDepart: string; nombre: number; indexChoisi: number }) {
  return (
    <div aria-hidden="true" className="relative hidden h-7 lg:block">
      <span className="absolute inset-x-0 top-1/2 h-2.5 -translate-y-1/2 border-y-2 border-secondary bg-[repeating-linear-gradient(90deg,var(--color-secondary)_0_3px,transparent_3px_11px)]" />
      <div className="absolute inset-0 grid grid-cols-3 gap-4">
        {Array.from({ length: nombre }, (_, index) => (
          <span key={index} className="flex items-center justify-center">
            {index === indexChoisi ? (
              <span key="choisie" className="size-6 rounded-full border-4 border-secondary bg-accent motion-safe:animate-pop" />
            ) : (
              <span className="size-4 rounded-full border-[3px] border-secondary bg-base-100" />
            )}
          </span>
        ))}
      </div>
      <span className="absolute left-0 top-0 flex h-7 items-center gap-1.5 rounded-full bg-secondary ps-1 pe-3 text-xs font-bold text-secondary-content">
        <span className="grid size-5 place-items-center rounded-full bg-accent text-accent-content">
          <TrainFront className="size-3.5" />
        </span>
        <span className="max-w-24 truncate">{gareDepart}</span>
      </span>
    </div>
  )
}

export default function Destinations() {
  const navigate = useNavigate()
  const etroit = useEcranEtroit()
  const groupe = useId()
  const { demande, destinations, siteChoisi, definirDestinations, choisirSite } = useVoyage()
  const [statut, setStatut] = useState<Statut>(demande && destinations.length === 0 ? 'chargement' : 'pret')
  const [erreur, setErreur] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [choix, setChoix] = useState<string | null>(siteChoisi?.site_id ?? null)
  const [voteEnCours, setVoteEnCours] = useState(false)
  const [erreurVote, setErreurVote] = useState<string | null>(null)
  const requete = useRef(0)
  const premierChargement = useRef(false)

  /** Interroge l'API ; l'état « chargement » est posé par l'appelant. */
  const interroger = useCallback(() => {
    if (!demande) return
    const numero = ++requete.current
    api
      .destinations(demande)
      .then((reponse) => {
        if (numero !== requete.current) return
        definirDestinations(reponse.destinations)
        setMessage(reponse.message)
        setStatut('pret')
      })
      .catch((e: unknown) => {
        if (numero !== requete.current) return
        setErreur(e instanceof ErreurApi ? e.message : 'Une erreur inattendue a interrompu la recherche.')
        setStatut('erreur')
      })
  }, [demande, definirDestinations])

  function rechercher() {
    setStatut('chargement')
    setErreur(null)
    interroger()
  }

  useEffect(() => {
    // Une seule recherche automatique, et seulement si rien n'est encore chargé
    // (l'état initial est alors déjà « chargement »).
    if (premierChargement.current) return
    premierChargement.current = true
    if (demande && destinations.length === 0) interroger()
  }, [demande, destinations.length, interroger])

  const visibles = destinations.filter((d) => !estEcartee(d))
  const ecartees = destinations.length - visibles.length
  const choisie = visibles.find((d) => d.site_id === choix) ?? visibles[0] ?? null
  const indexChoisi = choisie ? visibles.indexOf(choisie) : -1

  function voirTrains() {
    if (!choisie) return
    choisirSite(choisie)
    navigate(`/trajets/${encodeURIComponent(choisie.site_id)}`)
  }

  async function faireVoter() {
    if (!demande || visibles.length < OPTIONS_VOTE_MIN) return
    setVoteEnCours(true)
    setErreurVote(null)
    try {
      const sondage = await api.creerSondage(demande, visibles)
      navigate(`/vote/${encodeURIComponent(sondage.code)}/animer`)
    } catch (e: unknown) {
      setErreurVote(e instanceof ErreurApi ? e.message : "Le vote n'a pas pu être créé. Réessayez dans un instant.")
      setVoteEnCours(false)
    }
  }

  if (!demande) {
    return (
      <>
        <div className={CONTENEUR}>
          <IntroEcran titre={'Où aller\u00a0?'} phrase="Trois sorties accessibles en train liO, choisies pour votre programme." humeur="inquiete" />
          <EtatVide
            titre="Décrivez d'abord votre projet de sortie"
            actions={
              <Link to="/" className="btn btn-primary btn-sm">
                <PencilLine className="size-4" aria-hidden="true" />
                Décrire mon projet
              </Link>
            }
          >
            <p>
              Tchouette a besoin de votre classe, de votre thème, du nombre de voyageurs, de la date et de votre gare
              de départ.
            </p>
          </EtatVide>
        </div>
        <BarreAction retour={{ libelle: 'Mon projet', vers: '/' }} aide="Commencez par décrire votre sortie." />
      </>
    )
  }

  const gareDepart = demande.gare_depart?.nom ?? demande.lieu_depart?.libelle ?? 'votre gare'
  const messageAffiche =
    message ??
    (visibles.length > 0
      ? `Ces ${visibles.length} ${pluriel(visibles.length, 'destination')} sont accessibles en train liO depuis ${gareDepart}.`
      : null)
  const voteImpossible = visibles.length < OPTIONS_VOTE_MIN

  return (
    <>
      <div className={CONTENEUR}>
        <IntroEcran
          titre={'Où aller\u00a0?'}
          phrase="Trois sorties du catalogue, choisies pour votre programme et accessibles en train liO."
          humeur={statut === 'chargement' ? 'reflexion' : statut === 'erreur' ? 'inquiete' : 'parle'}
          aside={
            statut === 'chargement' ? (
              <ChargementTchouette texte="Tchouette cherche les sorties adaptées à votre classe…" />
            ) : (
              messageAffiche && <BulleTchouette texte={messageAffiche} />
            )
          }
        />

        <BandeauDemande
          demande={demande}
          action={
            <Link to="/" className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-accent hover:underline">
              <PencilLine className="size-3.5" aria-hidden="true" />
              Modifier
            </Link>
          }
        />

        {statut === 'erreur' && erreur && (
          <EtatErreur titre="Les destinations n'ont pas pu être chargées" message={erreur} onReessayer={rechercher} />
        )}

        {statut === 'chargement' && (
          <section aria-label="Destinations en cours de chargement" className="grid gap-3">
            <div className="skeleton h-7 w-64" />
            <div className="grid gap-4 lg:grid-cols-3">
              {[0, 1, 2].map((index) => (
                <div key={index} className="grid gap-3 rounded-box border-2 border-base-300 bg-base-100 p-4">
                  <div className="flex items-center gap-2.5">
                    <div className="skeleton size-7 shrink-0 rounded-full" />
                    <div className="grid flex-1 gap-1.5">
                      <div className="skeleton h-4 w-3/4" />
                      <div className="skeleton h-3 w-1/2" />
                    </div>
                  </div>
                  <div className="skeleton h-3 w-full" />
                  <div className="skeleton h-3 w-11/12" />
                  <div className="skeleton h-3 w-2/3" />
                  <div className="flex gap-1">
                    <div className="skeleton h-5 w-24" />
                    <div className="skeleton h-5 w-20" />
                  </div>
                  <div className="skeleton h-20 w-full" />
                </div>
              ))}
            </div>
          </section>
        )}

        {statut === 'pret' && visibles.length === 0 && (
          <EtatVide
            titre="Aucune destination accessible pour ce projet"
            actions={
              <>
                <Link to="/" className="btn btn-primary btn-sm">
                  <PencilLine className="size-4" aria-hidden="true" />
                  Modifier mon projet
                </Link>
                <button type="button" onClick={rechercher} className="btn btn-outline btn-secondary btn-sm">
                  <RefreshCw className="size-4" aria-hidden="true" />
                  Relancer la recherche
                </button>
              </>
            }
          >
            <p>
              {ecartees > 0
                ? `${ecartees} ${pluriel(ecartees, 'destination écartée', 'destinations écartées')} : aucun train liO compatible ce jour-là depuis ${gareDepart}.`
                : `Le catalogue ne propose pas de site accessible en train liO pour ce thème et cette classe depuis ${gareDepart}.`}
            </p>
            <p>Essayez une autre date, un thème plus large ou une autre gare de départ.</p>
          </EtatVide>
        )}

        {statut === 'pret' && visibles.length > 0 && (
          <section aria-labelledby="titre-destinations" className="grid gap-3">
            <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
              <div className="grid gap-0.5">
                <h2 id="titre-destinations" className="text-lg font-bold lg:text-xl">
                  Choisissez votre destination
                </h2>
                {ecartees > 0 ? (
                  <p className="flex items-center gap-1.5 text-xs font-semibold">
                    <EyeOff className="size-3.5 shrink-0" aria-hidden="true" />
                    {ecartees} {pluriel(ecartees, 'destination écartée', 'destinations écartées')} : aucun train liO
                    compatible ce jour-là
                  </p>
                ) : (
                  <p className="text-xs font-semibold">Cliquez une carte pour la choisir.</p>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <p className="flex max-w-xs items-center gap-1.5 text-xs sm:text-right">
                  <QrCode className="size-4 shrink-0" aria-hidden="true" />
                  {voteImpossible
                    ? 'Le vote demande au moins deux destinations.'
                    : 'Projetez un QR code : vos élèves votent depuis leur téléphone.'}
                </p>
                <button
                  type="button"
                  onClick={faireVoter}
                  disabled={voteEnCours || voteImpossible}
                  className="btn btn-secondary btn-sm"
                >
                  {voteEnCours ? (
                    <span className="loading loading-spinner loading-xs" aria-hidden="true" />
                  ) : (
                    <Vote className="size-4" aria-hidden="true" />
                  )}
                  {voteEnCours ? 'Création du vote…' : 'Faire voter ma classe'}
                </button>
                <button type="button" onClick={rechercher} className="btn btn-ghost btn-sm">
                  <RefreshCw className="size-4" aria-hidden="true" />
                  <span className="hidden sm:inline">Relancer</span>
                  <span className="sr-only sm:hidden">Relancer la recherche</span>
                </button>
              </div>
            </div>

            {erreurVote && (
              <div role="alert" className="alert alert-error alert-soft px-3 py-2 text-sm">
                <CircleX className="size-4 shrink-0" aria-hidden="true" />
                <span>{erreurVote}</span>
              </div>
            )}

            <div className="grid gap-2">
              <RailLigne gareDepart={gareDepart} nombre={visibles.length} indexChoisi={indexChoisi} />
              <div
                role="radiogroup"
                aria-labelledby="titre-destinations"
                className="grid gap-4 lg:grid-cols-3 lg:grid-rows-[auto_auto_1fr_auto]"
              >
                {visibles.map((destination, index) => (
                  <CarteDestination
                    key={destination.site_id}
                    destination={destination}
                    numero={index + 1}
                    groupe={groupe}
                    selectionnee={destination.site_id === choisie?.site_id}
                    onSelectionner={() => setChoix(destination.site_id)}
                  />
                ))}
              </div>
            </div>
          </section>
        )}
      </div>

      <BarreAction
        retour={{ libelle: 'Mon projet', vers: '/' }}
        aide={
          choisie ? `${choisie.nom} : ${Math.round(choisie.indice_confiance)}/100. Voyons ses trains !` : 'Choisissez une destination.'
        }
        principal={{
          libelle: choisie && !etroit ? `Voir les trains pour ${choisie.nom}` : 'Voir les trains',
          onClick: voirTrains,
          desactive: !choisie || statut !== 'pret',
          raison: 'Choisissez d’abord une destination.',
          icone: <TrainFront className="size-4" aria-hidden="true" />,
        }}
      />
    </>
  )
}
