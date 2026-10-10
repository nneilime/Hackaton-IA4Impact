#!/bin/sh
# Images du storytelling (NanoBanana, ~1024 px) -> JPEG 2048 px pour le plein écran du diapo, netteté rattrapée
cd "$(dirname "$0")/../public/assets/story" || exit 1
for f in 0*.png; do
  ffmpeg -v error -y -i "$f" -vf "scale=2048:-2:flags=lanczos,unsharp=5:5:0.8:5:5:0" -q:v 3 "${f%.png}.jpg"
done
ls -la *.jpg
