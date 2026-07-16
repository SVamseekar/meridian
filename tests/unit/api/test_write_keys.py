import hashlib

from meridian.api.write_keys import generate_write_key, hash_write_key


def test_generate_write_key_has_expected_prefix():
    plaintext, key_hash = generate_write_key()
    assert plaintext.startswith("wk_live_")


def test_generate_write_key_is_high_entropy():
    plaintext, _ = generate_write_key()
    suffix = plaintext.removeprefix("wk_live_")
    assert len(suffix) >= 32


def test_generate_write_key_hash_matches_hash_function():
    plaintext, key_hash = generate_write_key()
    assert key_hash == hashlib.sha256(plaintext.encode()).hexdigest()


def test_generate_write_key_is_unique_per_call():
    plaintext1, _ = generate_write_key()
    plaintext2, _ = generate_write_key()
    assert plaintext1 != plaintext2


def test_hash_write_key_is_deterministic():
    assert hash_write_key("wk_live_abc") == hash_write_key("wk_live_abc")


def test_hash_write_key_matches_sha256():
    assert hash_write_key("wk_live_abc") == hashlib.sha256(b"wk_live_abc").hexdigest()
