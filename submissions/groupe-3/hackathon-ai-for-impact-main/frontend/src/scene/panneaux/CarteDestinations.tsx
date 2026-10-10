import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Footprints, MapPin, TrainFront } from 'lucide-react'
import type { CarteGeo, PointCarte } from '../../api/types'

interface Props {
  carte: CarteGeo
  /** Numéros des candidates cochées par l'enseignant : mises en avant. */
  selectionnes?: number[]
  className?: string
}

function echapper(t: string): string {
  return t.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}

/** Repère HTML (pas d'image : aucun fichier à charger, donc toujours visible même sans tuiles). */
function icone(p: PointCarte, coche: boolean): L.DivIcon {
  const base =
    'display:grid;place-items:center;border-radius:9999px;font:800 13px/1 system-ui,sans-serif;border:2px solid #0B2341;box-sizing:border-box;'
  let style = base
  let html = ''
  let taille = 28
  if (p.type === 'depart') {
    style += 'background:#0B2341;color:#fff;border-radius:6px;'
    html = 'D'
  } else if (p.type === 'arrivee') {
    style += 'background:#fff;color:#0B2341;border-radius:6px;'
    html = 'G'
  } else if (p.type === 'destination') {
    taille = 34
    style += 'background:#C8102E;color:#fff;border-color:#fff;box-shadow:0 0 0 3px #0B2341;'
    html = String(p.numero ?? '')
  } else {
    // jaune en fond, jamais en texte sur blanc
    style += `background:#FFCD00;color:#0B2341;${coche ? 'box-shadow:0 0 0 3px #0B2341;' : 'opacity:.85;'}`
    if (coche) taille = 32
    html = String(p.numero ?? '')
  }
  return L.divIcon({
    className: '',
    html: `<div style="${style}width:${taille}px;height:${taille}px">${echapper(html)}</div>`,
    iconSize: [taille, taille],
    iconAnchor: [taille / 2, taille / 2],
  })
}

export default function CarteDestinations({ carte, selectionnes = [], className }: Props) {
  const conteneur = useRef<HTMLDivElement>(null)
  const cle = JSON.stringify([carte, selectionnes])

  useEffect(() => {
    const el = conteneur.current
    if (!el) return
    const map = L.map(el, { zoomControl: true, attributionControl: true, scrollWheelZoom: false })
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map)
    const bornes: L.LatLngExpression[] = []
    carte.traces.forEach((t, i) => {
      L.polyline(t, { color: '#C8102E', weight: 4, dashArray: i === 0 ? '2 8' : undefined, lineCap: 'round' }).addTo(map)
      bornes.push(...t)
    })
    for (const p of carte.points) {
      const coche = p.numero != null && selectionnes.includes(p.numero)
      L.marker([p.lat, p.lon], {
        icon: icone(p, coche),
        title: p.libelle,
        alt: p.libelle,
        zIndexOffset: p.type === 'destination' ? 1000 : coche ? 500 : 0,
      })
        .bindTooltip(p.libelle, { direction: 'top', offset: [0, -12] })
        .addTo(map)
      bornes.push([p.lat, p.lon])
    }
    if (bornes.length > 1) map.fitBounds(L.latLngBounds(bornes), { padding: [28, 28], maxZoom: 14 })
    else map.setView(carte.centre, carte.zoom)
    return () => {
      map.remove()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cle])

  return (
    <figure className={`grid min-w-0 gap-2 ${className ?? ''}`}>
      <div
        ref={conteneur}
        role="img"
        aria-label="Carte : gare de départ, destinations candidates et gare d’arrivée"
        className="h-[220px] w-full overflow-hidden rounded-field border-2 border-secondary bg-base-200"
      />
      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-semibold">
        <span className="flex items-center gap-1.5">
          <TrainFront className="size-3.5" aria-hidden="true" />
          D départ · G gare d’arrivée
        </span>
        <span className="flex items-center gap-1.5">
          <MapPin className="size-3.5" aria-hidden="true" />
          Numéros : destinations
        </span>
        {carte.traces.length > 0 && (
          <span className="flex items-center gap-1.5">
            <Footprints className="size-3.5" aria-hidden="true" />
            Pointillés : marche gare → site
          </span>
        )}
      </figcaption>
      <ul className="sr-only">
        {carte.points.map((p, i) => (
          <li key={i}>{p.libelle}</li>
        ))}
      </ul>
    </figure>
  )
}
