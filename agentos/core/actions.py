"""Action registry: the only things an agent is ever allowed to do."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentos.core.errors import UnknownActionError
from agentos.core.memory import Memory
from agentos.core.permissions import RiskLevel


@dataclass(slots=True)
class ExecutionContext:
    """Everything a handler may touch. ``workspace`` points at the sandbox during a dry run."""

    workspace: Path
    memory: Memory
    owner: str
    dry_run: bool


@dataclass(slots=True)
class ActionResult:
    """What a handler did, in a form the audit log can store verbatim."""

    summary: str
    files_modified: list[str] = field(default_factory=list)
    database_changes: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


Handler = Callable[[ExecutionContext, dict[str, Any]], ActionResult]


@dataclass(slots=True)
class Action:
    """A capability exposed to the AI layer, tagged with its risk profile."""

    name: str
    agent: str
    description: str
    risk: RiskLevel
    handler: Handler
    reversible: bool = True
    required_params: tuple[str, ...] = ()

    def validate(self, params: dict[str, Any]) -> None:
        missing = [p for p in self.required_params if p not in params]
        if missing:
            raise ValueError(f"{self.name} is missing parameters: {', '.join(missing)}")


class ActionRegistry:
    """Name -> :class:`Action` lookup shared by the planner and the kernel."""

    def __init__(self) -> None:
        self._actions: dict[str, Action] = {}

    def register(
        self,
        name: str,
        *,
        agent: str,
        description: str,
        risk: RiskLevel,
        reversible: bool = True,
        required_params: tuple[str, ...] = (),
    ) -> Callable[[Handler], Handler]:
        def decorator(handler: Handler) -> Handler:
            self._actions[name] = Action(
                name=name,
                agent=agent,
                description=description,
                risk=risk,
                handler=handler,
                reversible=reversible,
                required_params=required_params,
            )
            return handler

        return decorator

    def get(self, name: str) -> Action:
        try:
            return self._actions[name]
        except KeyError as exc:
            raise UnknownActionError(f"No such action: {name}") from exc

    def all(self) -> list[Action]:
        return sorted(self._actions.values(), key=lambda a: (a.agent, a.name))

    def for_agent(self, agent: str) -> list[Action]:
        return [a for a in self.all() if a.agent == agent]


registry = ActionRegistry()
