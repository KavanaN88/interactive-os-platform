"""Password hashing. Uses Argon2id when `argon2-cffi` is installed (it is in requirements.txt); otherwise falls back to
scrypt from the standard library. The hash string says which algorithm made it, so both verify correctly."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re

from app.engines.errors import ValidationError

try:  # preferred: Argon2id
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
    _PH = PasswordHasher()
except ImportError:  # pragma: no cover - depends on the environment
    _PH = None

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1


def validate_password(pw: str) -> None:
    if not isinstance(pw, str) or not 8 <= len(pw) <= 128:
        raise ValidationError("Password must be 8 to 128 characters long")
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        raise ValidationError("Password must contain at least one letter and one digit")


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password(pw: str) -> str:
    validate_password(pw)
    if _PH is not None:
        return _PH.hash(pw)
    salt = os.urandom(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(dk)}"


def verify_password(stored: str, pw: str) -> bool:
    """True only for a correct password. Never raises for malformed input."""
    try:
        if stored.startswith("$argon2"):
            if _PH is None:
                return False
            try:
                return bool(_PH.verify(stored, pw))
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False
        if stored.startswith("scrypt$"):
            _, n, r, p, salt, dk = stored.split("$")
            calc = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
            return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:
        return False
    return False


def algorithm_of(stored: str) -> str:
    return "argon2id" if stored.startswith("$argon2id") else "scrypt" if stored.startswith("scrypt$") else "unknown"
