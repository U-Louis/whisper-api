"""HTTP adapter. One authorization path, one error shape."""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.audio import (
    check_duration,
    normalize_language,
    parse_form,
    probe_duration_seconds,
    read_declared_length,
    write_temp,
)
from app.auth import authenticate
from app.errors import ERROR_CODES, Busy, DomainError, NotReady, PayloadTooLarge
from app.settings import Settings
from app.transcriber import Transcriber

log = logging.getLogger("whisper_api")
_CORRELATION = re.compile(r"[A-Za-z0-9._-]{1,128}")
Probe = Callable[[Path, float], float]


def create_app(
    settings: Settings,
    transcriber: Transcriber,
    probe: Probe = probe_duration_seconds,
    load_on_startup: bool = False,
) -> FastAPI:
    lifespan = None
    if load_on_startup:

        @asynccontextmanager
        async def lifespan(_app: FastAPI):  # type: ignore[no-redef]
            threading.Thread(target=transcriber.load, name="whisper-load", daemon=True).start()
            yield

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.settings = settings
    app.state.transcriber = transcriber
    app.state.probe = probe
    app.state.inference_lock = threading.Lock()

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        status, code = ERROR_CODES.get(type(exc), (500, "internal"))
        request.state.outcome = code
        return JSONResponse({"error": code}, status_code=status)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception(
            "unhandled",
            extra={
                "event": "unhandled",
                "outcome": "internal",
                "correlation_id": getattr(request.state, "correlation_id", None),
                "error_type": type(exc).__name__,
            },
        )
        request.state.outcome = "internal"
        return JSONResponse({"error": "internal"}, status_code=500)

    @app.get("/healthz")
    async def health(request: Request) -> JSONResponse:
        if transcriber.ready():
            request.state.outcome = "ok"
            return JSONResponse({"status": "ok"})
        request.state.outcome = "loading"
        return JSONResponse({"status": "loading"}, status_code=503)

    @app.post("/v1/transcribe")
    async def transcribe(request: Request) -> JSONResponse:
        key_id = authenticate(request.headers.get("authorization"), settings.keys)
        request.state.key_id = key_id
        if not transcriber.ready():
            raise NotReady()
        read_declared_length(
            request.headers.get("content-length"),
            settings.max_bytes + settings.multipart_slack,
        )
        lock: threading.Lock = request.app.state.inference_lock
        if not lock.acquire(blocking=False):
            raise Busy()
        path: Path | None = None
        try:
            body = await _read_limited(request, settings.max_bytes + settings.multipart_slack)
            file_bytes, language_raw = parse_form(
                body,
                request.headers.get("content-type", ""),
                settings.max_bytes,
            )
            language = normalize_language(language_raw)
            path = write_temp(settings.tmp_dir, file_bytes)
            duration = await asyncio.to_thread(
                request.app.state.probe, path, settings.probe_timeout_seconds
            )
            check_duration(duration, settings.max_seconds)
            transcript = await asyncio.to_thread(transcriber.transcribe, path, language)
            request.state.outcome = "ok"
            return JSONResponse({"text": transcript.text, "language": transcript.language})
        except DomainError:
            raise
        except Exception as exc:
            log.exception(
                "unhandled",
                extra={
                    "event": "unhandled",
                    "outcome": "internal",
                    "correlation_id": getattr(request.state, "correlation_id", None),
                    "error_type": type(exc).__name__,
                },
            )
            request.state.outcome = "internal"
            return JSONResponse({"error": "internal"}, status_code=500)
        finally:
            if path is not None:
                path.unlink(missing_ok=True)
            lock.release()

    app.add_middleware(RequestLog)
    return app


async def _read_limited(request: Request, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise PayloadTooLarge()
        chunks.append(chunk)
    return b"".join(chunks)


class RequestLog:
    """Correlation id and one JSON line. Does not read the body."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        cid = _correlation(scope)
        scope.setdefault("state", {})
        scope["state"]["correlation_id"] = cid
        status_holder: dict[str, int] = {}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = MutableHeaders(raw=message["headers"])
                headers["x-request-id"] = cid
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            state = scope.get("state", {})
            extra: dict[str, object] = {
                "event": "request",
                "outcome": state.get("outcome", "internal"),
                "correlation_id": cid,
                "path": scope.get("path"),
            }
            key_id = state.get("key_id")
            if isinstance(key_id, str):
                extra["key_id"] = key_id
            if "status" in status_holder:
                extra["status"] = status_holder["status"]
            log.info("request", extra=extra)


def _correlation(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name.lower() == b"x-request-id":
            try:
                text = value.decode("ascii")
            except UnicodeDecodeError:
                break
            if _CORRELATION.fullmatch(text):
                return text
            break
    return uuid.uuid4().hex
