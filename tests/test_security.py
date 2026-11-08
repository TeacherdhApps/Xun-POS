import base64

import security


def test_hash_roundtrip():
    stored = security.hash_password("secreta123")
    assert stored.startswith("pbkdf2_sha256$600000$")
    assert security.verify_password(stored, "secreta123")
    assert not security.verify_password(stored, "otra")
    assert not security.needs_rehash(stored)


def test_legacy_100k_hash_needs_rehash():
    stored = security.hash_password("vieja", iterations=100_000)
    assert stored.startswith("pbkdf2_sha256$100000$")
    assert security.verify_password(stored, "vieja")
    assert security.needs_rehash(stored)


def test_legacy_base64_password():
    stored = base64.b64encode(b"clave").decode()
    assert security.verify_password(stored, "clave")
    assert not security.verify_password(stored, "otra")
    assert security.needs_rehash(stored)


def test_malformed_hashes_are_rejected():
    assert not security.verify_password("", "x")
    assert not security.verify_password("pbkdf2_sha256$no", "x")
    assert not security.verify_password("no-es-base64!", "x")
