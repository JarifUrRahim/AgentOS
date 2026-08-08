"""Runtime configuration for an AgentOS instance."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from agentos.core.permissions import PermissionLevel


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


@dataclass(slots=True)
class Settings:
    """Where AgentOS keeps state and how much autonomy the agent is granted."""

    root: Path = field(default_factory=lambda: _env_path("AGENTOS_HOME", Path.cwd() / "var"))
    permission_level: PermissionLevel = PermissionLevel.SAFE_AUTOMATION
    snapshot_history: int = 5
    owner: str = "owner"

    @property
    def workspace(self) -> Path:
        """Managed assets (the "website") that agents are allowed to operate on."""
        return self.root / "workspace"

    @property
    def snapshots(self) -> Path:
        return self.root / "snapshots"

    @property
    def sandboxes(self) -> Path:
        return self.root / "sandboxes"

    @property
    def database(self) -> Path:
        return self.root / "agentos.db"

    def bootstrap(self) -> None:
        for directory in (self.root, self.workspace, self.snapshots, self.sandboxes):
            directory.mkdir(parents=True, exist_ok=True)


def settings_from_env() -> Settings:
    settings = Settings()
    level = os.environ.get("AGENTOS_PERMISSION_LEVEL")
    if level:
        settings.permission_level = PermissionLevel(int(level))
    history = os.environ.get("AGENTOS_SNAPSHOT_HISTORY")
    if history:
        settings.snapshot_history = int(history)
    owner = os.environ.get("AGENTOS_OWNER")
    if owner:
        settings.owner = owner
    return settings
