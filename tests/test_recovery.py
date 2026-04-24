# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Tests for phantomkey.vault.recovery — written BEFORE implementation (TDD)."""

import os
import pytest
from pathlib import Path


class TestRecoveryStrategy:
    """Test the abstract strategy interface."""

    def test_phrase_strategy_implements_interface(self):
        from phantomkey.vault.recovery import PhraseRecovery, RecoveryStrategy

        strategy = PhraseRecovery()
        assert isinstance(strategy, RecoveryStrategy)

    def test_strategy_has_required_methods(self):
        from phantomkey.vault.recovery import RecoveryStrategy

        assert hasattr(RecoveryStrategy, "generate")
        assert hasattr(RecoveryStrategy, "derive_kek")
        assert hasattr(RecoveryStrategy, "display_name")


class TestPhraseRecovery:
    """Test BIP-39 style recovery phrase generation."""

    def test_generate_returns_12_words(self):
        from phantomkey.vault.recovery import PhraseRecovery

        strategy = PhraseRecovery()
        phrase = strategy.generate()
        words = phrase.split()
        assert len(words) == 12

    def test_generate_unique_phrases(self):
        from phantomkey.vault.recovery import PhraseRecovery

        strategy = PhraseRecovery()
        phrases = {strategy.generate() for _ in range(10)}
        assert len(phrases) == 10

    def test_words_are_lowercase_alpha(self):
        from phantomkey.vault.recovery import PhraseRecovery

        strategy = PhraseRecovery()
        phrase = strategy.generate()
        for word in phrase.split():
            assert word.isalpha()
            assert word.islower()

    def test_derive_kek_from_phrase(self):
        from phantomkey.vault.recovery import PhraseRecovery

        strategy = PhraseRecovery()
        phrase = strategy.generate()
        salt = os.urandom(32)
        kek = strategy.derive_kek(phrase, salt)
        assert len(kek) == 32

    def test_derive_kek_deterministic(self):
        from phantomkey.vault.recovery import PhraseRecovery

        strategy = PhraseRecovery()
        phrase = strategy.generate()
        salt = os.urandom(32)
        kek1 = strategy.derive_kek(phrase, salt)
        kek2 = strategy.derive_kek(phrase, salt)
        assert kek1 == kek2

    def test_derive_kek_different_phrases_differ(self):
        from phantomkey.vault.recovery import PhraseRecovery

        strategy = PhraseRecovery()
        salt = os.urandom(32)
        kek1 = strategy.derive_kek(strategy.generate(), salt)
        kek2 = strategy.derive_kek(strategy.generate(), salt)
        assert kek1 != kek2

    def test_display_name(self):
        from phantomkey.vault.recovery import PhraseRecovery

        strategy = PhraseRecovery()
        assert strategy.display_name() == "recovery phrase"


class TestKeyRecovery:
    """Test opaque recovery key strategy (swappable alternative)."""

    def test_generate_returns_string(self):
        from phantomkey.vault.recovery import KeyRecovery

        strategy = KeyRecovery()
        key = strategy.generate()
        assert isinstance(key, str)
        assert key.startswith("PK-")
        assert len(key) > 20

    def test_generate_unique_keys(self):
        from phantomkey.vault.recovery import KeyRecovery

        strategy = KeyRecovery()
        keys = {strategy.generate() for _ in range(10)}
        assert len(keys) == 10

    def test_derive_kek_from_key(self):
        from phantomkey.vault.recovery import KeyRecovery

        strategy = KeyRecovery()
        key = strategy.generate()
        salt = os.urandom(32)
        kek = strategy.derive_kek(key, salt)
        assert len(kek) == 32

    def test_derive_kek_deterministic(self):
        from phantomkey.vault.recovery import KeyRecovery

        strategy = KeyRecovery()
        key = strategy.generate()
        salt = os.urandom(32)
        kek1 = strategy.derive_kek(key, salt)
        kek2 = strategy.derive_kek(key, salt)
        assert kek1 == kek2

    def test_display_name(self):
        from phantomkey.vault.recovery import KeyRecovery

        strategy = KeyRecovery()
        assert strategy.display_name() == "recovery key"


class TestConfirmationChallenge:
    """Test the word confirmation challenge for init."""

    def test_pick_challenge_words(self):
        from phantomkey.vault.recovery import pick_challenge_words

        phrase = "timber ocean velvet ignite harvest puzzle drift summit candle anchor marble breeze"
        indices, words = pick_challenge_words(phrase, count=3)
        assert len(indices) == 3
        assert len(words) == 3
        phrase_words = phrase.split()
        for idx, word in zip(indices, words):
            assert phrase_words[idx] == word

    def test_challenge_picks_unique_indices(self):
        from phantomkey.vault.recovery import pick_challenge_words

        phrase = "a b c d e f g h i j k l"
        for _ in range(20):
            indices, _ = pick_challenge_words(phrase, count=3)
            assert len(set(indices)) == 3


class TestVaultRecoveryIntegration:
    """Test vault init with recovery and vault recover flow."""

    def test_init_with_recovery_stores_recovery_kek(self, tmp_path):
        import json
        from phantomkey.vault.recovery import PhraseRecovery
        from phantomkey.vault.store import Vault

        vault_dir = tmp_path / ".phantomkey"
        v = Vault(vault_dir)
        strategy = PhraseRecovery()
        phrase = v.init_with_recovery(b"master-pw", strategy)

        # Vault file should have recovery fields
        raw = json.loads((vault_dir / "vault.pk").read_text())
        assert "recovery_encrypted_dek" in raw
        assert "recovery_dek_nonce" in raw
        assert "recovery_kek_salt" in raw
        assert "recovery_strategy" in raw
        assert raw["recovery_strategy"] == "phrase"

        # Phrase should be 12 words
        assert len(phrase.split()) == 12

    def test_recover_with_correct_phrase(self, tmp_path):
        from phantomkey.vault.recovery import PhraseRecovery
        from phantomkey.vault.store import Vault

        vault_dir = tmp_path / ".phantomkey"
        v = Vault(vault_dir)
        strategy = PhraseRecovery()
        phrase = v.init_with_recovery(b"original-pw", strategy)

        # Add a credential
        v.add("test-cred", fields={"secret": "value123"})
        v.lock()

        # Recover with the phrase and set new password
        v2 = Vault(vault_dir)
        v2.recover(phrase, b"new-master-pw", strategy)

        # Should be able to access credentials with new password
        v3 = Vault(vault_dir)
        v3.unlock(b"new-master-pw")
        assert v3.get("test-cred").fields["secret"] == "value123"

    def test_recover_with_wrong_phrase_fails(self, tmp_path):
        from phantomkey.vault.recovery import PhraseRecovery
        from phantomkey.vault.store import Vault

        vault_dir = tmp_path / ".phantomkey"
        v = Vault(vault_dir)
        strategy = PhraseRecovery()
        v.init_with_recovery(b"master-pw", strategy)
        v.lock()

        v2 = Vault(vault_dir)
        with pytest.raises(Exception):
            v2.recover("wrong words here that are not the right ones at all ever", b"new-pw", strategy)

    def test_old_password_invalid_after_recover(self, tmp_path):
        from phantomkey.vault.recovery import PhraseRecovery
        from phantomkey.vault.store import Vault

        vault_dir = tmp_path / ".phantomkey"
        v = Vault(vault_dir)
        strategy = PhraseRecovery()
        phrase = v.init_with_recovery(b"old-pw", strategy)
        v.lock()

        v2 = Vault(vault_dir)
        v2.recover(phrase, b"new-pw", strategy)
        v2.lock()

        v3 = Vault(vault_dir)
        with pytest.raises(Exception):
            v3.unlock(b"old-pw")

    def test_recover_with_key_strategy(self, tmp_path):
        from phantomkey.vault.recovery import KeyRecovery
        from phantomkey.vault.store import Vault

        vault_dir = tmp_path / ".phantomkey"
        v = Vault(vault_dir)
        strategy = KeyRecovery()
        recovery_key = v.init_with_recovery(b"master-pw", strategy)

        v.add("cred1", fields={"token": "abc"})
        v.lock()

        v2 = Vault(vault_dir)
        v2.recover(recovery_key, b"new-pw", strategy)

        v3 = Vault(vault_dir)
        v3.unlock(b"new-pw")
        assert v3.get("cred1").fields["token"] == "abc"