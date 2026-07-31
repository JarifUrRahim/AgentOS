"""Reasoning step: instruction -> ordered plan of registered actions.

``RulePlanner`` is deterministic and dependency-free so the safety layer can be exercised
without a model provider. Any LLM-backed planner can be swapped in by implementing
:class:`Planner`; the kernel never trusts a plan, it re-checks every step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from agentos.agents.base import AGENTS
from agentos.core.actions import ActionRegistry


@dataclass(slots=True)
class PlanStep:
    """One action the planner proposes, with the parameters it inferred."""

    action: str
    params: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""


@dataclass(slots=True)
class Plan:
    """The full response to an instruction: which specialist, which steps, and why."""

    instruction: str
    agent: str
    steps: list[PlanStep]
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "instruction": self.instruction,
            "agent": self.agent,
            "rationale": self.rationale,
            "steps": [
                {"action": s.action, "params": s.params, "rationale": s.rationale}
                for s in self.steps
            ],
        }


class Planner(Protocol):
    """Anything that can turn an instruction into a plan."""

    def plan(self, instruction: str, context: dict[str, Any]) -> Plan: ...


QUOTED = re.compile(r"[\"\u201c\u2018']([^\"\u201d\u2019']{2,120})[\"\u201d\u2019']")
NAMED = re.compile(r"(?:called|titled|named|about|on|for)\s+(.{2,80}?)(?:\.|$)", re.IGNORECASE)

Rule = tuple[re.Pattern[str], str, tuple[str, ...]]

# (pattern, action, extra actions to chain). Order matters: first match wins.
RULES: tuple[Rule, ...] = (
    (re.compile(r"broken link"), "website.find_broken_links", ()),
    (re.compile(r"\bbackup\b|back ?up everything"), "website.backup", ()),
    (re.compile(r"\bdns\b"), "website.change_dns", ()),
    (re.compile(r"delete .*\bpage\b"), "website.delete_page", ()),
    (re.compile(r"list .*\bpages?\b|what pages"), "website.list_pages", ()),
    (re.compile(r"landing page|create .*page|new page|build .*page"), "website.create_page", ()),
    (re.compile(r"newsletter"), "content.generate_newsletter", ()),
    (re.compile(r"\bpublish\b"), "content.publish", ()),
    (
        re.compile(r"(write|draft|create|generate) .*(article|post|blog)"),
        "content.create_draft",
        (),
    ),
    (re.compile(r"sitemap"), "seo.generate_sitemap", ()),
    (re.compile(r"fix .*seo|improve .*seo|optimi[sz]e .*seo"), "seo.audit", ("seo.fix",)),
    (re.compile(r"\bseo\b|meta description"), "seo.audit", ()),
    (re.compile(r"traffic report|analytics report|write .*report"), "analytics.write_report", ()),
    (re.compile(r"traffic|analytics|visitors|page views"), "analytics.traffic_summary", ()),
    (re.compile(r"social profile|update .*social|update .*bio"), "social.update_profiles", ()),
    (re.compile(r"schedule .*post|social post|tweet"), "social.schedule_post", ()),
    (re.compile(r"campaign"), "marketing.create_campaign", ()),
    (re.compile(r"research|investigate"), "research.save_note", ()),
    (re.compile(r"security scan|scan .*(secret|security)|security audit"), "security.scan", ()),
    (re.compile(r"rotate .*(key|credential|secret|password)"), "security.rotate_credentials", ()),
    (re.compile(r"\bdeploy\b|\brelease\b"), "developer.deploy", ()),
    (re.compile(r"migration|migrate .*database"), "developer.run_migration", ()),
    (re.compile(r"\bforget\b"), "knowledge.forget", ()),
    (re.compile(r"\bremember\b|store .*memory"), "knowledge.remember", ()),
    (re.compile(r"what do you know|recall|show .*memory"), "knowledge.recall", ()),
    (re.compile(r"support|ticket|customer|reply"), "support.draft_reply", ()),
)


def extract_subject(instruction: str) -> str | None:
    """Pull the most likely title/topic out of an instruction."""
    quoted = QUOTED.search(instruction)
    if quoted:
        return quoted.group(1).strip()
    named = NAMED.search(instruction)
    if named:
        return named.group(1).strip(" .")
    return None


PARAM_KEY_BY_ACTION = {
    "website.create_page": "title",
    "website.delete_page": "title",
    "content.create_draft": "title",
    "content.publish": "title",
    "marketing.create_campaign": "name",
    "research.save_note": "topic",
    "support.draft_reply": "ticket",
    "security.rotate_credentials": "name",
    "developer.run_migration": "migration",
    "social.schedule_post": "text",
}


class RulePlanner:
    """Keyword/intent planner used as the default reasoning engine."""

    def __init__(self, registry: ActionRegistry) -> None:
        self._registry = registry

    def plan(self, instruction: str, context: dict[str, Any]) -> Plan:
        text = instruction.lower().strip()
        overrides: dict[str, Any] = dict(context.get("params") or {})

        for pattern, action_name, chained in RULES:
            if not pattern.search(text):
                continue
            steps = [self._step(action_name, instruction, overrides)]
            steps += [self._step(name, instruction, overrides) for name in chained]
            agent = self._registry.get(action_name).agent
            return Plan(
                instruction=instruction,
                agent=agent,
                steps=steps,
                rationale=(
                    f"Matched '{pattern.pattern}' -> delegated to the "
                    f"{AGENTS[agent].title if agent in AGENTS else agent}."
                ),
            )

        return Plan(
            instruction=instruction,
            agent="orchestrator",
            steps=[],
            rationale=(
                "No registered capability matched this instruction. "
                "Rephrase it or use the manual control layer."
            ),
        )

    def _step(self, action_name: str, instruction: str, overrides: dict[str, Any]) -> PlanStep:
        action = self._registry.get(action_name)
        params: dict[str, Any] = {}
        key = PARAM_KEY_BY_ACTION.get(action_name)
        if key:
            subject = extract_subject(instruction)
            if subject:
                params[key] = subject
        params.update(overrides)
        return PlanStep(action=action_name, params=params, rationale=action.description)
