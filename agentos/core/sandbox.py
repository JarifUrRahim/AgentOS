"""Sandbox mode: run a change against a clone of the workspace before production."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


@contextmanager
def cloned_workspace(workspace: Path, sandbox_root: Path) -> Iterator[Path]:
    """Yield a throwaway copy of the workspace and always clean it up."""
    sandbox_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    clone = sandbox_root / stamp
    shutil.copytree(workspace, clone)
    try:
        yield clone
    finally:
        shutil.rmtree(clone, ignore_errors=True)
