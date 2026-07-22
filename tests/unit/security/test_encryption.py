import pytest
from cryptography.fernet import Fernet

from meridian.security.encryption import (
    EncryptionError,
    decrypt_token,
    encrypt_token,
)


@pytest.fixture
def key_env(monkeypatch):
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    return key


def test_encrypt_decrypt_roundtrip(key_env):
    token = "secret-access-token-12345"
    ciphertext = encrypt_token(token)
    assert isinstance(ciphertext, bytes)
    assert ciphertext != token.encode("utf-8")

    decrypted = decrypt_token(ciphertext)
    assert decrypted == token


def test_missing_encryption_key_raises_error(monkeypatch):
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    with pytest.raises(EncryptionError, match="ENCRYPTION_KEY environment variable is not set"):
        encrypt_token("some-token")


def test_invalid_key_format_raises_error(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "not-a-valid-fernet-key")
    with pytest.raises(EncryptionError, match="Invalid ENCRYPTION_KEY format"):
        encrypt_token("some-token")


def test_decrypt_corrupted_data_raises_error(key_env):
    ciphertext = encrypt_token("some-token")
    corrupted = ciphertext[:-5] + b"12345"
    with pytest.raises(EncryptionError, match="Failed to decrypt token"):
        decrypt_token(corrupted)


def test_empty_string_validation(key_env):
    with pytest.raises(ValueError, match="Plaintext token cannot be empty"):
        encrypt_token("")

    with pytest.raises(ValueError, match="Ciphertext cannot be empty"):
        decrypt_token(b"")
