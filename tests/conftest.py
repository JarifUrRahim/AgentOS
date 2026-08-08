from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from agentos.config import Settings
from agentos.core.kernel import AgentOS
from agentos.core.permissions import PermissionLevel


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(root=tmp_path / "var", permission_level=PermissionLevel.SAFE_AUTOMATION)


@pytest.fixture()
def kernel(settings: Settings) -> Iterator[AgentOS]:
    yield AgentOS(settings)
