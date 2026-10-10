import { useEffect, useState } from 'react'
import { Bot, Database, TrainFront, WifiOff } from 'lucide-react'
import { api } from '../api/client'
import type { Sante } from '../api/types'

// Pied de page compact : mention « prototype non officiel » et état du service (GET /api/sante).

type EtatService = { etat: 'verification' } | { etat: 'injoignable' } | { etat: 'ok'; sante: Sante }

function EtatDuService() {
  const [service, setService] = useState<EtatService>({ etat: 'verification' })

  useEffect(() => {
    let actif = true
    api
      .sante()
      .then((sante) => actif && setService({ etat: 'ok', sante }))
      .catch(() => actif && setService({ etat: 'injoignable' }))
    return () => {
      actif = false
    }
  }, [])

  if (service.etat === 'verification') {
    return (
      <span className="badge badge-sm badge-ghost">
        <span className="loading loading-spinner loading-xs" aria-hidden="true" />
        Vérification en cours
      </span>
    )
  }

  if (service.etat === 'injoignable') {
    return (
      <span className="badge badge-sm badge-warning">
        <WifiOff className="size-3" aria-hidden="true" />
        API non joignable
      </span>
    )
  }

  const { donnees, mode } = service.sante
  return (
    <>
      <span className="badge badge-sm badge-ghost">
        <Database className="size-3" aria-hidden="true" />
        {donnees === 'sncf' ? 'Données SNCF du hackathon' : 'Données de démonstration'}
      </span>
      <span className="badge badge-sm badge-ghost">
        {mode === 'llm' ? (
          <span className="status status-sm status-success" aria-hidden="true" />
        ) : (
          <span className="status status-sm status-warning" aria-hidden="true" />
        )}
        <Bot className="size-3" aria-hidden="true" />
        {mode === 'llm' ? 'IA connectée' : 'IA en mode démo'}
      </span>
    </>
  )
}

export default function PiedDePage() {
  return (
    <footer className="bg-neutral text-neutral-content print:hidden">
      <div className="footer mx-auto max-w-7xl items-center gap-x-8 gap-y-3 px-4 py-4 text-xs sm:footer-horizontal lg:px-6">
        <aside className="gap-1">
          <p className="flex items-center gap-2 font-bold">
            <TrainFront className="size-4 text-accent" aria-hidden="true" />
            Prototype non officiel · Hackathon For IA, 9 et 10 octobre 2026
          </p>
          <p className="max-w-3xl text-neutral-content/75">
            Défi SNCF Voyageurs « Dessine-moi une mobilité durable ». Aucune réservation n'est confirmée ici : chaque
            demande liO reste soumise à la validation d'un chargé de clientèle.
          </p>
        </aside>
        <section aria-labelledby="titre-etat-service" className="gap-1.5 sm:justify-self-end">
          <h2 id="titre-etat-service" className="footer-title mb-0 text-xs">
            État du service
          </h2>
          <div className="flex flex-wrap gap-1.5" aria-live="polite">
            <EtatDuService />
          </div>
        </section>
      </div>
    </footer>
  )
}
