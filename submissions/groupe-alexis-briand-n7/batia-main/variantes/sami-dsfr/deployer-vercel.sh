#!/usr/bin/env bash
set -euo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
cd "$ICI"
VERCEL="npx --yes vercel@50"

if ! $VERCEL whoami >/dev/null 2>&1; then
  echo "Pas connecté à Vercel : lance d'abord   npx vercel@50 login   puis relance ce script."
  exit 1
fi
for f in carte/fond/france-z0-8.pmtiles carte/fond/sud-ouest-z9-11.pmtiles carte/fond/toulouse-z12-14.pmtiles; do
  [ -s "$f" ] || { echo "Fond de carte absent ($f) : lance ./lancer.sh une fois pour le télécharger."; exit 1; }
  mkdir -p public/carte/fond
  ln -f "$f" "public/carte/fond/$(basename "$f")"
done

MDP="${BATIA_MDP:-}"
if [ -z "$MDP" ]; then
  MDP="$(LC_ALL=C tr -dc 'a-km-z2-9' </dev/urandom | head -c 12)"
  echo "Mot de passe généré pour le site : $MDP"
fi
if [ ! -d .vercel ]; then
  $VERCEL link --yes --project batia
fi
$VERCEL env rm BATIA_MDP production --yes >/dev/null 2>&1 || true
printf '%s' "$MDP" | $VERCEL env add BATIA_MDP production >/dev/null
echo "Déploiement en production, environ 250 Mo à envoyer, quelques minutes."
URL="$($VERCEL deploy --prod --yes 2>/dev/null | tail -1)"
echo
echo "Site : $URL"
echo "Mot de passe : $MDP"
