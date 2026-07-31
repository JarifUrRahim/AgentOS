"""Command line entry point: ``python -m agentos <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from agentos.config import settings_from_env
from agentos.core.kernel import AgentOS
from agentos.core.permissions import PermissionLevel


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentos", description="AI-first operations layer")
    sub = parser.add_subparsers(dest="command", required=True)

    chat = sub.add_parser("chat", help="Send a natural language instruction")
    chat.add_argument("instruction", nargs="+")

    sub.add_parser("status", help="Show permission level, agents and pending approvals")
    sub.add_parser("actions", help="List every registered capability")
    sub.add_parser("approvals", help="List pending approvals")

    approve = sub.add_parser("approve", help="Authorize a pending action")
    approve.add_argument("approval_id")

    reject = sub.add_parser("reject", help="Reject a pending action")
    reject.add_argument("approval_id")

    audit = sub.add_parser("audit", help="Show the audit log")
    audit.add_argument("--limit", type=int, default=20)

    sub.add_parser("snapshots", help="List recoverable snapshots")

    rollback = sub.add_parser("rollback", help="Restore a snapshot")
    rollback.add_argument("snapshot_id")

    level = sub.add_parser("permission", help="Set the AI permission level (1-4)")
    level.add_argument("level", type=int, choices=[1, 2, 3, 4])

    serve = sub.add_parser("serve", help="Run the HTTP API and chat console")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "serve":
        import uvicorn

        uvicorn.run("agentos.api.app:app", host=args.host, port=args.port)
        return 0

    kernel = AgentOS(settings_from_env())

    if args.command == "chat":
        _print(kernel.handle(" ".join(args.instruction)).as_dict())
    elif args.command == "status":
        _print(kernel.status())
    elif args.command == "actions":
        _print(
            [
                {"name": a.name, "agent": a.agent, "risk": int(a.risk), "about": a.description}
                for a in kernel.registry.all()
            ]
        )
    elif args.command == "approvals":
        _print([a.as_dict() for a in kernel.approvals.pending()])
    elif args.command == "approve":
        _print(kernel.approve(args.approval_id).as_dict())
    elif args.command == "reject":
        _print(kernel.reject(args.approval_id).as_dict())
    elif args.command == "audit":
        _print(kernel.audit.entries(args.limit))
    elif args.command == "snapshots":
        _print(
            [
                {"id": s.id, "created_at": s.created_at, "label": s.label}
                for s in kernel.snapshots.list()
            ]
        )
    elif args.command == "rollback":
        _print(kernel.rollback(args.snapshot_id))
    elif args.command == "permission":
        kernel.set_permission_level(PermissionLevel(args.level))
        _print(kernel.status())
    return 0


if __name__ == "__main__":
    sys.exit(main())
