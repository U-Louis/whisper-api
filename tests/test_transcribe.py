import threading
from pathlib import Path

from fastapi.testclient import TestClient

from app.errors import UnreadableAudio
from app.factory import create_app
from app.settings import ApiKey, Settings
from app.transcriber import Transcript, _warmup
from tests.conftest import SECRET_A, SECRET_B, hash_secret, post_clip


def test_short_clip_returns_text_and_deletes_the_file(client: TestClient, transcriber, tmp_audio) -> None:
    response = post_clip(client, SECRET_A, content=b"RIFFclip", data={"language": "fr"})
    assert response.status_code == 200
    assert response.json() == {"text": transcriber.text, "language": "fr"}
    assert transcriber.calls[0][1] == "fr"
    assert list(tmp_audio.iterdir()) == []


def test_omitted_language_is_detected(client: TestClient, transcriber) -> None:
    response = post_clip(client, SECRET_A)
    assert response.status_code == 200
    assert response.json()["language"] == "en"
    assert transcriber.calls[0][1] is None


def test_invalid_language_does_not_call_the_model(client: TestClient, transcriber) -> None:
    response = post_clip(client, SECRET_A, data={"language": "English"})
    assert response.status_code == 422
    assert response.json() == {"error": "invalid_language"}
    assert transcriber.calls == []


def test_oversize_file_is_413_before_the_model(client: TestClient, transcriber, tmp_audio) -> None:
    response = post_clip(client, SECRET_A, content=b"x" * 33)
    assert response.status_code == 413
    assert response.json() == {"error": "payload_too_large"}
    assert transcriber.calls == []
    assert list(tmp_audio.iterdir()) == []


def test_declared_length_is_refused_before_the_lock(client: TestClient, transcriber) -> None:
    client.app.state.inference_lock.acquire()
    try:
        response = post_clip(client, SECRET_A, content=b"x" * 5000)
    finally:
        client.app.state.inference_lock.release()
    assert response.status_code == 413
    assert transcriber.calls == []


def test_duration_boundary(tmp_audio, transcriber) -> None:
    settings = Settings(
        keys=(ApiKey("app-a", hash_secret(SECRET_A)), ApiKey("app-b", hash_secret(SECRET_B))),
        model="small",
        max_bytes=32,
        max_seconds=30,
        multipart_slack=4096,
        tmp_dir=tmp_audio,
        probe_timeout_seconds=10,
    )

    def accept(_path, _timeout):
        return 30

    app = create_app(settings, transcriber, probe=accept)
    with TestClient(app) as local:
        allowed = post_clip(local, SECRET_A)
    assert allowed.status_code == 200

    def reject(_path, _timeout):
        return 30.001

    app = create_app(settings, transcriber, probe=reject)
    with TestClient(app) as local:
        refused = post_clip(local, SECRET_A)
    assert refused.status_code == 422
    assert refused.json() == {"error": "too_long"}
    assert list(tmp_audio.iterdir()) == []


def test_unreadable_audio(client: TestClient, transcriber, tmp_audio) -> None:
    def boom(_path, _timeout):
        raise UnreadableAudio()

    client.app.state.probe = boom
    response = post_clip(client, SECRET_A)
    assert response.status_code == 422
    assert response.json() == {"error": "unreadable_audio"}
    assert transcriber.calls == []
    assert list(tmp_audio.iterdir()) == []


def test_busy_while_the_slot_is_held(client: TestClient, transcriber) -> None:
    client.app.state.inference_lock.acquire()
    try:
        response = post_clip(client, SECRET_A)
    finally:
        client.app.state.inference_lock.release()
    assert response.status_code == 429
    assert response.json() == {"error": "busy"}
    assert transcriber.calls == []
    follow = post_clip(client, SECRET_A)
    assert follow.status_code == 200


def test_not_ready_is_503_for_a_valid_key_and_401_for_a_bad_one(tmp_audio, transcriber) -> None:
    transcriber._ready = False
    settings = Settings(
        keys=(ApiKey("app-a", hash_secret(SECRET_A)), ApiKey("app-b", hash_secret(SECRET_B))),
        model="small",
        max_bytes=32,
        max_seconds=30,
        multipart_slack=4096,
        tmp_dir=tmp_audio,
        probe_timeout_seconds=10,
    )
    app = create_app(settings, transcriber, probe=lambda _p, _t: 1.0)
    with TestClient(app) as local:
        ready = post_clip(local, SECRET_A)
        anonymous = post_clip(local, "nope")
    assert ready.status_code == 503
    assert ready.json() == {"error": "not_ready"}
    assert anonymous.status_code == 401


def test_transcriber_failure_releases_the_slot_and_the_file(tmp_audio) -> None:
    class Boom:
        def ready(self) -> bool:
            return True

        def transcribe(self, path, language) -> Transcript:
            raise RuntimeError("model blew up")

    settings = Settings(
        keys=(ApiKey("app-a", hash_secret(SECRET_A)), ApiKey("app-b", hash_secret(SECRET_B))),
        model="small",
        max_bytes=32,
        max_seconds=30,
        multipart_slack=4096,
        tmp_dir=tmp_audio,
        probe_timeout_seconds=10,
    )
    fake = Boom()
    app = create_app(settings, fake, probe=lambda _p, _t: 1.0)
    with TestClient(app) as local:
        failed = post_clip(local, SECRET_A)
        assert failed.status_code == 500
        assert failed.json() == {"error": "internal"}
        assert list(tmp_audio.iterdir()) == []
    assert app.state.inference_lock.acquire(blocking=False) is True
    app.state.inference_lock.release()


def test_a_running_call_blocks_the_next_one(tmp_audio) -> None:
    started = threading.Event()
    release = threading.Event()

    class Blocking:
        def ready(self) -> bool:
            return True

        def transcribe(self, path, language) -> Transcript:
            started.set()
            assert release.wait(5)
            return Transcript("ok", "en")

    settings = Settings(
        keys=(ApiKey("app-a", hash_secret(SECRET_A)), ApiKey("app-b", hash_secret(SECRET_B))),
        model="small",
        max_bytes=32,
        max_seconds=30,
        multipart_slack=4096,
        tmp_dir=tmp_audio,
        probe_timeout_seconds=10,
    )
    app = create_app(settings, Blocking(), probe=lambda _p, _t: 1.0)
    with TestClient(app) as local:
        box: dict[str, object] = {}

        def run() -> None:
            box["response"] = post_clip(local, SECRET_A)

        thread = threading.Thread(target=run)
        thread.start()
        assert started.wait(2)
        # The slot is held inside the worker thread. Take the same observation
        # the next request would: the lock does not yield.
        assert app.state.inference_lock.acquire(blocking=False) is False
        release.set()
        thread.join(5)
    assert box["response"].status_code == 200
    assert list(tmp_audio.iterdir()) == []


def test_warmup_deletes_the_clip_and_discards_the_text(caplog) -> None:
    seen: dict[str, object] = {}

    class Model:
        def transcribe(self, path: str, **kwargs: object) -> dict[str, str]:
            seen["path"] = path
            seen["kwargs"] = kwargs
            assert Path(path).is_file()
            return {"text": "SHOULD-NOT-LEAK", "language": "en"}

    with caplog.at_level("DEBUG"):
        _warmup(Model())

    assert isinstance(seen["path"], str)
    assert not Path(seen["path"]).exists()
    assert seen["kwargs"] == {
        "fp16": False,
        "task": "transcribe",
        "temperature": 0,
        "verbose": False,
    }
    assert "SHOULD-NOT-LEAK" not in caplog.text
