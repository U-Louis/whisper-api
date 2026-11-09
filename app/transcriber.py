"""Whisper behind a small seam so tests do not load the model."""

from __future__ import annotations

import logging
import os
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.errors import InvalidLanguage

log = logging.getLogger("whisper_api")

_DECODE = {
    "fp16": False,
    "task": "transcribe",
    "temperature": 0,
    "verbose": False,
}


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str


class Transcriber(Protocol):
    def ready(self) -> bool: ...

    def transcribe(self, path: Path, language: str | None) -> Transcript: ...


class WhisperTranscriber:
    def __init__(self, model_name: str) -> None:
        if model_name != "small":
            raise RuntimeError("model must be small")
        self._model_name = model_name
        self._model: object | None = None

    def load(self) -> None:
        try:
            import whisper

            model = whisper.load_model(self._model_name, device="cpu")
            _warmup(model)
        except Exception:
            log.exception("model_load_failed", extra={"event": "model_load", "outcome": "failed"})
            self._model = None
            return
        self._model = model

    def ready(self) -> bool:
        return self._model is not None

    def transcribe(self, path: Path, language: str | None) -> Transcript:
        model = self._model
        if model is None:
            raise RuntimeError("model is not loaded")
        kwargs: dict[str, object] = dict(_DECODE)
        if language is not None:
            kwargs["language"] = language
        try:
            result = model.transcribe(str(path), **kwargs)  # type: ignore[attr-defined]
        except (ValueError, KeyError):
            raise InvalidLanguage() from None
        text = str(result.get("text", "")).strip()
        detected = language if language is not None else result.get("language")
        if not isinstance(detected, str) or not detected:
            raise InvalidLanguage()
        return Transcript(text=text, language=detected)


def _warmup(model: object) -> None:
    """One silent clip, so the first client does not pay CPU compilation."""
    fd, name = tempfile.mkstemp(prefix="whisper-warmup-", suffix=".wav")
    os.close(fd)
    path = Path(name)
    try:
        _write_silence(path)
        model.transcribe(str(path), **_DECODE)  # type: ignore[attr-defined]
    finally:
        path.unlink(missing_ok=True)


def _write_silence(path: Path) -> None:
    rate = 16000
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * rate)
