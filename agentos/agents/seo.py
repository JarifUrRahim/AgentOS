"""SEO Agent: audits and low-risk on-page fixes."""

from __future__ import annotations

from typing import Any

from agentos.agents.base import Agent, register_agent
from agentos.agents.workspace import listdir, read, write
from agentos.core.actions import ActionResult, ExecutionContext, registry
from agentos.core.permissions import RiskLevel

AGENT = register_agent(
    Agent(
        name="seo",
        title="SEO Agent",
        mission="Audits pages for search visibility and applies safe on-page fixes.",
        keywords=("seo", "meta", "search ranking", "keywords", "sitemap"),
    )
)

MIN_WORDS = 120


def _issues(ctx: ExecutionContext) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for relative in listdir(ctx.workspace, "pages") + listdir(ctx.workspace, "content/published"):
        if not relative.endswith(".md"):
            continue
        text = read(ctx.workspace, relative)
        if "description:" not in text:
            findings.append({"page": relative, "issue": "missing meta description"})
        if not any(line.startswith("# ") for line in text.splitlines()):
            findings.append({"page": relative, "issue": "missing H1"})
        if len(text.split()) < MIN_WORDS:
            findings.append({"page": relative, "issue": "thin content"})
    return findings


@registry.register(
    "seo.audit",
    agent=AGENT.name,
    description="Report SEO issues across pages and published articles.",
    risk=RiskLevel.READ,
)
def audit(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    findings = _issues(ctx)
    return ActionResult(f"{len(findings)} SEO issue(s) found.", data={"issues": findings})


@registry.register(
    "seo.fix",
    agent=AGENT.name,
    description="Add missing meta descriptions and H1 headings.",
    risk=RiskLevel.LOW,
)
def fix(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    fixed: list[str] = []
    for finding in _issues(ctx):
        relative = finding["page"]
        if finding["issue"] == "missing meta description":
            text = read(ctx.workspace, relative)
            summary = next(
                (line for line in text.splitlines() if line and not line.startswith(("#", "<!--"))),
                relative,
            )
            write(ctx.workspace, relative, f"description: {summary[:150]}\n{text}")
            fixed.append(relative)
    return ActionResult(f"Fixed meta descriptions on {len(fixed)} page(s).", files_modified=fixed)


@registry.register(
    "seo.generate_sitemap",
    agent=AGENT.name,
    description="Regenerate sitemap.txt from the current site contents.",
    risk=RiskLevel.LOW,
)
def generate_sitemap(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    base = str(params.get("base_url") or ctx.memory.recall("brand", "url", "https://example.com"))
    urls = [
        f"{base.rstrip('/')}/{relative.removesuffix('.md')}"
        for relative in listdir(ctx.workspace, "pages")
        + listdir(ctx.workspace, "content/published")
    ]
    relative = write(ctx.workspace, "sitemap.txt", "\n".join(urls) + "\n")
    return ActionResult(f"Sitemap regenerated with {len(urls)} URL(s).", files_modified=[relative])
