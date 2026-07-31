"""Long-term operational memory: brand, style, products, decisions, conversations."""

from __future__ import annotations

from typing import Any

from agentos.core.audit import utcnow
from agentos.core.store import Store, dumps, loads

DEFAULT_NAMESPACES = (
    "brand",
    "style",
    "products",
    "research",
    "projects",
    "roadmap",
    "decisions",
)


class Memory:
    """Namespaced key/value memory plus a rolling conversation history."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def remember(self, namespace: str, key: str, value: Any) -> None:
        self._store.execute(
            """
            INSERT INTO memory (created_at, namespace, key, value) VALUES (?, ?, ?, ?)
            ON CONFLICT(namespace, key) DO UPDATE SET value = excluded.value,
                                                      created_at = excluded.created_at
            """,
            (utcnow(), namespace, key, dumps(value)),
        )

    def recall(self, namespace: str, key: str, default: Any = None) -> Any:
        rows = self._store.query(
            "SELECT value FROM memory WHERE namespace = ? AND key = ?", (namespace, key)
        )
        return loads(rows[0]["value"]) if rows else default

    def namespace(self, namespace: str) -> dict[str, Any]:
        rows = self._store.query(
            "SELECT key, value FROM memory WHERE namespace = ? ORDER BY key", (namespace,)
        )
        return {row["key"]: loads(row["value"]) for row in rows}

    def snapshot(self) -> dict[str, dict[str, Any]]:
        rows = self._store.query("SELECT DISTINCT namespace FROM memory ORDER BY namespace")
        return {row["namespace"]: self.namespace(row["namespace"]) for row in rows}

    def forget(self, namespace: str, key: str) -> bool:
        existed = bool(self.recall(namespace, key) is not None)
        self._store.execute("DELETE FROM memory WHERE namespace = ? AND key = ?", (namespace, key))
        return existed

    def log_message(self, role: str, content: str) -> None:
        self._store.execute(
            "INSERT INTO conversations (created_at, role, content) VALUES (?, ?, ?)",
            (utcnow(), role, content),
        )

    def conversation(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._store.query("SELECT * FROM conversations ORDER BY id DESC LIMIT ?", (limit,))
        return list(reversed(rows))
