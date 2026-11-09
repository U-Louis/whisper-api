# M2 — API keys

## Outcome and actor

Application A and application B, each with its own secret, can be told apart. Everyone else cannot call transcription.

## Done-means

- A bearer token whose SHA-256 matches the first hash is application A.
- A bearer token whose SHA-256 matches the second hash is application B.
- No header, an empty bearer, a token longer than 512 characters, and an unknown token all return `401` and `{"error":"unauthorized"}`. The bodies are identical.
- The log of a successful authentication contains `key_id` and does not contain the secret. A refusal log has no `key_id`.

## Non-goals

- Issuing keys. Rotation is an environment change and a restart.
- A fixed cap on how many applications. Add a `id:hash` pair and restart.

## Assumptions

- `confirmed`: the secret is UTF-8 and is hashed with SHA-256, hex-encoded, lowercase or uppercase both accepted in the environment.
- `confirmed`: the scheme is `Bearer`, case-insensitive. One space. No query-string key.

## Invariants

- One comparison path, `app.auth`.
- Both hashes are compared on every attempt.
- The raw secret is not stored and not logged.

## Data

Read: the hashes from the environment. Secret class. The key id is account class and may be logged after a match.

## Security-critical paths

Authentication. Allow one configured key. Deny missing and unknown with the same body.

## Paths

- Allowed: `app/auth.py`, `app/settings.py`, `app/factory.py`, tests for keys.
- Forbidden: a second header, cookie, or JWT parser.

## Dependencies

None beyond M1.

## Acceptance examples

1. Given key id `app-a` and its secret, when `POST /v1/transcribe` with `Authorization: Bearer <secret-a>`, then the handler runs and the log `key_id` is `app-a`.
2. Given the same app and secret B, when the call uses secret B, then `key_id` is `app-b`.
3. Given no `Authorization` header, when `POST /v1/transcribe`, then `401` and `{"error":"unauthorized"}`.
4. Given bearer `not-a-real-key`, when `POST /v1/transcribe`, then `401` and `{"error":"unauthorized"}`, the same bytes as example 3.
5. Given a bad key and a body larger than the cap, when `POST /v1/transcribe`, then `401`, not `413`. The model is not called.

## Test seams

- Public boundary: `POST /v1/transcribe` with a fake transcriber.
- Catches: the status, the exact refusal body, and that the log contains the key id rather than the secret.
- Misses: whether the hash in a deployed `.env` is the one you think you issued. That is an operator check, not this suite.

## Quality budgets

Unchanged.

## Risk class

Authentication.

## Rollback

Revert the commit. Keys live in the environment, not in the image.
