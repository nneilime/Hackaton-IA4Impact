#!/usr/bin/env bash
set -euo pipefail
DOSSIER="$HOME/batia"
DEPOT="git@github.com:ai-for-impact-team/ai-for-impact-2026.git"
BRANCHE="main"

if ! command -v git >/dev/null 2>&1; then
  echo "git manque : macOS propose de l'installer, accepte puis relance ce fichier."
  xcode-select --install || true
  read -r -p "Appuie sur Entrée pour fermer." _
  exit 1
fi
if ! command -v node >/dev/null 2>&1; then
  echo "Node.js manque. Installe-le depuis https://nodejs.org (version 20 ou plus) ou avec : brew install node"
  read -r -p "Appuie sur Entrée pour fermer." _
  exit 1
fi

if [ -d "$DOSSIER/.git" ]; then
  echo "Mise à jour de $DOSSIER"
  git -C "$DOSSIER" fetch -q origin "$BRANCHE"
  git -C "$DOSSIER" checkout -q "$BRANCHE"
  git -C "$DOSSIER" pull -q --ff-only origin "$BRANCHE"
else
  echo "Récupération du dépôt dans $DOSSIER (il faut être membre de l'organisation GitHub et avoir une clé SSH)."
  if ! git clone -q --filter=blob:none --no-checkout --branch "$BRANCHE" "$DEPOT" "$DOSSIER"; then
    echo "La clé SSH ne passe pas, essai en HTTPS (GitHub demandera un identifiant et un jeton)."
    git clone -q --filter=blob:none --no-checkout --branch "$BRANCHE" "https://github.com/ai-for-impact-team/ai-for-impact-2026.git" "$DOSSIER"
  fi
  git -C "$DOSSIER" sparse-checkout set variantes/sami-dsfr donnees docs
  git -C "$DOSSIER" checkout -q "$BRANCHE"
fi

cd "$DOSSIER/variantes/sami-dsfr"
chmod +x lancer.sh
./lancer.sh
