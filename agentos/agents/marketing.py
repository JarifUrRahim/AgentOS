"""Marketing Agent: campaigns and launch checklists."""

from __future__ import annotations

from typing import Any

from agentos.agents.base import Agent, register_agent
from agentos.agents.workspace import listdir, slugify, today, write
from agentos.core.actions import ActionResult, ExecutionContext, registry
from agentos.core.permissions import RiskLevel

AGENT = register_agent(
    Agent(
        name="marketing",
        title="Marketing Agent",
        mission="Plans campaigns and coordinates launches.",
        keywords=("campaign", "marketing", "launch", "promotion", "ads"),
    )
)


@registry.register(
    "marketing.list_campaigns",
    agent=AGENT.name,
    description="List planned campaigns.",
    risk=RiskLevel.READ,
)
def list_campaigns(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    campaigns = listdir(ctx.workspace, "campaigns")
    return ActionResult(f"{len(campaigns)} campaign(s).", data={"campaigns": campaigns})


@registry.register(
    "marketing.create_campaign",
    agent=AGENT.name,
    description="Draft a campaign brief with channels and a checklist.",
    risk=RiskLevel.LOW,
    required_params=("name",),
)
def create_campaign(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    name = str(params["name"])
    channels = params.get("channels") or ["newsletter", "social", "blog"]
    lines = [f"# Campaign: {name}", f"Created: {today()}", "", "## Channels"]
    lines += [f"- {channel}" for channel in channels]
    relative = write(ctx.workspace, f"campaigns/{slugify(name)}.md", "\n".join(lines) + "\n")
    return ActionResult(f"Campaign '{name}' drafted.", files_modified=[relative])
