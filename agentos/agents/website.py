"""Website Agent: pages, backups, link hygiene and infrastructure settings."""

from __future__ import annotations

import re
from typing import Any

from agentos.agents.base import Agent, register_agent
from agentos.agents.workspace import listdir, read, resolve, slugify, write
from agentos.core.actions import ActionResult, ExecutionContext, registry
from agentos.core.permissions import RiskLevel

AGENT = register_agent(
    Agent(
        name="website",
        title="Website Agent",
        mission="Builds and maintains pages, backups and site infrastructure.",
        keywords=("page", "landing", "website", "site", "backup", "broken link", "dns"),
    )
)

LINK_RE = re.compile(r"\]\(([^)]+)\)")


@registry.register(
    "website.list_pages",
    agent=AGENT.name,
    description="List every page currently published on the site.",
    risk=RiskLevel.READ,
)
def list_pages(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    pages = listdir(ctx.workspace, "pages")
    return ActionResult(f"{len(pages)} page(s) on the site.", data={"pages": pages})


@registry.register(
    "website.create_page",
    agent=AGENT.name,
    description="Create a new page from a title and optional body.",
    risk=RiskLevel.LOW,
    required_params=("title",),
)
def create_page(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    title = str(params["title"])
    body = str(params.get("body") or f"# {title}\n\nDrafted by the Website Agent.\n")
    brand = ctx.memory.recall("brand", "name")
    header = f"<!-- brand: {brand} -->\n" if brand else ""
    relative = write(ctx.workspace, f"pages/{slugify(title)}.md", header + body)
    return ActionResult(f"Created page '{title}'.", files_modified=[relative])


@registry.register(
    "website.delete_page",
    agent=AGENT.name,
    description="Delete a page from the site.",
    risk=RiskLevel.CRITICAL,
    required_params=("title",),
)
def delete_page(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    relative = f"pages/{slugify(str(params['title']))}.md"
    path = resolve(ctx.workspace, relative)
    if not path.exists():
        return ActionResult(f"No page named '{params['title']}'.")
    path.unlink()
    return ActionResult(f"Deleted page '{params['title']}'.", files_modified=[relative])


@registry.register(
    "website.backup",
    agent=AGENT.name,
    description="Take a full recoverable backup of the managed site.",
    risk=RiskLevel.LOW,
)
def backup(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    files = listdir(ctx.workspace, ".")
    return ActionResult(f"Backup point requested for {len(files)} file(s).", data={"files": files})


@registry.register(
    "website.find_broken_links",
    agent=AGENT.name,
    description="Scan markdown content for links pointing at missing local files.",
    risk=RiskLevel.READ,
)
def find_broken_links(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    broken: list[dict[str, str]] = []
    for relative in listdir(ctx.workspace, "."):
        if not relative.endswith(".md"):
            continue
        for link in LINK_RE.findall(read(ctx.workspace, relative)):
            if link.startswith(("http://", "https://", "#", "mailto:")):
                continue
            if not resolve(ctx.workspace, link.lstrip("/")).exists():
                broken.append({"page": relative, "link": link})
    return ActionResult(f"{len(broken)} broken link(s).", data={"broken_links": broken})


@registry.register(
    "website.change_dns",
    agent=AGENT.name,
    description="Point the domain at a different host.",
    risk=RiskLevel.CRITICAL,
    reversible=False,
    required_params=("record", "value"),
)
def change_dns(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    record, value = str(params["record"]), str(params["value"])
    relative = write(ctx.workspace, f"infra/dns/{slugify(record)}.txt", value)
    return ActionResult(
        f"DNS record {record} set to {value}.",
        files_modified=[relative],
        database_changes=[f"dns:{record}"],
    )
