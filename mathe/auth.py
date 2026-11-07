"""Passwort-Hashes mit hashlib.scrypt aus der Python-Standardbibliothek."""

from __future__ import annotations

import hashlib
import secrets

_N = 2**14
_R = 8
_P = 1
_DKLEN = 32


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
        dklen=_DKLEN,
    )
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n_s, r_s, p_s, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_s),
            r=int(r_s),
            p=int(p_s),
            dklen=len(expected),
        )
        return secrets.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


def burn_password_time(password: str) -> None:
    """Gleiche Rechenarbeit, wenn es den Benutzer nicht gibt."""
    salt = bytes.fromhex("a1" * 16)
    hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
        dklen=_DKLEN,
    )


def check_password(user: dict | None, password: str) -> bool:
    if user is None:
        burn_password_time(password)
        return False
    return verify_password(password, user["password_hash"])
