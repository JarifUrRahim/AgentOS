from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from agentos.api.app import create_app
from agentos.config import Settings


@pytest.fixture()
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_status_lists_every_specialist(client: TestClient) -> None:
    payload = client.get("/api/status").json()
    assert payload["permission_level_name"] == "SAFE_AUTOMATION"
    assert len(payload["agents"]) == 11


def test_chat_executes_a_safe_instruction(client: TestClient) -> None:
    report = client.post(
        "/api/chat", json={"instruction": 'Write an article called "Launch Day".'}
    ).json()
    assert report["outcomes"][0]["decision"] == "execute"
    assert report["outcomes"][0]["files_modified"] == ["content/drafts/launch-day.md"]


def test_chat_queues_critical_work_then_owner_approves(client: TestClient) -> None:
    client.post("/api/chat", json={"instruction": 'Create a page called "Terms".'})
    report = client.post(
        "/api/chat", json={"instruction": 'Delete the page called "Terms".'}
    ).json()
    outcome = report["outcomes"][0]
    assert outcome["decision"] == "needs_approval"

    pending = client.get("/api/approvals").json()["approvals"]
    assert len(pending) == 1

    approved = client.post(f"/api/approvals/{pending[0]['id']}/approve").json()
    assert approved["decision"] == "execute"
    assert client.get("/api/approvals").json()["approvals"] == []


def test_snapshot_rollback_endpoint(client: TestClient) -> None:
    client.post("/api/chat", json={"instruction": 'Write an article called "One".'})
    client.post("/api/chat", json={"instruction": 'Write an article called "Two".'})
    snapshots = client.get("/api/snapshots").json()["snapshots"]

    restored = client.post(f"/api/snapshots/{snapshots[0]['id']}/rollback").json()
    assert restored["restored"] == snapshots[0]["id"]

    content = client.post("/api/chat", json={"instruction": "list content"})
    assert content.status_code == 200


def test_manual_layer_runs_actions_directly(client: TestClient) -> None:
    outcome = client.post(
        "/api/actions/run",
        json={"action": "marketing.create_campaign", "params": {"name": "Spring"}},
    ).json()
    assert outcome["files_modified"] == ["campaigns/spring.md"]


def test_unknown_action_is_404(client: TestClient) -> None:
    assert client.post("/api/actions/run", json={"action": "nope.nope"}).status_code == 404


def test_audit_log_is_exposed(client: TestClient) -> None:
    client.post("/api/chat", json={"instruction": "Backup everything."})
    entries = client.get("/api/audit").json()["entries"]
    assert entries and entries[0]["action"] == "website.backup"


def test_emergency_stop_switches_to_read_only(client: TestClient) -> None:
    client.post("/api/chat", json={"instruction": 'Write an article called "Risky".'})
    client.post("/api/emergency-stop")
    assert client.get("/api/status").json()["permission_level"] == 1
