from __future__ import annotations

import pytest

from agentos.core.actions import ActionResult, ExecutionContext, registry
from agentos.core.errors import SandboxRejected
from agentos.core.kernel import AgentOS
from agentos.core.permissions import Decision, PermissionLevel, RiskLevel


def test_safe_action_executes_and_snapshots(kernel: AgentOS) -> None:
    outcome = kernel.run_action("content.create_draft", {"title": "Hello World"})
    assert outcome.decision is Decision.EXECUTE
    assert outcome.rollback_id is not None
    assert outcome.sandbox_verified
    assert (kernel.settings.workspace / "content/drafts/hello-world.md").exists()


def test_critical_action_is_queued_for_approval(kernel: AgentOS) -> None:
    kernel.run_action("website.create_page", {"title": "About"})
    outcome = kernel.run_action("website.delete_page", {"title": "About"})

    assert outcome.decision is Decision.NEEDS_APPROVAL
    assert outcome.approval_id is not None
    assert (kernel.settings.workspace / "pages/about.md").exists()

    kernel.approve(outcome.approval_id)
    assert not (kernel.settings.workspace / "pages/about.md").exists()


def test_rejected_approval_never_executes(kernel: AgentOS) -> None:
    kernel.run_action("website.create_page", {"title": "Pricing"})
    outcome = kernel.run_action("website.delete_page", {"title": "Pricing"})
    assert outcome.approval_id is not None

    approval = kernel.reject(outcome.approval_id)
    assert approval.status == "rejected"
    assert (kernel.settings.workspace / "pages/pricing.md").exists()


def test_read_only_mode_refuses_changes(kernel: AgentOS) -> None:
    kernel.set_permission_level(PermissionLevel.READ_ONLY)
    outcome = kernel.run_action("content.create_draft", {"title": "Nope"})
    assert outcome.decision is Decision.DENIED
    assert not (kernel.settings.workspace / "content/drafts/nope.md").exists()


def test_missing_parameters_are_rejected(kernel: AgentOS) -> None:
    outcome = kernel.run_action("website.create_page", {})
    assert outcome.decision is Decision.DENIED
    assert "missing parameters" in outcome.summary


def test_sandbox_failure_leaves_production_untouched(kernel: AgentOS) -> None:
    @registry.register(
        "test.explodes",
        agent="developer",
        description="Always fails.",
        risk=RiskLevel.LOW,
    )
    def explodes(ctx: ExecutionContext, params: dict[str, object]) -> ActionResult:
        (ctx.workspace / "boom.txt").write_text("boom", encoding="utf-8")
        raise RuntimeError("handler blew up")

    with pytest.raises(SandboxRejected):
        kernel.run_action("test.explodes")

    assert not (kernel.settings.workspace / "boom.txt").exists()
    assert kernel.audit.entries()[0]["decision"] == Decision.DENIED.value


def test_rollback_restores_previous_state(kernel: AgentOS) -> None:
    kernel.run_action("content.create_draft", {"title": "Keep Me"})
    outcome = kernel.run_action("content.create_draft", {"title": "Remove Me"})
    assert outcome.rollback_id is not None

    kernel.rollback(outcome.rollback_id)

    assert (kernel.settings.workspace / "content/drafts/keep-me.md").exists()
    assert not (kernel.settings.workspace / "content/drafts/remove-me.md").exists()


def test_snapshot_history_is_capped(kernel: AgentOS) -> None:
    for index in range(8):
        kernel.run_action("content.create_draft", {"title": f"Article {index}"})
    assert len(kernel.snapshots.list()) == kernel.settings.snapshot_history


def test_emergency_stop_drops_to_read_only_and_rolls_back(kernel: AgentOS) -> None:
    kernel.run_action("content.create_draft", {"title": "Before"})
    kernel.run_action("content.create_draft", {"title": "Oops"})

    kernel.emergency_stop()

    assert kernel.settings.permission_level is PermissionLevel.READ_ONLY
    assert (kernel.settings.workspace / "content/drafts/before.md").exists()


def test_every_action_is_audited(kernel: AgentOS) -> None:
    kernel.run_action("content.create_draft", {"title": "Audited"})
    entry = kernel.audit.entries()[0]
    assert entry["action"] == "content.create_draft"
    assert entry["files_modified"] == ["content/drafts/audited.md"]
    assert entry["rollback_id"]
