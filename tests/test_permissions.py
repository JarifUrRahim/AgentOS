from __future__ import annotations

import pytest

from agentos.core.permissions import Decision, PermissionLevel, RiskLevel, assess


@pytest.mark.parametrize("level", list(PermissionLevel))
def test_reads_are_always_allowed(level: PermissionLevel) -> None:
    assert assess(RiskLevel.READ, level, reversible=True).decision is Decision.EXECUTE


def test_read_only_blocks_every_mutation() -> None:
    assessment = assess(RiskLevel.LOW, PermissionLevel.READ_ONLY, reversible=True)
    assert assessment.decision is Decision.DENIED


def test_suggestion_mode_requires_approval_for_low_risk() -> None:
    assessment = assess(RiskLevel.LOW, PermissionLevel.SUGGESTION, reversible=True)
    assert assessment.decision is Decision.NEEDS_APPROVAL


def test_safe_automation_executes_low_risk() -> None:
    assessment = assess(RiskLevel.LOW, PermissionLevel.SAFE_AUTOMATION, reversible=True)
    assert assessment.decision is Decision.EXECUTE


def test_critical_always_needs_approval_even_at_highest_level() -> None:
    assessment = assess(RiskLevel.CRITICAL, PermissionLevel.CRITICAL_OPERATIONS, reversible=True)
    assert assessment.decision is Decision.NEEDS_APPROVAL


def test_irreversible_actions_are_never_auto_executed() -> None:
    assessment = assess(RiskLevel.LOW, PermissionLevel.CRITICAL_OPERATIONS, reversible=False)
    assert assessment.decision is Decision.NEEDS_APPROVAL
