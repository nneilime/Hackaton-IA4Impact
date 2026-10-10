import type {
  Demande,
  Dossier,
  MessageChat,
  ReponseChat,
  ReponseDestinations,
  ReponseRetour,
  ReponseTrajets,
  Reseau,
  ReponseScene,
  EtatScene,
  EvenementScene,
  RetourExperience,
  Sante,
  Sondage,
  Destination,
} from './types'

/** Erreur renvoyée par l'API, avec un message lisible à afficher tel quel. */
export class ErreurApi extends Error {
  readonly statut: number

  constructor(message: string, statut: number) {
    super(message)
    this.name = 'ErreurApi'
    this.statut = statut
  }
}

async function appeler<T>(chemin: string, options: RequestInit = {}): Promise<T> {
  let reponse: Response
  try {
    reponse = await fetch(`/api${chemin}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    })
  } catch {
    throw new ErreurApi(
      "Impossible de joindre le serveur du copilote. Vérifiez que l'API tourne sur le port 8000.",
      0,
    )
  }
  if (!reponse.ok) {
    let detail = `Le serveur a répondu avec une erreur ${reponse.status}.`
    try {
      const corps = await reponse.json()
      if (typeof corps?.detail === 'string') detail = corps.detail
    } catch {
      // corps non JSON : on garde le message générique
    }
    throw new ErreurApi(detail, reponse.status)
  }
  return (await reponse.json()) as T
}

const poster = <T>(chemin: string, corps: unknown) =>
  appeler<T>(chemin, { method: 'POST', body: JSON.stringify(corps) })

export const api = {
  sante: () => appeler<Sante>('/sante'),

  chat: (messages: MessageChat[], demande: Demande | null) =>
    poster<ReponseChat>('/chat', { messages, demande }),

  validerDemande: (demande: Demande) => poster<Demande>('/demande/valider', { demande }),

  destinations: (demande: Demande) => poster<ReponseDestinations>('/destinations', { demande }),

  trajets: (demande: Demande, siteId: string) =>
    poster<ReponseTrajets>('/trajets', { demande, site_id: siteId }),

  preReserver: (propositionId: string, email: string, demande: Demande) =>
    poster<Dossier>('/pre-reservations', { proposition_id: propositionId, email, demande }),

  dossier: (reference: string) =>
    appeler<Dossier>(`/pre-reservations/${encodeURIComponent(reference)}`),

  simulerReponse: (reference: string, decision: 'confirmer' | 'contre-proposition') =>
    poster<Dossier>(`/pre-reservations/${encodeURIComponent(reference)}/simuler-reponse`, {
      decision,
    }),

  envoyerRetour: (retour: RetourExperience) => poster<ReponseRetour>('/retours', retour),

  // Vote en classe
  creerSondage: (demande: Demande, destinations: Destination[]) =>
    poster<Sondage>('/sondages', { demande, destinations }),

  sondage: (code: string) => appeler<Sondage>(`/sondages/${encodeURIComponent(code)}`),

  voter: (code: string, siteId: string, votantId: string) =>
    poster<Sondage>(`/sondages/${encodeURIComponent(code)}/votes`, { site_id: siteId, votant_id: votantId }),

  votesManuels: (code: string, votes: Record<string, number>) =>
    poster<Sondage>(`/sondages/${encodeURIComponent(code)}/votes-manuels`, { votes }),

  fermerSondage: (code: string) => poster<Sondage>(`/sondages/${encodeURIComponent(code)}/fermer`, {}),

  reseau: () => appeler<Reseau>('/reseau'),

  // Scène : un tour de dialogue avec Tchouette (le back est une machine à états)
  scene: (etat: EtatScene | null, evenement: EvenementScene) =>
    poster<ReponseScene>('/scene', { etat, evenement }),
}
