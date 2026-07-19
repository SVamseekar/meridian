import pytest
from cryptography.fernet import Fernet, InvalidToken

from meridian.crypto import decrypt_secret, encrypt_secret


def test_encrypt_decrypt_round_trips(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    plaintext = "hubspot-access-token-abc123"

    ciphertext = encrypt_secret(plaintext)

    assert isinstance(ciphertext, bytes)
    assert ciphertext != plaintext.encode()
    assert decrypt_secret(ciphertext) == plaintext


def test_decrypt_fails_with_wrong_key(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    ciphertext = encrypt_secret("some-secret")

    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(InvalidToken):
        decrypt_secret(ciphertext)


def test_decrypt_fails_on_corrupted_ciphertext(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    ciphertext = encrypt_secret("some-secret")
    corrupted = ciphertext[:-1] + (b"A" if ciphertext[-1:] != b"A" else b"B")

    with pytest.raises(InvalidToken):
        decrypt_secret(corrupted)
