# Progress

## 2026-11-09 — M0 through bounds

- Slice: constitution, health, API keys, transcribe, bounds evidence.
- Commit: not created in this session.
- Passed: `pytest` (23). Container run recorded in [evidence/bounds/result.md](evidence/bounds/result.md): missing and unknown keys `401` with the same body, `413`, `422` for too long and unreadable, `429` while a call was in flight, and `tests/fixtures/short.wav` equal to `{"text":"This is a short test.","language":"en"}`. Logs from that run contained `app-a` and did not contain the secret or the transcript.
- Failed along the way: Docker Hub timed out from this network, so the image was built with `WHISPER_BASE_IMAGE` pointed at a reachable mirror. BuildKit could not verify `download.pytorch.org`; the CPU wheel was prefetched into `wheels/` (gitignored) and installed from there. `--network=host` did not fix that certificate error.
- Dead ends: a browser JWT, an external identity provider, and a token endpoint were rejected before implementation. The first speech clip used the system voice and was recognized as French; it was replaced with an English voice before the oracle was frozen.
- Next: nothing in this plan. `docs/features.json` stays failing until a verifier sets `passes`.
