import os
from cryptography.fernet import Fernet


class EncryptionError(Exception):
    """Raised when encryption or decryption fails due to invalid key or corrupted data."""


def _get_fernet() -> Fernet:
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise EncryptionError("ENCRYPTION_KEY environment variable is not set")
    try:
        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    except Exception as exc:
        raise EncryptionError("Invalid ENCRYPTION_KEY format") from exc


def encrypt_token(plaintext: str) -> bytes:
    """Encrypt a plaintext token string into Fernet ciphertext bytes."""
    if not plaintext:
        raise ValueError("Plaintext token cannot be empty")
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode("utf-8"))


def decrypt_token(ciphertext: bytes) -> str:
    """Decrypt Fernet ciphertext bytes back into a plaintext token string."""
    if not ciphertext:
        raise ValueError("Ciphertext cannot be empty")
    fernet = _get_fernet()
    try:
        return fernet.decrypt(ciphertext).decode("utf-8")
    except Exception as exc:
        raise EncryptionError("Failed to decrypt token: corrupted or invalid key") from exc
