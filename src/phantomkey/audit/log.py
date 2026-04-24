# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Append-only audit log for credential access tracking."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class AuditLog:
    def __init__(self, log_path: Path):
        self._path = Path(log_path)

    def record(
        self,
        action: str,
        credential: str = "",
        agent: Optional[str] = None,
        fields_used: Optional[list[str]] = None,
        success: bool = True,
    ) -> None:
        """Append an audit entry. Never logs secret values — only names."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "credential": credential,
            "agent": agent or "anonymous",
            "success": success,
        }
        if fields_used:
            entry["fields"] = fields_used

        with open(self._path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def read(
        self,
        credential: Optional[str] = None,
        last: Optional[int] = None,
    ) -> list[dict]:
        """Read audit log entries, optionally filtered."""
        if not self._path.exists():
            return []

        entries = []
        for line in self._path.read_text().strip().split("\n"):
            if line:
                entries.append(json.loads(line))

        if credential:
            entries = [e for e in entries if e.get("credential") == credential]

        if last:
            entries = entries[-last:]

        return entries