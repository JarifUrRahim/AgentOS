from __future__ import annotations

from agentos.core.kernel import AgentOS


def test_memory_round_trip(kernel: AgentOS) -> None:
    kernel.memory.remember("brand", "name", "Rashik")
    assert kernel.memory.recall("brand", "name") == "Rashik"
    assert kernel.memory.snapshot()["brand"] == {"name": "Rashik"}


def test_agents_use_remembered_brand(kernel: AgentOS) -> None:
    kernel.memory.remember("brand", "name", "Rashik")
    kernel.run_action("website.create_page", {"title": "Home"})
    assert "brand: Rashik" in (kernel.settings.workspace / "pages/home.md").read_text()


def test_conversation_is_recorded(kernel: AgentOS) -> None:
    kernel.handle("Backup everything.")
    roles = [message["role"] for message in kernel.memory.conversation()]
    assert roles == ["human", "agent"]
