# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Tests for phantomkey.vault.crypto — written BEFORE implementation (TDD)."""

import os
import pytest


class TestDeriveKEK:
    """Test Scrypt-based key derivation."""

    def test_derive_kek_returns_32_bytes(self):
        from phantomkey.vault.crypto import derive_kek

        salt = os.urandom(32)
        kek = derive_kek(b"master-password", salt)
        assert len(kek) == 32

    def test_derive_kek_deterministic(self):
        """Same password + salt = same KEK."""
        from phantomkey.vault.crypto import derive_kek

        salt = os.urandom(32)
        kek1 = derive_kek(b"password123", salt)
        kek2 = derive_kek(b"password123", salt)
        assert kek1 == kek2

    def test_derive_kek_different_passwords_differ(self):
        from phantomkey.vault.crypto import derive_kek

        salt = os.urandom(32)
        kek1 = derive_kek(b"password1", salt)
        kek2 = derive_kek(b"password2", salt)
        assert kek1 != kek2

    def test_derive_kek_different_salts_differ(self):
        from phantomkey.vault.crypto import derive_kek

        kek1 = derive_kek(b"password", os.urandom(32))
        kek2 = derive_kek(b"password", os.urandom(32))
        assert kek1 != kek2


class TestGenerateDEK:
    """Test random DEK generation."""

    def test_generate_dek_returns_32_bytes(self):
        from phantomkey.vault.crypto import generate_dek

        dek = generate_dek()
        assert len(dek) == 32

    def test_generate_dek_unique(self):
        from phantomkey.vault.crypto import generate_dek

        deks = {generate_dek() for _ in range(10)}
        assert len(deks) == 10


class TestEncryptDecrypt:
    """Test AES-256-GCM encrypt/decrypt round-trips."""

    def test_round_trip(self):
        from phantomkey.vault.crypto import encrypt, decrypt, generate_dek

        key = generate_dek()
        plaintext = b"secret credential data"
        nonce, ciphertext = encrypt(key, plaintext)
        result = decrypt(key, nonce, ciphertext)
        assert result == plaintext

    def test_ciphertext_differs_from_plaintext(self):
        from phantomkey.vault.crypto import encrypt, generate_dek

        key = generate_dek()
        plaintext = b"secret credential data"
        nonce, ciphertext = encrypt(key, plaintext)
        assert ciphertext != plaintext

    def test_nonce_is_12_bytes(self):
        from phantomkey.vault.crypto import encrypt, generate_dek

        key = generate_dek()
        nonce, _ = encrypt(key, b"data")
        assert len(nonce) == 12

    def test_unique_nonces(self):
        """Each encryption should produce a unique nonce."""
        from phantomkey.vault.crypto import encrypt, generate_dek

        key = generate_dek()
        nonces = set()
        for _ in range(20):
            nonce, _ = encrypt(key, b"data")
            nonces.add(nonce)
        assert len(nonces) == 20

    def test_wrong_key_fails(self):
        from phantomkey.vault.crypto import encrypt, decrypt, generate_dek

        key1 = generate_dek()
        key2 = generate_dek()
        nonce, ciphertext = encrypt(key1, b"secret")
        with pytest.raises(Exception):
            decrypt(key2, nonce, ciphertext)

    def test_tampered_ciphertext_fails(self):
        from phantomkey.vault.crypto import encrypt, decrypt, generate_dek

        key = generate_dek()
        nonce, ciphertext = encrypt(key, b"secret")
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF
        with pytest.raises(Exception):
            decrypt(key, nonce, bytes(tampered))

    def test_empty_plaintext(self):
        from phantomkey.vault.crypto import encrypt, decrypt, generate_dek

        key = generate_dek()
        nonce, ciphertext = encrypt(key, b"")
        assert decrypt(key, nonce, ciphertext) == b""

    def test_large_plaintext(self):
        from phantomkey.vault.crypto import encrypt, decrypt, generate_dek

        key = generate_dek()
        plaintext = os.urandom(1024 * 100)  # 100KB
        nonce, ciphertext = encrypt(key, plaintext)
        assert decrypt(key, nonce, ciphertext) == plaintext


class TestWipe:
    """Test best-effort memory wiping."""

    def test_wipe_zeros_bytearray(self):
        from phantomkey.vault.crypto import wipe

        secret = bytearray(b"super-secret-key-material-here!!")
        wipe(secret)
        assert all(b == 0 for b in secret)

    def test_wipe_empty_bytearray(self):
        from phantomkey.vault.crypto import wipe

        secret = bytearray(b"")
        wipe(secret)
        assert len(secret) == 0


class TestGenerateSalt:
    """Test salt generation."""

    def test_generate_salt_returns_32_bytes(self):
        from phantomkey.vault.crypto import generate_salt

        salt = generate_salt()
        assert len(salt) == 32

    def test_generate_salt_unique(self):
        from phantomkey.vault.crypto import generate_salt

        salts = {generate_salt() for _ in range(10)}
        assert len(salts) == 10