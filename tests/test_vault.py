# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Tests for phantomkey.vault.models and phantomkey.vault.store — written BEFORE implementation (TDD)."""

import json
import os
import pytest
from pathlib import Path


@pytest.fixture
def vault_dir(tmp_path):
    """Provide a temporary directory for vault storage."""
    return tmp_path / ".phantomkey"


@pytest.fixture
def vault(vault_dir):
    """Create and initialize a vault with a test password."""
    from phantomkey.vault.store import Vault

    v = Vault(vault_dir)
    v.init(b"test-master-password")
    return v


class TestCredentialModel:
    """Test the Credential Pydantic model."""

    def test_create_credential_defaults(self):
        from phantomkey.vault.models import Credential, CredentialType

        cred = Credential(
            name="test-cred",
            fields={"username": "admin", "password": "secret"},
        )
        assert cred.name == "test-cred"
        assert cred.credential_type == CredentialType.GENERIC
        assert cred.fields["password"] == "secret"
        assert cred.id  # UUID should be auto-generated
        assert cred.tags == []
        assert cred.access_policy is None

    def test_create_credential_with_type(self):
        from phantomkey.vault.models import Credential, CredentialType

        cred = Credential(
            name="api-key",
            credential_type=CredentialType.API_KEY,
            service="stripe.com",
            fields={"key": "sk_test_123"},
            tags=["production", "billing"],
        )
        assert cred.credential_type == CredentialType.API_KEY
        assert cred.service == "stripe.com"
        assert cred.tags == ["production", "billing"]

    def test_credential_serialization_roundtrip(self):
        from phantomkey.vault.models import Credential

        cred = Credential(name="test", fields={"token": "abc"})
        data = cred.model_dump(mode="json")
        restored = Credential.model_validate(data)
        assert restored.name == cred.name
        assert restored.fields == cred.fields
        assert restored.id == cred.id


class TestVaultData:
    """Test the VaultData model."""

    def test_empty_vault_data(self):
        from phantomkey.vault.models import VaultData

        vd = VaultData()
        assert vd.credentials == {}
        assert vd.version == 1
        assert vd.sequence == 0

    def test_vault_data_serialization(self):
        from phantomkey.vault.models import VaultData, Credential

        vd = VaultData()
        vd.credentials["test"] = Credential(name="test", fields={"k": "v"})
        data = vd.model_dump(mode="json")
        restored = VaultData.model_validate(data)
        assert "test" in restored.credentials
        assert restored.credentials["test"].fields["k"] == "v"


class TestVaultInit:
    """Test vault initialization."""

    def test_init_creates_vault_file(self, vault_dir):
        from phantomkey.vault.store import Vault

        v = Vault(vault_dir)
        v.init(b"password")
        assert (vault_dir / "vault.pk").exists()

    def test_init_creates_config(self, vault_dir):
        from phantomkey.vault.store import Vault

        v = Vault(vault_dir)
        v.init(b"password")
        assert (vault_dir / "config.toml").exists()

    def test_init_twice_raises(self, vault):
        """Cannot re-initialize an existing vault."""
        with pytest.raises(Exception):
            vault.init(b"another-password")

    def test_vault_file_is_encrypted(self, vault_dir):
        from phantomkey.vault.store import Vault

        v = Vault(vault_dir)
        v.init(b"password")
        raw = (vault_dir / "vault.pk").read_text()
        data = json.loads(raw)
        # Should have encrypted fields, not plaintext credentials
        assert "encrypted_data" in data
        assert "kek_salt" in data
        assert "credentials" not in raw  # No plaintext credentials


class TestVaultUnlockLock:
    """Test vault lock/unlock cycle."""

    def test_unlock_with_correct_password(self, vault):
        vault.lock()
        vault.unlock(b"test-master-password")
        assert vault.is_unlocked

    def test_unlock_with_wrong_password_fails(self, vault):
        vault.lock()
        with pytest.raises(Exception):
            vault.unlock(b"wrong-password")

    def test_lock_clears_state(self, vault):
        vault.lock()
        assert not vault.is_unlocked

    def test_operations_require_unlock(self, vault_dir):
        from phantomkey.vault.store import Vault

        v = Vault(vault_dir)
        v.init(b"password")
        v.lock()
        with pytest.raises(Exception):
            v.add("test", fields={"k": "v"})


class TestVaultCRUD:
    """Test credential CRUD operations."""

    def test_add_and_get(self, vault):
        vault.add("github", fields={"token": "ghp_123"}, service="github.com")
        meta = vault.get("github")
        assert meta.name == "github"
        assert meta.service == "github.com"
        # get() should return the full credential including fields
        assert meta.fields["token"] == "ghp_123"

    def test_add_duplicate_raises(self, vault):
        vault.add("github", fields={"token": "ghp_123"})
        with pytest.raises(Exception):
            vault.add("github", fields={"token": "ghp_456"})

    def test_get_nonexistent_raises(self, vault):
        with pytest.raises(KeyError):
            vault.get("nonexistent")

    def test_list_empty(self, vault):
        result = vault.list()
        assert result == []

    def test_list_returns_metadata(self, vault):
        vault.add("cred1", fields={"k": "v1"}, tags=["prod"])
        vault.add("cred2", fields={"k": "v2"}, tags=["staging"])
        result = vault.list()
        assert len(result) == 2
        names = {c.name for c in result}
        assert names == {"cred1", "cred2"}

    def test_list_filter_by_tag(self, vault):
        vault.add("cred1", fields={"k": "v1"}, tags=["prod"])
        vault.add("cred2", fields={"k": "v2"}, tags=["staging"])
        result = vault.list(tag="prod")
        assert len(result) == 1
        assert result[0].name == "cred1"

    def test_list_filter_by_service(self, vault):
        vault.add("cred1", fields={"k": "v1"}, service="github.com")
        vault.add("cred2", fields={"k": "v2"}, service="stripe.com")
        result = vault.list(service="github.com")
        assert len(result) == 1
        assert result[0].name == "cred1"

    def test_update(self, vault):
        vault.add("cred1", fields={"user": "admin", "pass": "old"})
        vault.update("cred1", fields={"pass": "new"})
        cred = vault.get("cred1")
        assert cred.fields["pass"] == "new"
        assert cred.fields["user"] == "admin"  # Unchanged field preserved

    def test_update_nonexistent_raises(self, vault):
        with pytest.raises(KeyError):
            vault.update("nonexistent", fields={"k": "v"})

    def test_delete(self, vault):
        vault.add("cred1", fields={"k": "v"})
        vault.delete("cred1")
        with pytest.raises(KeyError):
            vault.get("cred1")

    def test_delete_nonexistent_raises(self, vault):
        with pytest.raises(KeyError):
            vault.delete("nonexistent")

    def test_get_field(self, vault):
        """get_field returns a single field value — used by template engine."""
        vault.add("stripe", fields={"secret_key": "sk_123", "public_key": "pk_456"})
        assert vault.get_field("stripe", "secret_key") == "sk_123"
        assert vault.get_field("stripe", "public_key") == "pk_456"

    def test_get_field_nonexistent_credential(self, vault):
        with pytest.raises(KeyError):
            vault.get_field("nonexistent", "field")

    def test_get_field_nonexistent_field(self, vault):
        vault.add("stripe", fields={"secret_key": "sk_123"})
        with pytest.raises(KeyError):
            vault.get_field("stripe", "nonexistent_field")


class TestVaultPersistence:
    """Test that vault data persists across load/save cycles."""

    def test_persist_and_reload(self, vault_dir):
        from phantomkey.vault.store import Vault

        # Create and populate vault
        v1 = Vault(vault_dir)
        v1.init(b"password")
        v1.add("cred1", fields={"token": "abc123"}, service="example.com")
        v1.lock()

        # Reload from disk
        v2 = Vault(vault_dir)
        v2.unlock(b"password")
        cred = v2.get("cred1")
        assert cred.fields["token"] == "abc123"
        assert cred.service == "example.com"

    def test_sequence_increments_on_save(self, vault):
        """Each write should increment the sequence number for sync compatibility."""
        vault.add("cred1", fields={"k": "v"})
        seq1 = vault.sequence
        vault.add("cred2", fields={"k": "v"})
        seq2 = vault.sequence
        assert seq2 > seq1

    def test_multiple_credentials_persist(self, vault_dir):
        from phantomkey.vault.store import Vault

        v1 = Vault(vault_dir)
        v1.init(b"pw")
        for i in range(10):
            v1.add(f"cred-{i}", fields={"key": f"value-{i}"})
        v1.lock()

        v2 = Vault(vault_dir)
        v2.unlock(b"pw")
        assert len(v2.list()) == 10
        assert v2.get("cred-5").fields["key"] == "value-5"