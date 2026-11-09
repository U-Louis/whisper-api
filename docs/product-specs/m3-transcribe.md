# M3 — Transcribe

## Outcome and actor

An authenticated application sends one short speech clip and receives text.

## Done-means

- `POST /v1/transcribe` with multipart field `file` returns `200` and `{"text":"<string>","language":"<code>"}`.
- Optional field `language` is a two-letter code. Omitted or empty means auto-detect. Any other value is `422` and `{"error":"invalid_language"}`. The model is not called for a malformed code.
- The task is always transcribe. The model is always `small`. Neither is a field.
- File part longer than `5242880` bytes: `413` `{"error":"payload_too_large"}`, model not called.
- Declared `Content-Length` above `5242880 + 65536`: `413` before the single-flight lock.
- Duration greater than `probe_duration_seconds`: `422` `{"error":"too_long"}`, model not called. A duration equal to that setting is accepted. The shipped file sets 30.
- No audio stream, a failed probe, or a probe that exceeds `10` seconds: `422` `{"error":"unreadable_audio"}`.
- Not multipart: `422` `{"error":"unsupported_media"}`.
- Multipart with no file part, or an empty file: `422` `{"error":"missing_file"}` for a missing part, `422` `{"error":"unreadable_audio"}` for an empty part.
- A second authenticated call while the first holds the slot: `429` `{"error":"busy"}`.
- The temp file is gone when the response is produced, including when the attempt fails.
- The client filename is not used as a path.

## Non-goals

- Timestamps, segments, translation, diarization, streaming.
- A queue, a retry, or a stored transcript.
- Killing a Whisper call at a deadline. No deadline was set.

## Assumptions

- `confirmed`: language codes are two ASCII letters. Names such as `English` are rejected.
- `confirmed`: Whisper's detected language is returned as the `language` string when the caller did not force one.
- `confirmed`: the oracle for `tests/fixtures/short.wav` is the body in `tests/fixtures/short.expected.json`, written from the first accepted container run and not recomputed by the test.

## Invariants

- Auth, then readiness, then the content-length cap, then the single-flight lock, then the body, then duration, then the model.
- A bad key never sees `413`, `422`, `429`, or `503` from this route.
- Temp file unlinked and lock released on every exit after the lock is taken.
- Transcript text is not logged.

## Data

Read: the clip, in memory up to the body cap, then one temp file. Secret. Not retained.
Written: the JSON response only.

## Security-critical paths

The body cap, the filename ignore, the temp unlink, and the lock.

## Paths

- Allowed: `app/factory.py`, `app/audio.py`, `app/transcriber.py`, tests, `tests/fixtures/short.wav`, `tests/fixtures/short.expected.json`.
- Forbidden: a model-name parameter, a translate task, a job table.

## Dependencies

`openai-whisper`, CPU `torch`, and the `ffmpeg` package (provides `ffprobe`). Introduced here. Whisper is installed with `--no-deps` after the CPU wheel so the CUDA wheel is not selected.

## Acceptance examples

1. Given a valid key and a clip the probe says is `1` second, when the fake transcriber returns `hello` / `en`, then `200` and `{"text":"hello","language":"en"}`, and the temp directory is empty.
2. Given a file part of `max_bytes + 1`, then `413` and `{"error":"payload_too_large"}`, and the transcriber is not called.
3. Given a probe duration of `30`, then the transcriber is called. Given `30.001`, then `422` and `{"error":"too_long"}`.
4. Given bytes that are not audio, then `422` and `{"error":"unreadable_audio"}`.
5. Given a call that has entered the transcriber and not returned, when a second valid call arrives, then `429` and `{"error":"busy"}`.
6. Given `tests/fixtures/short.wav` (the sentence "This is a short test." spoken in English) and the booted container, when `POST /v1/transcribe`, then the body equals `{"text":"This is a short test.","language":"en"}`, which is `tests/fixtures/short.expected.json`.

## Test seams

- Public boundary: `POST /v1/transcribe` on the ASGI app, fake transcriber and fake probe, except example 6.
- Catches: status codes, exact error bodies, lock refusal, temp deletion, language passthrough.
- Misses: the acoustic accuracy of `small`. Example 6 is the journey seam. It checks one frozen string. It does not check other accents, noise, or languages.
- A unit test that calls Whisper to decide the expected text does not count as example 6.

## Quality budgets

Payload `5242880` bytes. Duration is `probe_duration_seconds` in `whisper-api.conf`. One in-flight transcription. No latency bar.

## Risk class

Untrusted input, temp files, and the inference lock.

## Rollback

Revert the commit. No migration. In-flight calls die with the process.
