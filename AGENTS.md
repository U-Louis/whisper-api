# Map

Whisper HTTP API. One API key per backend, as many as `WHISPER_KEYS` lists. Clip length is `probe_duration_seconds` in `whisper-api.conf` (shipped at 30) and 5 MiB. Model `small` on CPU. Audio is not stored.

## Read when the slice needs it

- [docs/constitution.md](docs/constitution.md) — invariants and bounds
- [docs/architecture.md](docs/architecture.md) — process, edges, environment
- [docs/security.md](docs/security.md) — keys, logs, deferred IP allow-list
- [docs/reliability.md](docs/reliability.md) — startup, lock, probe timeout
- [docs/product-specs/index.md](docs/product-specs/index.md) — acceptance examples
- [docs/features.json](docs/features.json) — observable behavior; leave `passes` alone
- [docs/exec-plans/decisions.md](docs/exec-plans/decisions.md) — rejected alternatives

## Commands

```text
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pytest
cp .env.example .env   # then set one hash per app; see docs/security.md
./init.sh
./scripts/collect-evidence.sh
```

Unit tests must not import `whisper`. The real model runs only in the image.

## Do not

- Commit `.env` or a raw API key.
- Add a second auth scheme, a queue, or a model parameter.
- Set `passes` in `docs/features.json`.
