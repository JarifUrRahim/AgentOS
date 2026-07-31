# AgentOS

An AI-first operating layer for administering a website and the digital assets around it.
Natural language is the primary interface; the manual control layer stays available as a
fallback and is never removed.

```
Human -> AI layer -> planning -> risk analysis -> confirmation
                          -> sandbox dry run -> snapshot -> execute -> audit log
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python -m agentos serve            # http://127.0.0.1:8000 — chat console
python -m agentos chat "Create a landing page called \"Winter Sale\""
python -m agentos approvals        # what the AI is waiting on
python -m agentos audit --limit 10
```

State lives under `./var` (override with `AGENTOS_HOME`): `workspace/` is the managed site,
`snapshots/` holds the rollback points and `agentos.db` stores audit log, approvals and memory.

## Dual-mode architecture

| Layer | Surface | Purpose |
| --- | --- | --- |
| AI operating layer | `POST /api/chat`, `agentos chat` | Default interface. Instruction in, plan out, executed under the safety pipeline. |
| Manual control layer | `POST /api/actions/run`, `agentos` subcommands | Emergency recovery, precise configuration, developer access. Same gating, no planner. |

## Permission levels

Set with `POST /api/permission-level`, `agentos permission <1-4>` or `AGENTOS_PERMISSION_LEVEL`.

| Level | Name | Behaviour |
| --- | --- | --- |
| 1 | Read only | Inspection only, every mutation is refused. |
| 2 | Suggestion | Every change is queued as a proposal for the owner. |
| 3 | Safe automation | Low-risk reversible work runs automatically (drafts, publishing, SEO fixes, reports). |
| 4 | Critical operations | Adds medium-risk work (deploys, bulk profile updates). |

Two rules hold at every level: **critical actions always require explicit approval**
(delete a page, change DNS, run a migration, rotate credentials) and **irreversible actions
are never auto-executed**.

## Safety pipeline

Every mutating action goes through `AgentOS.run_action`:

1. **Validate** the parameters against the registered action.
2. **Risk analysis** — `agentos/core/permissions.py` maps risk × permission level to
   execute / needs-approval / denied.
3. **Confirmation** — anything gated becomes a row in the approval queue; nothing runs until
   the owner approves it.
4. **Sandbox** — the action first runs against a throwaway clone of the workspace. If the dry
   run raises, production is never touched (`SandboxRejected`).
5. **Snapshot** — a rollback point is created before the real run; the last five are kept.
6. **Execute**, then **log** an immutable audit entry: time, actor, agent, instruction, reason,
   risk, decision, files modified, database changes, rollback id and result.

Emergency recovery: `POST /api/emergency-stop` drops the instance to read-only and restores the
most recent snapshot. Any snapshot can be restored individually with
`POST /api/snapshots/{id}/rollback` (which snapshots the current state first, so a rollback is
itself reversible).

## Specialist agents

The orchestrator routes each instruction to one specialist rather than to a single giant agent:

| Agent | Sample capabilities |
| --- | --- |
| Website | `create_page`, `delete_page` (critical), `backup`, `find_broken_links`, `change_dns` (critical) |
| Content | `create_draft`, `publish`, `generate_newsletter` |
| SEO | `audit`, `fix`, `generate_sitemap` |
| Research | `save_note`, `list_notes` |
| Marketing | `create_campaign` |
| Analytics | `traffic_summary`, `write_report` |
| Social | `update_profiles`, `schedule_post` |
| Support | `list_tickets`, `draft_reply` |
| Security | `scan`, `rotate_credentials` (critical, irreversible) |
| Developer | `deploy`, `run_migration` (critical, irreversible) |
| Knowledge | `remember`, `recall`, `forget` |

`GET /api/actions` lists every capability with its risk level and what the current permission
level would do with it.

## Memory

Long-term operational memory is namespaced (`brand`, `style`, `products`, `research`,
`projects`, `roadmap`, `decisions`) and is read by the agents themselves — the Content Agent
writes in the remembered tone, the Website Agent stamps the remembered brand, the Social Agent
publishes the remembered bio. Conversation history is stored alongside it.

```bash
curl -X POST localhost:8000/api/memory \
  -H 'content-type: application/json' \
  -d '{"namespace": "brand", "key": "name", "value": "Rashik"}'
```

## Planning

`RulePlanner` (`agentos/brain/planner.py`) is a deterministic intent matcher, so the safety
layer runs without any model provider. Any LLM-backed planner can replace it by implementing
the `Planner` protocol and passing it to `AgentOS(settings, planner=...)`. The kernel never
trusts a plan: it re-validates and re-gates every step it is handed.

## Development

```bash
pytest          # 42 tests: permissions, kernel pipeline, planner, memory, API
ruff check .
ruff format --check .
mypy agentos
```

## Roadmap

- LLM-backed planner and multi-step delegation between specialists.
- Real connectors (CMS, DNS provider, social APIs, analytics) behind the same action registry.
- Snapshotting external state (database dumps) in addition to the workspace.
- Per-agent permission levels and scheduled autonomous runs.
