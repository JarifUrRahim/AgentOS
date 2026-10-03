# AgentOS architecture overview

AgentOS is a traceable local Python prototype for a safety-aware action path: an instruction is routed to a registered handler, checked against a permission policy, optionally held for approval, executed against local state, and recorded. These are architectural patterns relevant to connecting organizational systems and personal agents, but this repository does not implement that interconnection. It is not a production system and does not claim real enterprise deployment.

The README gives a concise [project introduction and safe local run](../README.md). The source links below describe the current implementation; commit history provides the record of changes.

## Request and control flow

1. A local user submits an instruction through the CLI in [`agentos/cli.py`](../agentos/cli.py) or `POST /api/chat` in [`agentos/api/app.py`](../agentos/api/app.py).
2. [`RulePlanner`](../agentos/brain/planner.py) matches deterministic regular expressions and proposes registered action names. It does not call a language model or coordinate autonomous agent-to-agent work.
3. Modules under [`agentos/agents/`](../agentos/agents/) register handlers in the shared action registry. Most handlers inspect or change local workspace files or SQLite state; specialist names do not imply live provider integrations.
4. [`AgentOS.run_action`](../agentos/core/kernel.py) validates parameters and calls [`assess()`](../agentos/core/permissions.py) to decide whether an action can run, needs approval, or is denied. Pending requests are stored by [`ApprovalQueue`](../agentos/core/approvals.py) and resolved through the API or CLI.
5. Mutating local actions first run against a temporary workspace copy using [`cloned_workspace()`](../agentos/core/sandbox.py). The workspace is then captured by [`SnapshotStore`](../agentos/core/snapshots.py), the local handler runs, and the result is recorded by the SQLite-backed [`AuditLog`](../agentos/core/audit.py) through [`Store`](../agentos/core/store.py).

```text
Local instruction
    -> deterministic planner
    -> action registry + parameter validation
    -> risk policy -> deny | approval queue | execute
    -> workspace-copy dry-run -> workspace snapshot -> local handler
    -> SQLite audit record
```

The copy and snapshot cover only the local workspace. They are not a process-level network sandbox, database snapshot, transaction, or rollback for external systems. General action handlers are not confined by operating-system isolation.

## Source map

| Area | Implemented location |
| --- | --- |
| HTTP routes and local web console | [`agentos/api/app.py`](../agentos/api/app.py), [`agentos/web/`](../agentos/web/) |
| CLI commands | [`agentos/cli.py`](../agentos/cli.py) |
| Request models | [`agentos/api/schemas.py`](../agentos/api/schemas.py) |
| Rule-based planning | [`agentos/brain/planner.py`](../agentos/brain/planner.py) |
| Action registration and local examples | [`agentos/agents/`](../agentos/agents/) |
| Permission and approval policy | [`agentos/core/permissions.py`](../agentos/core/permissions.py), [`agentos/core/approvals.py`](../agentos/core/approvals.py) |
| Kernel, workspace copy, snapshots, audit | [`agentos/core/kernel.py`](../agentos/core/kernel.py), [`agentos/core/sandbox.py`](../agentos/core/sandbox.py), [`agentos/core/snapshots.py`](../agentos/core/snapshots.py), [`agentos/core/audit.py`](../agentos/core/audit.py) |
| Local persistence and memory | [`agentos/core/store.py`](../agentos/core/store.py), [`agentos/core/memory.py`](../agentos/core/memory.py) |
| Narrow website API connector | [`agentos/connectors/website_api.py`](../agentos/connectors/website_api.py), registered actions in [`agentos/agents/content.py`](../agentos/agents/content.py) |

## External boundary and safety limits

The API exposes chat, action inventory/run, approval, audit, snapshot/rollback, emergency-stop, permission-level, and memory routes. It has **no authentication or user-identity boundary**; keep the server bound to loopback and do not expose it to a network. The SQLite audit history is append-only through the app interface but is not tamper-proof. Snapshots do not include the database or remote state.

The only implemented remote integration is a narrow website API connector. `content.check_website_connection` performs real HTTP GET requests. `content.publish_to_website` can send a real blog POST after explicit approval and when a token is configured. It is classified critical and non-reversible, so the policy gate requires approval at every permission level. Its registered dry-run passes `dry_run=True` into the connector, which exits before opening an HTTP request. The approval-flow regression test replaces the connector with a stub; it makes no live call. The connector's `update_post()` helper is not a registered AgentOS action. Local `content.publish` only moves a file inside the prototype workspace.

The connector-level dry-run guard does not sandbox arbitrary Python handlers or prevent a handler from making its own network call. Any future use beyond a local prototype needs a stronger, explicit capability or operating-system isolation boundary, plus authentication, authorization, and system-wide external-state controls; those are not implemented here.

## Scope and relevance

The implementation demonstrates action registration, deterministic routing, permission decisions, human approval, local workspace copying/snapshots, and SQLite audit records. This architecture can serve as a traceable discussion prototype for safety-aware orchestration and system-boundary design. It does not establish that the patterns are sufficient for enterprise use.

It does **not** implement an LLM planner, a full multi-agent runtime, end-to-end delegation, a shared identity or protocol model, a conformance suite, or interoperability between companies' systems and personal agents. Most action names relating to CMS, DNS, analytics, social media, support, deployment, and migrations are local examples—not integrations to those providers. There is no production hardening, tenant isolation, robust transaction/retry/idempotency guarantee, or rollback spanning remote state.

The separately hosted [concept demo](https://agentos-concept-demo.invented-yacht.workers.dev/) is a synthetic simulation, not this repository's running application or backend; its [archived preview image](agentos-demo-preview.png) is illustrative only.

## Verification

The regression suite checks that the website connector's dry-run does not call `urlopen`, the kernel passes dry-run mode to the connector boundary, and remote publication is classified critical/non-reversible and waits for approval. Network-bound paths are stubbed or blocked in these tests; no live website is contacted.

Local verification on Python 3.11: `python -m pytest -q` — **46 passed**; `python -m ruff check .` — passed; `python -m ruff format --check .` — passed (45 files); `python -m mypy agentos` — no issues in 36 source files. GitHub Actions is configured to run these checks on Python 3.11, but these local results do not assert that a hosted GitHub Actions run has passed. Package versions resolve within declared ranges rather than from a fully locked dependency set. These checks cover local behavior only, not production security, live integrations, or interoperability.
