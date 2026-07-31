"""Append-only audit log: nothing an agent does is hidden."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from agentos.core.permissions import Decision, RiskLevel
from agentos.core.store import Store, dumps, loads


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class AuditEntry:
    """One immutable record of an attempted or completed action."""

    actor: str
    agent: str
    action: str
    instruction: str
    reason: str
    risk: RiskLevel
    decision: Decision
    result: str
    files_modified: list[str] = field(default_factory=list)
    database_changes: list[str] = field(default_factory=list)
    rollback_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class AuditLog:
    """Writes audit entries and reads them back newest-first."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def record(self, entry: AuditEntry) -> int:
        return self._store.execute(
            """
            INSERT INTO audit_log (created_at, actor, agent, action, instruction, reason, risk,
                                   decision, result, files_modified, database_changes,
                                   rollback_id, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utcnow(),
                entry.actor,
                entry.agent,
                entry.action,
                entry.instruction,
                entry.reason,
                int(entry.risk),
                entry.decision.value,
                entry.result,
                dumps(entry.files_modified),
                dumps(entry.database_changes),
                entry.rollback_id,
                dumps(entry.details),
            ),
        )

    def entries(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._store.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))
        for row in rows:
            row["files_modified"] = loads(row["files_modified"])
            row["database_changes"] = loads(row["database_changes"])
            row["details"] = loads(row["details"])
        return rows
