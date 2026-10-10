#!/usr/bin/env bash
# macOS / Linux : installation puis lancement
set -e
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv; . .venv/bin/activate; pip install -r requirements.txt; }
. .venv/bin/activate
cd backend && python -m sentinel.cli serve
