"""Production entrypoint. Importing this module refuses to start without two key hashes."""

from app.factory import create_app
from app.log import configure_logging
from app.settings import Settings
from app.transcriber import WhisperTranscriber

configure_logging()
_settings = Settings.from_env()
_transcriber = WhisperTranscriber(_settings.model)
app = create_app(_settings, _transcriber, load_on_startup=True)
