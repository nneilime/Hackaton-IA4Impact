#!/usr/bin/env bash
set -euo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
cd "$ICI"
PORT="${PORT:-4860}"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js manque. Sur Mac : brew install node   (ou https://nodejs.org, version 20 ou plus)."
  exit 1
fi
MAJ="$(node -p 'process.versions.node.split(".")[0]')"
if [ "$MAJ" -lt 20 ]; then
  echo "Node.js $MAJ trouvé, il faut la version 20 ou plus."
  exit 1
fi

FOND="$ICI/carte/fond"
if [ ! -s "$FOND/toulouse-z12-14.pmtiles" ] || [ ! -s "$FOND/sud-ouest-z9-11.pmtiles" ] || [ ! -s "$FOND/france-z0-8.pmtiles" ]; then
  echo "Fond de carte absent : téléchargement unique d'environ 140 Mo."
  OS="$(uname -s)"; ARCH="$(uname -m)"
  case "$OS-$ARCH" in
    Darwin-arm64)  ASSET="go-pmtiles-1.31.2_Darwin_arm64.zip" ;;
    Darwin-x86_64) ASSET="go-pmtiles-1.31.2_Darwin_x86_64.zip" ;;
    Linux-x86_64)  ASSET="go-pmtiles_1.31.2_Linux_x86_64.tar.gz" ;;
    Linux-aarch64|Linux-arm64) ASSET="go-pmtiles_1.31.2_Linux_arm64.tar.gz" ;;
    *) echo "Système $OS $ARCH non prévu : voir https://github.com/protomaps/go-pmtiles/releases/tag/v1.31.2"; exit 1 ;;
  esac
  BIN="$ICI/carte/telechargements/pmtiles-bin"
  mkdir -p "$BIN" "$FOND"
  if [ ! -x "$BIN/pmtiles" ]; then
    curl -sSL -o "$BIN/$ASSET" "https://github.com/protomaps/go-pmtiles/releases/download/v1.31.2/$ASSET"
    case "$ASSET" in
      *.zip) unzip -o -q "$BIN/$ASSET" -d "$BIN" ;;
      *.tar.gz) tar xzf "$BIN/$ASSET" -C "$BIN" pmtiles ;;
    esac
    chmod +x "$BIN/pmtiles"
  fi
  SRC="https://build.protomaps.com/20261009.pmtiles"
  "$BIN/pmtiles" extract "$SRC" "$FOND/france-z0-8.pmtiles"     --bbox=-6.2,41.0,10.2,51.6  --maxzoom=8                --download-threads=8
  "$BIN/pmtiles" extract "$SRC" "$FOND/sud-ouest-z9-11.pmtiles" --bbox=-2.3,42.4,4.5,45.95  --minzoom=9  --maxzoom=11  --download-threads=8
  "$BIN/pmtiles" extract "$SRC" "$FOND/toulouse-z12-14.pmtiles" --bbox=0.95,43.33,1.9,43.95 --minzoom=12 --maxzoom=14  --download-threads=8
  rm -rf "$ICI/carte/telechargements"
fi

URL="http://localhost:$PORT"
echo "BâtIA sur $URL  (Ctrl+C pour arrêter ; PORT=4871 ./lancer.sh pour un autre port ; ./lancer.sh --reseau pour le téléphone)"
( sleep 2; if command -v open >/dev/null 2>&1; then open "$URL"; elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true; fi ) &
PORT="$PORT" exec node serveur.mjs "$@"
