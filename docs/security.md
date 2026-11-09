# Security

## Trust boundary

The internet reaches a TLS proxy you run. The proxy speaks HTTP to this process. The only authenticated clients are the backends listed in `WHISPER_KEYS`. A browser is not a client. This service does not issue tokens and does not call an identity provider.

A valid-looking bearer token is an application key or it is nothing. There is no user subject.

## Credential

Each application gets a random secret out of band. You store only `SHA-256(secret)` in `WHISPER_KEYS`.

```text
python -c "import hashlib,secrets; s=secrets.token_urlsafe(32); print(s); print(hashlib.sha256(s.encode()).hexdigest())"
```

Print the secret once, put it in the calling app, and put `app-id:<hex>` in `.env`. `.env` is not committed. The hash is not a substitute for keeping `.env` off the internet; it limits damage if the environment is copied into a log later.

Comparison uses `hmac.compare_digest` on the raw digests and always checks every key. A missing header, an empty token, a token longer than 512 characters, and an unknown token all return `401` with `{"error":"unauthorized"}`.

The access log records `key_id` only after a match. It does not record the header, the secret, the body, or the transcript.

## Bounds

Authentication runs before the body is treated as audio. An oversized `Content-Length` is refused with `413` before the single-flight lock. The stream is capped as it is read. The extracted file part is capped again at `5242880` bytes. The client filename is ignored. The temp name comes from `mkstemp`.

Duration comes from ffprobe. Files without an audio stream, and probes that fail or exceed `10` seconds, are `422` and are not sent to the model.

One transcription holds the lock. The next authenticated call gets `429` immediately.

## Data

Audio and transcript are secret. They are not written to the log and not written to a volume. The temp file is unlinked before the HTTP response is returned.

Health is unauthenticated and returns `{"status":"ok"}` or `{"status":"loading"}`. It does not return the model path, the key ids, or an exception message.

Unhandled failures return `{"error":"internal"}`. The log line includes the exception type, not the request body.

## Deferred

An IP allow-list may be added later, in front of this process. It is not implemented. A request that passes an allow-list and fails the key check is still `401`.

## Dependency rule

New Python dependencies are named in the slice spec that introduces them. The image installs CPU PyTorch from the PyTorch CPU index before Whisper, and installs Whisper with `--no-deps`, so the CUDA wheel is not pulled in.
