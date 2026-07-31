"""Security Agent: posture checks and credential rotation."""

from __future__ import annotations

from typing import Any

from agentos.agents.base import Agent, register_agent
from agentos.agents.workspace import listdir, read, today, write
from agentos.core.actions import ActionResult, ExecutionContext, registry
from agentos.core.permissions import RiskLevel

AGENT = register_agent(
    Agent(
        name="security",
        title="Security Agent",
        mission="Scans managed assets for exposure and rotates credentials.",
        keywords=("security", "secret", "credential", "vulnerability", "scan", "rotate"),
    )
)

SECRET_MARKERS = ("api_key", "apikey", "password", "secret", "private_key", "token")


@registry.register(
    "security.scan",
    agent=AGENT.name,
    description="Look for credentials accidentally committed into managed content.",
    risk=RiskLevel.READ,
)
def scan(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    hits: list[dict[str, str]] = []
    for relative in listdir(ctx.workspace, "."):
        try:
            text = read(ctx.workspace, relative).lower()
        except UnicodeDecodeError:
            continue
        for marker in SECRET_MARKERS:
            if marker in text:
                hits.append({"file": relative, "marker": marker})
    return ActionResult(f"{len(hits)} potential exposure(s).", data={"findings": hits})


@registry.register(
    "security.rotate_credentials",
    agent=AGENT.name,
    description="Rotate a stored credential. Old value cannot be recovered.",
    risk=RiskLevel.CRITICAL,
    reversible=False,
    required_params=("name",),
)
def rotate_credentials(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    name = str(params["name"])
    relative = write(ctx.workspace, f"infra/rotations/{name}.log", f"rotated {today()}\n")
    return ActionResult(
        f"Credential '{name}' rotated.",
        files_modified=[relative],
        database_changes=[f"credential:{name}"],
    )
