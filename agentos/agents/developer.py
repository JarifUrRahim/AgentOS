"""Developer Agent: deployments and database migrations."""

from __future__ import annotations

from typing import Any

from agentos.agents.base import Agent, register_agent
from agentos.agents.workspace import slugify, today, write
from agentos.core.actions import ActionResult, ExecutionContext, registry
from agentos.core.permissions import RiskLevel

AGENT = register_agent(
    Agent(
        name="developer",
        title="Developer Agent",
        mission="Ships code and runs schema changes behind approval gates.",
        keywords=("deploy", "migration", "build", "release", "server", "database"),
    )
)


@registry.register(
    "developer.deploy",
    agent=AGENT.name,
    description="Deploy the current workspace to an environment.",
    risk=RiskLevel.MEDIUM,
)
def deploy(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    environment = str(params.get("environment") or "production")
    relative = write(
        ctx.workspace, f"infra/deploys/{today()}-{slugify(environment)}.log", "deployed\n"
    )
    return ActionResult(f"Deployed to {environment}.", files_modified=[relative])


@registry.register(
    "developer.run_migration",
    agent=AGENT.name,
    description="Apply a database migration.",
    risk=RiskLevel.CRITICAL,
    reversible=False,
    required_params=("migration",),
)
def run_migration(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    migration = str(params["migration"])
    relative = write(ctx.workspace, f"infra/migrations/{slugify(migration)}.log", "applied\n")
    return ActionResult(
        f"Migration '{migration}' applied.",
        files_modified=[relative],
        database_changes=[f"migration:{migration}"],
    )
