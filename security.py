import os
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(value: str) -> str:
    return generate_password_hash(value)


def verify_password(password_hash: str, value: str) -> bool:
    return check_password_hash(password_hash, value)


def _fernet() -> Fernet:
    key = os.environ.get("LOOKOUT_ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError("LOOKOUT_ENCRYPTION_KEY is required")
    return Fernet(key.encode())


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().decrypt(value.encode()).decode()
