import { useEffect, useMemo, useRef } from "react"
import L from "leaflet"
import "leaflet/dist/leaflet.css"
import { CircleMarker, GeoJSON, MapContainer, useMap } from "react-leaflet"
import { franceRegions } from "../data/franceRegions"
import { riskTone, type RiskTone } from "../lib/risk"
import type { RegionStats } from "../lib/regionStats"

const TONE_FILL: Record<RiskTone, string> = {
  rose: "#fda4af",
  amber: "#fcd34d",
  emerald: "#6ee7b7",
}
const NO_DATA_FILL = "#e2e8f0"

// Deliberately more saturated than TONE_FILL (the pastel region choropleth)
// so a clinic marker never blends into a same-tone region — e.g. a "rose"
// clinic sitting on a "rose" region stayed invisible with a shared palette.
const MARKER_FILL: Record<RiskTone, string> = {
  rose: "#e11d48",
  amber: "#d97706",
  emerald: "#059669",
}

function styleFor(
  stats: RegionStats,
  opts: { isSelected: boolean; isDimmed: boolean; isHovered: boolean },
): L.PathOptions {
  return {
    fillColor: stats.tone ? TONE_FILL[stats.tone] : NO_DATA_FILL,
    fillOpacity: opts.isDimmed ? 0.15 : 1,
    color: opts.isSelected ? "#1d4ed8" : opts.isHovered ? "#0f172a" : "#ffffff",
    weight: opts.isSelected || opts.isHovered ? 2.5 : 1.3,
  }
}

function tooltipHtml(stats: RegionStats) {
  const title = `<b>${stats.feature.properties.nom}</b>`
  if (stats.regionClinics.length === 0) {
    return `${title}<br/>Aucune clinique`
  }
  return [
    title,
    `${stats.regionClinics.length} clinique(s)`,
    `${stats.flaggedCount} signalée(s)`,
    `Taux moyen ${stats.avgErrorRate.toFixed(1).replace(".", ",")} %`,
    `Non conforme ${stats.totalLoss.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €`,
  ].join("<br/>")
}

function FitBounds({ bounds }: { bounds: L.LatLngBounds }) {
  const map = useMap()
  useEffect(() => {
    map.fitBounds(bounds, { padding: [24, 24], animate: true })
  }, [map, bounds])
  return null
}

export function FranceMap({
  regionStats,
  selectedRegion,
  hoveredRegion,
  onHoverRegion,
  onSelectRegion,
  onSelectClinic,
}: {
  regionStats: RegionStats[]
  selectedRegion: string | null
  hoveredRegion: string | null
  onHoverRegion: (nom: string | null) => void
  onSelectRegion: (nom: string) => void
  onSelectClinic: (id: number) => void
}) {
  const layersRef = useRef<Record<string, L.Polygon>>({})

  const franceBounds = useMemo(
    () => L.geoJSON(franceRegions as GeoJSON.FeatureCollection).getBounds(),
    [],
  )

  const selectedStats = selectedRegion
    ? (regionStats.find((r) => r.feature.properties.nom === selectedRegion) ??
      null)
    : null

  const fitBounds = useMemo(() => {
    if (!selectedStats) return franceBounds
    const layer = layersRef.current[selectedStats.feature.properties.code]
    return layer ? layer.getBounds() : franceBounds
    // regionStats included so a freshly mounted layer (not yet in the ref on
    // the first selection render) is picked up once it registers itself.
  }, [selectedStats, franceBounds, regionStats])

  useEffect(() => {
    regionStats.forEach((stats) => {
      const layer = layersRef.current[stats.feature.properties.code]
      if (!layer) return
      layer.setStyle(
        styleFor(stats, {
          isSelected: stats.feature.properties.nom === selectedRegion,
          isDimmed:
            selectedRegion !== null &&
            stats.feature.properties.nom !== selectedRegion,
          isHovered: stats.feature.properties.nom === hoveredRegion,
        }),
      )
    })
  }, [regionStats, selectedRegion, hoveredRegion])

  return (
    <MapContainer
      center={[46.7, 2.5]}
      zoom={6}
      scrollWheelZoom
      attributionControl={false}
      className="h-full w-full"
      style={{ background: "#eff4fb" }}
    >
      <FitBounds bounds={fitBounds} />
      <GeoJSON
        // tooltips and handlers are bound once per mount: remount when the figures change
        key={regionStats.map((r) => `${r.regionClinics.length}:${r.avgErrorRate}`).join("|")}
        data={franceRegions as GeoJSON.FeatureCollection}
        style={(feature) => {
          const stats = regionStats.find(
            (r) => r.feature.properties.code === feature?.properties?.code,
          )
          if (!stats) return {}
          return styleFor(stats, {
            isSelected: stats.feature.properties.nom === selectedRegion,
            isDimmed:
              selectedRegion !== null &&
              stats.feature.properties.nom !== selectedRegion,
            isHovered: false,
          })
        }}
        onEachFeature={(feature, layer) => {
          const code = feature.properties?.code as string
          const stats = regionStats.find(
            (r) => r.feature.properties.code === code,
          )
          if (!stats) return
          layersRef.current[code] = (layer as L.Polygon)
          layer.bindTooltip(tooltipHtml(stats), {
            sticky: true,
            className: "region-tooltip",
          })
          layer.on({
            mouseover: () => onHoverRegion(stats.feature.properties.nom),
            mouseout: () => onHoverRegion(null),
            click: () => onSelectRegion(stats.feature.properties.nom),
          })
        }}
      />
      {selectedStats?.regionClinics.map((clinic) => (
        <CircleMarker
          key={clinic.id}
          center={[clinic.lat, clinic.lon]}
          radius={9}
          pathOptions={{
            color: "#ffffff",
            weight: 2.5,
            fillColor: MARKER_FILL[riskTone(clinic.errorRate)],
            fillOpacity: 1,
          }}
          eventHandlers={{ click: () => onSelectClinic(clinic.id) }}
        />
      ))}
    </MapContainer>
  )
}
