# Architecture

One process. No database. No second service inside this repository.

```text
HTTP  →  auth  →  limits  →  Transcriber
                              ↑
                         Whisper small (CPU)
                         or a fake in unit tests
```

Allowed edges:

- `app.asgi` loads settings, builds the HTTP app, and starts the model load.
- `app.factory` is the only HTTP adapter. It calls auth, the body limit, the duration check, and `Transcriber`.
- `app.auth`, `app.audio`, and `app.transcriber` do not import FastAPI or Starlette.
- `WhisperTranscriber` is the only module that imports `whisper`, and only inside `load` and `transcribe`.

Forbidden:

- A second way to accept a caller (JWT, cookies, mutual TLS, a query-string key).
- A request field that selects the model or the task.
- Writing the transcript or the audio anywhere except the response and the temp file.
- More than one uvicorn worker. The single-flight lock is in-process.

## Boot

`init.sh` requires `.env`, then `docker compose up --build -d`, then waits until `GET /healthz` is `200`.

The image installs CPU PyTorch, then `openai-whisper` without letting that package replace the CPU wheel. The `small` weights are downloaded during `docker build`, into the image user's cache, so a later start does not need the network to load the model.

## Deployment shape

The container listens on port `8080` without TLS. Publish that port only to a proxy that terminates TLS. The application does not know the proxy's certificate.

Host port defaults to `8080` (`WHISPER_PORT`).

`WHISPER_BASE_IMAGE` overrides the Docker Hub Python image when that registry is unreachable. The default is `python:3.11-slim-bookworm`.

## Runtime configuration

| Variable | Required | Meaning |
| --- | --- | --- |
| `WHISPER_KEYS` | yes | Comma-separated `id:sha256hex`. One or more, all distinct. |
| `WHISPER_MODEL` | no | Must be absent or `small`. |
| `WHISPER_TMP_DIR` | no | Temp clips. Default `/tmp/whisper-api`. |
| `WHISPER_PORT` | no | Host port only. The process always listens on `8080` inside the container. |
| `WHISPER_CONFIG` | no | Path to the conf file. Default `./whisper-api.conf`. |

`probe_duration_seconds` is not an environment variable. It is read from that conf file. The image copies `whisper-api.conf` to `/srv/whisper-api.conf`, and Compose mounts the repo file over it.
