import { useCallback, useState } from 'react'
import { RotateCcw, TriangleAlert } from 'lucide-react'
import type { EvenementScene, HumeurScene, ReponseScene } from '../api/types'
import RailTchouette from '../mascot/RailTchouette'
import BadgesSource from './composants/BadgesSource'
import BarreHaute from './composants/BarreHaute'
import BarreSaisie from './composants/BarreSaisie'
import CartesReponse from './composants/CartesReponse'
import { installerMaquette } from './composants/maquette'
import PucesCriteres from './composants/PucesCriteres'
import WidgetDate from './composants/WidgetDate'
import WidgetEffectif from './composants/WidgetEffectif'
import WidgetLieu from './composants/WidgetLieu'
import PanneauEtape from './panneaux'
import { useScene } from './useScene'

// Maquette hors back : jamais active par défaut (voir composants/maquette.ts).
if (import.meta.env.VITE_SCENE_MAQUETTE === '1') installerMaquette()

/** Parole de Tchouette posée par un panneau (hors back) ; elle ne vaut que pour la réponse en cours. */
interface Surcharge {
  texte: string
  humeur: HumeurScene | undefined
  pour: ReponseScene | null
}

const MESSAGE_ATTENTE_ACCUEIL = 'Tchouette arrive…'
const MESSAGE_ATTENTE = 'Un instant, je regarde ça…'
const MESSAGE_ERREUR_SANS_REPONSE = 'Oups, je n’arrive pas à joindre mon aiguilleur.'

/** Squelette à la forme des cartes : jamais d'écran vide pendant un tour. */
function SqueletteCartes() {
  return (
    <div role="status" className="grid grid-cols-1 gap-4 min-[400px]:grid-cols-2">
      <span className="sr-only">Tchouette prépare les réponses…</span>
      <div className="skeleton h-28 w-full" />
      <div className="skeleton h-28 w-full" />
    </div>
  )
}

/**
 * La scène « Tchouette est l'interface » : une réplique à la fois, de grandes cartes à toucher,
 * une barre « Écrire ou parler » toujours visible. Aucune logique métier : le back est la machine à états.
 */
export default function ScenePage() {
  const { reponse, chargement, erreur, envoyer, reessayer, recommencer } = useScene()
  const [surcharge, setSurcharge] = useState<Surcharge | null>(null)

  const commenter = useCallback(
    (texte: string | null, humeur?: HumeurScene) => {
      setSurcharge(texte === null ? null : { texte, humeur, pour: reponse })
    },
    [reponse],
  )

  const agir = useCallback(
    (evenement: EvenementScene) => {
      if (chargement) return
      void envoyer(evenement)
    },
    [chargement, envoyer],
  )

  const choisir = useCallback((id: string) => agir({ type: 'choix', id }), [agir])
  const ecrire = useCallback((texte: string) => agir({ type: 'texte', texte }), [agir])

  const parole = !chargement && surcharge && surcharge.pour === reponse ? surcharge : null
  const replique = chargement
    ? reponse
      ? MESSAGE_ATTENTE
      : MESSAGE_ATTENTE_ACCUEIL
    : (parole?.texte ?? (erreur && !reponse ? MESSAGE_ERREUR_SANS_REPONSE : (reponse?.replique ?? MESSAGE_ATTENTE_ACCUEIL)))
  const humeur: HumeurScene = chargement
    ? 'loupe'
    : erreur
      ? 'inquiete'
      : (parole?.humeur ?? reponse?.humeur ?? 'salue')

  const attente = chargement || (!reponse && !erreur)
  const primairePresente = reponse?.cartes.some((c) => c.style === 'primaire') ?? false
  const saisie = !attente && reponse ? reponse.saisie : null

  return (
    <div className="relative flex min-h-dvh flex-col overflow-x-clip bg-base-200 bg-[radial-gradient(var(--color-base-300)_1.5px,transparent_1.5px)] bg-size-[22px_22px]">
      {/* Formes plates Memphis : seulement dans les marges des grands écrans, jamais sous le contenu. */}
      <div aria-hidden="true" className="pointer-events-none absolute top-32 right-[5%] hidden size-16 rounded-full bg-accent lg:block" />
      <div aria-hidden="true" className="pointer-events-none absolute top-[58%] left-[4%] hidden h-14 w-28 rounded-t-full bg-primary lg:block" />
      <BarreHaute
        carnet={reponse?.etat.carnet ?? []}
        parcoursAvance={reponse !== null && reponse.etape !== 'accueil'}
        onRecommencer={recommencer}
      />

      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-5 px-4 pt-5 pb-6">
        <h1 className="sr-only">Tchouette, le copilote des sorties scolaires en train liO</h1>

        <RailTchouette ancre={reponse?.ancre ?? 'centre'} humeur={humeur} replique={replique}>
          {!attente && reponse && <BadgesSource badges={reponse.badges} />}
        </RailTchouette>

        {erreur && (
          <div role="alert" className="alert alert-error alert-vertical sm:alert-horizontal motion-safe:animate-entree">
            <TriangleAlert className="size-6 shrink-0" aria-hidden="true" />
            <span className="font-semibold">{erreur}</span>
            <button type="button" onClick={reessayer} disabled={chargement} className="btn btn-md">
              <RotateCcw className="size-4" aria-hidden="true" />
              Réessayer
            </button>
          </div>
        )}

        {reponse && (
          <div className="contents [&>:empty]:hidden">
            <PanneauEtape reponse={reponse} envoyer={agir} chargement={chargement} commenter={commenter} />
          </div>
        )}

        {attente ? (
          <SqueletteCartes />
        ) : (
          reponse && (
            <div key={reponse.etat.tours} className="flex flex-col gap-5">
              <CartesReponse
                cartes={
                  reponse.etape === 'destination' && (reponse.choix_destinations?.length ?? 0) >= 2
                    ? reponse.cartes.filter((c) => c.id !== 'choisir' && c.id !== 'vote') // remplacées par la sélection multiple
                    : reponse.cartes
                }
                onChoisir={choisir}
                desactive={chargement}
              />
              {saisie?.type === 'effectif' && (
                <WidgetEffectif saisie={saisie} actionPrimaireDejaPresente={primairePresente} onValider={agir} />
              )}
              {saisie?.type === 'date' && (
                <WidgetDate saisie={saisie} actionPrimaireDejaPresente={primairePresente} onValider={agir} />
              )}
              {saisie?.type === 'lieu' && (
                <WidgetLieu saisie={saisie} actionPrimaireDejaPresente={primairePresente} onValider={agir} />
              )}
            </div>
          )
        )}
      </main>

      <footer className="sticky bottom-0 z-20 border-t-2 border-secondary bg-base-100 pb-[env(safe-area-inset-bottom)]">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-2 px-4 py-3">
          {reponse && <PucesCriteres puces={reponse.puces} manquants={reponse.manquants} />}
          <BarreSaisie onEnvoyer={ecrire} desactive={chargement} />
        </div>
      </footer>
    </div>
  )
}
