import logging

from fastapi.testclient import TestClient

from app.log import JsonFormatter
from tests.conftest import PHRASE, SECRET_A, SECRET_B, post_clip


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_health_ready(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_not_ready(tmp_path, transcriber) -> None:
    from app.factory import create_app
    from app.settings import ApiKey, Settings
    from tests.conftest import hash_secret

    transcriber._ready = False
    settings = Settings(
        keys=(ApiKey("app-a", hash_secret(SECRET_A)), ApiKey("app-b", hash_secret(SECRET_B))),
        model="small",
        max_bytes=32,
        max_seconds=30,
        multipart_slack=4096,
        tmp_dir=tmp_path,
        probe_timeout_seconds=10,
    )
    app = create_app(settings, transcriber, probe=lambda _p, _t: 1.0)
    with TestClient(app) as local:
        response = local.get("/healthz")
    assert response.status_code == 503
    assert response.json() == {"status": "loading"}


def test_missing_and_unknown_keys_match(client: TestClient) -> None:
    missing = client.post("/v1/transcribe")
    unknown = post_clip(client, "not-a-real-key")
    assert missing.status_code == unknown.status_code == 401
    assert missing.content == unknown.content
    assert missing.json() == {"error": "unauthorized"}


def test_oversized_anonymous_request_is_unauthorized(client: TestClient) -> None:
    response = post_clip(client, None, content=b"x" * 80)
    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}


def test_each_app_is_distinct_and_secret_stays_out_of_logs(client: TestClient, transcriber) -> None:
    handler = _ListHandler()
    logger = logging.getLogger("whisper_api")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        first = post_clip(client, SECRET_A)
        second = post_clip(client, SECRET_B)
    finally:
        logger.removeHandler(handler)
    assert first.status_code == 200
    assert first.json() == {"text": PHRASE, "language": "en"}
    assert second.status_code == 200
    rendered = "\n".join(JsonFormatter().format(record) for record in handler.records)
    assert '"key_id":"app-a"' in rendered
    assert '"key_id":"app-b"' in rendered
    assert SECRET_A not in rendered
    assert SECRET_B not in rendered
    assert PHRASE not in rendered
    assert transcriber.calls
