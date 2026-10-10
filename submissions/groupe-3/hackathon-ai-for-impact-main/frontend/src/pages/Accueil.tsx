import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import { ClipboardPen, MessagesSquare } from 'lucide-react'
import BilletDemande from '../features/accueil/BilletDemande'
import ChatTchouette from '../features/accueil/ChatTchouette'
import FormulaireProjet from '../features/accueil/FormulaireProjet'
import LignePromesse from '../features/accueil/LignePromesse'
import {
  CHAMPS_OBLIGATOIRES,
  EFFECTIF_MAX,
  EFFECTIF_MIN,
  ID_FORMULAIRE_PROJET,
  LIBELLES_MANQUANTS,
  demandePrete,
  manquantsObligatoires,
} from '../features/accueil/demande'
import type { EtatFormulaire } from '../features/accueil/demande'
import { useConversation } from '../features/accueil/useConversation'
import BarreAction from '../layout/BarreAction'
import Tchouette from '../mascot/Tchouette'
import type { HumeurTchouette } from '../mascot/Tchouette'
import { useVoyage } from '../state/VoyageContext'

type Mode = 'chat' | 'formulaire'

/** Texte alternatif de la mascotte de l'intro, selon son humeur. */
const TITRES_TCHOUETTE: Record<HumeurTchouette, string> = {
  repos: 'Tchouette vous écoute',
  salue: 'Tchouette vous salue et vous écoute',
  reflexion: 'Tchouette réfléchit',
  parle: 'Tchouette vous répond',
  joie: 'Tchouette se réjouit : votre demande est complète',
  inquiete: 'Tchouette s’inquiète : un souci est survenu',
  pointe: 'Tchouette vous montre quelque chose',
  loupe: 'Tchouette examine les données',
  celebre: 'Tchouette fait la fête : votre demande est complète',
}

const libelle = (champ: string) => LIBELLES_MANQUANTS[champ] ?? champ

/** La petite phrase de Tchouette dans la barre d'action (15 mots au plus). */
function phraseAide(etat: {
  mode: Mode
  enErreur: boolean
  enAttente: boolean
  pret: boolean
  manquants: string[]
}): string {
  const { mode, enErreur, enAttente, pret, manquants } = etat
  if (enErreur) return 'Petit souci de connexion. Réessayez, je reste là.'
  if (enAttente)
    return mode === 'chat' ? 'Je lis votre message… une seconde !' : 'Je vérifie votre demande et cherche la gare…'
  if (pret) return 'Tout y est ! En route pour les destinations ?'
  if (manquants.length === 0) return `Ajustez l’effectif : de ${EFFECTIF_MIN} à ${EFFECTIF_MAX} voyageurs par groupe.`
  if (manquants.length === CHAMPS_OBLIGATOIRES.length) {
    return mode === 'chat'
      ? 'Racontez votre sortie, ou touchez l’exemple pour essayer.'
      : 'Remplissez les quatre blocs, le billet se met à jour.'
  }
  if (manquants.length === 1) {
    return mode === 'chat'
      ? `Dites-moi juste ${libelle(manquants[0])} et c’est parti !`
      : `Plus que ${libelle(manquants[0])}, et c’est parti !`
  }
  if (manquants.length === 2) return `Encore ${libelle(manquants[0])} et ${libelle(manquants[1])}, et c’est parti !`
  return `Encore ${manquants.length} informations, et je cherche vos destinations.`
}

/** Pourquoi « Voir les destinations » est désactivé, en une ligne. */
function raisonBlocage(manquants: string[]): string {
  if (manquants.length === 0) return `Ajustez l’effectif : ${EFFECTIF_MIN} à ${EFFECTIF_MAX} voyageurs.`
  if (manquants.length <= 3) return `Il manque : ${manquants.map(libelle).join(', ')}`
  return `Il manque ${manquants.length} informations sur ${CHAMPS_OBLIGATOIRES.length}.`
}

export default function Accueil() {
  const { demande } = useVoyage()
  const conversation = useConversation()
  const [mode, setMode] = useState<Mode>('chat')
  const [etatFormulaire, setEtatFormulaire] = useState<EtatFormulaire>('repos')

  const pret = demandePrete(demande)
  const manquants = manquantsObligatoires(demande)
  const envoiFormulaire = mode === 'formulaire' && etatFormulaire === 'envoi'
  const enAttente = conversation.enAttente || envoiFormulaire
  const enErreur = mode === 'chat' ? conversation.erreur !== null : etatFormulaire === 'erreur'
  const humeur: HumeurTchouette = enErreur
    ? 'inquiete'
    : enAttente
      ? 'reflexion'
      : pret
        ? 'joie'
        : conversation.parle && mode === 'chat'
          ? 'parle'
          : mode === 'chat' && conversation.messages.length === 0 && demande === null
            ? 'salue'
            : 'repos'

  function changerMode(suivant: Mode, focaliser = false) {
    setMode(suivant)
    if (focaliser) document.getElementById(suivant === 'chat' ? 'onglet-chat' : 'onglet-formulaire')?.focus()
  }

  function surToucheOnglets(evenement: KeyboardEvent<HTMLDivElement>) {
    const touches: Record<string, Mode> = {
      ArrowLeft: mode === 'chat' ? 'formulaire' : 'chat',
      ArrowRight: mode === 'chat' ? 'formulaire' : 'chat',
      Home: 'chat',
      End: 'formulaire',
    }
    const suivant = touches[evenement.key]
    if (!suivant) return
    evenement.preventDefault()
    changerMode(suivant, true)
  }

  return (
    <>
      <div className="mx-auto flex max-w-7xl flex-col gap-4 overflow-x-clip px-4 py-5 lg:gap-5 lg:px-6 lg:py-6">
        {/* Intro sur une seule rangée : Tchouette, le titre, la bascule chat / formulaire */}
        <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between md:gap-6">
          <div className="flex min-w-0 items-center gap-3 lg:gap-4">
            <div className="relative shrink-0">
              {/* Deux formes plates Memphis : le « O » en or, un demi-cercle rouge */}
              <span aria-hidden="true" className="absolute -left-1 -top-1 size-12 rounded-full bg-accent" />
              <span aria-hidden="true" className="absolute -bottom-0.5 -right-1.5 h-4 w-8 rounded-t-full bg-primary" />
              <Tchouette humeur={humeur} taille={72} titre={TITRES_TCHOUETTE[humeur]} className="relative" />
            </div>
            <div className="min-w-0">
              <h1 className="text-2xl font-extrabold leading-tight tracking-tight text-balance text-secondary lg:text-3xl">
                Racontez-moi votre sortie,{' '}
                <span className="bg-accent px-1 box-decoration-clone text-accent-content">je trouve le train.</span>
              </h1>
              <p className="mt-0.5 hidden text-sm text-base-content/80 sm:block lg:text-[15px]">
                Des sorties en Occitanie, des trains liO vérifiés pour votre groupe.
              </p>
            </div>
          </div>

          <div
            role="tablist"
            aria-label="Comment décrire votre sortie"
            onKeyDown={surToucheOnglets}
            className="join grid w-full shrink-0 grid-cols-2 rounded-field border-2 border-secondary bg-base-100 md:inline-flex md:w-auto"
          >
            <button
              type="button"
              role="tab"
              id="onglet-chat"
              aria-selected={mode === 'chat'}
              aria-controls="panneau-chat"
              tabIndex={mode === 'chat' ? 0 : -1}
              onClick={() => changerMode('chat')}
              className={
                mode === 'chat'
                  ? 'btn btn-secondary btn-sm join-item gap-1.5 border-0 max-md:h-10'
                  : 'btn btn-ghost btn-sm join-item gap-1.5 border-0 max-md:h-10'
              }
            >
              <MessagesSquare className="size-4 shrink-0" aria-hidden="true" />
              <span className="sm:hidden">Discuter</span>
              <span className="hidden sm:inline">Discuter avec Tchouette</span>
            </button>
            <button
              type="button"
              role="tab"
              id="onglet-formulaire"
              aria-selected={mode === 'formulaire'}
              aria-controls="panneau-formulaire"
              tabIndex={mode === 'formulaire' ? 0 : -1}
              onClick={() => changerMode('formulaire')}
              className={
                mode === 'formulaire'
                  ? 'btn btn-secondary btn-sm join-item gap-1.5 border-0 max-md:h-10'
                  : 'btn btn-ghost btn-sm join-item gap-1.5 border-0 max-md:h-10'
              }
            >
              <ClipboardPen className="size-4 shrink-0" aria-hidden="true" />
              <span className="sm:hidden">Formulaire</span>
              <span className="hidden sm:inline">Remplir le formulaire</span>
            </button>
          </div>
        </header>

        {/* Corps en largeur : la conversation (ou le formulaire) à gauche, le billet à droite */}
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(20rem,1fr)] lg:items-start lg:gap-5">
          <div className="min-w-0">
            <div role="tabpanel" id="panneau-chat" aria-labelledby="onglet-chat" hidden={mode !== 'chat'}>
              {mode === 'chat' && <ChatTchouette conversation={conversation} humeur={humeur} pret={pret} />}
            </div>
            <div
              role="tabpanel"
              id="panneau-formulaire"
              aria-labelledby="onglet-formulaire"
              hidden={mode !== 'formulaire'}
            >
              {mode === 'formulaire' && <FormulaireProjet surEtat={setEtatFormulaire} />}
            </div>
          </div>

          <aside aria-label="Récapitulatif de votre demande" className="min-w-0 lg:sticky lg:top-40">
            <BilletDemande demande={demande} occupe={enAttente} />
          </aside>
        </div>

        <LignePromesse />
      </div>

      {/* Une seule action principale, toujours au même endroit */}
      <BarreAction
        principal={{
          libelle: 'Voir les destinations',
          ...(mode === 'formulaire' ? { form: ID_FORMULAIRE_PROJET } : { vers: '/destinations' }),
          desactive: !pret || conversation.enAttente,
          raison: pret ? 'Tchouette termine sa réponse…' : raisonBlocage(manquants),
          chargement: envoiFormulaire,
        }}
        aide={phraseAide({ mode, enErreur, enAttente, pret, manquants })}
      />
    </>
  )
}
