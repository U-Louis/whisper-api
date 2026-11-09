from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.log import JsonFormatter
from app.settings import MAX_BYTES, ApiKey, Settings
from app.transcriber import Transcript

SECRET_A = "test-secret-app-a"
SECRET_B = "test-secret-app-b"
PHRASE = "TRANSCRIPT-SHOULD-NOT-BE-LOGGED"


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class FakeTranscriber:
    def __init__(self, text: str = PHRASE, language: str = "en", ready: bool = True) -> None:
        self.text = text
        self.language = language
        self._ready = ready
        self.calls: list[tuple[Path, str | None]] = []

    def ready(self) -> bool:
        return self._ready

    def transcribe(self, path: Path, language: str | None) -> Transcript:
        self.calls.append((path, language))
        assert path.is_file()
        return Transcript(self.text, language or self.language)


@pytest.fixture
def tmp_audio(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def transcriber() -> FakeTranscriber:
    return FakeTranscriber()


@pytest.fixture
def client(tmp_audio: Path, transcriber: FakeTranscriber):
    settings = Settings(
        keys=(
            ApiKey("app-a", hash_secret(SECRET_A)),
            ApiKey("app-b", hash_secret(SECRET_B)),
        ),
        model="small",
        max_bytes=32,
        max_seconds=30,
        multipart_slack=4096,
        tmp_dir=tmp_audio,
        probe_timeout_seconds=10,
    )
    app = create_app(settings, transcriber, probe=lambda _path, _timeout: 1.0)
    with TestClient(app) as test_client:
        yield test_client


def auth(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


def post_clip(client: TestClient, secret: str | None, content: bytes = b"RIFFclip", **extra):
    headers = auth(secret) if secret is not None else {}
    files = {"file": ("../../etc/passwd", content, "audio/wav")}
    return client.post("/v1/transcribe", headers=headers, files=files, **extra)
