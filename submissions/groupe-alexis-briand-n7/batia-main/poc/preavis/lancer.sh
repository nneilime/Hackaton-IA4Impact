#!/usr/bin/env bash
# Préavis — une seule commande : recalcule les risques depuis les CSV puis ouvre l'application.
# Usage : ./lancer.sh                      (données du kit)
#         ./lancer.sh dossier-du-trimestre (vos 13 fichiers CSV du nouveau trimestre)
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8642}"
python3 preparer.py "$@"
echo
echo "Préavis est prêt : http://localhost:${PORT}"
exec python3 -m http.server "$PORT" --bind 0.0.0.0 --directory app
