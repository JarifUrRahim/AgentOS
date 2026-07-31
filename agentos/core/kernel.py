"""The kernel: reasoning -> risk -> confirmation -> sandbox -> snapshot -> execute -> log."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import agentos.agents  # noqa: F401  (importing registers every specialist agent and action)
from agentos.agents.base import AGENTS
from agentos.brain.planner import Plan, Planner, RulePlanner
from agentos.config import Settings
from agentos.core.actions import Action, ActionResult, ExecutionContext, registry
from agentos.core.approvals import Approval, ApprovalQueue
from agentos.core.audit import AuditEntry, AuditLog
from agentos.core.errors import SandboxRejected
from agentos.core.memory import Memory
from agentos.core.permissions import Decision, PermissionLevel, RiskLevel, assess
from agentos.core.sandbox import cloned_workspace
from agentos.core.snapshots import SnapshotStore
from agentos.core.store import Store


@dataclass(slots=True)
class StepOutcome:
    """What happened to a single planned action."""

    action: str
    agent: str
    decision: Decision
    risk: RiskLevel
    reason: str
    summary: str
    params: dict[str, Any] = field(default_factory=dict)
    files_modified: list[str] = field(default_factory=list)
    database_changes: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    rollback_id: str | None = None
    approval_id: str | None = None
    sandbox_verified: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "agent": self.agent,
            "decision": self.decision.value,
            "risk": int(self.risk),
            "reason": self.reason,
            "summary": self.summary,
            "params": self.params,
            "files_modified": self.files_modified,
            "database_changes": self.database_changes,
            "data": self.data,
            "rollback_id": self.rollback_id,
            "approval_id": self.approval_id,
            "sandbox_verified": self.sandbox_verified,
        }


@dataclass(slots=True)
class InstructionReport:
    """The full response to one natural-language instruction."""

    instruction: str
    agent: str
    rationale: str
    outcomes: list[StepOutcome]

    @property
    def message(self) -> str:
        if not self.outcomes:
            return self.rationale
        return " ".join(outcome.summary for outcome in self.outcomes)

    def as_dict(self) -> dict[str, Any]:
        return {
            "instruction": self.instruction,
            "agent": self.agent,
            "rationale": self.rationale,
            "message": self.message,
            "outcomes": [outcome.as_dict() for outcome in self.outcomes],
        }


class AgentOS:
    """The AI operating layer. Every mutation goes through :meth:`run_action`."""

    def __init__(self, settings: Settings, planner: Planner | None = None) -> None:
        settings.bootstrap()
        self.settings = settings
        self.registry = registry
        self.store = Store(settings.database)
        self.audit = AuditLog(self.store)
        self.memory = Memory(self.store)
        self.approvals = ApprovalQueue(self.store)
        self.snapshots = SnapshotStore(
            settings.workspace, settings.snapshots, settings.snapshot_history
        )
        self.planner: Planner = planner or RulePlanner(self.registry)

    # ------------------------------------------------------------------ chat

    def handle(self, instruction: str, *, actor: str | None = None) -> InstructionReport:
        """Plan an instruction and run each step through the safety pipeline."""
        actor = actor or self.settings.owner
        self.memory.log_message("human", instruction)
        plan: Plan = self.planner.plan(instruction, {})
        outcomes = [
            self.run_action(step.action, step.params, instruction=instruction, actor=actor)
            for step in plan.steps
        ]
        report = InstructionReport(instruction, plan.agent, plan.rationale, outcomes)
        self.memory.log_message("agent", report.message)
        if not plan.steps:
            self.audit.record(
                AuditEntry(
                    actor=actor,
                    agent=plan.agent,
                    action="none",
                    instruction=instruction,
                    reason=plan.rationale,
                    risk=RiskLevel.READ,
                    decision=Decision.DENIED,
                    result="no matching capability",
                )
            )
        return report

    # --------------------------------------------------------------- actions

    def run_action(
        self,
        action_name: str,
        params: dict[str, Any] | None = None,
        *,
        instruction: str = "",
        actor: str | None = None,
        preapproved: bool = False,
    ) -> StepOutcome:
        """Validate, gate, dry-run, snapshot, execute and log a single action."""
        actor = actor or self.settings.owner
        params = dict(params or {})
        action = self.registry.get(action_name)

        try:
            action.validate(params)
        except ValueError as exc:
            return self._record(
                action,
                params,
                instruction,
                actor,
                Decision.DENIED,
                RiskLevel.READ,
                str(exc),
                str(exc),
            )

        assessment = assess(
            action.risk, self.settings.permission_level, reversible=action.reversible
        )

        if assessment.decision is Decision.DENIED:
            return self._record(
                action,
                params,
                instruction,
                actor,
                Decision.DENIED,
                assessment.risk,
                assessment.reason,
                f"Refused: {assessment.reason}",
            )

        if assessment.decision is Decision.NEEDS_APPROVAL and not preapproved:
            approval = self.approvals.create(
                instruction=instruction or action.description,
                agent=action.agent,
                action=action.name,
                params=params,
                risk=action.risk,
                reason=assessment.reason,
            )
            outcome = self._record(
                action,
                params,
                instruction,
                actor,
                Decision.NEEDS_APPROVAL,
                assessment.risk,
                assessment.reason,
                f"Waiting for your approval ({approval.id}): {action.description}",
            )
            outcome.approval_id = approval.id
            return outcome

        if action.risk is RiskLevel.READ:
            result = action.handler(self._context(self.settings.workspace, dry_run=False), params)
            return self._record(
                action,
                params,
                instruction,
                actor,
                Decision.EXECUTE,
                assessment.risk,
                assessment.reason,
                result.summary,
                result=result,
            )

        try:
            self._dry_run(action, params)
        except Exception as exc:  # noqa: BLE001 - any sandbox failure blocks production
            reason = f"Sandbox run failed: {exc}"
            self._record(
                action, params, instruction, actor, Decision.DENIED, assessment.risk, reason, reason
            )
            raise SandboxRejected(reason) from exc

        snapshot = self.snapshots.create(instruction or action.name)
        result = action.handler(self._context(self.settings.workspace, dry_run=False), params)
        outcome = self._record(
            action,
            params,
            instruction,
            actor,
            Decision.EXECUTE,
            assessment.risk,
            assessment.reason,
            result.summary,
            result=result,
            rollback_id=snapshot.id,
        )
        outcome.sandbox_verified = True
        return outcome

    def _dry_run(self, action: Action, params: dict[str, Any]) -> ActionResult:
        with cloned_workspace(self.settings.workspace, self.settings.sandboxes) as clone:
            return action.handler(self._context(clone, dry_run=True), params)

    def _context(self, workspace: Any, *, dry_run: bool) -> ExecutionContext:
        return ExecutionContext(
            workspace=workspace, memory=self.memory, owner=self.settings.owner, dry_run=dry_run
        )

    def _record(
        self,
        action: Action,
        params: dict[str, Any],
        instruction: str,
        actor: str,
        decision: Decision,
        risk: RiskLevel,
        reason: str,
        summary: str,
        *,
        result: ActionResult | None = None,
        rollback_id: str | None = None,
    ) -> StepOutcome:
        self.audit.record(
            AuditEntry(
                actor=actor,
                agent=action.agent,
                action=action.name,
                instruction=instruction or action.description,
                reason=reason,
                risk=risk,
                decision=decision,
                result=summary,
                files_modified=result.files_modified if result else [],
                database_changes=result.database_changes if result else [],
                rollback_id=rollback_id,
                details={"params": params},
            )
        )
        return StepOutcome(
            action=action.name,
            agent=action.agent,
            decision=decision,
            risk=risk,
            reason=reason,
            summary=summary,
            params=params,
            files_modified=result.files_modified if result else [],
            database_changes=result.database_changes if result else [],
            data=result.data if result else {},
            rollback_id=rollback_id,
        )

    # -------------------------------------------------------------- approvals

    def approve(self, approval_id: str, *, actor: str | None = None) -> StepOutcome:
        """Owner authorization: resolve the approval and execute the proposed action."""
        actor = actor or self.settings.owner
        approval = self.approvals.resolve(approval_id, status="approved", resolved_by=actor)
        return self.run_action(
            approval.action,
            approval.params,
            instruction=approval.instruction,
            actor=actor,
            preapproved=True,
        )

    def reject(self, approval_id: str, *, actor: str | None = None) -> Approval:
        actor = actor or self.settings.owner
        approval = self.approvals.resolve(approval_id, status="rejected", resolved_by=actor)
        action = self.registry.get(approval.action)
        self.audit.record(
            AuditEntry(
                actor=actor,
                agent=action.agent,
                action=action.name,
                instruction=approval.instruction,
                reason="Rejected by owner.",
                risk=approval.risk,
                decision=Decision.DENIED,
                result="rejected",
                details={"approval_id": approval.id, "params": approval.params},
            )
        )
        return approval

    # ------------------------------------------------------- emergency recovery

    def rollback(self, snapshot_id: str, *, actor: str | None = None) -> dict[str, Any]:
        """Restore a snapshot and log the recovery."""
        actor = actor or self.settings.owner
        snapshot = self.snapshots.restore(snapshot_id)
        self.audit.record(
            AuditEntry(
                actor=actor,
                agent="orchestrator",
                action="system.rollback",
                instruction=f"rollback to {snapshot_id}",
                reason="Emergency recovery requested by the owner.",
                risk=RiskLevel.CRITICAL,
                decision=Decision.EXECUTE,
                result=f"workspace restored to {snapshot_id}",
                files_modified=snapshot.files,
                rollback_id=snapshot_id,
            )
        )
        return {"restored": snapshot_id, "created_at": snapshot.created_at, "label": snapshot.label}

    def emergency_stop(self, *, actor: str | None = None) -> dict[str, Any]:
        """Drop to read-only and roll back to the most recent snapshot."""
        actor = actor or self.settings.owner
        self.settings.permission_level = PermissionLevel.READ_ONLY
        snapshots = self.snapshots.list()
        restored = self.rollback(snapshots[0].id, actor=actor) if snapshots else None
        return {"permission_level": int(self.settings.permission_level), "rollback": restored}

    # ------------------------------------------------------------------ status

    def status(self) -> dict[str, Any]:
        return {
            "owner": self.settings.owner,
            "permission_level": int(self.settings.permission_level),
            "permission_level_name": self.settings.permission_level.name,
            "workspace": str(self.settings.workspace),
            "snapshot_history": self.settings.snapshot_history,
            "pending_approvals": len(self.approvals.pending()),
            "snapshots": len(self.snapshots.list()),
            "agents": [
                {"name": a.name, "title": a.title, "mission": a.mission} for a in AGENTS.values()
            ],
        }

    def set_permission_level(self, level: PermissionLevel, *, actor: str | None = None) -> None:
        actor = actor or self.settings.owner
        previous = self.settings.permission_level
        self.settings.permission_level = level
        self.audit.record(
            AuditEntry(
                actor=actor,
                agent="orchestrator",
                action="system.set_permission_level",
                instruction=f"set permission level to {level.name}",
                reason="Human override.",
                risk=RiskLevel.CRITICAL,
                decision=Decision.EXECUTE,
                result=f"{previous.name} -> {level.name}",
            )
        )
