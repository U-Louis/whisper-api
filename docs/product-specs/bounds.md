# Bounds evidence

No new behavior. This records the booted container against the frozen refusals and one real transcription.

## Done-means

`scripts/collect-evidence.sh` boots via `init.sh` and records, under `docs/evidence/bounds/`:

- `401` and `{"error":"unauthorized"}` for a missing key and for an unknown key, byte-identical.
- `413` and `{"error":"payload_too_large"}` for a file part of `5242881` bytes with a valid key.
- `422` and `{"error":"too_long"}` for a generated clip of about `31` seconds.
- `422` and `{"error":"unreadable_audio"}` for a text body sent as the file.
- `429` and `{"error":"busy"}` for a second valid call while a first call of about `25` seconds is running.
- `200` for `tests/fixtures/short.wav`, equal to `tests/fixtures/short.expected.json`.

The script prints status codes and error bodies. It does not print secrets.

## Non-goals

- A load test, a latency threshold, or an IP allow-list.

## Test seam

The booted container on `127.0.0.1:$WHISPER_PORT`. Catches the codes above against the real model and real ffprobe. Misses concurrent behavior beyond two overlapping calls, and misses TLS at the proxy.
