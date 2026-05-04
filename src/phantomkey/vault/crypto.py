# Copyright 2026 Ritvik Salim
# SPDX-License-Identifier: Apache-2.0

"""Core cryptographic primitives for PhantomKey vault encryption.

Key hierarchy:
  Master Password -> Scrypt KDF -> KEK (Key-Encryption-Key)
  KEK encrypts -> DEK (Data-Encryption-Key, random per vault)
  DEK encrypts -> Vault credential data
"""

import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

# Scrypt parameters (OWASP recommended, memory-hard)
_SCRYPT_N = 2**17  # CPU/memory cost
_SCRYPT_R = 8  # Block size
_SCRYPT_P = 1  # Parallelism
_KEY_LENGTH = 32  # 256 bits


def derive_kek(passphrase: bytes, salt: bytes) -> bytes:
    """Derive a Key-Encryption-Key from a passphrase using Scrypt."""
    kdf = Scrypt(salt=salt, length=_KEY_LENGTH, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return kdf.derive(passphrase)


def generate_dek() -> bytes:
    """Generate a random 256-bit Data-Encryption-Key."""
    return secrets.token_bytes(_KEY_LENGTH)


def generate_salt() -> bytes:
    """Generate a random 256-bit salt for KDF."""
    return secrets.token_bytes(32)


def encrypt(key: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    """Encrypt plaintext with AES-256-GCM.

    Returns:
        (nonce, ciphertext) tuple. Nonce is 12 bytes.
    """
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce, ciphertext


def decrypt(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    """Decrypt ciphertext with AES-256-GCM.

    Raises:
        cryptography.exceptions.InvalidTag: If key is wrong or data is tampered.
    """
    return AESGCM(key).decrypt(nonce, ciphertext, None)


def wipe(b: bytearray) -> None:
    """Best-effort zeroing of secret bytes in memory."""
    for i in range(len(b)):
        b[i] = 0