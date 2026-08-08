"""Social Media Agent: profiles and scheduled posts."""

from __future__ import annotations

import json
from typing import Any

from agentos.agents.base import Agent, register_agent
from agentos.agents.workspace import listdir, slugify, today, write
from agentos.core.actions import ActionResult, ExecutionContext, registry
from agentos.core.permissions import RiskLevel

AGENT = register_agent(
    Agent(
        name="social",
        title="Social Media Agent",
        mission="Keeps social profiles consistent and schedules posts.",
        keywords=("social", "profile", "twitter", "linkedin", "instagram", "bio"),
    )
)

DEFAULT_NETWORKS = ("x", "linkedin", "instagram", "github")


@registry.register(
    "social.list_profiles",
    agent=AGENT.name,
    description="List the social profiles under management.",
    risk=RiskLevel.READ,
)
def list_profiles(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    profiles = listdir(ctx.workspace, "social/profiles")
    return ActionResult(f"{len(profiles)} profile(s).", data={"profiles": profiles})


@registry.register(
    "social.update_profiles",
    agent=AGENT.name,
    description="Push the remembered brand bio and links to every social profile.",
    risk=RiskLevel.MEDIUM,
)
def update_profiles(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    networks = tuple(params.get("networks") or DEFAULT_NETWORKS)
    bio = str(params.get("bio") or ctx.memory.recall("brand", "bio", "")).strip()
    if not bio:
        return ActionResult("No brand bio in memory; nothing to publish.")
    changed = [
        write(
            ctx.workspace,
            f"social/profiles/{slugify(network)}.json",
            json.dumps({"network": network, "bio": bio, "updated": today()}, indent=2) + "\n",
        )
        for network in networks
    ]
    return ActionResult(f"Updated {len(changed)} profile(s).", files_modified=changed)


@registry.register(
    "social.schedule_post",
    agent=AGENT.name,
    description="Queue a social post for a given date.",
    risk=RiskLevel.LOW,
    required_params=("text",),
)
def schedule_post(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    when = str(params.get("date") or today())
    text = str(params["text"])
    relative = write(
        ctx.workspace,
        f"social/queue/{when}-{slugify(text[:24])}.json",
        json.dumps({"date": when, "text": text}, indent=2) + "\n",
    )
    return ActionResult(f"Post scheduled for {when}.", files_modified=[relative])
