# crypto_utils.py - ENCRYPTION AT REST (AES-256-GCM).
# The key is NOT in the code and NOT in the database. It is read from .env.
import base64
import binascii
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoConfigError(Exception):
    """Raised when the encryption key in .env is missing or wrong."""


def get_key():
    """Load the 32-byte AES key from the DATA_ENCRYPTION_KEY environment variable."""
    text = os.getenv("DATA_ENCRYPTION_KEY", "").strip()
    if not text:
        raise CryptoConfigError("DATA_ENCRYPTION_KEY is missing in backend/.env")
    try:
        key = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        raise CryptoConfigError("DATA_ENCRYPTION_KEY is not valid base64")
    if len(key) != 32:                      # 32 bytes = 256 bits
        raise CryptoConfigError("DATA_ENCRYPTION_KEY must be exactly 32 bytes (AES-256)")
    return key


def encrypt_bytes(plaintext, aad):
    """Encrypt bytes. Returns (nonce, ciphertext).
    - nonce: 12 random bytes, a NEW one for every encryption (never reuse with the same key)
    - aad:   extra data that is authenticated but not hidden. We pass the dataset id,
             so an encrypted blob copied into another dataset row will fail to decrypt.
    - GCM adds a 16-byte tag at the end of the ciphertext, so any tampering is detected."""
    nonce = os.urandom(12)
    ciphertext = AESGCM(get_key()).encrypt(nonce, plaintext, aad)
    return nonce, ciphertext


def decrypt_bytes(nonce, ciphertext, aad):
    """Decrypt bytes in memory. Raises InvalidTag if the key, nonce, aad or data is wrong."""
    return AESGCM(get_key()).decrypt(bytes(nonce), bytes(ciphertext), aad)
