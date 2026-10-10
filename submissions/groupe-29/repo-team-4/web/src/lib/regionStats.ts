import { useMemo } from "react"
import type { Clinic } from "../data/clinics"
import { franceRegions, type RegionFeature } from "../data/franceRegions"
import { riskTone, type RiskTone } from "./risk"

export type RegionStats = {
  feature: RegionFeature
  regionClinics: Clinic[]
  avgErrorRate: number
  flaggedCount: number
  totalLoss: number
  tone: RiskTone | null
}

export function useRegionStats(clinics: Clinic[]): RegionStats[] {
  return useMemo(
    () =>
      franceRegions.features.map((feature) => {
        const regionClinics = clinics.filter(
          (clinic) => clinic.region === feature.properties.nom,
        )
        const avgErrorRate =
          regionClinics.length === 0
            ? 0
            : regionClinics.reduce((sum, c) => sum + c.errorRate, 0) /
              regionClinics.length
        return {
          feature,
          regionClinics,
          avgErrorRate,
          flaggedCount: regionClinics.filter((c) => c.errorRate > 15).length,
          totalLoss: regionClinics.reduce((sum, c) => sum + c.financialLoss, 0),
          tone: regionClinics.length === 0 ? null : riskTone(avgErrorRate),
        }
      }),
    [clinics],
  )
}
