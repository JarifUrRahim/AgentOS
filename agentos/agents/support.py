"""Customer Support Agent: inbox triage and reply drafting."""

from __future__ import annotations

from typing import Any

from agentos.agents.base import Agent, register_agent
from agentos.agents.workspace import listdir, slugify, today, write
from agentos.core.actions import ActionResult, ExecutionContext, registry
from agentos.core.permissions import RiskLevel

AGENT = register_agent(
    Agent(
        name="support",
        title="Customer Support Agent",
        mission="Triages incoming questions and drafts on-brand replies.",
        keywords=("support", "customer", "ticket", "reply", "inbox", "complaint"),
    )
)


@registry.register(
    "support.list_tickets",
    agent=AGENT.name,
    description="List open support tickets.",
    risk=RiskLevel.READ,
)
def list_tickets(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    tickets = listdir(ctx.workspace, "support/inbox")
    return ActionResult(f"{len(tickets)} open ticket(s).", data={"tickets": tickets})


@registry.register(
    "support.draft_reply",
    agent=AGENT.name,
    description="Draft a reply to a ticket using the remembered tone of voice.",
    risk=RiskLevel.LOW,
    required_params=("ticket",),
)
def draft_reply(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    ticket = str(params["ticket"])
    tone = ctx.memory.recall("style", "tone", "warm and concise")
    body = str(params.get("body") or f"Thanks for reaching out about {ticket}.")
    text = f"# Reply: {ticket}\n\n_Tone: {tone}_\n\n{body}\n"
    relative = write(ctx.workspace, f"support/replies/{today()}-{slugify(ticket)}.md", text)
    return ActionResult(f"Reply drafted for '{ticket}'.", files_modified=[relative])
