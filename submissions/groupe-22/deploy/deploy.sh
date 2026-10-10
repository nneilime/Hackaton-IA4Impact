#!/usr/bin/env bash
# Builds the image here, ships it to the VPS, starts it and checks it answers.
set -euo pipefail
umask 077

PROJECT="voice-assistant"
APP_PORT="8098"
HEALTH_PATH="/api/health"
VPS_SSH="root@72.60.94.113"
VPS_PATH="/root/code/voice-assistant"
PLATFORM="${PLATFORM:-linux/amd64}"
IMAGE="${PROJECT}-app:latest"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
mkdir -p .deploy-build
BUILD_DIR="$(mktemp -d "$ROOT_DIR/.deploy-build/run-XXXXXXXX")"

echo ">> Building $IMAGE ($PLATFORM)"
docker buildx build --platform "$PLATFORM" --load -t "$IMAGE" .

echo ">> Bundling"
docker save "$IMAGE" -o "$BUILD_DIR/images.tar"
cp deploy/docker-compose.prod.yml "$BUILD_DIR/docker-compose.yml"
cp .env "$BUILD_DIR/.env"
tar -C "$BUILD_DIR" -czf "$BUILD_DIR/bundle.tar.gz" images.tar docker-compose.yml .env

echo ">> Uploading to $VPS_SSH:$VPS_PATH"
ssh "$VPS_SSH" "mkdir -p '$VPS_PATH'"
scp "$BUILD_DIR/bundle.tar.gz" "$VPS_SSH:$VPS_PATH/${PROJECT}-deploy.tar.gz"

echo ">> Starting"
ssh "$VPS_SSH" "bash -s" <<REMOTE
set -euo pipefail
umask 077
cd '$VPS_PATH'
# No remote deletion: other apps and files are left untouched.
tar -xzf '${PROJECT}-deploy.tar.gz'
docker load -i images.tar
APP_PORT='$APP_PORT' docker compose up -d
check() { curl --retry 15 --retry-all-errors --retry-delay 2 -fsS "http://127.0.0.1:$APP_PORT\$1" >/dev/null; }
if ! check / || ! check '$HEALTH_PATH'; then
    docker compose logs --tail=100
    exit 1
fi
docker compose ps
REMOTE

echo ">> Done: http://127.0.0.1:$APP_PORT on $VPS_SSH (https://voice-assistant.nathan-petitboulanger.fr once Nginx is set up)"
