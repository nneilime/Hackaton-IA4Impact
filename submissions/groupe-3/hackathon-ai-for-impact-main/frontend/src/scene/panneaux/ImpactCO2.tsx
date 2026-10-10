import { useEffect, useRef, useState } from 'react'
import { Leaf } from 'lucide-react'

/** Distance à vol d'oiseau (formule de haversine), en km. */
export function distanceKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const rad = (x: number) => (x * Math.PI) / 180
  const dLat = rad(b.lat - a.lat)
  const dLon = rad(b.lon - a.lon)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2
  return 2 * 6371 * Math.asin(Math.sqrt(h))
}

interface Props {
  /** Distance aller-retour entre les gares, en km (à vol d'oiseau). */
  km: number
}

/**
 * Simulateur ADEME « Impact CO2 » (impactco2.fr), adapté au trajet : TER (train liO) comparé à la voiture
 * thermique, avec voiture électrique et autocar. Aucun facteur d'émission n'est codé ici : tous les chiffres
 * viennent du widget officiel.
 */
export default function ImpactCO2({ km }: Props) {
  const conteneur = useRef<HTMLDivElement>(null)
  const [echec, setEchec] = useState(false)
  const kmArrondi = Math.max(1, Math.round(km))

  useEffect(() => {
    const zone = conteneur.current
    if (!zone) return
    setEchec(false)
    zone.replaceChildren()
    const script = document.createElement('script')
    script.src = 'https://impactco2.fr/iframe.js'
    script.async = true
    script.setAttribute('data-name', 'impact-co2')
    script.setAttribute('data-type', 'transport')
    script.setAttribute(
      'data-search',
      `?theme=default&language=fr&km=${kmArrondi}&defaultMode=comparison&comparison=ter,voiturethermique&modes=voitureelectrique,autocar`,
    )
    script.onerror = () => setEchec(true)
    zone.appendChild(script)
    // Hors ligne ou script bloqué : si aucun iframe n'apparaît au bout de 6 s, on affiche le repli.
    const veille = window.setTimeout(() => {
      if (!zone.querySelector('iframe')) setEchec(true)
    }, 6000)
    return () => {
      window.clearTimeout(veille)
      zone.replaceChildren()
    }
  }, [kmArrondi])

  return (
    <section aria-label="Impact carbone du trajet" className="grid min-w-0 gap-2 rounded-field bg-base-200 p-3">
      <p className="flex items-center gap-1.5 text-xs font-semibold text-base-content/70">
        <Leaf className="size-3.5 shrink-0" aria-hidden="true" />
        Impact carbone de votre sortie
      </p>
      <p className="text-sm leading-snug">
        Comparaison pour <span className="font-bold tabular-nums">{kmArrondi} km</span> (aller-retour, distance à vol
        d’oiseau entre les gares).
      </p>
      <div ref={conteneur} className="min-w-0 overflow-hidden" />
      {echec && (
        <p role="note" className="text-xs leading-snug">
          Le simulateur ne s’est pas chargé (connexion indisponible). Il compare le TER, la voiture et l’autocar sur
          impactco2.fr.
        </p>
      )}
      <p className="text-xs text-base-content/70">Source : ADEME, impactco2.fr</p>
    </section>
  )
}
