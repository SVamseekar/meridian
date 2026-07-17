import hashlib
import secrets


def hash_write_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def generate_write_key() -> tuple[str, str]:
    """Returns (plaintext_key, key_hash). The plaintext is shown to the
    caller exactly once; only the hash is persisted (see Decision D14)."""
    suffix = secrets.token_urlsafe(24)  # >32 chars of high-entropy base64url
    plaintext = f"wk_live_{suffix}"
    return plaintext, hash_write_key(plaintext)
