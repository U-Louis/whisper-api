#!/bin/sh
# Boot the API. The first run builds an image that downloads the small model.
set -eu
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  echo "missing .env: copy .env.example and set WHISPER_KEYS" >&2
  exit 1
fi
base=${WHISPER_BASE_IMAGE:-python:3.11-slim-bookworm}
docker build --build-arg BASE_IMAGE="$base" -t whisper-api:local .
docker compose up -d --no-build
port=$(grep -E '^WHISPER_PORT=' .env | cut -d= -f2- || true)
if [ -z "${port}" ]; then
  port=8080
fi
i=0
while [ "$i" -lt 60 ]; do
  if curl -sf "http://127.0.0.1:${port}/healthz" >/dev/null; then
    echo "ready on ${port}"
    exit 0
  fi
  i=$((i + 1))
  sleep 5
done
echo "healthz did not return 200" >&2
docker compose logs --tail 80 >&2
exit 1
