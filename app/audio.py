"""Body limits, multipart extraction, and the duration probe. No HTTP types."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path

from app.errors import InvalidLanguage, MissingFile, PayloadTooLarge, TooLong, UnreadableAudio, UnsupportedMedia

_LANGUAGE = re.compile(r"[a-z]{2}")
_DISPOSITION_NAME = re.compile(r"""(?:^|;)\s*name\s*=\s*(?:"([^"]*)"|([^";\s]+))""", re.IGNORECASE)
_DISPOSITION_FILE = re.compile(r"""filename\s*=""", re.IGNORECASE)


def check_duration(duration: float, max_seconds: float) -> None:
    if not math.isfinite(duration) or duration <= 0:
        raise UnreadableAudio()
    if duration > max_seconds:
        raise TooLong()


def normalize_language(raw: str | None) -> str | None:
    if raw is None:
        return None
    code = raw.strip().lower()
    if code == "":
        return None
    if not _LANGUAGE.fullmatch(code):
        raise InvalidLanguage()
    return code


def read_declared_length(content_length: str | None, limit: int) -> None:
    """Refuse an obviously oversized request before spending the inference slot."""
    if content_length is None:
        return
    try:
        declared = int(content_length)
    except ValueError:
        raise PayloadTooLarge() from None
    if declared < 0 or declared > limit:
        raise PayloadTooLarge()


def parse_form(body: bytes, content_type: str, max_bytes: int) -> tuple[bytes, str | None]:
    boundary = _boundary(content_type)
    parts = _parts(body, boundary)
    file_bytes: bytes | None = None
    language: str | None = None
    for headers, content in parts:
        name, is_file = _content_disposition(headers)
        if name == "file" and is_file:
            if file_bytes is not None:
                raise UnsupportedMedia()
            file_bytes = content
        elif name == "language" and not is_file:
            try:
                language = content.decode("utf-8")
            except UnicodeDecodeError:
                raise InvalidLanguage() from None
    if file_bytes is None:
        raise MissingFile()
    if len(file_bytes) == 0:
        raise UnreadableAudio()
    if len(file_bytes) > max_bytes:
        raise PayloadTooLarge()
    return file_bytes, language


def write_temp(directory: Path, data: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="clip-", suffix=".bin", dir=directory)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    return Path(name)


def probe_duration_seconds(path: Path, timeout_seconds: float) -> float:
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_type:format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        raise UnreadableAudio() from None
    if proc.returncode != 0:
        raise UnreadableAudio()
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise UnreadableAudio() from None
    streams = payload.get("streams") or []
    if not streams or streams[0].get("codec_type") != "audio":
        raise UnreadableAudio()
    raw = (payload.get("format") or {}).get("duration")
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise UnreadableAudio() from None


def _boundary(content_type: str) -> bytes:
    if not content_type:
        raise UnsupportedMedia()
    media, _, rest = content_type.partition(";")
    if media.strip().lower() != "multipart/form-data":
        raise UnsupportedMedia()
    boundary = ""
    for piece in rest.split(";"):
        name, sep, value = piece.strip().partition("=")
        if sep and name.lower() == "boundary":
            boundary = value.strip().strip('"')
    if not boundary or len(boundary) > 70 or "\r" in boundary or "\n" in boundary:
        raise UnsupportedMedia()
    try:
        return boundary.encode("ascii")
    except UnicodeEncodeError:
        raise UnsupportedMedia() from None


def _parts(body: bytes, boundary: bytes) -> list[tuple[str, bytes]]:
    marker = b"--" + boundary
    if not body.startswith(marker):
        raise UnsupportedMedia()
    chunks = body.split(b"\r\n" + marker)
    # First chunk still starts with the marker; drop that prefix.
    chunks[0] = chunks[0][len(marker) :]
    parts: list[tuple[str, bytes]] = []
    for chunk in chunks:
        if chunk.startswith(b"--") or chunk in (b"", b"\r\n"):
            continue
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        header_blob, sep, content = chunk.partition(b"\r\n\r\n")
        if not sep:
            raise UnsupportedMedia()
        try:
            headers = header_blob.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise UnsupportedMedia() from None
        parts.append((headers, content))
    if len(parts) > 4:
        raise UnsupportedMedia()
    return parts


def _content_disposition(headers: str) -> tuple[str, bool]:
    line = ""
    for raw in headers.split("\r\n"):
        if raw.lower().startswith("content-disposition:"):
            line = raw.split(":", 1)[1]
            break
    if "form-data" not in line.lower():
        raise UnsupportedMedia()
    match = _DISPOSITION_NAME.search(line)
    if not match:
        raise UnsupportedMedia()
    name = match.group(1) if match.group(1) is not None else match.group(2)
    return name, bool(_DISPOSITION_FILE.search(line))
