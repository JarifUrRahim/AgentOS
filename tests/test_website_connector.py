from __future__ import annotations

import pytest

from agentos.connectors import website_api
from agentos.core.kernel import AgentOS
from agentos.core.permissions import Decision, PermissionLevel, RiskLevel, assess

PUBLISH_PARAMS = {
    "title": "Example post",
    "slug": "example-post",
    "excerpt": "A local regression-test payload.",
    "content": "This test must never reach a website.",
}


def test_connector_dry_run_never_opens_a_network_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(website_api, "WEBSITE_API_TOKEN", "test-only-placeholder")

    def unexpected_request(*args: object, **kwargs: object) -> None:
        pytest.fail("A dry-run attempted an outbound website request.")

    monkeypatch.setattr(website_api.urllib.request, "urlopen", unexpected_request)
    result = website_api.publish_post(**PUBLISH_PARAMS, dry_run=True)

    assert result.success is False
    assert "no website request sent" in result.message.lower()


def test_kernel_dry_run_passes_network_guard_to_website_connector(
    kernel: AgentOS, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(website_api, "WEBSITE_API_TOKEN", "test-only-placeholder")

    def unexpected_request(*args: object, **kwargs: object) -> None:
        pytest.fail("The kernel dry-run reached the website connector's network path.")

    monkeypatch.setattr(website_api.urllib.request, "urlopen", unexpected_request)
    action = kernel.registry.get("content.publish_to_website")
    result = kernel._dry_run(action, PUBLISH_PARAMS)

    assert result.data == {"would_publish": True, "slug": "example-post"}
    assert "no website request was sent" in result.summary.lower()


def test_remote_publish_is_critical_and_always_requires_manual_approval(
    kernel: AgentOS,
) -> None:
    action = kernel.registry.get("content.publish_to_website")

    assert action.risk is RiskLevel.CRITICAL
    assert action.reversible is False
    for level in (PermissionLevel.SAFE_AUTOMATION, PermissionLevel.CRITICAL_OPERATIONS):
        assessment = assess(action.risk, level, reversible=action.reversible)
        assert assessment.decision is Decision.NEEDS_APPROVAL


def test_remote_publish_runs_only_after_approval_and_uses_one_live_call(
    kernel: AgentOS, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[bool] = []

    def fake_publish_post(*, dry_run: bool = False, **kwargs: object) -> website_api.PublishResult:
        calls.append(dry_run)
        return website_api.PublishResult(
            success=True,
            message="Stubbed response; no network used.",
            post_url="https://example.invalid/example-post",
        )

    monkeypatch.setattr(website_api, "publish_post", fake_publish_post)
    queued = kernel.run_action("content.publish_to_website", PUBLISH_PARAMS)

    assert queued.decision is Decision.NEEDS_APPROVAL
    assert queued.approval_id is not None
    assert calls == []

    completed = kernel.approve(queued.approval_id)

    assert completed.decision is Decision.EXECUTE
    assert calls == [True, False]
