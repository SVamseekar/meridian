import os

from cryptography.fernet import Fernet, InvalidToken

__all__ = ["encrypt_secret", "decrypt_secret", "InvalidToken"]


def _fernet() -> Fernet:
    return Fernet(os.environ["ENCRYPTION_KEY"].encode())


def encrypt_secret(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt_secret(ciphertext: bytes) -> str:
    return _fernet().decrypt(ciphertext).decode()
