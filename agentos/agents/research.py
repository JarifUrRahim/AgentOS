"""Research Agent: gathers findings into the workspace and memory."""

from __future__ import annotations

from typing import Any

from agentos.agents.base import Agent, register_agent
from agentos.agents.workspace import listdir, slugify, today, write
from agentos.core.actions import ActionResult, ExecutionContext, registry
from agentos.core.permissions import RiskLevel

AGENT = register_agent(
    Agent(
        name="research",
        title="Research Agent",
        mission="Collects, structures and stores research notes.",
        keywords=("research", "investigate", "compare", "study", "find out"),
    )
)


@registry.register(
    "research.list_notes",
    agent=AGENT.name,
    description="List stored research notes.",
    risk=RiskLevel.READ,
)
def list_notes(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    notes = listdir(ctx.workspace, "research")
    return ActionResult(f"{len(notes)} research note(s).", data={"notes": notes})


@registry.register(
    "research.save_note",
    agent=AGENT.name,
    description="Save a research note and index it in long-term memory.",
    risk=RiskLevel.LOW,
    required_params=("topic",),
)
def save_note(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    topic = str(params["topic"])
    body = str(params.get("body") or f"# {topic}\n\nCollected {today()}.\n")
    relative = write(ctx.workspace, f"research/{slugify(topic)}.md", body)
    ctx.memory.remember("research", slugify(topic), {"topic": topic, "path": relative})
    return ActionResult(f"Research note on '{topic}' saved.", files_modified=[relative])
