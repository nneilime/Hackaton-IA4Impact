#!/usr/bin/env bash
# Installe les dépendances du back (venv) et du front après la création du conteneur.
set -euo pipefail

cd "$(dirname "$0")/.."

python -m venv backend/.venv
backend/.venv/bin/pip install --quiet --upgrade pip
backend/.venv/bin/pip install --quiet -r backend/requirements.txt

npm --prefix frontend ci

echo
echo "Environnement prêt. Lancer le projet : .devcontainer/dev.sh"
