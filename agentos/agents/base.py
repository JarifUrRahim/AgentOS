"""Specialist agent descriptors. The orchestrator delegates work to these."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Agent:
    """A specialist the orchestrator can route an instruction to."""

    name: str
    title: str
    mission: str
    keywords: tuple[str, ...] = field(default=())


AGENTS: dict[str, Agent] = {}


def register_agent(agent: Agent) -> Agent:
    AGENTS[agent.name] = agent
    return agent


def match_agent(instruction: str) -> Agent | None:
    """Pick the specialist whose keywords best cover the instruction."""
    text = instruction.lower()
    best: tuple[int, Agent] | None = None
    for agent in AGENTS.values():
        score = sum(1 for keyword in agent.keywords if keyword in text)
        if score and (best is None or score > best[0]):
            best = (score, agent)
    return best[1] if best else None
