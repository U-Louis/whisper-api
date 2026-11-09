# M1 — Health

## Outcome and actor

Any caller, including an unauthenticated probe, can see whether the model is loaded.

## Done-means

- `GET /healthz` returns `200` and `{"status":"ok"}` when the model is loaded.
- `GET /healthz` returns `503` and `{"status":"loading"}` before that.
- The body has no key id, path, exception text, or secret.

## Non-goals

- Authentication on this route.
- A readiness check that loads the model itself.

## Assumptions

- `confirmed`: the model loads after the process starts listening, so `503` is observable.
- `confirmed`: health stays `503` if the load fails.

## Invariants

- This route does not read `WHISPER_KEYS` and does not log a key id.
- It does not call Whisper's transcribe.

## Data

None written. None read except the in-memory ready flag. Public.

## Security-critical paths

None. The route must not become an authentication bypass for `/v1/transcribe`.

## Paths

- Allowed: `app/factory.py`, `app/transcriber.py`, `app/asgi.py`, `Dockerfile`, `init.sh`, tests for health.
- Forbidden: accepting audio on this route.

## Dependencies

`fastapi`, `uvicorn`. Introduced here.

## Acceptance examples

1. Given a transcriber whose `ready` is true, when `GET /healthz`, then `200` and `{"status":"ok"}`.
2. Given a transcriber whose `ready` is false, when `GET /healthz`, then `503` and `{"status":"loading"}`.

## Test seams

- Public boundary: `GET /healthz` on the ASGI app.
- Catches: the status codes and the exact bodies above.
- Misses: whether the real `small` weights loaded. The container boot covers that. A fake ready flag does not prove the weights are present.

## Quality budgets

Unchanged. No latency bar.

## Risk class

Deployment entrypoint and the first network listener.

## Rollback

Revert the commit. The container is stateless.
