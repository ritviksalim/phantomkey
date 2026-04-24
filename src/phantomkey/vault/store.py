# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Vault storage — encrypted CRUD operations for credentials."""

import json
from base64 import b64decode, b64encode
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from phantomkey.vault.crypto import (
    decrypt,
    derive_kek,
    encrypt,
    generate_dek,
    generate_salt,
)
from phantomkey.vault.models import Credential, CredentialType, VaultData

_DEFAULT_CONFIG = """\
[security]
auto_lock_minutes = 15

[registration]
webhook_url = ""
"""


class VaultLocked(Exception):
    pass


class Vault:
    def __init__(self, vault_dir: Path):
        self._vault_dir = Path(vault_dir)
        self._vault_file = self._vault_dir / "vault.pk"
        self._config_file = self._vault_dir / "config.toml"
        self._data: Optional[VaultData] = None
        self._dek: Optional[bytes] = None

    @property
    def is_unlocked(self) -> bool:
        return self._dek is not None and self._data is not None

    @property
    def sequence(self) -> int:
        self._require_unlocked()
        return self._data.sequence

    def _require_unlocked(self):
        if not self.is_unlocked:
            raise VaultLocked("Vault is locked. Call unlock() first.")

    def init(self, master_password: bytes) -> None:
        """Initialize a new vault with the given master password."""
        if self._vault_file.exists():
            raise FileExistsError(f"Vault already exists at {self._vault_file}")

        self._vault_dir.mkdir(parents=True, exist_ok=True)

        # Generate cryptographic material
        salt = generate_salt()
        kek = derive_kek(master_password, salt)
        dek = generate_dek()

        # Encrypt the DEK with the KEK
        dek_nonce, encrypted_dek = encrypt(kek, dek)

        # Encrypt empty vault data with the DEK
        self._data = VaultData()
        self._dek = dek
        vault_bytes = self._data.model_dump_json().encode()
        data_nonce, encrypted_data = encrypt(dek, vault_bytes)

        # Write vault file
        envelope = {
            "version": 1,
            "kdf": "scrypt",
            "kdf_params": {"n": 131072, "r": 8, "p": 1},
            "kek_salt": b64encode(salt).decode(),
            "encrypted_dek": b64encode(encrypted_dek).decode(),
            "dek_nonce": b64encode(dek_nonce).decode(),
            "encrypted_data": b64encode(encrypted_data).decode(),
            "data_nonce": b64encode(data_nonce).decode(),
        }
        self._vault_file.write_text(json.dumps(envelope, indent=2))

        # Write default config
        if not self._config_file.exists():
            self._config_file.write_text(_DEFAULT_CONFIG)

    def init_with_recovery(
        self,
        master_password: bytes,
        recovery_strategy: "RecoveryStrategy",
    ) -> str:
        """Initialize vault with a recovery credential.

        Returns the recovery credential (phrase or key) — display it to the
        human once, it is never stored.
        """
        from phantomkey.vault.recovery import RecoveryStrategy

        if self._vault_file.exists():
            raise FileExistsError(f"Vault already exists at {self._vault_file}")

        self._vault_dir.mkdir(parents=True, exist_ok=True)

        # Generate cryptographic material
        salt = generate_salt()
        kek = derive_kek(master_password, salt)
        dek = generate_dek()

        # Encrypt the DEK with the master KEK
        dek_nonce, encrypted_dek = encrypt(kek, dek)

        # Generate recovery credential and encrypt DEK with recovery KEK
        recovery_credential = recovery_strategy.generate()
        recovery_salt = generate_salt()
        recovery_kek = recovery_strategy.derive_kek(recovery_credential, recovery_salt)
        recovery_dek_nonce, recovery_encrypted_dek = encrypt(recovery_kek, dek)

        # Encrypt empty vault data with the DEK
        self._data = VaultData()
        self._dek = dek
        vault_bytes = self._data.model_dump_json().encode()
        data_nonce, encrypted_data = encrypt(dek, vault_bytes)

        # Write vault file with both master and recovery encrypted DEKs
        envelope = {
            "version": 1,
            "kdf": "scrypt",
            "kdf_params": {"n": 131072, "r": 8, "p": 1},
            "kek_salt": b64encode(salt).decode(),
            "encrypted_dek": b64encode(encrypted_dek).decode(),
            "dek_nonce": b64encode(dek_nonce).decode(),
            "encrypted_data": b64encode(encrypted_data).decode(),
            "data_nonce": b64encode(data_nonce).decode(),
            "recovery_strategy": recovery_strategy.strategy_id(),
            "recovery_kek_salt": b64encode(recovery_salt).decode(),
            "recovery_encrypted_dek": b64encode(recovery_encrypted_dek).decode(),
            "recovery_dek_nonce": b64encode(recovery_dek_nonce).decode(),
        }
        self._vault_file.write_text(json.dumps(envelope, indent=2))

        if not self._config_file.exists():
            self._config_file.write_text(_DEFAULT_CONFIG)

        return recovery_credential

    def recover(
        self,
        recovery_credential: str,
        new_master_password: bytes,
        recovery_strategy: "RecoveryStrategy",
    ) -> None:
        """Recover vault access using a recovery credential, then set a new master password."""
        from phantomkey.vault.recovery import RecoveryStrategy

        raw = json.loads(self._vault_file.read_text())

        # Decrypt DEK using recovery KEK
        recovery_salt = b64decode(raw["recovery_kek_salt"])
        recovery_kek = recovery_strategy.derive_kek(recovery_credential, recovery_salt)
        recovery_dek_nonce = b64decode(raw["recovery_dek_nonce"])
        recovery_encrypted_dek = b64decode(raw["recovery_encrypted_dek"])
        dek = decrypt(recovery_kek, recovery_dek_nonce, recovery_encrypted_dek)

        # Decrypt vault data to verify it works
        data_nonce = b64decode(raw["data_nonce"])
        encrypted_data = b64decode(raw["encrypted_data"])
        vault_bytes = decrypt(dek, data_nonce, encrypted_data)
        self._data = VaultData.model_validate_json(vault_bytes)
        self._dek = dek

        # Re-encrypt DEK with new master password
        new_salt = generate_salt()
        new_kek = derive_kek(new_master_password, new_salt)
        new_dek_nonce, new_encrypted_dek = encrypt(new_kek, dek)

        # Generate new recovery credential and re-encrypt DEK with it
        new_recovery_salt = generate_salt()
        new_recovery_kek = recovery_strategy.derive_kek(recovery_credential, new_recovery_salt)
        new_recovery_dek_nonce, new_recovery_encrypted_dek = encrypt(new_recovery_kek, dek)

        # Update vault file
        raw["kek_salt"] = b64encode(new_salt).decode()
        raw["encrypted_dek"] = b64encode(new_encrypted_dek).decode()
        raw["dek_nonce"] = b64encode(new_dek_nonce).decode()
        raw["recovery_kek_salt"] = b64encode(new_recovery_salt).decode()
        raw["recovery_encrypted_dek"] = b64encode(new_recovery_encrypted_dek).decode()
        raw["recovery_dek_nonce"] = b64encode(new_recovery_dek_nonce).decode()
        self._vault_file.write_text(json.dumps(raw, indent=2))

    def unlock(self, master_password: bytes) -> None:
        """Unlock the vault by decrypting it with the master password."""
        raw = json.loads(self._vault_file.read_text())

        salt = b64decode(raw["kek_salt"])
        kek = derive_kek(master_password, salt)

        # Decrypt the DEK
        dek_nonce = b64decode(raw["dek_nonce"])
        encrypted_dek = b64decode(raw["encrypted_dek"])
        dek = decrypt(kek, dek_nonce, encrypted_dek)

        # Decrypt the vault data
        data_nonce = b64decode(raw["data_nonce"])
        encrypted_data = b64decode(raw["encrypted_data"])
        vault_bytes = decrypt(dek, data_nonce, encrypted_data)

        self._data = VaultData.model_validate_json(vault_bytes)
        self._dek = dek

    def lock(self) -> None:
        """Lock the vault, clearing all decrypted data from memory."""
        self._data = None
        self._dek = None

    def _save(self) -> None:
        """Re-encrypt and save the vault to disk."""
        self._require_unlocked()
        self._data.sequence += 1

        # Read existing envelope to preserve KDF params and encrypted DEK
        raw = json.loads(self._vault_file.read_text())

        # Re-encrypt vault data with DEK
        vault_bytes = self._data.model_dump_json().encode()
        data_nonce, encrypted_data = encrypt(self._dek, vault_bytes)

        raw["encrypted_data"] = b64encode(encrypted_data).decode()
        raw["data_nonce"] = b64encode(data_nonce).decode()

        self._vault_file.write_text(json.dumps(raw, indent=2))

    def add(
        self,
        name: str,
        fields: dict[str, str],
        credential_type: CredentialType = CredentialType.GENERIC,
        service: Optional[str] = None,
        tags: Optional[list[str]] = None,
        notes: Optional[str] = None,
        access_policy: Optional[list[str]] = None,
    ) -> Credential:
        """Add a new credential to the vault."""
        self._require_unlocked()
        if name in self._data.credentials:
            raise ValueError(f"Credential '{name}' already exists")

        cred = Credential(
            name=name,
            credential_type=credential_type,
            service=service,
            fields=fields,
            tags=tags or [],
            notes=notes,
            access_policy=access_policy,
        )
        self._data.credentials[name] = cred
        self._save()
        return cred

    def get(self, name: str) -> Credential:
        """Get a credential by name."""
        self._require_unlocked()
        if name not in self._data.credentials:
            raise KeyError(f"Credential '{name}' not found")
        cred = self._data.credentials[name]
        cred.last_accessed_at = datetime.now(timezone.utc)
        return cred

    def get_field(self, credential_name: str, field_name: str) -> str:
        """Get a single field value from a credential — used by template engine."""
        cred = self.get(credential_name)
        if field_name not in cred.fields:
            raise KeyError(
                f"Field '{field_name}' not found in credential '{credential_name}'"
            )
        return cred.fields[field_name]

    def list(
        self,
        tag: Optional[str] = None,
        service: Optional[str] = None,
    ) -> list[Credential]:
        """List credentials, optionally filtered by tag or service."""
        self._require_unlocked()
        creds = list(self._data.credentials.values())
        if tag:
            creds = [c for c in creds if tag in c.tags]
        if service:
            creds = [c for c in creds if c.service == service]
        return creds

    def update(self, name: str, fields: dict[str, str]) -> Credential:
        """Update fields on an existing credential (merges with existing fields)."""
        self._require_unlocked()
        if name not in self._data.credentials:
            raise KeyError(f"Credential '{name}' not found")

        cred = self._data.credentials[name]
        cred.fields.update(fields)
        cred.updated_at = datetime.now(timezone.utc)
        self._save()
        return cred

    def delete(self, name: str) -> None:
        """Delete a credential by name."""
        self._require_unlocked()
        if name not in self._data.credentials:
            raise KeyError(f"Credential '{name}' not found")
        del self._data.credentials[name]
        self._save()