"""JWT access tokens (HS256, standard library only) and opaque refresh tokens.
decode() accepts ONLY alg=HS256 with a valid signature and an unexpired `exp` (so "alg: none" tokens are rejected)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

ACCESS_TTL = 15 * 60
REFRESH_TTL = 14 * 24 * 3600


class TokenError(Exception):
    pass


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def encode(payload: dict, secret: bytes) -> str:
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(secret, f"{head}.{body}".encode(), hashlib.sha256).digest()
    return f"{head}.{body}.{_b64(sig)}"


def decode(token: str, secret: bytes, now: float | None = None) -> dict:
    try:
        head_s, body_s, sig_s = token.split(".")
        head = json.loads(_unb64(head_s))
        if head.get("alg") != "HS256":
            raise TokenError("Unsupported token algorithm")
        expected = hmac.new(secret, f"{head_s}.{body_s}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(sig_s)):
            raise TokenError("Bad signature")
        payload = json.loads(_unb64(body_s))
    except TokenError:
        raise
    except Exception as e:
        raise TokenError("Malformed token") from e
    if not isinstance(payload.get("exp"), (int, float)) or (now if now is not None else time.time()) >= payload["exp"]:
        raise TokenError("Token expired")
    return payload


def create_access_token(user_id: str, secret: bytes, ttl: int = ACCESS_TTL, now: float | None = None) -> str:
    t = int(now if now is not None else time.time())
    return encode({"sub": user_id, "iat": t, "exp": t + ttl, "typ": "access"}, secret)


def new_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def load_secret(data_dir: Path) -> bytes:
    """OSLAB_JWT_SECRET if set, otherwise a random secret generated once and kept in the data folder (never in code)."""
    env = os.getenv("OSLAB_JWT_SECRET")
    if env:
        if len(env) < 32:
            raise RuntimeError("OSLAB_JWT_SECRET must be at least 32 characters")
        return env.encode()
    f = data_dir / "jwt_secret"
    if f.exists():
        return f.read_text().strip().encode()
    data_dir.mkdir(parents=True, exist_ok=True)
    s = secrets.token_hex(32)
    f.write_text(s)
    try:
        os.chmod(f, 0o600)
    except OSError:
        pass
    return s.encode()
