#!/usr/bin/env bash
# Start the whole app locally: the FastAPI backend on :8000 and the web app on :8443 (it proxies /api to the backend).
# First run: creates the virtualenv, installs the web dependencies, and builds invoices.db with the demo accounts
# (agent / agent, admin / admin) from the B2 files and OCR results.
#
#   ./dev.sh                       FACTURES_DIR, BORDEREAUX_DIR, IMAGES_DIR override the data folders below
set -euo pipefail
cd "$(dirname "$0")"

FACTURES_DIR="${FACTURES_DIR:-$HOME/Downloads/General-main/Factures txt}"
BORDEREAUX_DIR="${BORDEREAUX_DIR:-factures}"
IMAGES_DIR="${IMAGES_DIR:-$HOME/Downloads/General-main/Bordereaux jpg}"
DB="${INVOICES_DB:-invoices.db}"

if [ ! -x .venv/bin/python ]; then
  uv venv -q .venv
  uv pip install -q -p .venv -r requirements.txt
fi
[ -d web/node_modules ] || (cd web && pnpm install --frozen-lockfile)

if [ ! -f "$DB" ]; then
  .venv/bin/python create_db.py --db "$DB" --demo
  .venv/bin/python ingest.py "$FACTURES_DIR" "$BORDEREAUX_DIR" --images "$IMAGES_DIR" --db "$DB"
else
  .venv/bin/python users.py --db "$DB" demo >/dev/null  # make sure the demo logins exist
fi

trap 'kill 0' EXIT INT TERM
INVOICES_DB="$DB" .venv/bin/uvicorn api:app --host 127.0.0.1 --port 8000 &
(cd web && pnpm dev) &
echo "Web app: http://localhost:8443  (agent / agent, admin / admin) · API docs: http://localhost:8000/docs"
wait
