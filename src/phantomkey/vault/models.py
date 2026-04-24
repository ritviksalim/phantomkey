# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Pydantic data models for PhantomKey vault credentials."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class CredentialType(str, Enum):
    PASSWORD = "password"
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    SSH_KEY = "ssh_key"
    CERTIFICATE = "certificate"
    GENERIC = "generic"


class Credential(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    credential_type: CredentialType = CredentialType.GENERIC
    service: Optional[str] = None
    fields: dict[str, str]
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    access_policy: Optional[list[str]] = None


class VaultData(BaseModel):
    credentials: dict[str, Credential] = Field(default_factory=dict)
    version: int = 1
    sequence: int = 0