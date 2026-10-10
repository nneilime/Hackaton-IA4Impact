#!/usr/bin/env bash
# Assemble la copie en ligne d'Assise (version du port 9011) dans $SITE.
set -euo pipefail
ART="$(cd "$(dirname "$0")/.." && pwd)"; POC="$(cd "$ART/../.." && pwd)"; SITE="$ART/site"
rm -rf "$SITE"; mkdir -p "$SITE/lib" "$SITE/vendor/carte/vendor" "$SITE/vendor/carte/fond" "$SITE/donnees"
A="$POC/assise/app"; C="$POC/carte"
cp "$A/style.css" "$SITE/"; cp "$A/lib/risque.js" "$A/lib/epreuve.js" "$A/lib/csv.js" "$SITE/lib/"
cp -r "$A/vendor/fonts" "$SITE/vendor/"
sed "s|import('/vendor/carte/carte.mjs')|import('./vendor/carte/carte.mjs')|" "$A/app.js" > "$SITE/app.js"
grep -q "import('./vendor/carte/carte.mjs')" "$SITE/app.js"
cp "$ART/outils/serveur-local.js" "$SITE/"
cp "$C/carte.css" "$SITE/vendor/carte/"
sed 's|glyphs: `${base}vendor/glyphes/{fontstack}/{range}.pbf`|glyphs: '"'"'assise-glyphes://{fontstack}/{range}'"'"'|' "$C/style.mjs" > "$SITE/vendor/carte/style.mjs"
grep -q "assise-glyphes://" "$SITE/vendor/carte/style.mjs"; cp -r "$C/geo" "$SITE/vendor/carte/"
cp -r "$C/vendor/maplibre" "$C/vendor/pmtiles" "$C/vendor/glyphes" "$SITE/vendor/carte/vendor/"
# licence de MapLibre gardée à côté de la bibliothèque
# fichiers binaires refusés par l'hébergeur : fond et glyphes passent en base64
for f in "$ART"/fond/fond-*.pmtiles; do base64 -w0 "$f" > "$SITE/vendor/carte/fond/$(basename "$f" .pmtiles).txt"; done
for f in $(cd "$SITE/vendor/carte/vendor/glyphes" && find . -name '*.pbf'); do base64 -w0 "$SITE/vendor/carte/vendor/glyphes/$f" > "$SITE/vendor/carte/vendor/glyphes/${f%.pbf}.txt"; rm "$SITE/vendor/carte/vendor/glyphes/$f"; done
for f in 01_residences 02_batiments 03_logements 04_equipements 05_demandes_locataires 06_interventions 07_commandes 08_plan_investissement 09_prestataires 10_ref_familles_equipements 10_ref_seuils_dpe; do
  cp "$POC/assise/donnees/kit-batia/donnees/$f.csv" "$SITE/donnees/"; done
python3 "$ART/outils/patcher.py" "$C/carte.mjs" "$ART/fond/morceaux.json" "$SITE/vendor/carte/carte.mjs"
python3 "$ART/outils/page.py" "$A/index.html" "$SITE/index.html"
