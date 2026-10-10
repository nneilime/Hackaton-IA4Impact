import raw from "./franceRegions.json"

// Real (simplified) boundaries of the 13 metropolitan French regions —
// sourced once from the public "france-geojson" dataset and simplified
// (Douglas-Peucker, ~2km tolerance, islets dropped) down to ~38KB so it
// ships locally and the app works fully offline. See franceRegions.json.
export type LonLat = [number, number]

export type RegionProperties = {
  code: string
  nom: string
}

export type RegionFeature = {
  type: "Feature"
  properties: RegionProperties
  geometry: { type: "Polygon"; coordinates: LonLat[][] } | {
    type: "MultiPolygon"
    coordinates: LonLat[][][]
  }
}

export type RegionsGeoJSON = {
  type: "FeatureCollection"
  features: RegionFeature[]
}

export const franceRegions = raw as unknown as RegionsGeoJSON
