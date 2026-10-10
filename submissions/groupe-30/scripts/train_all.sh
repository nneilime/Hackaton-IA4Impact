#!/usr/bin/env bash
# Bootstrap and train the complete prediction pipeline on Linux / WSL.
set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$PROJECT_ROOT"

STEP="initialisation"
trap 'printf "\nÉchec pendant : %s (ligne %s).\n" "$STEP" "$LINENO" >&2' ERR

if (( $# != 0 )); then
    printf 'Utilisation : bash scripts/train_all.sh\n' >&2
    exit 2
fi

PYTHON_BIN="${PYTHON_BIN:-python3.11}"
TRAINING_VENV="${TRAINING_VENV:-$PROJECT_ROOT/.venv-training}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    printf 'Python 3.11 est requis. Installez python3.11 et python3.11-venv dans WSL/Linux.\n' >&2
    exit 1
fi
"$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else "Python 3.11 est requis.")'

DATA_DIR="$PROJECT_ROOT/DATA 2 _le kit étudiants/BatIA_Kit_Hackathon/donnees"
for filename in 04_equipements.csv 05_demandes_locataires.csv 06_interventions.csv; do
    if [[ ! -f "$DATA_DIR/$filename" ]]; then
        printf 'Données manquantes : %s\n' "$DATA_DIR/$filename" >&2
        exit 1
    fi
done
PRICE_CATALOG="$PROJECT_ROOT/extra/11_equipements_interventions_pannes_possibles_avec_prix.csv"
if [[ ! -f "$PRICE_CATALOG" ]]; then
    printf 'Catalogue de prix manquant : %s\n' "$PRICE_CATALOG" >&2
    exit 1
fi

STEP="création de l'environnement Python"
if [[ ! -x "$TRAINING_VENV/bin/python" ]]; then
    if [[ -e "$TRAINING_VENV" ]]; then
        printf 'Environnement incompatible : %s. Choisissez un autre dossier avec TRAINING_VENV.\n' "$TRAINING_VENV" >&2
        exit 1
    fi
    if ! "$PYTHON_BIN" -m venv "$TRAINING_VENV"; then
        printf 'Impossible de créer le venv. Sous Ubuntu/WSL, installez python3-venv, puis relancez le script.\n' >&2
        exit 1
    fi
fi
PYTHON="$TRAINING_VENV/bin/python"
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else "Le venv nécessite Python 3.11.")'

STEP="installation des dépendances"
printf '\nInstallation des dépendances dans %s\n' "$TRAINING_VENV"
"$PYTHON" -m pip install -r "$PROJECT_ROOT/requirements.txt"

for horizon in 90 180 365 730; do
    STEP="construction de la table à $horizon jours"
    printf '\n=== Horizon %s jours : préparation des données ===\n' "$horizon"
    "$PYTHON" -m scripts.build_monthly_training_table --horizon-days "$horizon"

    STEP="entraînement du risque de panne à $horizon jours"
    printf '\n=== Horizon %s jours : risque de panne ===\n' "$horizon"
    "$PYTHON" -m scripts.train_failure_model --horizon-days "$horizon"

    STEP="entraînement des symptômes à $horizon jours"
    printf '\n=== Horizon %s jours : symptômes ===\n' "$horizon"
    "$PYTHON" -m scripts.train_failure_types --horizon-days "$horizon"
done

STEP="tests"
"$PYTHON" -m unittest discover -s tests -v

STEP="vérification d'une prédiction complète"
"$PYTHON" -m scripts.predict_equipment \
    --equipment-id EQP-00001 --as-of-date 2025-01-01 \
    --output "$PROJECT_ROOT/artifacts/example_prediction.json"

printf '\nEntraînement terminé. Modèles et métriques : %s/artifacts/\n' "$PROJECT_ROOT"
printf 'Exemple de prédiction : artifacts/example_prediction.json\n'
printf 'Pour utiliser cet environnement : source %q\n' "$TRAINING_VENV/bin/activate"
