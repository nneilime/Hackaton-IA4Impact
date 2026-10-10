import { api } from "../api/client"
import type { ClinicStats } from "../api/types"
import { useApi } from "../lib/useApi"
import { franceRegions } from "./franceRegions"

// A clinic as the manager screens use it, built from GET /clinics. Amounts are in euros here.
export type Clinic = {
  id: number
  name: string
  city: string
  region: string
  finess: string
  caisse: string
  invoices: number
  issues: number
  pending: number
  reports: number
  errorRate: number
  financialLoss: number // billed amount of the invoices found non-compliant
  lat: number
  lon: number
}

// Centre of a region's bounding box: where a clinic without known coordinates is drawn.
const regionCentres = new Map(
  franceRegions.features.map((feature) => {
    const rings =
      feature.geometry.type === "Polygon" ? feature.geometry.coordinates : feature.geometry.coordinates.flat()
    const points = rings.flat()
    const lons = points.map((p) => p[0])
    const lats = points.map((p) => p[1])
    return [
      feature.properties.nom,
      [(Math.min(...lats) + Math.max(...lats)) / 2, (Math.min(...lons) + Math.max(...lons)) / 2] as const,
    ]
  }),
)

export function toClinic(row: ClinicStats): Clinic {
  const centre = regionCentres.get(row.region ?? "") ?? [46.6, 2.4]
  // spread clinics that share a fallback position so their markers stay clickable
  const jitter = row.lat === null ? ((row.id % 7) - 3) * 0.08 : 0
  return {
    id: row.id,
    name: row.name ?? `Établissement ${row.finess}`,
    city: row.city ?? "Ville inconnue",
    region: row.region ?? "Région inconnue",
    finess: row.finess,
    caisse: row.caisse ?? "Caisse inconnue",
    invoices: row.invoices,
    issues: row.issues,
    pending: row.pending,
    reports: row.reports,
    errorRate: row.error_rate,
    financialLoss: row.at_risk / 100,
    lat: row.lat ?? centre[0] + jitter,
    lon: row.lon ?? centre[1] + jitter,
  }
}

export function useClinics() {
  const state = useApi(async () => (await api.clinics()).map(toClinic), [])
  return { clinics: state.data ?? [], loading: state.loading, error: state.error, reload: state.reload }
}
