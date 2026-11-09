# Constitution

Invariants for this service. A feature session does not reopen them.

## Outcome

Backends you own send a short speech clip and receive text. The process runs OpenAI Whisper, model `small`, on CPU, in one container.

## Confirmed

- Callers are the applications listed in `WHISPER_KEYS`. One key each. Only their backends connect. There is no end-user identity. There is no fixed count.
- The credential is one opaque API key per application, presented as `Authorization: Bearer`. The process stores the SHA-256 hash only.
- The listen path is HTTP. TLS terminates in front of this process. This process does not terminate TLS.
- One transcription runs at a time. A second call is refused. There is no queue.
- A call is synchronous. The audio is a temp file deleted before the response returns, including on failure. Nothing is stored.
- The model is `small`. A request cannot choose a model. The task is transcribe, not translate.
- Bounds: 5 MiB (`5242880` bytes) and `probe_duration_seconds` in `whisper-api.conf`. The shipped file sets 30. Oversize is `413`. Over-duration and unreadable audio are `422`.
- Missing and unknown keys produce the same status and the same body.

## Non-goals

- JWT, an identity provider, browser callers, CORS, per-user quotas, self-service key issuance.
- IP allow-list. Deferred. It does not replace the key check.
- GPU, `turbo`, `large`, diarization, streaming, word timestamps, segments.
- Async jobs, inference retries, a database, storing audio or transcripts.

## Invariants

- One authorization path: hash the bearer token and compare it to every stored hash.
- One error body: `{"error":"<code>"}`. Health is the only other JSON shape: `{"status":"ok"|"loading"}`.
- One log line per request: JSON, with `path`, `status`, `outcome`, `correlation_id`. `key_id` is present only after a key matches. The secret, the audio, and the transcript are not logged.
- Domain code does not import the HTTP framework. Delivery depends on the application functions. Whisper sits behind `Transcriber`.
- The process exits before it listens when `WHISPER_KEYS` is missing or not a list of distinct hashes, when `whisper-api.conf` does not set `probe_duration_seconds`, and when the model is not `small`.
- Temp audio is removed on every exit from the transcription attempt.
- A red bound (size, duration, auth, single flight) is not waived.

## Quality bars

- Payload bound: `5242880` bytes for the file part. Request body bound: that size plus `65536` bytes of multipart overhead.
- Duration bound: greater than `probe_duration_seconds` is refused. That number is accepted. A non-finite or non-positive measured duration is unreadable. The shipped file sets 30.
- ffprobe is killed at `10` seconds and the audio is then unreadable. That is a stuck-probe limit, not a latency objective.
- No latency bar. The five fields (request, proportion, threshold, measurement point, window) are unnamed, so there is no latency gate.
- No inference retry.

## Risk classes

Authentication, the key hashes, the temp-file handling, and the container entrypoint are risk-class changes.

## Scores the checks report

`complexity-score` is unset. Report cyclomatic complexity and cognitive complexity when a tool is present. Neither blocks.

`diff-posture` is unset. Neither Read nor Metrics is the rule until a steward names one. Recommendation, not a rule: Read, because authentication is a risk class and this repo has no metric gauntlet.

`instruction-model` is unset.

## Data classes

| Class | What | Rule |
| --- | --- | --- |
| secret | API key, raw audio, transcript | Not stored, not logged. Audio exists only as a temp file for the duration of the attempt. The key exists only as a SHA-256 hash in the environment. |
| account | key id | Logged on a successful authentication. Not a person. |
| public | health status, error code | Returned to any caller. Health reveals readiness and nothing else. |
