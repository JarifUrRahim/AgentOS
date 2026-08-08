"""Exception types raised by the AgentOS kernel."""

from __future__ import annotations


class AgentOSError(Exception):
    """Base class for all AgentOS failures."""


class UnknownActionError(AgentOSError):
    """Raised when a plan references an action that is not registered."""


class ActionFailed(AgentOSError):
    """Raised by an action handler when execution cannot complete."""


class ApprovalError(AgentOSError):
    """Raised when an approval cannot be resolved."""


class SandboxRejected(AgentOSError):
    """Raised when a dry run inside the sandbox fails, so production is never touched."""
