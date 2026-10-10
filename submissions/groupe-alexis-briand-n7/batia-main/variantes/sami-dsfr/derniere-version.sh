#!/usr/bin/env bash
set -euo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
DEPOT="$(cd "$ICI/../.." && pwd)"
PORT="${PORT:-4860}"

cd "$DEPOT"
if [ -n "$(git status --porcelain)" ]; then
  echo "Des fichiers sont modifiés localement, ils sont mis de côté avec git stash."
  git stash push -q -m "derniere-version.sh $(date +%H:%M)"
fi
git fetch -q origin
git checkout -q main
git pull -q --ff-only origin main
echo "main à $(git log -1 --format='%h · %s')"

if command -v lsof >/dev/null 2>&1; then
  ANCIEN="$(lsof -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
elif command -v ss >/dev/null 2>&1; then
  ANCIEN="$(ss -ltnp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p"$" {match($0, /pid=[0-9]+/); print substr($0, RSTART+4, RLENGTH-4)}' | head -1)"
else
  ANCIEN=""
fi
if [ -n "$ANCIEN" ]; then
  echo "Un serveur tourne déjà sur le port $PORT, il est arrêté."
  kill "$ANCIEN" 2>/dev/null || true
  sleep 1
fi

cd "$ICI"
PORT="$PORT" exec ./lancer.sh "$@"
