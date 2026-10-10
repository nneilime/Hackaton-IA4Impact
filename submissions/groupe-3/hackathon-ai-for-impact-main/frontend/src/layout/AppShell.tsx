import { useEffect, useRef, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useVoyage } from '../state/VoyageContext'
import { ecranDuChemin } from './etapes'
import GuideEtape from './GuideEtape'
import HeaderTrain from './HeaderTrain'
import LigneEtapes from './LigneEtapes'
import PiedDePage from './PiedDePage'

// Le shell du parcours : en-tête collant (bandeau liO + ligne des étapes + barre de guidage),
// page animée à chaque changement de route, pied de page compact.
//
// Hauteurs exactes de l'en-tête, identiques à toutes les largeurs :
//   bandeau 48 px + étapes 48 px = 96 px ; + guidage 41 px (40 + bordure) = 137 px.
// Collant à partir de `sm` (640 px) ; sur téléphone il défile avec la page pour laisser la place au contenu.
// Les pages lisent la hauteur courante dans `--hauteur-header` (ex. `lg:top-[calc(var(--hauteur-header)+1rem)]`).

const CLE_GUIDE_MASQUE = 'tchouette-guide-masque'

/* Classes complètes (pas de concaténation) : la variable suit la présence du guidage. */
const RACINE_AVEC_GUIDE = 'flex min-h-dvh flex-col bg-base-200 text-base-content [--hauteur-header:137px]'
const RACINE_SANS_GUIDE = 'flex min-h-dvh flex-col bg-base-200 text-base-content [--hauteur-header:96px]'

function lireGuideMasque(): boolean {
  try {
    return sessionStorage.getItem(CLE_GUIDE_MASQUE) === '1'
  } catch {
    return false
  }
}

export default function AppShell() {
  const { pathname, key: cleVisite } = useLocation()
  const navigate = useNavigate()
  const { demande, messages, siteChoisi, comparaison, propositionChoisie, dossier, reinitialiser } = useVoyage()
  const [guideMasque, setGuideMasque] = useState(lireGuideMasque)
  const refBoutonGuide = useRef<HTMLButtonElement>(null)

  const ecran = ecranDuChemin(pathname)
  const reference = dossier?.reference ?? null
  const guideAffiche = ecran !== null && !guideMasque

  // Chaque nouvelle page repart du haut.
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0 })
  }, [pathname])

  function definirGuideMasque(masque: boolean) {
    setGuideMasque(masque)
    try {
      sessionStorage.setItem(CLE_GUIDE_MASQUE, masque ? '1' : '0')
    } catch {
      // stockage indisponible : le choix vaut pour cet onglet seulement
    }
  }

  function masquerGuide() {
    definirGuideMasque(true)
    // Le bouton de fermeture disparaît : le focus va au bouton « Astuces » du bandeau.
    refBoutonGuide.current?.focus()
  }

  function nouvelleSortie() {
    reinitialiser()
    navigate('/')
  }

  return (
    <div className={guideAffiche ? RACINE_AVEC_GUIDE : RACINE_SANS_GUIDE}>
      <a
        href="#contenu"
        className="btn btn-sm btn-accent fixed top-2 left-2 z-40 -translate-y-16 focus:translate-y-0"
      >
        Aller au contenu
      </a>

      <header className="z-30 bg-secondary text-secondary-content sm:sticky sm:top-0 print:hidden">
        <HeaderTrain
          lienDossier={reference ? `/dossier/${encodeURIComponent(reference)}` : null}
          voyageEnCours={demande !== null || dossier !== null || messages.length > 0}
          onNouvelleSortie={nouvelleSortie}
          guideVisible={ecran ? !guideMasque : null}
          onBasculerGuide={() => definirGuideMasque(!guideMasque)}
          refBoutonGuide={refBoutonGuide}
        />
        <LigneEtapes
          courante={ecran?.etape ?? null}
          avancement={{
            demande: demande !== null,
            siteId: siteChoisi?.site_id ?? null,
            comparaison: comparaison.length,
            propositionChoisie: propositionChoisie !== null,
            reference,
          }}
        />
        {ecran && guideAffiche && <GuideEtape ecran={ecran} cleVisite={cleVisite} onMasquer={masquerGuide} />}
      </header>

      <main id="contenu" tabIndex={-1} className="flex-1 focus:outline-none">
        {/* Nouvelle clé à chaque route : la page réapparaît en fondu (motion-safe). */}
        <div key={pathname} className="motion-safe:animate-entree">
          <Outlet />
        </div>
      </main>

      <PiedDePage />
    </div>
  )
}
