"""Domain failures. HTTP status lives in the adapter, not here."""


class DomainError(Exception):
    """A refusal with a stable code. The message is never returned to the caller."""


class Unauthorized(DomainError):
    pass


class PayloadTooLarge(DomainError):
    pass


class TooLong(DomainError):
    pass


class UnreadableAudio(DomainError):
    pass


class InvalidLanguage(DomainError):
    pass


class MissingFile(DomainError):
    pass


class UnsupportedMedia(DomainError):
    pass


class Busy(DomainError):
    pass


class NotReady(DomainError):
    pass


ERROR_CODES: dict[type[DomainError], tuple[int, str]] = {
    Unauthorized: (401, "unauthorized"),
    PayloadTooLarge: (413, "payload_too_large"),
    TooLong: (422, "too_long"),
    UnreadableAudio: (422, "unreadable_audio"),
    InvalidLanguage: (422, "invalid_language"),
    MissingFile: (422, "missing_file"),
    UnsupportedMedia: (422, "unsupported_media"),
    Busy: (429, "busy"),
    NotReady: (503, "not_ready"),
}
