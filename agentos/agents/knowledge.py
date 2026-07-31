"""Knowledge Agent: curates the organization's long-term memory."""

from __future__ import annotations

from typing import Any

from agentos.agents.base import Agent, register_agent
from agentos.core.actions import ActionResult, ExecutionContext, registry
from agentos.core.permissions import RiskLevel

AGENT = register_agent(
    Agent(
        name="knowledge",
        title="Knowledge Agent",
        mission="Remembers brand identity, decisions and everything worth reusing.",
        keywords=("remember", "memory", "knowledge", "brand", "identity", "forget"),
    )
)


@registry.register(
    "knowledge.recall",
    agent=AGENT.name,
    description="Read everything stored in long-term memory.",
    risk=RiskLevel.READ,
)
def recall(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    namespace = params.get("namespace")
    data = ctx.memory.namespace(str(namespace)) if namespace else ctx.memory.snapshot()
    return ActionResult("Memory read.", data={"memory": data})


@registry.register(
    "knowledge.remember",
    agent=AGENT.name,
    description="Store a fact in long-term memory.",
    risk=RiskLevel.LOW,
    required_params=("namespace", "key", "value"),
)
def remember(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    namespace, key = str(params["namespace"]), str(params["key"])
    if not ctx.dry_run:
        ctx.memory.remember(namespace, key, params["value"])
    return ActionResult(
        f"Remembered {namespace}.{key}.", database_changes=[f"memory:{namespace}.{key}"]
    )


@registry.register(
    "knowledge.forget",
    agent=AGENT.name,
    description="Remove a fact from long-term memory.",
    risk=RiskLevel.MEDIUM,
    reversible=False,
    required_params=("namespace", "key"),
)
def forget(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    namespace, key = str(params["namespace"]), str(params["key"])
    if ctx.dry_run:
        return ActionResult(f"Would forget {namespace}.{key}.")
    existed = ctx.memory.forget(namespace, key)
    return ActionResult(
        f"Forgot {namespace}.{key}." if existed else f"Nothing stored at {namespace}.{key}.",
        database_changes=[f"memory:{namespace}.{key}"] if existed else [],
    )
