#!/usr/bin/env python3
"""Hashing y verificación de contraseñas de Xun-POS."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

PREFIX = "pbkdf2_sha256"
ITERATIONS = 600_000
LEGACY_ITERATIONS = 100_000


def hash_password(
    password: str,
    salt: bytes | None = None,
    iterations: int = ITERATIONS,
) -> str:
    """Return a portable pbkdf2_sha256$iteraciones$salt$hash string."""
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return f"{PREFIX}${iterations}${salt.hex()}${digest.hex()}"


def _pbkdf2_matches(password: str, salt_hex: str, hash_hex: str, iterations: int) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(digest.hex(), hash_hex)


def verify_password(stored: str, provided: str) -> bool:
    """Verify a modern hash, the old salt$hash format, or legacy base64."""
    if not stored:
        return False

    if stored.startswith(PREFIX + "$"):
        try:
            _, iterations, salt_hex, hash_hex = stored.split("$", 3)
            return _pbkdf2_matches(provided, salt_hex, hash_hex, int(iterations))
        except (ValueError, TypeError):
            return False

    if "$" in stored:
        salt_hex, hash_hex = stored.split("$", 1)
        return _pbkdf2_matches(provided, salt_hex, hash_hex, LEGACY_ITERATIONS)

    try:
        decoded = base64.b64decode(stored).decode("utf-8")
    except Exception:
        return False
    return hmac.compare_digest(decoded, provided)


def needs_rehash(stored: str) -> bool:
    """True when the stored hash uses fewer iterations or a legacy format."""
    return not stored.startswith(f"{PREFIX}${ITERATIONS}$")
