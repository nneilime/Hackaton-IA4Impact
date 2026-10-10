import { useCallback, useEffect, useState } from 'react'
import { ErreurApi, api } from '../../api/client'
import type { Dossier } from '../../api/types'
import { useVoyage } from '../../state/VoyageContext'

interface Resultat {
  /** Requête à laquelle ce résultat répond (référence + numéro d'essai). */
  cle: string
  erreur: ErreurApi | null
}

/**
 * Charge un dossier par sa référence. Le dossier du contexte sert d'affichage immédiat
 * s'il correspond, puis il est rafraîchi depuis l'API (le contexte reste la seule source).
 */
export function useDossier(reference: string | undefined) {
  const { dossier: dossierContexte, definirDossier } = useVoyage()
  const [essai, setEssai] = useState(0)
  const [resultat, setResultat] = useState<Resultat | null>(null)
  const cle = `${reference ?? ''}#${essai}`

  useEffect(() => {
    if (!reference) return
    let annule = false
    api
      .dossier(reference)
      .then((frais) => {
        if (annule) return
        definirDossier(frais)
        setResultat({ cle, erreur: null })
      })
      .catch((cause: unknown) => {
        if (annule) return
        setResultat({
          cle,
          erreur:
            cause instanceof ErreurApi
              ? cause
              : new ErreurApi('Une erreur inattendue est survenue pendant le chargement du dossier.', 0),
        })
      })
    return () => {
      annule = true
    }
  }, [cle, reference, definirDossier])

  const recharger = useCallback(() => setEssai((n) => n + 1), [])
  const remplacer = useCallback((nouveau: Dossier) => definirDossier(nouveau), [definirDossier])

  const chargement = Boolean(reference) && resultat?.cle !== cle
  const erreur = !chargement ? (resultat?.erreur ?? null) : null
  const dossier = dossierContexte && dossierContexte.reference === reference ? dossierContexte : null

  return {
    dossier,
    chargement,
    erreur,
    introuvable: erreur?.statut === 404,
    recharger,
    remplacer,
  }
}
