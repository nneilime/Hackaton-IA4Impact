#!/usr/bin/env bash
# Start the prediction API on Linux / WSL using the training environment.
set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$PROJECT_ROOT"

TRAINING_VENV="${TRAINING_VENV:-$PROJECT_ROOT/.venv-training}"
PYTHON="$TRAINING_VENV/bin/python"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

if [[ ! -x "$PYTHON" ]]; then
    printf 'Environnement Python absent : %s\nLancez d’abord : bash scripts/train_all.sh\n' "$TRAINING_VENV" >&2
    exit 1
fi

if ! "$PYTHON" -c 'import fastapi, uvicorn, catboost, pandas, psycopg, httpx, dotenv, multipart' >/dev/null 2>&1; then
    printf 'Installation des dépendances de l’API…\n'
    "$PYTHON" -m pip install -r "$PROJECT_ROOT/requirements.txt"
fi

# Check configured paths before starting a server that cannot predict.
"$PYTHON" - <<'PYTHON'
import json
import os
from pathlib import Path
from scripts.database import connection
from scripts.scoring import artifacts_dir, model_version

artifacts = artifacts_dir()
required = []
for horizon in (90, 180, 365, 730):
    directory = artifacts / f'{horizon}d'
    required.extend([directory / f'catboost_failure_{horizon}d.cbm', directory / 'metrics.json'])
    manifest_path = directory / 'failure_types' / 'manifest.json'
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        required.extend(manifest_path.parent / entry['model_file']
                        for entry in manifest['families'].values() if 'model_file' in entry)
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise SystemExit('Fichiers manquants :\n' + '\n'.join(missing)
                     + '\nEntraînez les modèles ou vérifiez PREDICTION_ARTIFACTS_DIR.')
model_version()
with connection(snapshot=True) as conn:
    conn.execute('select count(*) from public.equipements').fetchone()
    conn.execute('select count(*) from public.prix_interventions').fetchone()
PYTHON

printf '\nAPI de prédiction : http://%s:%s\n' "$HOST" "$PORT"
printf 'Documentation : http://%s:%s/docs\n' "$HOST" "$PORT"
printf 'Arrêt : Ctrl+C\n\n'
exec "$PYTHON" -m uvicorn scripts.api:app --host "$HOST" --port "$PORT" "$@"
