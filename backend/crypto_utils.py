import base64
import binascii
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoConfigError(Exception):
    """Raised when the encryption key is missing or wrong."""


def get_key():
    text = os.getenv("DATA_ENCRYPTION_KEY", "").strip()
    if not text:
        raise CryptoConfigError("DATA_ENCRYPTION_KEY is missing in backend/.env")
    try:
        key = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        raise CryptoConfigError("DATA_ENCRYPTION_KEY is not valid base64")
    if len(key) != 32:                      
        raise CryptoConfigError("DATA_ENCRYPTION_KEY must be exactly 32 bytes (AES-256)")
    return key


def encrypt_bytes(plaintext, aad):
    nonce = os.urandom(12)
    ciphertext = AESGCM(get_key()).encrypt(nonce, plaintext, aad)
    return nonce, ciphertext


def decrypt_bytes(nonce, ciphertext, aad):
    return AESGCM(get_key()).decrypt(bytes(nonce), bytes(ciphertext), aad)
