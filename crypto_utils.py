import os
from cryptography.fernet import Fernet


def get_cipher():
    key = os.getenv("TOKEN_ENCRYPTION_KEY")

    if not key:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY sozlanmagan!"
        )

    return Fernet(key.encode())


def encrypt_token(token: str) -> str:
    return get_cipher().encrypt(
        token.encode("utf-8")
    ).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    return get_cipher().decrypt(
        encrypted_token.encode("utf-8")
    ).decode("utf-8")
