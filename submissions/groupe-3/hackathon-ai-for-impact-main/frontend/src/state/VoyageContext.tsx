import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { Demande, Destination, Dossier, MessageChat, Proposition } from '../api/types'

/** Une proposition de trajet avec le site qu'elle dessert, pour comparer et pré-réserver. */
export interface PropositionSite {
  site: Destination
  proposition: Proposition
}

interface EtatVoyage {
  demande: Demande | null
  messages: MessageChat[]
  destinations: Destination[]
  siteChoisi: Destination | null
  propositionsParSite: Record<string, Proposition[]>
  comparaison: PropositionSite[]
  propositionChoisie: PropositionSite | null
  dossier: Dossier | null
}

interface ActionsVoyage {
  definirDemande: (demande: Demande | null) => void
  definirMessages: (messages: MessageChat[]) => void
  definirDestinations: (destinations: Destination[]) => void
  choisirSite: (site: Destination | null) => void
  definirPropositions: (siteId: string, propositions: Proposition[]) => void
  /** Ajoute ou retire une proposition de la comparaison (3 au maximum). */
  basculerComparaison: (element: PropositionSite) => void
  choisirProposition: (element: PropositionSite | null) => void
  definirDossier: (dossier: Dossier | null) => void
  /** Repart de zéro : nouvelle sortie. */
  reinitialiser: () => void
}

const ETAT_INITIAL: EtatVoyage = {
  demande: null,
  messages: [],
  destinations: [],
  siteChoisi: null,
  propositionsParSite: {},
  comparaison: [],
  propositionChoisie: null,
  dossier: null,
}

export const MAX_COMPARAISON = 3
const CLE_STOCKAGE = 'lio-copilote-voyage'

function lireEtatSauvegarde(): EtatVoyage {
  try {
    const brut = sessionStorage.getItem(CLE_STOCKAGE)
    if (!brut) return ETAT_INITIAL
    return { ...ETAT_INITIAL, ...(JSON.parse(brut) as Partial<EtatVoyage>) }
  } catch {
    return ETAT_INITIAL
  }
}

const VoyageContext = createContext<(EtatVoyage & ActionsVoyage) | null>(null)

export function VoyageProvider({ children }: { children: ReactNode }) {
  const [etat, setEtat] = useState<EtatVoyage>(lireEtatSauvegarde)

  useEffect(() => {
    try {
      sessionStorage.setItem(CLE_STOCKAGE, JSON.stringify(etat))
    } catch {
      // stockage indisponible (navigation privée) : l'application fonctionne sans
    }
  }, [etat])

  const definirDemande = useCallback((demande: Demande | null) => setEtat((e) => ({ ...e, demande })), [])
  const definirMessages = useCallback((messages: MessageChat[]) => setEtat((e) => ({ ...e, messages })), [])
  const definirDestinations = useCallback(
    (destinations: Destination[]) => setEtat((e) => ({ ...e, destinations })),
    [],
  )
  const choisirSite = useCallback((siteChoisi: Destination | null) => setEtat((e) => ({ ...e, siteChoisi })), [])
  const definirPropositions = useCallback(
    (siteId: string, propositions: Proposition[]) =>
      setEtat((e) => ({ ...e, propositionsParSite: { ...e.propositionsParSite, [siteId]: propositions } })),
    [],
  )
  const basculerComparaison = useCallback(
    (element: PropositionSite) =>
      setEtat((e) => {
        const id = element.proposition.proposition_id
        const present = e.comparaison.some((c) => c.proposition.proposition_id === id)
        if (present) {
          return { ...e, comparaison: e.comparaison.filter((c) => c.proposition.proposition_id !== id) }
        }
        if (e.comparaison.length >= MAX_COMPARAISON) return e
        return { ...e, comparaison: [...e.comparaison, element] }
      }),
    [],
  )
  const choisirProposition = useCallback(
    (propositionChoisie: PropositionSite | null) => setEtat((e) => ({ ...e, propositionChoisie })),
    [],
  )
  const definirDossier = useCallback((dossier: Dossier | null) => setEtat((e) => ({ ...e, dossier })), [])
  const reinitialiser = useCallback(() => setEtat(ETAT_INITIAL), [])

  const valeur = useMemo(
    () => ({
      ...etat,
      definirDemande,
      definirMessages,
      definirDestinations,
      choisirSite,
      definirPropositions,
      basculerComparaison,
      choisirProposition,
      definirDossier,
      reinitialiser,
    }),
    [
      etat,
      definirDemande,
      definirMessages,
      definirDestinations,
      choisirSite,
      definirPropositions,
      basculerComparaison,
      choisirProposition,
      definirDossier,
      reinitialiser,
    ],
  )

  return <VoyageContext.Provider value={valeur}>{children}</VoyageContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useVoyage() {
  const contexte = useContext(VoyageContext)
  if (!contexte) throw new Error('useVoyage doit être utilisé dans <VoyageProvider>')
  return contexte
}
