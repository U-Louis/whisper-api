"""Whisper behind a small seam so tests do not load the model."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.errors import InvalidLanguage

log = logging.getLogger("whisper_api")


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

            self._model = whisper.load_model(self._model_name, device="cpu")
        except Exception:
            log.exception("model_load_failed", extra={"event": "model_load", "outcome": "failed"})
            self._model = None

    def ready(self) -> bool:
        return self._model is not None

    def transcribe(self, path: Path, language: str | None) -> Transcript:
        model = self._model
        if model is None:
            raise RuntimeError("model is not loaded")
        kwargs: dict[str, object] = {
            "fp16": False,
            "task": "transcribe",
            "temperature": 0,
            "verbose": False,
        }
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
