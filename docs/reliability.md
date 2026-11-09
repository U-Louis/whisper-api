# Reliability

## Start

The process exits before it listens when required configuration is missing or invalid. Required: at least one distinct API-key hash, `probe_duration_seconds` in the conf file, model `small`. The model object is loaded after listen starts. Until `load` finishes, `GET /healthz` is `503` and an authenticated transcription is `503` with `{"error":"not_ready"}`. A bad key is still `401` while the model is loading.

A failed model load leaves the process not ready. It does not start serving transcriptions against an empty model.

## Request

There is no retry of ffprobe or of Whisper. A timeout, a crash, or a bad file becomes one of the named error codes. It does not become a second inference.

ffprobe is limited to `10` seconds. On timeout the audio is unreadable (`422`), the temp file is removed, and the single-flight lock is released.

The lock is released on every exit: success, refusal, and unexpected error. The temp file is removed on those same exits.

A caller that disconnects does not leave the lock held past the attempt. The next caller is not queued.

## What is not promised

No latency objective. A 30-second clip on CPU can take longer than 30 seconds of wall time. Callers must set their own HTTP timeout. This service does not kill a running Whisper call, because no inference deadline was set.

No idempotency key. A replay transcribes again. Nothing is booked or stored, so a replay cannot create a second holder.

No circuit breaker around Whisper. Whisper is in-process. If it fails, that request fails and the next one may try.
