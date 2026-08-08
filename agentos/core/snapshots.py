"""Automatic versioning: a rollback point before every mutating operation."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A recoverable copy of the managed workspace."""

    id: str
    created_at: str
    label: str
    path: Path

    @property
    def files(self) -> list[str]:
        return sorted(str(p.relative_to(self.path)) for p in self.path.rglob("*") if p.is_file())


class SnapshotStore:
    """Keeps the last ``history`` snapshots of the workspace and can restore any of them."""

    def __init__(self, workspace: Path, snapshot_root: Path, history: int = 5) -> None:
        self._workspace = workspace
        self._root = snapshot_root
        self._history = history
        self._root.mkdir(parents=True, exist_ok=True)
        self._workspace.mkdir(parents=True, exist_ok=True)

    def create(self, label: str) -> Snapshot:
        created_at = datetime.now(timezone.utc)
        snapshot_id = f"{created_at.strftime('%Y%m%dT%H%M%S%f')}"
        target = self._root / snapshot_id
        shutil.copytree(self._workspace, target)
        (target / ".label").write_text(label, encoding="utf-8")
        self._prune()
        return Snapshot(snapshot_id, created_at.isoformat(timespec="seconds"), label, target)

    def list(self) -> list[Snapshot]:
        snapshots = []
        for path in sorted(self._root.iterdir(), reverse=True):
            if not path.is_dir():
                continue
            label_file = path / ".label"
            label = label_file.read_text(encoding="utf-8") if label_file.exists() else ""
            created_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            snapshots.append(
                Snapshot(path.name, created_at.isoformat(timespec="seconds"), label, path)
            )
        return snapshots

    def get(self, snapshot_id: str) -> Snapshot | None:
        return next((s for s in self.list() if s.id == snapshot_id), None)

    def restore(self, snapshot_id: str) -> Snapshot:
        """Roll the workspace back to a snapshot, snapshotting the current state first."""
        snapshot = self.get(snapshot_id)
        if snapshot is None:
            raise FileNotFoundError(f"Unknown snapshot: {snapshot_id}")
        self.create(f"pre-rollback to {snapshot_id}")
        shutil.rmtree(self._workspace)
        shutil.copytree(snapshot.path, self._workspace, ignore=shutil.ignore_patterns(".label"))
        return snapshot

    def _prune(self) -> None:
        for stale in self.list()[self._history :]:
            shutil.rmtree(stale.path, ignore_errors=True)
