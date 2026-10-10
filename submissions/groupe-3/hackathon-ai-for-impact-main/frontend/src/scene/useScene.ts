import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ErreurApi } from '../api/client'
import type { EvenementScene, ReponseScene } from '../api/types'
import { useVoyage } from '../state/VoyageContext'

const CLE_STOCKAGE = 'tchouette-scene-reponse'

function lire(): ReponseScene | null {
  try {
    const brut = sessionStorage.getItem(CLE_STOCKAGE)
    return brut ? (JSON.parse(brut) as ReponseScene) : null
  } catch {
    return null
  }
}

function ecrire(reponse: ReponseScene | null) {
  try {
    if (reponse) sessionStorage.setItem(CLE_STOCKAGE, JSON.stringify(reponse))
    else sessionStorage.removeItem(CLE_STOCKAGE)
  } catch {
    // stockage indisponible : la scène fonctionne sans reprise après rechargement
  }
}

/**
 * Pilote la scène : envoie un événement au back, garde l'état renvoyé (opaque), le persiste, et recopie
 * demande / destination / trajet dans VoyageContext pour que les pages classiques et le vote restent cohérents.
 * Aucune logique métier ici : le back est la machine à états.
 */
export function useScene() {
  const voyage = useVoyage()
  const [reponse, setReponse] = useState<ReponseScene | null>(lire)
  const [chargement, setChargement] = useState(false)
  const [erreur, setErreur] = useState<string | null>(null)
  const derniereReponse = useRef<ReponseScene | null>(reponse)
  const dernierEvenement = useRef<EvenementScene>({ type: 'demarrer' })
  const demarre = useRef(false)

  const appliquer = useCallback(
    (r: ReponseScene) => {
      derniereReponse.current = r
      setReponse(r)
      ecrire(r)
      voyage.definirDemande(r.etat.demande)
      if (r.destination) voyage.choisirSite(r.destination)
      if (r.destination && r.proposition) {
        voyage.choisirProposition({ site: r.destination, proposition: r.proposition })
      }
    },
    // les setters du contexte sont stables
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [voyage.definirDemande, voyage.choisirSite, voyage.choisirProposition],
  )

  const envoyer = useCallback(
    async (evenement: EvenementScene) => {
      dernierEvenement.current = evenement
      setChargement(true)
      setErreur(null)
      try {
        appliquer(await api.scene(derniereReponse.current?.etat ?? null, evenement))
      } catch (e) {
        setErreur(e instanceof ErreurApi ? e.message : "Tchouette n'a pas pu répondre. Réessayez dans un instant.")
      } finally {
        setChargement(false)
      }
    },
    [appliquer],
  )

  // Première visite : Tchouette accueille toute seule (garde contre le double rendu de StrictMode).
  useEffect(() => {
    if (demarre.current || derniereReponse.current) return
    demarre.current = true
    void envoyer({ type: 'demarrer' })
  }, [envoyer])

  const reessayer = useCallback(() => void envoyer(dernierEvenement.current), [envoyer])

  const recommencer = useCallback(() => {
    derniereReponse.current = null
    setReponse(null)
    ecrire(null)
    voyage.reinitialiser()
    void envoyer({ type: 'demarrer' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [envoyer, voyage.reinitialiser])

  return { reponse, chargement, erreur, envoyer, reessayer, recommencer }
}
