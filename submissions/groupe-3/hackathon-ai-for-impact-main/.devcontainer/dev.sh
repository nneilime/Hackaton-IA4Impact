#!/usr/bin/env bash
# Lance l'API (8000) et le front (5173) ensemble. Ctrl+C arrête les deux.
set -euo pipefail

cd "$(dirname "$0")/.."

backend/.venv/bin/uvicorn --app-dir backend app.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT

npm --prefix frontend run dev
