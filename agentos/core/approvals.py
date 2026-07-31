"""Pending approvals: the human gate in front of risky work."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from agentos.core.audit import utcnow
from agentos.core.errors import ApprovalError
from agentos.core.permissions import RiskLevel
from agentos.core.store import Store, dumps, loads


@dataclass(slots=True)
class Approval:
    """A proposed action waiting for the owner's yes or no."""

    id: str
    created_at: str
    status: str
    instruction: str
    agent: str
    action: str
    params: dict[str, Any]
    risk: RiskLevel
    reason: str
    resolved_at: str | None = None
    resolved_by: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "status": self.status,
            "instruction": self.instruction,
            "agent": self.agent,
            "action": self.action,
            "params": self.params,
            "risk": int(self.risk),
            "reason": self.reason,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
        }


def _row_to_approval(row: dict[str, Any]) -> Approval:
    return Approval(
        id=row["id"],
        created_at=row["created_at"],
        status=row["status"],
        instruction=row["instruction"],
        agent=row["agent"],
        action=row["action"],
        params=loads(row["params"]),
        risk=RiskLevel(row["risk"]),
        reason=row["reason"],
        resolved_at=row["resolved_at"],
        resolved_by=row["resolved_by"],
    )


class ApprovalQueue:
    """Persisted queue of proposals produced by suggestion mode and critical operations."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def create(
        self,
        *,
        instruction: str,
        agent: str,
        action: str,
        params: dict[str, Any],
        risk: RiskLevel,
        reason: str,
    ) -> Approval:
        approval = Approval(
            id=uuid.uuid4().hex[:12],
            created_at=utcnow(),
            status="pending",
            instruction=instruction,
            agent=agent,
            action=action,
            params=params,
            risk=risk,
            reason=reason,
        )
        self._store.execute(
            """
            INSERT INTO approvals (id, created_at, resolved_at, status, instruction, agent,
                                   action, params, risk, reason, resolved_by)
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                approval.id,
                approval.created_at,
                approval.status,
                approval.instruction,
                approval.agent,
                approval.action,
                dumps(approval.params),
                int(approval.risk),
                approval.reason,
            ),
        )
        return approval

    def get(self, approval_id: str) -> Approval:
        rows = self._store.query("SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if not rows:
            raise ApprovalError(f"Unknown approval: {approval_id}")
        return _row_to_approval(rows[0])

    def pending(self) -> list[Approval]:
        rows = self._store.query(
            "SELECT * FROM approvals WHERE status = 'pending' ORDER BY created_at"
        )
        return [_row_to_approval(row) for row in rows]

    def all(self, limit: int = 50) -> list[Approval]:
        rows = self._store.query(
            "SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [_row_to_approval(row) for row in rows]

    def resolve(self, approval_id: str, *, status: str, resolved_by: str) -> Approval:
        approval = self.get(approval_id)
        if approval.status != "pending":
            raise ApprovalError(f"Approval {approval_id} is already {approval.status}.")
        self._store.execute(
            "UPDATE approvals SET status = ?, resolved_at = ?, resolved_by = ? WHERE id = ?",
            (status, utcnow(), resolved_by, approval_id),
        )
        return self.get(approval_id)
