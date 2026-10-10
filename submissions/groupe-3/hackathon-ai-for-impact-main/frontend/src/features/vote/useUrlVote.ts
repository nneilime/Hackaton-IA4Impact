import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { estLocal, urlVote } from './vote'

export type AdresseVote =
  | { etat: 'calcul' }
  | { etat: 'prete'; url: string }
  /** Site ouvert sur localhost et IP locale introuvable : les téléphones ne peuvent pas la joindre. */
  | { etat: 'sans-ip' }

type IpLocale = { etat: 'calcul' } | { etat: 'trouvee'; ip: string } | { etat: 'sans-ip' }

/**
 * Adresse que les téléphones des élèves doivent ouvrir. Sur localhost, elle n'a de sens que pour
 * l'ordinateur de l'enseignant : on la remplace par l'adresse IP de la machine sur le Wi-Fi.
 */
export function useUrlVote(code: string): AdresseVote {
  const { hostname, origin, protocol, port } = window.location
  const local = estLocal(hostname)
  const [ip, setIp] = useState<IpLocale>({ etat: 'calcul' })

  useEffect(() => {
    if (!local) return
    let annule = false
    api
      .reseau()
      .then(({ ip_locale }) => {
        if (!annule) setIp(ip_locale ? { etat: 'trouvee', ip: ip_locale } : { etat: 'sans-ip' })
      })
      .catch(() => {
        if (!annule) setIp({ etat: 'sans-ip' })
      })
    return () => {
      annule = true
    }
  }, [local])

  if (!local) return { etat: 'prete', url: urlVote(origin, code) }
  if (ip.etat === 'trouvee') {
    return { etat: 'prete', url: urlVote(`${protocol}//${ip.ip}${port ? `:${port}` : ''}`, code) }
  }
  return ip
}
