"""The only authorization path: one bearer token, compared with every stored hash."""

from __future__ import annotations

import hashlib
import hmac

from app.errors import Unauthorized
from app.settings import MAX_TOKEN_LENGTH, ApiKey


def authenticate(authorization: str | None, keys: tuple[ApiKey, ...]) -> str:
    """Return the key id, or raise Unauthorized. Missing and unknown look the same."""
    token = _bearer(authorization)
    presented = hashlib.sha256(token.encode("utf-8")).digest() if token is not None else hashlib.sha256(b"").digest()
    found: str | None = None
    for key in keys:
        if hmac.compare_digest(presented, key.digest()) and token is not None:
            found = key.id
    if found is None:
        raise Unauthorized()
    return found


def _bearer(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, sep, rest = authorization.partition(" ")
    if not sep or scheme.lower() != "bearer":
        return None
    token = rest.strip()
    if not token or len(token) > MAX_TOKEN_LENGTH or " " in rest.strip():
        return None
    return token
