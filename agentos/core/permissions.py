"""Permission levels and the risk classification that gates every action."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class PermissionLevel(IntEnum):
    """How much autonomy the human owner has granted the AI layer."""

    READ_ONLY = 1
    SUGGESTION = 2
    SAFE_AUTOMATION = 3
    CRITICAL_OPERATIONS = 4


class RiskLevel(IntEnum):
    """Blast radius of a single action."""

    READ = 0
    LOW = 1
    MEDIUM = 2
    CRITICAL = 3


class Decision(str, Enum):
    EXECUTE = "execute"
    NEEDS_APPROVAL = "needs_approval"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Outcome of risk analysis for one action."""

    risk: RiskLevel
    decision: Decision
    reason: str
    reversible: bool


def assess(risk: RiskLevel, level: PermissionLevel, *, reversible: bool) -> RiskAssessment:
    """Map an action's risk onto the granted permission level.

    Critical operations always require explicit human approval, no matter the level, and
    irreversible actions are never auto-executed.
    """
    if risk is RiskLevel.READ:
        return RiskAssessment(risk, Decision.EXECUTE, "Read-only inspection.", True)

    if level is PermissionLevel.READ_ONLY:
        return RiskAssessment(risk, Decision.DENIED, "Instance is in read-only mode.", reversible)

    if risk is RiskLevel.CRITICAL:
        return RiskAssessment(
            risk,
            Decision.NEEDS_APPROVAL,
            "Critical operation: owner authorization required.",
            reversible,
        )

    if level is PermissionLevel.SUGGESTION:
        return RiskAssessment(
            risk,
            Decision.NEEDS_APPROVAL,
            "Suggestion mode: every change needs approval.",
            reversible,
        )

    if not reversible:
        return RiskAssessment(
            risk,
            Decision.NEEDS_APPROVAL,
            "Action has no rollback path: approval required.",
            reversible,
        )

    if risk is RiskLevel.MEDIUM and level < PermissionLevel.CRITICAL_OPERATIONS:
        return RiskAssessment(
            risk,
            Decision.NEEDS_APPROVAL,
            "Medium-risk change above the safe-automation bar.",
            reversible,
        )

    return RiskAssessment(
        risk, Decision.EXECUTE, "Low-risk, reversible and inside the safe set.", reversible
    )
