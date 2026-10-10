import { useCallback, useEffect, useId, useRef, useState } from 'react'
import type { Ref } from 'react'
import { Link } from 'react-router-dom'
import { FolderOpen, Lightbulb, LightbulbOff, RotateCcw } from 'lucide-react'
import Tchouette from '../mascot/Tchouette'
import { useMouvementReduit } from '../mascot/useMouvementReduit'
import TrainLio from './TrainLio'

// Bandeau haut du shell (48 px) : marque, actions globales, et le train liO qui
// passe derrière. Tchouette fait coucou à chaque passage du train.

/** Décalage du coucou après le départ du cycle : le nez du train arrive sur Tchouette. */
const DEBUT_SALUT_MS = 450
/** Durée d'un coucou complet (montée, 2 à 3 battements, descente). */
const DUREE_SALUT_MS = 2400

/**
 * Coucou calé sur le cycle de 11 s du train : chaque début de traversée (événements
 * `animationstart` / `animationiteration`) programme le salut. Minuteurs nettoyés
 * au démontage. Rien si l'utilisateur demande moins d'animations.
 */
function useSalutAuPassage() {
  const mouvementReduit = useMouvementReduit()
  const [salue, setSalue] = useState(false)
  const minuteurs = useRef<number[]>([])

  const annuler = useCallback(() => {
    minuteurs.current.forEach((id) => window.clearTimeout(id))
    minuteurs.current = []
  }, [])

  useEffect(() => annuler, [annuler])

  const auPassage = useCallback(() => {
    if (mouvementReduit) return
    annuler()
    minuteurs.current = [
      window.setTimeout(() => setSalue(true), DEBUT_SALUT_MS),
      window.setTimeout(() => setSalue(false), DEBUT_SALUT_MS + DUREE_SALUT_MS),
    ]
  }, [annuler, mouvementReduit])

  return { salue: salue && !mouvementReduit, auPassage }
}

/** Bouton d'action du bandeau : carré 40 px sur mobile (icône seule), compact avec libellé ensuite. */
const BOUTON =
  'btn btn-secondary btn-square btn-md border-secondary-content/25 sm:btn-sm sm:w-auto sm:px-3 focus-visible:outline-accent'

interface HeaderTrainProps {
  /** Lien vers le dossier en cours, s'il existe. */
  lienDossier: string | null
  /** Vrai s'il y a un voyage en cours : « Nouvelle sortie » demande alors confirmation. */
  voyageEnCours: boolean
  onNouvelleSortie: () => void
  /** État du guide d'étape ; `null` quand la page n'en a pas (404). */
  guideVisible: boolean | null
  onBasculerGuide: () => void
  refBoutonGuide: Ref<HTMLButtonElement>
}

export default function HeaderTrain({
  lienDossier,
  voyageEnCours,
  onNouvelleSortie,
  guideVisible,
  onBasculerGuide,
  refBoutonGuide,
}: HeaderTrainProps) {
  const { salue, auPassage } = useSalutAuPassage()
  const refConfirmation = useRef<HTMLDialogElement>(null)
  const idTitreConfirmation = useId()

  function demanderNouvelleSortie() {
    if (voyageEnCours) refConfirmation.current?.showModal()
    else onNouvelleSortie()
  }

  function confirmerNouvelleSortie() {
    refConfirmation.current?.close()
    onNouvelleSortie()
  }

  return (
    <div className="relative isolate">
      <TrainLio onPassage={auPassage} />

      {/* Le contenu repose sur des aplats bleu nuit : le train passe derrière sans gêner la lecture. */}
      <nav className="navbar relative z-10 mx-auto min-h-12 max-w-7xl gap-2 px-4 py-0 lg:px-6" aria-label="Navigation principale">
        <div className="navbar-start min-w-0">
          <Link
            to="/"
            title="Revenir à l'accueil"
            className="flex min-w-0 items-center gap-2 rounded-field bg-secondary py-0.5 pr-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <Tchouette humeur={salue ? 'salue' : 'repos'} taille={40} titre="" className="shrink-0" />
            <span className="flex min-w-0 flex-col leading-tight">
              <span className="text-base font-extrabold tracking-tight">Tchouette</span>
              <span className="hidden truncate text-xs font-semibold text-secondary-content/80 sm:block">
                Copilote des sorties scolaires liO
              </span>
            </span>
          </Link>
        </div>

        <div className="navbar-end gap-1.5">
          {guideVisible !== null && (
            <button
              ref={refBoutonGuide}
              type="button"
              onClick={onBasculerGuide}
              aria-pressed={guideVisible}
              title={guideVisible ? 'Masquer les astuces de Tchouette' : 'Afficher les astuces de Tchouette'}
              className={BOUTON}
            >
              {guideVisible ? (
                <Lightbulb className="size-4 text-accent" aria-hidden="true" />
              ) : (
                <LightbulbOff className="size-4" aria-hidden="true" />
              )}
              <span className="hidden lg:inline">Astuces</span>
              <span className="sr-only lg:hidden">Astuces de Tchouette</span>
            </button>
          )}
          {lienDossier && (
            <Link to={lienDossier} className={BOUTON}>
              <FolderOpen className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">Mon dossier</span>
              <span className="sr-only sm:hidden">Mon dossier</span>
            </Link>
          )}
          <button type="button" onClick={demanderNouvelleSortie} aria-haspopup="dialog" className={BOUTON}>
            <RotateCcw className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Nouvelle sortie</span>
            <span className="sr-only sm:hidden">Nouvelle sortie</span>
          </button>
        </div>
      </nav>

      {/* Confirmation avant d'effacer le voyage en cours (couche supérieure : hors du bandeau). */}
      <dialog ref={refConfirmation} className="modal" aria-labelledby={idTitreConfirmation}>
        <div className="modal-box max-w-sm border-2 border-secondary p-4 text-base-content">
          <div className="flex items-start gap-3">
            <Tchouette humeur="inquiete" taille={56} titre="" className="shrink-0" />
            <div className="flex min-w-0 flex-col gap-1">
              <h2 id={idTitreConfirmation} className="text-base font-bold">
                Repartir de zéro ?
              </h2>
              <p className="text-sm text-base-content/80">
                Votre projet, vos trajets et le lien du dossier seront effacés de cet onglet.
              </p>
            </div>
          </div>
          <div className="modal-action mt-4">
            <form method="dialog">
              <button type="submit" className="btn btn-ghost btn-sm">
                Garder ma sortie
              </button>
            </form>
            <button type="button" onClick={confirmerNouvelleSortie} className="btn btn-error btn-sm">
              <RotateCcw className="size-4" aria-hidden="true" />
              Effacer et recommencer
            </button>
          </div>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button type="submit">Fermer</button>
        </form>
      </dialog>
    </div>
  )
}
