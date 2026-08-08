from __future__ import annotations

import pytest

from agentos.brain.planner import RulePlanner
from agentos.core.actions import registry


@pytest.fixture()
def planner() -> RulePlanner:
    return RulePlanner(registry)


@pytest.mark.parametrize(
    ("instruction", "action"),
    [
        ("Publish tomorrow's article.", "content.publish"),
        ("Update all social profiles.", "social.update_profiles"),
        ("Backup everything.", "website.backup"),
        ('Create a landing page called "Winter Sale".', "website.create_page"),
        ("Find broken links.", "website.find_broken_links"),
        ("Analyze traffic.", "analytics.traffic_summary"),
        ("Generate newsletter.", "content.generate_newsletter"),
        ("Run a security scan.", "security.scan"),
        ("Deploy to production.", "developer.deploy"),
    ],
)
def test_blueprint_examples_route_to_the_right_action(
    planner: RulePlanner, instruction: str, action: str
) -> None:
    plan = planner.plan(instruction, {})
    assert [step.action for step in plan.steps][0] == action


def test_fix_seo_audits_before_changing_anything(planner: RulePlanner) -> None:
    plan = planner.plan("Fix SEO.", {})
    assert [step.action for step in plan.steps] == ["seo.audit", "seo.fix"]


def test_quoted_title_becomes_a_parameter(planner: RulePlanner) -> None:
    plan = planner.plan('Create a landing page called "Winter Sale".', {})
    assert plan.steps[0].params == {"title": "Winter Sale"}


def test_unknown_instruction_produces_no_steps(planner: RulePlanner) -> None:
    plan = planner.plan("Make me a sandwich.", {})
    assert plan.steps == []
    assert "manual control layer" in plan.rationale
