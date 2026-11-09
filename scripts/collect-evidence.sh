#!/bin/sh
# Exercise the booted container. Prints status codes and error bodies, never secrets.
# Replaces .env with a generated key pair for this run.
set -eu
cd "$(dirname "$0")/.."
umask 077
mkdir -p tmp-evidence docs/evidence/bounds

python3 - <<'PY'
import hashlib
import math
import os
import secrets
import struct
import wave

root = "tmp-evidence"

def tone(path: str, seconds: float) -> None:
    rate = 16000
    count = int(rate * seconds)
    with wave.open(path, "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for i in range(count):
            sample = int(8000 * math.sin(2 * math.pi * 440 * i / rate))
            frames += struct.pack("<h", sample)
        handle.writeframes(frames)

def key() -> tuple[str, str]:
    secret = secrets.token_urlsafe(32)
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    return secret, digest

secret_a, hash_a = key()
secret_b, hash_b = key()
with open(".env", "w", encoding="utf-8") as handle:
    handle.write(f"WHISPER_KEYS=app-a:{hash_a},app-b:{hash_b}\n")
    handle.write("WHISPER_MODEL=small\n")
    handle.write("WHISPER_PORT=8080\n")
os.chmod(".env", 0o600)
with open(f"{root}/secret-a", "w", encoding="utf-8") as handle:
    handle.write(secret_a)
with open(f"{root}/secret-b", "w", encoding="utf-8") as handle:
    handle.write(secret_b)
os.chmod(f"{root}/secret-a", 0o600)
os.chmod(f"{root}/secret-b", 0o600)
tone(f"{root}/long.wav", 31)
tone(f"{root}/busy.wav", 25)
with open(f"{root}/big.bin", "wb") as handle:
    handle.write(b"\0" * (5 * 1024 * 1024 + 1))
with open(f"{root}/note.txt", "w", encoding="utf-8") as handle:
    handle.write("not audio")
PY

./init.sh
port=$(grep -E '^WHISPER_PORT=' .env | cut -d= -f2-)
secret=$(cat tmp-evidence/secret-a)
base="http://127.0.0.1:${port}"

call() {
  # $1 name, $2 expected status, remaining args are curl args
  name=$1
  want=$2
  shift 2
  code=$(curl -sS -o "tmp-evidence/${name}.body" -w "%{http_code}" "$@")
  printf '%s %s\n' "$name" "$code" | tee -a tmp-evidence/statuses.txt
  if [ "$code" != "$want" ]; then
    echo "${name}: expected ${want}, got ${code}" >&2
    cat "tmp-evidence/${name}.body" >&2
    exit 1
  fi
}

: > tmp-evidence/statuses.txt

call missing 401 -X POST "$base/v1/transcribe"
call unknown 401 -X POST "$base/v1/transcribe" -H "Authorization: Bearer not-a-real-key"
cmp tmp-evidence/missing.body tmp-evidence/unknown.body

call oversize 413 -X POST "$base/v1/transcribe" \
  -H "Authorization: Bearer ${secret}" \
  -F "file=@tmp-evidence/big.bin;type=application/octet-stream"

call toolong 422 -X POST "$base/v1/transcribe" \
  -H "Authorization: Bearer ${secret}" \
  -F "file=@tmp-evidence/long.wav;type=audio/wav"

call unreadable 422 -X POST "$base/v1/transcribe" \
  -H "Authorization: Bearer ${secret}" \
  -F "file=@tmp-evidence/note.txt;type=text/plain"

curl -sS -o tmp-evidence/busy-first.body -w "%{http_code}" \
  -X POST "$base/v1/transcribe" \
  -H "Authorization: Bearer ${secret}" \
  -F "file=@tmp-evidence/busy.wav;type=audio/wav" \
  --max-time 300 > tmp-evidence/busy-first.code &
first_pid=$!
sleep 2
call busy 429 -X POST "$base/v1/transcribe" \
  -H "Authorization: Bearer ${secret}" \
  -F "file=@tests/fixtures/short.wav;type=audio/wav" \
  --max-time 60
wait "$first_pid"
echo "busy-first $(cat tmp-evidence/busy-first.code)" | tee -a tmp-evidence/statuses.txt

call speech 200 -X POST "$base/v1/transcribe" \
  -H "Authorization: Bearer ${secret}" \
  -F "file=@tests/fixtures/short.wav;type=audio/wav" \
  --max-time 300

{
  echo "# Bounds evidence"
  echo
  echo "Command: ./scripts/collect-evidence.sh"
  echo
  echo "Versions:"
  docker compose exec -T whisper-api python -c "import platform, whisper; print(platform.python_version()); print('openai-whisper', whisper.__version__)"
  echo
  echo "Statuses:"
  cat tmp-evidence/statuses.txt
  echo
  echo "Bodies (refusals only):"
  for name in missing unknown oversize toolong unreadable busy; do
    printf '%s ' "$name"
    cat "tmp-evidence/${name}.body"
    echo
  done
  echo
  echo "Speech body:"
  cat tmp-evidence/speech.body
  echo
} > docs/evidence/bounds/result.md

python3 - <<'PY'
import json
import pathlib
import sys

observed = json.loads(pathlib.Path("tmp-evidence/speech.body").read_text())
expected_path = pathlib.Path("tests/fixtures/short.expected.json")
print(json.dumps(observed, ensure_ascii=False))
if not expected_path.exists():
    print("ORACLE_MISSING", file=sys.stderr)
    sys.exit(2)
expected = json.loads(expected_path.read_text())
if observed != expected:
    print("ORACLE_MISMATCH", file=sys.stderr)
    sys.exit(1)
PY

echo "evidence written to docs/evidence/bounds/result.md"
