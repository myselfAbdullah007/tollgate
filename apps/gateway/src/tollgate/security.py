import base64
import hashlib
import os
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

passwords = PasswordHasher()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_key() -> str:
    return "tg_live_" + secrets.token_urlsafe(32)


def verify_password(encoded: str, value: str) -> bool:
    try:
        return passwords.verify(encoded, value)
    except VerificationError:
        return False


class Crypto:
    def __init__(self, key: str):
        raw = base64.b64decode(key, validate=True)
        if len(raw) != 32:
            raise ValueError("Master key must decode to 32 bytes")
        self.aes = AESGCM(raw)

    def encrypt(self, value: str) -> str:
        nonce = os.urandom(12)
        return base64.b64encode(nonce + self.aes.encrypt(nonce, value.encode(), b"tollgate-v1")).decode()

    def decrypt(self, value: str) -> str:
        raw = base64.b64decode(value)
        return self.aes.decrypt(raw[:12], raw[12:], b"tollgate-v1").decode()
