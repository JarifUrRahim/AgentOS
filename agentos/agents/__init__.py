"""Specialist agents. Importing this package registers every agent and action."""

from __future__ import annotations

from agentos.agents import (
    analytics,
    content,
    developer,
    knowledge,
    marketing,
    research,
    security,
    seo,
    social,
    support,
    website,
)
from agentos.agents.base import AGENTS, Agent, match_agent

__all__ = [
    "AGENTS",
    "Agent",
    "match_agent",
    "analytics",
    "content",
    "developer",
    "knowledge",
    "marketing",
    "research",
    "security",
    "seo",
    "social",
    "support",
    "website",
]
