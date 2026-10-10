#!/usr/bin/env bash
# Fond de carte de l'Occitanie seule, servi par le site lui-même (aucun serveur de tuiles tiers) :
#   - public/basemap/occitanie.pmtiles : tuiles vectorielles Protomaps (OpenStreetMap) découpées sur la
#     région, zoom 0 à 13 (MapLibre agrandit au-delà). ~370 Mo, mais le navigateur ne lit que les tuiles
#     affichées, par requêtes HTTP Range.
#   - public/basemap/fonts, public/basemap/sprites : polices et icônes du style Protomaps « light ».
# Trop lourd pour git : à relancer sur chaque machine (ou au déploiement).  Prérequis : brew install pmtiles
#
#   scripts/fetch-basemap.sh [AAAAMMJJ]     (défaut : build Protomaps d'hier)
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=public/basemap
DATE=${1:-$(date -v-1d +%Y%m%d 2>/dev/null || date -d yesterday +%Y%m%d)}
BBOX=-0.9,42.0,5.4,45.4   # = OCCITANIE_BOUNDS dans src/occitanie.ts
ASSETS=https://protomaps.github.io/basemaps-assets

mkdir -p "$OUT/fonts" "$OUT/sprites"
pmtiles extract "https://build.protomaps.com/$DATE.pmtiles" "$OUT/occitanie.pmtiles" --bbox=$BBOX --maxzoom=13

for f in light light@2x; do
  for ext in json png; do curl -fsSL "$ASSETS/sprites/v4/$f.$ext" -o "$OUT/sprites/$f.$ext"; done
done

# Alphabet latin (accents, ligatures, ponctuation typographique) : plages 0 à 8447
for font in "Noto Sans Regular" "Noto Sans Medium" "Noto Sans Italic"; do
  mkdir -p "$OUT/fonts/$font"
  for start in $(seq 0 256 8192); do
    range="$start-$((start + 255))"
    curl -fsSL "$ASSETS/fonts/${font// /%20}/$range.pbf" -o "$OUT/fonts/$font/$range.pbf" || rm -f "$OUT/fonts/$font/$range.pbf"
  done
done
du -sh "$OUT"/*
