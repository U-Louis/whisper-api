# Decisions

Why this shape, and the alternative that was rejected.

## Caller

The backends you own, one API key each, with no fixed count. Rejected: browsers presenting a user JWT, a general multi-tenant signup, and a cap of two keys. There is no end user on this service.

## Credential

Opaque API key, one per app, stored as a SHA-256 hash. Rejected: short-lived JWT issued here, JWT issued by an identity provider, and a long-lived JWT used as a bearer secret. Two first-party backends would still have needed a long-lived secret, plus a signer, for no extra revocation story. Revocation is deleting the hash.

## Exposure

HTTP behind a TLS proxy, reachable from the internet once that proxy is in place. Rejected for v1: publishing Whisper with no application credential. An IP allow-list was discussed and deferred. It is not a substitute for the key.

## Call

Synchronous `POST`, max 5 MiB, temp file deleted when the attempt ends. The duration cap is `probe_duration_seconds` in `whisper-api.conf`, shipped at 30. Rejected: a 60-second / 10 MiB bound, a 5-minute sync bound, an async job that keeps audio, and hiding the duration cap in code. One in-flight transcription; the next call gets `429`. Rejected: a queue.

## Model

Official `openai-whisper`, model `small`, CPU, language auto-detected unless the caller passes a two-letter code. Rejected: `base` (weaker), GPU `turbo` / `large` (this image has no CUDA), and a request field that selects the model. Translation is out of scope.

## Stack

Python, because that is the library being wrapped. FastAPI is the HTTP adapter. Unit tests use a fake `Transcriber` so they do not load the model. One container journey runs the real model.
