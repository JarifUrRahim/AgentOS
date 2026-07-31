"""Analytics Agent: read-only reporting over collected site events."""

from __future__ import annotations

import json
from typing import Any

from agentos.agents.base import Agent, register_agent
from agentos.agents.workspace import listdir, read, today, write
from agentos.core.actions import ActionResult, ExecutionContext, registry
from agentos.core.permissions import RiskLevel

AGENT = register_agent(
    Agent(
        name="analytics",
        title="Analytics Agent",
        mission="Turns raw traffic events into readable reports.",
        keywords=("analytics", "traffic", "visitors", "report", "stats"),
    )
)


def _events(ctx: ExecutionContext) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for relative in listdir(ctx.workspace, "analytics"):
        if relative.endswith(".json"):
            payload = json.loads(read(ctx.workspace, relative) or "[]")
            events.extend(payload if isinstance(payload, list) else [payload])
    return events


@registry.register(
    "analytics.traffic_summary",
    agent=AGENT.name,
    description="Summarise page views per path from collected events.",
    risk=RiskLevel.READ,
)
def traffic_summary(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    per_path: dict[str, int] = {}
    for event in _events(ctx):
        path = str(event.get("path", "/"))
        per_path[path] = per_path.get(path, 0) + int(event.get("views", 1))
    total = sum(per_path.values())
    return ActionResult(
        f"{total} view(s) across {len(per_path)} path(s).",
        data={"total_views": total, "per_path": per_path},
    )


@registry.register(
    "analytics.write_report",
    agent=AGENT.name,
    description="Persist a traffic report into the workspace.",
    risk=RiskLevel.LOW,
)
def write_report(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    summary = traffic_summary(ctx, params)
    lines = [f"# Traffic report {today()}", "", f"Total views: {summary.data['total_views']}", ""]
    lines += [f"- {path}: {views}" for path, views in sorted(summary.data["per_path"].items())]
    relative = write(ctx.workspace, f"reports/traffic-{today()}.md", "\n".join(lines) + "\n")
    return ActionResult("Traffic report written.", files_modified=[relative], data=summary.data)
