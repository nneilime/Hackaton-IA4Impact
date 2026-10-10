#!/usr/bin/env bash
# Refait les trois extraits du fond de carte (≈ 140 Mo au total) depuis le build Protomaps du jour choisi.
# Usage : outils/extraire-fond.sh [AAAAMMJJ]     (par défaut 20261009)
# Seules les zones demandées sont téléchargées (lecture par plages d'un fichier de 139 Go).
set -euo pipefail
ICI="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="${1:-20261009}"
SRC="https://build.protomaps.com/${BUILD}.pmtiles"
OUTIL="$ICI/telechargements/pmtiles-bin/pmtiles"
if [ ! -x "$OUTIL" ]; then
  mkdir -p "$ICI/telechargements/pmtiles-bin"
  curl -sSL -o "$ICI/telechargements/pmtiles-bin/go-pmtiles.tar.gz" \
    https://github.com/protomaps/go-pmtiles/releases/download/v1.31.2/go-pmtiles_1.31.2_Linux_x86_64.tar.gz
  tar xzf "$ICI/telechargements/pmtiles-bin/go-pmtiles.tar.gz" -C "$ICI/telechargements/pmtiles-bin" pmtiles
fi
FOND="$ICI/carte/fond"; mkdir -p "$FOND"
# La France pour s'orienter (zooms 0 à 8), le Sud-Ouest et ses cinq départements (9 à 11), la métropole jusqu'au quartier (12 à 14).
"$OUTIL" extract "$SRC" "$FOND/france-z0-8.pmtiles"       --bbox=-6.2,41.0,10.2,51.6  --maxzoom=8                --download-threads=8
"$OUTIL" extract "$SRC" "$FOND/sud-ouest-z9-11.pmtiles"   --bbox=-2.3,42.4,4.5,45.95  --minzoom=9  --maxzoom=11  --download-threads=8
"$OUTIL" extract "$SRC" "$FOND/toulouse-z12-14.pmtiles"   --bbox=0.95,43.33,1.9,43.95 --minzoom=12 --maxzoom=14  --download-threads=8
du -ch "$FOND"/*.pmtiles
