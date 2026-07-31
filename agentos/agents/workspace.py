"""Filesystem helpers shared by the specialist agents."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    slug = SLUG_RE.sub("-", text.strip().lower()).strip("-")
    return slug or "untitled"


def resolve(workspace: Path, *parts: str) -> Path:
    """Resolve a path inside the workspace, refusing anything that escapes it."""
    target = workspace.joinpath(*parts).resolve()
    root = workspace.resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"Path escapes the managed workspace: {target}")
    return target


def write(workspace: Path, relative: str, content: str) -> str:
    path = resolve(workspace, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return relative


def read(workspace: Path, relative: str) -> str:
    return resolve(workspace, relative).read_text(encoding="utf-8")


def listdir(workspace: Path, relative: str) -> list[str]:
    path = resolve(workspace, relative)
    if not path.exists():
        return []
    return sorted(str(p.relative_to(workspace)) for p in path.rglob("*") if p.is_file())


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
