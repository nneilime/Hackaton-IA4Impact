#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Chaîne complète. Usage : ./run_all.sh [--sample N]   (N = passages max par produit et pays)
set -euo pipefail
cd "$(dirname "$0")"
PY="${VEILLE_PYTHON:-python3}"
[ -x "$HOME/.astro/bin/python3" ] && [ -z "${VEILLE_PYTHON:-}" ] && PY="$HOME/.astro/bin/python3"
SAMPLE=""; [ "${1:-}" = "--sample" ] && SAMPLE="--per-product $2"
$PY -m veille_reglementaire status
$PY -m veille_reglementaire collect
$PY -m veille_reglementaire index
$PY -m veille_reglementaire extract $SAMPLE
$PY -m veille_reglementaire eval
$PY -m veille_reglementaire web
